"""Bounded, JSON-safe parser contract. Locator indices are one-based."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from pydantic.alias_generators import to_camel

SourceKind = Literal['pdf', 'docx', 'pptx', 'xlsx', 'csv', 'png', 'jpeg']
CellValue = str | int | float | bool | None


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', allow_inf_nan=False,
                              alias_generator=to_camel, populate_by_name=True)


class SourceLocator(StrictModel):
    page: int | None = Field(default=None, ge=1)
    slide: int | None = Field(default=None, ge=1)
    paragraph: int | None = Field(default=None, ge=1)
    sheet: str | None = Field(default=None, min_length=1, max_length=300)
    row: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def valid_locator(self):
        if sum(value is not None for value in (self.page, self.slide, self.paragraph, self.sheet)) != 1:
            raise ValueError('Exactly one source coordinate is required')
        if (self.row is None) != (self.column is None) or (self.row is not None and self.sheet is None):
            raise ValueError('Cell coordinates require sheet, row, and column')
        return self


class Segment(StrictModel):
    text: str = Field(max_length=1_000_000)
    role: Literal['text', 'heading'] = 'text'
    locator: SourceLocator


class FormulaCell(StrictModel):
    # Excel data-table formula records have attributes but no formula text.
    formula: str | None = Field(default=None, max_length=32_767)
    formula_kind: Literal['normal', 'array', 'dataTable'] = 'normal'
    formula_range: str | None = Field(default=None, max_length=100)
    attributes: dict[str, str] = Field(default_factory=dict)
    cached_value: CellValue = None
    locator: SourceLocator


class SourceTable(StrictModel):
    name: str = Field(max_length=300)
    locator: SourceLocator
    # Row/column offsets are 1-based relative to this origin, including blank cells.
    start_row: int = Field(default=1, ge=1)
    start_column: int = Field(default=1, ge=1)
    rows: list[list[CellValue]] = Field(default_factory=list, max_length=10_000)
    formulas: list[FormulaCell] = Field(default_factory=list, max_length=100_000)

    def cell_locator(self, row: int, column: int) -> SourceLocator:
        if self.locator.sheet is None or not (0 <= row < len(self.rows)) or not (0 <= column < len(self.rows[row])):
            raise ValueError('Cell is outside this source table')
        return SourceLocator(sheet=self.locator.sheet, row=self.start_row + row,
                             column=self.start_column + column)


class SourceImage(StrictModel):
    width: int = Field(ge=1, le=50_000)
    height: int = Field(ge=1, le=50_000)
    format: Literal['png', 'jpeg']
    locator: SourceLocator


class ParsedSource(StrictModel):
    kind: SourceKind
    title: str = Field(max_length=300)
    segments: list[Segment] = Field(default_factory=list, max_length=10_000)
    tables: list[SourceTable] = Field(default_factory=list, max_length=100)
    images: list[SourceImage] = Field(default_factory=list, max_length=1_000)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
