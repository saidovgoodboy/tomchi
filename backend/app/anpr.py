from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

from app.crud import is_valid_plate

_OCR_LOCK = threading.BoundedSemaphore(1)
_WORD_PATTERN = re.compile(r"[^A-Z0-9]")
_DIGIT_CORRECTIONS = str.maketrans(
    {
        "O": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "L": "1",
        "Z": "2",
        "S": "5",
        "G": "6",
        "B": "8",
    }
)
_LETTER_CORRECTIONS = str.maketrans(
    {
        "0": "O",
        "1": "I",
        "2": "Z",
        "5": "S",
        "6": "G",
        "8": "B",
    }
)
_PLATE_DIGIT_POSITIONS = ({0, 1, 3, 4, 5}, {0, 1, 2, 3, 4})


@dataclass(frozen=True)
class PlateCandidate:
    plate: str
    confidence: float


class OCRUnavailableError(RuntimeError):
    pass


class OCRProcessingError(RuntimeError):
    pass


def is_ocr_available(command: str) -> bool:
    return bool(shutil.which(command))


def _normalize_candidate(raw: str) -> tuple[str, int] | None:
    cleaned = _WORD_PATTERN.sub("", raw.upper())
    if len(cleaned) != 8:
        return None

    candidates: list[tuple[str, int]] = []
    for digit_positions in _PLATE_DIGIT_POSITIONS:
        normalized = list(cleaned)
        corrections = 0
        for index, char in enumerate(cleaned):
            translated = char.translate(
                _DIGIT_CORRECTIONS if index in digit_positions else _LETTER_CORRECTIONS
            )
            normalized[index] = translated
            corrections += translated != char
        plate = "".join(normalized)
        if is_valid_plate(plate):
            candidates.append((plate, corrections))
    return min(candidates, key=lambda item: item[1]) if candidates else None


def candidate_from_tsv(tsv: str) -> PlateCandidate | None:
    lines: dict[tuple[str, str, str, str], list[tuple[str, float]]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        if row.get("level") != "5":
            continue
        word = _WORD_PATTERN.sub("", row.get("text", "").upper())
        if not word:
            continue
        try:
            confidence = float(row["conf"])
        except (KeyError, ValueError):
            continue
        if confidence < 0:
            continue
        line_key = tuple(
            row.get(name, "")
            for name in ("page_num", "block_num", "par_num", "line_num")
        )
        lines.setdefault(line_key, []).append((word, confidence))

    best: PlateCandidate | None = None
    for words in lines.values():
        line_text = "".join(word for word, _ in words)
        line_confidence = sum(
            confidence * len(word) for word, confidence in words
        ) / max(1, sum(len(word) for word, _ in words))
        for start in range(max(1, len(line_text) - 7)):
            normalized = _normalize_candidate(line_text[start:start + 8])
            if normalized is None:
                continue
            plate, corrections = normalized
            confidence = max(0.0, min(1.0, line_confidence / 100 - corrections * 0.015))
            if best is None or confidence > best.confidence:
                best = PlateCandidate(plate=plate, confidence=confidence)
    return best


def _prepare_image(image_bytes: bytes) -> bytes:
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.format != "JPEG":
                raise ValueError("ANPR accepts JPEG images only")
            image = ImageOps.exif_transpose(source).convert("L")
            image = ImageOps.autocontrast(image)
            image = ImageEnhance.Contrast(image).enhance(1.35)
            if image.width < 1280:
                image = image.resize(
                    (image.width * 2, image.height * 2),
                    Image.Resampling.LANCZOS,
                )
            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise OCRProcessingError("Could not decode image for OCR") from exc


def recognize_plate(
    image_bytes: bytes,
    command: str = "tesseract",
    timeout_seconds: int = 5,
) -> PlateCandidate | None:
    executable = shutil.which(command)
    if executable is None:
        raise OCRUnavailableError(f"Tesseract executable not found: {command}")

    prepared_image = _prepare_image(image_bytes)
    try:
        with _OCR_LOCK:
            result = subprocess.run(
                [
                    executable,
                    "stdin",
                    "stdout",
                    "--psm",
                    "6",
                    "-l",
                    "eng",
                    "-c",
                    "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                    "tsv",
                ],
                input=prepared_image,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise OCRProcessingError("Tesseract OCR timed out") from exc
    except FileNotFoundError as exc:
        raise OCRUnavailableError(f"Tesseract executable disappeared: {command}") from exc
    except OSError as exc:
        raise OCRProcessingError("Could not start Tesseract OCR") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        detail = detail or f"Tesseract exited with status {result.returncode}"
        raise OCRProcessingError(detail)
    return candidate_from_tsv(result.stdout.decode("utf-8", errors="replace"))
