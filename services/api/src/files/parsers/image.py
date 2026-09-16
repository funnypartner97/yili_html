import warnings
from pathlib import Path

from PIL import Image

from src.files.parsers.base import finalize, inspect_file, invalid, limit
from src.files.types import ParsedSource, SourceImage, SourceLocator


class ImageParser:
    def parse(self, path: Path) -> ParsedSource:
        kind = inspect_file(path, path.name)
        if kind not in ('png', 'jpeg'):
            raise invalid()
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
                if width * height > 40_000_000 or max(width, height) > 50_000:
                    raise limit()
                if image.format.lower() != kind:
                    raise invalid()
                image.verify()
        return finalize(ParsedSource(kind=kind, title=path.stem, images=[SourceImage(
            width=width, height=height, format=kind, locator=SourceLocator(page=1))],
            metadata={'ocr': False}))
