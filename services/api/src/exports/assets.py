"""Managed-asset resolution for export.

Only manifest-declared assets are copied into the archive, and each one's bytes
are hashed so the manifest can record a verifiable SHA-256. The resolver is an
injectable boundary: tests supply deterministic bytes, production reads the
stored source object.
"""
from __future__ import annotations

import hashlib
import posixpath
import tempfile
from pathlib import Path
from typing import Protocol

_EXTENSIONS = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    "image/gif": ".gif", "image/svg+xml": ".svg",
}


class AssetResolver(Protocol):
    def load(self, asset: dict) -> bytes: ...


class StaticAssetResolver:
    """Deterministic resolver keyed by asset uri, for tests and local export."""

    def __init__(self, mapping: dict[str, bytes]):
        self.mapping = mapping

    def load(self, asset: dict) -> bytes:
        return self.mapping[asset["uri"]]


class StorageAssetResolver:
    """Loads managed asset bytes from object storage, bounded to 50 MiB each."""

    MAX_ASSET_BYTES = 52_428_800

    def __init__(self, storage):
        self.storage = storage

    def load(self, asset: dict) -> bytes:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset"
            self.storage.download_file(asset["uri"], path, max_bytes=self.MAX_ASSET_BYTES)
            return path.read_bytes()


class PreparedAsset:
    def __init__(self, *, asset_id: str, path: str, content_type: str, sha256: str,
                 data: bytes, alt: str, caption: str | None):
        self.asset_id = asset_id
        self.path = path
        self.content_type = content_type
        self.sha256 = sha256
        self.data = data
        self.alt = alt
        self.caption = caption

    def manifest_entry(self) -> dict:
        entry = {"id": self.asset_id, "path": self.path, "contentType": self.content_type,
                 "sha256": self.sha256, "bytes": len(self.data), "alt": self.alt}
        if self.caption:
            entry["caption"] = self.caption
        return entry


def _guess(asset: dict) -> tuple[str, str]:
    uri = asset.get("uri", "")
    extension = posixpath.splitext(uri)[1].lower()
    content_type = next((key for key, value in _EXTENSIONS.items() if value == extension), "application/octet-stream")
    if not extension:
        extension = _EXTENSIONS.get(content_type, ".bin")
    return content_type, extension


def collect_assets(graph: dict, resolver: AssetResolver) -> list[PreparedAsset]:
    prepared: list[PreparedAsset] = []
    for asset in graph.get("assets", []):
        if asset.get("kind") != "image":
            # Only image assets are embedded in this slice; other kinds are declared
            # but not copied, keeping the archive self-contained and bounded.
            continue
        data = resolver.load(asset)
        content_type, extension = _guess(asset)
        intent = asset.get("mediaIntent", {})
        prepared.append(PreparedAsset(
            asset_id=asset["id"], path=f"assets/{asset['id']}{extension}", content_type=content_type,
            sha256=hashlib.sha256(data).hexdigest(), data=data, alt=intent.get("alt", ""),
            caption=intent.get("caption")))
    prepared.sort(key=lambda item: item.asset_id)
    return prepared
