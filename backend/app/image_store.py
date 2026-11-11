from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.models import DetectionRecord


def compress_jpeg(data: bytes, max_size: tuple[int, int], quality: int) -> bytes:
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format != "JPEG":
                raise ValueError("Only JPEG images are supported")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid JPEG image") from exc


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary_path.write_bytes(data)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def save_detection_image(storage_dir: Path, image_key: str, data: bytes) -> str:
    compressed = compress_jpeg(data, (640, 480), 62)
    relative_path = Path("detections") / f"{image_key}.jpg"
    _atomic_write(storage_dir / relative_path, compressed)
    return relative_path.as_posix()


def save_live_frame(storage_dir: Path, box_id: str, data: bytes) -> Path:
    compressed = compress_jpeg(data, (320, 240), 42)
    key = sha256(box_id.encode("utf-8")).hexdigest()
    path = storage_dir / "live" / f"{key}.jpg"
    _atomic_write(path, compressed)
    return path


def live_frame_path(storage_dir: Path, box_id: str) -> Path:
    key = sha256(box_id.encode("utf-8")).hexdigest()
    return storage_dir / "live" / f"{key}.jpg"


def cleanup_detection_images(
    db: Session,
    storage_dir: Path,
    retention_days: int,
    max_storage_bytes: int,
) -> None:
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    expired = (
        db.query(DetectionRecord)
        .filter(DetectionRecord.created_at < cutoff)
        .order_by(DetectionRecord.created_at.asc())
        .all()
    )
    for detection in expired:
        path = storage_dir / "detections" / f"{detection.image_key}.jpg"
        path.unlink(missing_ok=True)
        db.delete(detection)
    db.flush()

    kept = (
        db.query(DetectionRecord)
        .order_by(DetectionRecord.created_at.asc())
        .all()
    )
    image_sizes = []
    total_size = 0
    for detection in kept:
        path = storage_dir / "detections" / f"{detection.image_key}.jpg"
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            db.delete(detection)
            continue
        image_sizes.append((detection, path, size))
        total_size += size

    while total_size > max_storage_bytes and image_sizes:
        detection, path, size = image_sizes.pop(0)
        path.unlink(missing_ok=True)
        db.delete(detection)
        total_size -= size

    db.commit()
