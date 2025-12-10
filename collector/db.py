# collector/db.py

import sqlite3
from datetime import datetime
from typing import List, Optional
from .models import MeterConfig


def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if val is None:
        return None
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return None


def row_to_meter(row: sqlite3.Row) -> MeterConfig:
    return MeterConfig(
        id=row["id"],
        serial_number=row["serial_number"],
        ip_address=row["ip_address"],
        unit_id=row["unit_id"],
        baud_rate=row["baud_rate"],
        model=row["model"],
        site_name=row["site_name"],
        enabled=bool(row["enabled"]),
        last_collected=_parse_dt(row["last_collected"]),
        last_timesync=_parse_dt(row["last_timesync"]),
        last_drift_seconds=row["last_drift_seconds"],
        created=_parse_dt(row["created"]),
        updated=_parse_dt(row["updated"]),
        last_record_index=row["last_record_index"] or 0,
        output_folder=row["output_folder"],
    )


def get_enabled_meters(conn: sqlite3.Connection) -> List[MeterConfig]:
    cur = conn.execute("SELECT * FROM meters WHERE enabled = 1 ORDER BY id ASC")
    return [row_to_meter(r) for r in cur.fetchall()]


def get_meter_by_id(conn: sqlite3.Connection, meter_id: int):
    cur = conn.execute("SELECT * FROM meters WHERE id = ?", (meter_id,))
    row = cur.fetchone()
    return row_to_meter(row) if row else None


def update_meter_pointer(conn, meter_id, last_record_index, last_collected):
    conn.execute(
        """
        UPDATE meters
        SET last_record_index = ?,
            last_collected = ?,
            updated = ?
        WHERE id = ?
        """,
        (
            last_record_index,
            last_collected.isoformat(sep=" "),
            datetime.now().isoformat(sep=" "),
            meter_id,
        ),
    )
    conn.commit()


def update_timesync_info(conn, meter_id, last_timesync, drift_seconds):
    conn.execute(
        """
        UPDATE meters
        SET last_timesync = ?,
            last_drift_seconds = ?,
            updated = ?
        WHERE id = ?
        """,
        (
            last_timesync.isoformat(sep=" "),
            drift_seconds,
            datetime.now().isoformat(sep=" "),
            meter_id,
        ),
    )
    conn.commit()
