"""Shared contracts: canonical JSON Schema -> strict Pydantic models.

Field annotations, requiredness and camelCase JSON aliases are derived from the
same checked-in schemas used by TypeScript. Cross-reference rules live below;
no network schema resolution or external data source is permitted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, ClassVar, Literal, Union

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import BaseModel, ConfigDict, Field, RootModel, create_model, model_validator
from referencing import Registry, Resource

ENABLED_OUTPUT_MODES = ("document", "presentation")
OutputMode = Literal["document", "presentation", "data", "dashboard"]
ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = ROOT / "packages/contracts/schemas"
SCHEMAS = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in SCHEMA_DIR.glob("*.schema.json")}
REGISTRY = Registry().with_resources((name, Resource.from_contents(schema)) for name, schema in SCHEMAS.items())
CORE_LAYOUTS = json.loads((ROOT / "packages/contracts/registries/core-presentation-layouts.json").read_text(encoding="utf-8"))
CONTRACT_REFS = {
    "DocumentGraph": "document-graph.schema.json",
    "GenerationPlan": "generation-plan.schema.json",
    "EditCommand": "edit-command.schema.json",
    "PresentationDocument": "presentation.schema.json",
    "LayoutRegistry": "layout-registry.schema.json",
    "MediaIntent": "presentation.schema.json#/definitions/MediaIntent",
    "TemplatePackage": "template-package.schema.json",
    **{name: "data-visualization.schema.json#/definitions/" + name for name in (
        "DatasetProfile", "AnalyticIntent", "ChartPlan", "ChartSpec", "EncodingSpec", "ChartFrame"
    )},
}


def validate_schema(name: str, value: Any) -> None:
    """Validate raw wire data using the same JSON Schema as the TS boundary."""
    _validate_ref(CONTRACT_REFS[name], value)


def _validate_ref(ref: str, value: Any) -> None:
    try:
        Draft7Validator({"$ref": ref}, registry=REGISTRY).validate(value)
    except SchemaValidationError as exc:
        raise ValueError(f"{'/'.join(map(str, exc.absolute_path))}: {exc.message}") from exc


def _unique(values: list[Any], label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError("Duplicate " + label)


def _identities(value: Any) -> None:
    ids = []

    def visit(item):
        if isinstance(item, list):
            _unique([x["order"] for x in item if isinstance(x, dict) and "order" in x], "order")
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            if isinstance(item.get("artifactId"), str):
                ids.append(item["artifactId"])
            if isinstance(item.get("id"), str) and re.match(r"^[0-9a-f]{8}-", item["id"]):
                ids.append(item["id"])
            for child in item.values():
                visit(child)

    visit(value)
    _unique(ids, "stable identity")


def _table(table: dict) -> None:
    if any(len(row) != len(table["columns"]) for row in table["rows"]):
        raise ValueError("Table row width mismatch")


def _chart(chart: dict) -> None:
    _unique([encoding["channel"] for encoding in chart["encodings"]], "encoding channel")
    kinds = {"bar": "proportionalBars", "arc": "composition", "ohlc": "ohlc", "hierarchy": "hierarchy", "network": "network", "map": "map"}
    if kinds.get(chart["mark"], "general") != chart["invariants"]["kind"]:
        raise ValueError("Incompatible chart invariants")
    if chart["mark"] == "bar" and any(e["type"] == "quantitative" and (e["scale"]["baseline"] != 0 or e["scale"]["type"] == "log") for e in chart["encodings"]):
        raise ValueError("Bars require a zero baseline")


def _presentation(presentation: dict, document: dict | None = None) -> None:
    _identities(presentation)
    blocks = {block["id"]: block for section in (document or {}).get("sections", []) for block in section["blocks"]}
    assets = {asset["id"]: asset for asset in (document or {}).get("assets", [])}
    sections = {section["id"] for section in (document or {}).get("sections", [])}
    for slide in presentation["slides"]:
        layout = next((layout for layout in CORE_LAYOUTS["layouts"] if layout["id"] == slide["layoutId"]), None)
        if layout is None or slide["kind"] not in layout["slideKinds"]:
            raise ValueError("Unknown or incompatible layout")
        if document is not None and slide["sectionId"] not in sections:
            raise ValueError("Unknown section")
        if "speakerNotes" in slide and slide["speakerNotes"]["slideId"] != slide["id"]:
            raise ValueError("Note/slide mismatch")
        _unique([assignment["slotId"] for assignment in slide["slotAssignments"]], "slot assignment")
        targets = {slide["id"]}
        for assignment in slide["slotAssignments"]:
            targets.update([assignment["id"], *assignment["blockIds"], *assignment["assetIds"]])
        for animation in slide["animationTimeline"]:
            if any(target not in targets for target in animation["targetIds"]):
                raise ValueError("Unknown animation target")
        for assignment in slide["slotAssignments"]:
            slot = next((slot for slot in layout["slots"] if slot["id"] == assignment["slotId"]), None)
            if slot is None:
                raise ValueError("Unknown slot")
            count = len(assignment["blockIds"]) + len(assignment["assetIds"])
            if count > slot["maxItems"] or count < slot.get("minItems", 1 if slot["required"] else 0):
                raise ValueError("Slot capacity exceeded")
            if document is None:
                if assignment["assetIds"] and slot["kind"] != "media":
                    raise ValueError("Incompatible media slot")
                continue

            def check_media(identity):
                asset = assets.get(identity)
                if asset is None or slot["kind"] != "media":
                    raise ValueError("Unknown or incompatible media")
                intent = asset["mediaIntent"]
                if intent["slotId"] != slot["id"] or ("aspectRatios" in slot and intent["targetAspectRatio"] not in slot["aspectRatios"]):
                    raise ValueError("Media slot/aspect mismatch")

            chars = lines = 0
            for identity in assignment["blockIds"]:
                block = blocks.get(identity)
                if block is None:
                    raise ValueError("Unknown block reference")
                expected = {"text": "richText", "media": "image"}.get(slot["kind"], slot["kind"])
                if block["kind"] != expected:
                    raise ValueError("Incompatible block slot")
                if block["kind"] == "richText":
                    chars += len(block["text"])
                    lines += len(block["text"].split("\n"))
                if block["kind"] == "image":
                    check_media(block["assetId"])
            if chars > slot.get("maxChars", float("inf")) or lines > slot.get("maxLines", float("inf")):
                raise ValueError("Text or line capacity exceeded")
            for identity in assignment["assetIds"]:
                check_media(identity)
        for slot in layout["slots"]:
            if slot["required"] and not any(a["slotId"] == slot["id"] for a in slide["slotAssignments"]):
                raise ValueError("Missing required slot")


def _semantics(name: str, value: dict) -> None:
    if name == "DocumentGraph":
        _identities(value)
        if "presentation" in value and "presentation" not in value["outputModes"]:
            raise ValueError("Presentation mode required")
        asset_ids = {asset["id"] for asset in value["assets"]}
        for section in value["sections"]:
            for block in section["blocks"]:
                if block["kind"] == "image" and block["assetId"] not in asset_ids:
                    raise ValueError("Unknown image asset")
                if block["kind"] == "table":
                    _table(block["table"])
                if block["kind"] == "chart":
                    _chart(block["chart"])
                    _table(block["frame"]["tableFallback"])
        if "presentation" in value:
            _presentation(value["presentation"], value)
    elif name == "PresentationDocument":
        _presentation(value)
    elif name == "GenerationPlan":
        _unique(value["outputModes"], "output mode")
        _unique([item["id"] for item in value["outline"]], "outline id")
    elif name == "LayoutRegistry":
        _unique([layout["id"] for layout in value["layouts"]], "layout")
        for layout in value["layouts"]:
            ids = [slot["id"] for slot in layout["slots"]]
            _unique(ids, "slot")
            _unique([slot["order"] for slot in layout["slots"] if "order" in slot], "slot order")
            if any(slot.get("minItems", 0) > slot["maxItems"] for slot in layout["slots"]):
                raise ValueError("Invalid slot capacity")
            if "readingOrder" in layout and (len(layout["readingOrder"]) != len(ids) or set(layout["readingOrder"]) != set(ids)):
                raise ValueError("Invalid reading order")
    elif name == "TemplatePackage":
        _unique([item["name"] for item in value["dependencies"]], "dependency")
        _unique([item["id"] for item in value["licenseMetadata"]], "license entry")
    elif name == "DatasetProfile":
        _unique([field["name"] for field in value["fields"]], "field")
        if value["sampling"]["sampleSize"] > value["sampling"]["populationSize"] or any(f["cardinality"] > value["rowCount"] or f["nullCount"] + f["invalidCount"] > value["rowCount"] for f in value["fields"]):
            raise ValueError("Invalid dataset counts")
    elif name == "ChartPlan":
        _unique([value["selectedCandidate"]["id"], *[item["id"] for item in value["alternatives"]]], "candidate")
    elif name == "ChartSpec":
        _chart(value)
    elif name == "ChartFrame":
        _table(value["tableFallback"])
    elif name == "TableData":
        _table(value)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    _schema_ref: ClassVar[str] = ""
    _contract_name: ClassVar[str] = ""

    @model_validator(mode="after")
    def check_contract(self):
        wire = self.model_dump(by_alias=True, exclude_unset=True, mode="json")
        _validate_ref(self._schema_ref, wire)
        _semantics(self._contract_name, wire)
        return self


def _snake(name: str) -> str:
    result = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return result + "_" if result in {"as"} else result


_MODEL_CACHE: dict[str, Any] = {}


def _annotation(schema: dict, file: str, pointer: str, name: str) -> Any:
    if "$ref" in schema:
        target_file, _, target_pointer = schema["$ref"].partition("#")
        target_file = target_file or file
        target = SCHEMAS[target_file]
        for part in target_pointer.strip("/").split("/") if target_pointer else []:
            target = target[part]
        return _annotation(target, target_file, target_pointer, target.get("title", target_pointer.rsplit("/", 1)[-1] or name))
    if "const" in schema:
        return Literal[schema["const"]]
    if "enum" in schema:
        return Literal[tuple(schema["enum"])]
    if "oneOf" in schema:
        return Union[tuple(_annotation(item, file, pointer + f"/oneOf/{index}", name + str(index)) for index, item in enumerate(schema["oneOf"]))]
    kind = schema.get("type")
    if isinstance(kind, list):
        return Union[tuple(_annotation({"type": item}, file, pointer, name) for item in kind)]
    if kind == "array":
        return list[_annotation(schema["items"], file, pointer + "/items", name + "Item")]
    if kind == "object":
        if "properties" not in schema:
            return dict[str, _annotation(schema["additionalProperties"], file, pointer + "/additionalProperties", name + "Value")]
        key = file + "#" + pointer
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        fields = {}
        for property_name, child in schema["properties"].items():
            child_type = _annotation(child, file, pointer + "/properties/" + property_name, name + property_name[0].upper() + property_name[1:])
            required = property_name in schema.get("required", [])
            fields[_snake(property_name)] = (child_type if required else child_type | None, Field(... if required else None, alias=property_name))
        model = create_model(name + "Model", __base__=ContractModel, __module__=__name__, **fields)
        model._schema_ref = key
        model._contract_name = name
        _MODEL_CACHE[key] = model
        return model
    return {"string": str, "integer": int, "number": float, "boolean": bool, "null": type(None)}[kind]


def _contract(name: str) -> type[BaseModel]:
    ref = CONTRACT_REFS[name]
    annotation = _annotation({"$ref": ref}, ref.split("#")[0], "", name)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation

    class UnionContract(RootModel[annotation]):
        model_config = ConfigDict(strict=True)

        @model_validator(mode="after")
        def check_contract(self):
            _validate_ref(ref, self.model_dump(by_alias=True, exclude_unset=True, mode="json"))
            return self

    UnionContract.__name__ = name + "Model"
    return UnionContract


DocumentGraphModel = _contract("DocumentGraph")
GenerationPlanModel = _contract("GenerationPlan")
EditCommandModel = _contract("EditCommand")
PresentationDocumentModel = _contract("PresentationDocument")
LayoutRegistryModel = _contract("LayoutRegistry")
MediaIntentModel = _contract("MediaIntent")
TemplatePackageModel = _contract("TemplatePackage")
DatasetProfileModel = _contract("DatasetProfile")
AnalyticIntentModel = _contract("AnalyticIntent")
ChartPlanModel = _contract("ChartPlan")
ChartSpecModel = _contract("ChartSpec")
EncodingSpecModel = _contract("EncodingSpec")
ChartFrameModel = _contract("ChartFrame")
