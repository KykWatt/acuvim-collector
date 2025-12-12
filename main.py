from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
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
    Timestamp in text format "YYYY/MM/DD HH:MM" (no seconds),
    and energies with 1 decimal place.
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
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
        )
        writer.writeheader()

        for r in records:
            ts_text = r.timestamp.strftime("%Y/%m/%d %H:%M")
            writer.writerow(
                {
                    "serial": serial or "",
                    "index": r.index,
                    "seq": r.seq,
                    "timestamp": ts_text,
                    "kwh_import": f"{r.kwh_import:.1f}",
                    "kwh_export": f"{r.kwh_export:.1f}",
                    "kvarh_import": f"{r.kvarh_import:.1f}",
                    "kvarh_export": f"{r.kvarh_export:.1f}",
                }
            )


def main() -> None:
    args = _parse_args()
    # Defensive fallback for environments running an older argparse schema
    verbose = getattr(args, "verbose", False)

    _log(f"Connecting to {args.host}:{args.port} (unit/device_id {args.unit})...")
    with AcuvimClient(args.host, port=args.port, unit=args.unit) as cli:
        _log("Connected.")

        if args.sync_time:
            _sync_time_if_needed(cli, allowed_drift=args.allowed_drift)
        elif verbose:
            _log_time_drift_only(cli, allowed_drift=args.allowed_drift)
            _log(
                "Time sync not requested; use --sync-time to automatically update the meter clock"
            )
        else:
            _log("Time sync skipped (use --sync-time to enable meter/system drift check).")

        # 1) Status
        status = cli.read_log_status()
        if verbose:
            _log(
                "Log status → used=%s total=%s record_size=%sB interval=%smin"
                % (
                    status.used_records,
                    status.max_records,
                    status.record_size_bytes,
                    RECORD_INTERVAL_MINUTES,
                )
            )
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
        if verbose:
            _log(
                f"Mode={args.mode} minutes={args.minutes} computed needed={needed}"
            )

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
    p.add_argument(
        "--sync-time",
        action="store_true",
        help="Check meter/system drift and update meter time when drift exceeds allowed seconds",
    )
    p.add_argument(
        "--allowed-drift",
        type=int,
        default=60,
        help="Maximum allowed drift in seconds before syncing meter time",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print additional diagnostics including time-drift decisions and log status",
    )

    return p.parse_args()


def _sync_time_if_needed(cli: AcuvimClient, allowed_drift: int) -> float:
    _log("Checking meter/system time drift...")
    meter_time = cli.read_meter_time()
    system_time = datetime.now().replace(microsecond=0)

    drift_seconds = abs((system_time - meter_time).total_seconds())
    _log(
        "Time drift check: meter=%s, system=%s, drift=%.1fs"
        % (meter_time, system_time, drift_seconds)
    )

    if drift_seconds > allowed_drift:
        _log(
            f"Drift {drift_seconds:.1f}s exceeds allowed {allowed_drift}s → syncing meter time"
        )
        cli.write_meter_time(system_time)
        new_time = cli.read_meter_time()
        _log(f"Meter time after sync: {new_time}")
    else:
        _log("Drift within limits → no sync required.")

    return drift_seconds


def _log_time_drift_only(cli: AcuvimClient, allowed_drift: int) -> float:
    """
    Read and log meter/system drift without applying a sync. Useful when
    --sync-time is omitted but diagnostics are requested.
    """
    meter_time = cli.read_meter_time()
    system_time = datetime.now().replace(microsecond=0)
    drift_seconds = abs((system_time - meter_time).total_seconds())
    _log(
        "Drift check only: meter=%s, system=%s, drift=%.1fs (allowed=%ss)"
        % (meter_time, system_time, drift_seconds, allowed_drift)
    )

    if drift_seconds > allowed_drift:
        _log(
            f"Drift exceeds allowed threshold but sync disabled (use --sync-time to update meter)."
        )
    else:
        _log("Drift within allowed threshold.")

    return drift_seconds


if __name__ == "__main__":
    main()
