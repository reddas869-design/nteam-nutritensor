"""Bounded decoding, EXIF removal, and owner-scoped upload lifecycle."""

from __future__ import annotations

import hashlib
import io
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from nutritensor.core.config import Settings
from nutritensor.core.errors import InvalidImage, NotFound
from nutritensor.storage.database import Database, identifier


class ImageService:
    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.directory = settings.uploads_path.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.directory.chmod(0o700)

    def save(self, owner: str, content: bytes) -> dict:
        if not content or len(content) > self.settings.upload_limit_bytes:
            raise InvalidImage("Image is empty or exceeds the upload size limit")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as probe:
                    if probe.format not in {"JPEG", "PNG", "WEBP"}:
                        raise InvalidImage("Upload a JPEG, PNG, or WebP image")
                    if probe.width * probe.height > self.settings.image_max_pixels:
                        raise InvalidImage("Image dimensions exceed the pixel limit")
                    if getattr(probe, "n_frames", 1) != 1:
                        raise InvalidImage("Animated images are not supported")
                    probe.verify()
                with Image.open(io.BytesIO(content)) as decoded:
                    normalized = ImageOps.exif_transpose(decoded).convert("RGB")
                    normalized.thumbnail((self.settings.image_max_edge, self.settings.image_max_edge))
                    clean = Image.new("RGB", normalized.size)
                    clean.paste(normalized)
                    width, height = clean.size
                    output = io.BytesIO()
                    clean.save(output, format="JPEG", quality=88, optimize=True)
        except InvalidImage:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise InvalidImage("The image could not be decoded safely") from exc
        image_id = identifier()
        relative = f"{image_id}.jpg"
        encoded = output.getvalue()
        destination = self.directory / relative
        destination.write_bytes(encoded)
        destination.chmod(0o600)
        try:
            self.database.store_image(owner, image_id, relative, width, height, hashlib.sha256(encoded).hexdigest())
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return {"id": image_id, "width": width, "height": height, "bytes": len(encoded)}

    def path(self, owner: str, image_id: str) -> Path:
        record = self.database.get_image(image_id, owner)
        destination = (self.directory / record["relative_path"]).resolve()
        if destination.parent != self.directory or not destination.is_file():
            raise NotFound("Image is unavailable or expired")
        return destination

    def remove(self, owner: str, image_id: str) -> None:
        relative = self.database.delete_image(image_id, owner)
        destination = (self.directory / relative).resolve()
        if destination.parent == self.directory:
            destination.unlink(missing_ok=True)

    def cleanup(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.settings.image_retention_hours)
        records = self.database.expired_images(cutoff.isoformat())
        for record in records:
            try:
                self.remove(record["owner_id"], record["id"])
            except NotFound:
                continue
        return len(records)
