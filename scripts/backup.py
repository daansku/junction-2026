"""Hourly backup of $DATA_DIR/runs (PLAN.md 3.4: lost traces are lost money).

    python scripts/backup.py                 # loop forever, one archive per hour
    python scripts/backup.py --once          # single archive
    BACKUP_DIR=D:/junction-backups python scripts/backup.py

Writes runs-<UTC stamp>.tar.gz into BACKUP_DIR (default ~/junction-backups), keeps the newest --keep archives.
Restore: tar -xzf runs-<stamp>.tar.gz -C $DATA_DIR
"""
from __future__ import annotations

import argparse
import os
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path


def backup_once(data_dir: Path, backup_dir: Path, keep: int) -> Path | None:
    runs = data_dir / "runs"
    if not runs.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp = backup_dir / f"runs-{stamp}.tar.gz.part"
    with tarfile.open(tmp, "w:gz") as tar:
        tar.add(runs, arcname="runs")
    final = tmp.with_suffix("")  # strip .part
    os.replace(tmp, final)
    archives = sorted(backup_dir.glob("runs-*.tar.gz"))
    for old in archives[:-keep]:
        old.unlink(missing_ok=True)
    return final


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR", str(Path.home() / "junction-data")))
    ap.add_argument("--backup-dir", default=os.environ.get("BACKUP_DIR", str(Path.home() / "junction-backups")))
    ap.add_argument("--every", type=int, default=3600, help="seconds between archives")
    ap.add_argument("--keep", type=int, default=48)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    while True:
        try:
            out = backup_once(Path(a.data_dir), Path(a.backup_dir), a.keep)
            print(f"{datetime.now().isoformat(timespec='seconds')} backup -> {out}", flush=True)
        except Exception as e:  # noqa: BLE001 - never die; try again next round
            print(f"backup failed: {e}", flush=True)
        if a.once:
            return
        time.sleep(a.every)


if __name__ == "__main__":
    main()
