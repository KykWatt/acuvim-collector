from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from acuvim import (
    AcuvimClient,
    RECORD_INTERVAL_MINUTES,
)


def _log(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    print(f"[{ts}] {msg}")


def _default_csv_filename(serial: str) -> Path:
    """
    Generate filename: SERIAL_YYYYMMDD-HHMMSS.csv
    """
    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    return Path(f"{serial}-{stamp}.csv")


def _records_to_csv(
    records,
    serial: Optional[str],
    csv_path: Path,
) -> None:
    """
    Write records to CSV in a flat, easy-to-import format.
    Timestamp in text format "YYYY-MM-DD HH:MM:SS".
    """
    fieldnames = [
        "serial",
        "index",
        "seq",
        "timestamp",
        "kwh_import",
        "kwh_export",
        "kvarh_import",
        "kvarh_export",
    ]

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in records:
            ts_text = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")  # <-- FIXED FORMAT
            writer.writerow(
                {
                    "serial": serial or "",
                    "index": r.index,
                    "seq": r.seq,
                    "timestamp": ts_text,
                    "kwh_import": f"{r.kwh_import:.3f}",
                    "kwh_export": f"{r.kwh_export:.3f}",
                    "kvarh_import": f"{r.kvarh_import:.3f}",
                    "kvarh_export": f"{r.kvarh_export:.3f}",
                }
            )


def main() -> None:
    args = _parse_args()

    _log(f"Connecting to {args.host}:{args.port} (unit/device_id {args.unit})...")
    with AcuvimClient(args.host, port=args.port, unit=args.unit) as cli:
        _log("Connected.")

        # 1) Status
        status = cli.read_log_status()
        if status.record_size_bytes != 28:
            _log(
                f"WARNING: recordSize={status.record_size_bytes}B "
                f"(expected 28B). Proceeding anyway."
            )

        if status.used_records == 0:
            _log("No historical records available.")
            return

        cli.latch_log()

        # 2) Determine slice
        if args.mode == "all":
            offset = 0
            count = status.used_records
        else:
            needed = max(
                1,
                min(
                    status.used_records,
                    math.ceil(args.minutes / RECORD_INTERVAL_MINUTES),
                ),
            )
            offset = max(0, status.used_records - needed)
            count = needed

        _log(f"Retrieving {count} records from offset={offset}...")

        records = cli.read_records_range(offset=offset, count=count)

        if not records:
            _log("No records retrieved.")
            return

        _log(f"Retrieved {len(records)} records successfully.")

        # 3) Choose CSV filename
        if args.output:
            csv_file = args.output
        else:
            serial = args.serial or "unknown"
            csv_file = _default_csv_filename(serial)

        # 4) Write CSV
        _records_to_csv(records, args.serial, csv_file)
        _log(f"CSV written to {csv_file}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Acuvim CL historical log collector")
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--unit", type=int, default=1)
    p.add_argument("--serial", required=False)

    p.add_argument("--mode", choices=["last", "all"], default="last")
    p.add_argument("--minutes", type=int, default=60)

    p.add_argument("--output", type=Path, help="Optional explicit CSV filename")

    return p.parse_args()


if __name__ == "__main__":
    main()
