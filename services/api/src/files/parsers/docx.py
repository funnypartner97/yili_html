from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph

from src.files.parsers.base import (MAX_CELL_TEXT, MAX_CELLS, MAX_ROWS, MAX_TEXT, WORD_NS,
                                    finalize, inspect_file, invalid, limit, word_int)
from src.files.types import ParsedSource, Segment, SourceLocator, SourceTable


class DocxParser:
    def parse(self, path: Path) -> ParsedSource:
        if inspect_file(path, path.name) != 'docx':
            raise invalid()
        document = Document(path)
        segments = []
        total = 0
        paragraph_indices = {}
        # Citation paragraph indices include every actual body descendant w:p,
        # including cell paragraphs. A table anchor resolves to its own first
        # paragraph even when the document contains no body-level paragraphs.
        for index, element in enumerate(document.element.body.iter(WORD_NS + 'p'), 1):
            paragraph = Paragraph(element, document._body)
            text = paragraph.text
            total += len(text)
            if index > 10_000 or total > MAX_TEXT:
                raise limit()
            paragraph_indices[element] = index
            segments.append(Segment(text=text,
                role='heading' if paragraph.style and paragraph.style.name.startswith('Heading') else 'text',
                locator=SourceLocator(paragraph=index)))
        tables = []
        total_cells = 0
        for index, table in enumerate(document.element.body.iter(WORD_NS + 'tbl'), 1):
            if index > 100:
                raise limit()
            rows = []
            for row_number, row in enumerate(table.findall(WORD_NS + 'tr'), 1):
                if row_number > MAX_ROWS:
                    raise limit()
                before = word_int(row, 'trPr/gridBefore', 0)
                values = [''] * before
                total_cells += before
                for cell in row.findall(WORD_NS + 'tc'):
                    span = word_int(cell, 'tcPr/gridSpan', 1)
                    merge = cell.find(WORD_NS + 'tcPr/' + WORD_NS + 'vMerge')
                    if merge is not None and merge.get(WORD_NS + 'val', 'continue') == 'continue':
                        text = rows[-1][len(values)]
                    else:
                        text = '\n'.join(Paragraph(p, document._body).text for p in cell.findall(WORD_NS + 'p'))
                    total_cells += span
                    total += len(text) * span
                    if total_cells > MAX_CELLS or len(text) > MAX_CELL_TEXT or total > MAX_TEXT:
                        raise limit()
                    # Span arithmetic and budgets precede even this bounded list.
                    values.extend([text] * span)
                after = word_int(row, 'trPr/gridAfter', 0)
                total_cells += after
                if total_cells > MAX_CELLS:
                    raise limit()
                values.extend([''] * after)
                rows.append(values)
            anchor = paragraph_indices[next(table.iter(WORD_NS + 'p'))]
            tables.append(SourceTable(name=f'Table {index}', locator=SourceLocator(paragraph=anchor),
                                      rows=rows))
        return finalize(ParsedSource(kind='docx', title=path.stem, segments=segments, tables=tables))
