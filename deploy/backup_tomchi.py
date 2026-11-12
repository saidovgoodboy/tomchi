#!/usr/bin/env python3
"""Tomchi ma'lumotlar bazasi va arxiv rasmlaridan zaxira nusxa oladi.

Ishlatish:
    python3 deploy/backup_tomchi.py --dest /var/backups/tomchi --keep 14

SQLite'ning `backup` API'sidan foydalanadi: baza ishlab turganda ham izchil
nusxa oladi. Arxiv papkasi alohida tar.gz qilib saqlanadi.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "backend" / "database" / "tomchi.db"
DEFAULT_STORAGE = REPO_ROOT / "backend" / "storage"


def backup_database(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    target_db = sqlite3.connect(destination)
    try:
        source_db.backup(target_db)
    finally:
        target_db.close()
        source_db.close()
    return destination


def backup_storage(source: Path, destination: Path) -> Path | None:
    if not source.is_dir() or not any(source.rglob("*.jpg")):
        return None
    with tarfile.open(destination, "w:gz") as archive:
        archive.add(source, arcname=source.name)
    return destination


def prune(directory: Path, pattern: str, keep_days: int) -> list[Path]:
    if keep_days <= 0:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    removed = []
    for path in sorted(directory.glob(pattern)):
        if datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) < cutoff:
            path.unlink()
            removed.append(path)
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tomchi zaxira nusxasi")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--storage", type=Path, default=DEFAULT_STORAGE)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--keep", type=int, default=14, help="Necha kun saqlanadi (0 = cheksiz)")
    args = parser.parse_args(argv)

    if not args.db.is_file():
        print(f"Baza topilmadi: {args.db}", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    args.dest.mkdir(parents=True, exist_ok=True)

    db_copy = backup_database(args.db, args.dest / f"tomchi-{stamp}.db")
    print(f"Baza: {db_copy} ({db_copy.stat().st_size} bayt)")

    storage_copy = backup_storage(args.storage, args.dest / f"storage-{stamp}.tar.gz")
    if storage_copy is not None:
        print(f"Rasmlar: {storage_copy} ({storage_copy.stat().st_size} bayt)")

    for pattern in ("tomchi-*.db", "storage-*.tar.gz"):
        for old in prune(args.dest, pattern, args.keep):
            print(f"Eski nusxa o'chirildi: {old}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
