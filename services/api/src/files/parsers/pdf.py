from pathlib import Path

import pymupdf

from src.files.parsers.base import MAX_TEXT, finalize, inspect_file, invalid, limit
from src.files.types import ParsedSource, Segment, SourceLocator


class PdfParser:
    def parse(self, path: Path) -> ParsedSource:
        if inspect_file(path, path.name) != 'pdf':
            raise invalid()
        segments = []
        total = 0
        # Text extraction does not execute JavaScript, attachments, actions, or URLs.
        # Failed native constructors can retain a Windows file handle. Passing
        # bounded bytes closes our file before MuPDF sees even malformed input.
        with pymupdf.open(stream=path.read_bytes(), filetype='pdf') as document:
            if document.needs_pass:
                raise invalid()
            if document.page_count > 1_000:
                raise limit()
            for index, page in enumerate(document):
                text = page.get_text('text')
                total += len(text)
                if total > MAX_TEXT:
                    raise limit()
                segments.append(Segment(text=text, locator=SourceLocator(page=index + 1)))
        return finalize(ParsedSource(kind='pdf', title=path.stem, segments=segments,
                                     metadata={'pageCount': len(segments)}))
