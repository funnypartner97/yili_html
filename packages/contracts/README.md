# Shared document contracts

The files in `schemas/` are the canonical Draft 7 JSON Schemas. They define wire
shape, required provenance, UUIDv7 identities, bounded enums, and reserved pack
metadata. `pnpm --filter @html-office/contracts generate` generates committed
TypeScript declarations using json-schema-to-typescript. The test command checks
that those declarations are current before running the contract suite.

The exported Zod validators validate against these schemas with Ajv and then
enforce relationships JSON Schema cannot express: global entity identity,
explicit sibling order, registered layout and slot capacity, reference integrity,
note bindings, media aspect ratio, and chart baseline/mark consistency.

Python uses the same local schemas to construct strict Pydantic models with
snake_case attributes and camelCase wire aliases. There is no remote schema
resolution. Deployments of the API must include `packages/contracts/schemas`
and `packages/contracts/registries` at the repository-relative location.
Serialize with `model_dump(by_alias=True, mode="json")`. The shared model
serializer omits optional fields that were not supplied, including nested fields.
Ordinary FastAPI `response_model=...Model` routes inherit this behavior without
additional exclusion flags. Explicit nullable data is preserved; explicit null
for a nonnullable field is still rejected. This also applies to contract models
nested inside union edit commands.

Use `DocumentGraphSchema` / `DocumentGraphModel` when a complete graph is
available. Standalone presentation validation can check layout, counts, note
binding, and animation references, but only graph validation can resolve block
and asset contents. Arrays preserve transport order; renderers should use the
explicit `order` field. Reordering must not replace IDs or note bindings.

`OutputMode` includes all four product modes. This slice only accepts
`document` and `presentation` in generation plans and document graphs.
The data visualization and template contracts reserve future behavior; they do
not enable endpoints, external sources, recommendation logic, or authoring UI.
Chart invariants describe the required evidence and capacity; a later data
validator must verify those claims against actual datasets.

Layout slot IDs and registry/template IDs are semantic names. Document entities,
including assignment, note, animation entry and chart IDs, are UUIDv7 values.
Source references point to ingested source IDs and locators; asset URIs use the
local `asset:` scheme. Block text is text, never executable HTML or JavaScript.

TypeScript and Python tests consume the same JSON round-trip fixtures. Both
runtime validators must be updated together when cross-field rules change.
