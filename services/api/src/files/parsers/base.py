"""Preflight untrusted files before any document library sees their content.

Archives are inspected in place, never extracted. XML entities/DTDs, macros and
embedded programs are rejected. Parsers only read local bytes; relationships and
hyperlinks are metadata, never network inputs.
"""
import csv
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Protocol
from zipfile import ZipFile

from defusedxml import ElementTree

from src.core.errors import DomainError
from src.db.validation import validate_persistence_text
from src.files.types import ParsedSource, SourceKind

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_MEMBERS = 1_000
MAX_TEXT = 2_000_000
MAX_ROWS = 10_000
MAX_COLUMNS = 256
MAX_CELLS = 100_000
MAX_CELL_TEXT = 32_767
CONTENT_TYPES = {
    'pdf': 'application/pdf', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'csv': 'text/csv', 'png': 'image/png', 'jpeg': 'image/jpeg',
}
OOXML = {
    'docx': ('word/document.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'),
    'pptx': ('ppt/presentation.xml', 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'),
    'xlsx': ('xl/workbook.xml', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'),
}


class Parser(Protocol):
    def parse(self, path: Path) -> ParsedSource: ...


def invalid() -> DomainError:
    return DomainError('unsupported_file_signature', 'File content is not a supported, safe format.')


def limit() -> DomainError:
    return DomainError('source_limit_exceeded', 'The source exceeds supported parsing limits.')


def safe_filename(filename: str | None) -> str:
    name = (filename or 'source').replace('\\', '/').rsplit('/', 1)[-1]
    name = re.sub(r'[^\w. -]', '_', name, flags=re.UNICODE).strip(' .')
    name = name[:180].rstrip(' .') or 'source'
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{x}' for x in range(1, 10)), *(f'LPT{x}' for x in range(1, 10))}:
        name = '_' + name
    return name


def check_archive(path: Path, kind: str) -> None:
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_MEMBERS or sum(member.file_size for member in members) > MAX_ARCHIVE_BYTES:
                raise limit()
            seen = set()
            for member in members:
                name = member.filename
                lower = name.lower()
                if (name in seen or '\\' in name or ':' in name or '\x00' in name or
                        PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or
                        stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1 or
                        any(part in lower for part in ('vbaproject', '/activex/', '/embeddings/'))):
                    raise invalid()
                seen.add(name)
                if member.file_size > MAX_MEMBER_BYTES or member.file_size > max(member.compress_size, 1) * 200:
                    raise limit()
                if member.compress_type not in (0, 8):
                    raise invalid()
                if lower.endswith(('.xml', '.rels')):
                    # defusedxml forbids external entities; forbid_dtd also rejects internal DTDs.
                    root = ElementTree.fromstring(archive.read(member), forbid_dtd=True)
                    if lower == '[content_types].xml' or lower.endswith('.rels'):
                        for node in root:
                            declaration = (node.get('ContentType', '') + node.get('Type', '')).lower()
                            if any(token in declaration for token in ('macro', 'vbaproject', 'activex', 'oleobject')):
                                raise invalid()
                    if kind == 'xlsx' and lower.startswith('xl/worksheets/'):
                        check_sheet(root)
            main, expected_type = OOXML[kind]
            if main not in seen or '[Content_Types].xml' not in seen:
                raise invalid()
            root = ElementTree.fromstring(archive.read('[Content_Types].xml'), forbid_dtd=True)
            if not any(node.get('PartName') == '/' + main and node.get('ContentType') == expected_type for node in root):
                raise invalid()
    except DomainError:
        raise
    except Exception as error:
        raise invalid() from error


def check_sheet(root) -> None:
    """Check sparse coordinates before openpyxl expands gaps into empty cells."""
    cells = rows = 0
    for node in root.iter():
        tag = node.tag.rsplit('}', 1)[-1]
        if tag == 'row':
            rows += 1
            if rows > MAX_ROWS or not 1 <= int(node.get('r', str(rows))) <= MAX_ROWS:
                raise limit()
        if tag == 'c':
            cells += 1
            if cells > MAX_CELLS:
                raise limit()
        if tag in ('c', 'dimension', 'mergeCell'):
            reference = node.get('r' if tag == 'c' else 'ref', '')
            for coordinate in reference.split(':'):
                match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', coordinate)
                if not match:
                    raise invalid()
                column = 0
                for letter in match[1]:
                    column = column * 26 + ord(letter) - ord('A') + 1
                if column > MAX_COLUMNS or int(match[2]) > MAX_ROWS:
                    raise limit()


def read_csv(path: Path) -> list[list[str]]:
    try:
        # Bounded before decoding; a CSV has no binary magic, so text validation is essential.
        if path.stat().st_size > MAX_FILE_BYTES:
            raise limit()
        with path.open('r', encoding='utf-8-sig', newline='') as stream:
            sample = stream.read(8192)
            if not sample.strip() or sample.lstrip().startswith(('<', '{', '[')) or any(ord(c) < 32 and c not in '\r\n\t' for c in sample):
                raise invalid()
            stream.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
            except csv.Error:
                dialect = csv.excel
            rows = []
            width = None
            cells = text = 0
            for row in csv.reader(stream, dialect, strict=True):
                cells += len(row)
                text += sum(len(cell) for cell in row)
                if len(rows) >= MAX_ROWS or len(row) > MAX_COLUMNS or cells > MAX_CELLS or text > MAX_TEXT or any(len(cell) > MAX_CELL_TEXT for cell in row):
                    raise limit()
                if row and width is not None and len(row) != width:
                    raise invalid()
                if row and width is None:
                    width = len(row)
                if any(any(ord(c) < 32 and c not in '\r\n\t' for c in cell) for cell in row):
                    raise invalid()
                rows.append(row)
            if not rows:
                raise invalid()
            return rows
    except DomainError:
        raise
    except (UnicodeError, csv.Error) as error:
        raise invalid() from error


def inspect_file(path: Path, filename: str) -> SourceKind:
    if not 0 < path.stat().st_size <= MAX_FILE_BYTES:
        raise limit()
    with path.open('rb') as stream:
        header = stream.read(16)
    extension = Path(filename).suffix.lower()
    if extension == '.pdf' and header.startswith(b'%PDF-'):
        return 'pdf'
    if extension == '.png' and header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if extension in ('.jpg', '.jpeg') and header.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    kind = extension.lstrip('.')
    if kind in OOXML and header.startswith(b'PK\x03\x04'):
        check_archive(path, kind)
        return kind
    if extension == '.csv':
        read_csv(path)
        return 'csv'
    raise invalid()


def finalize(parsed: ParsedSource) -> ParsedSource:
    payload = parsed.model_dump(mode='json', by_alias=True)
    validate_persistence_text(payload)
    text = sum(len(segment.text) for segment in parsed.segments)
    text += sum(len(str(cell)) for table in parsed.tables for row in table.rows for cell in row if cell is not None)
    if text > MAX_TEXT:
        raise limit()
    return parsed
