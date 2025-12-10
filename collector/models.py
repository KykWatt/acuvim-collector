# collector/models.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class MeterConfig:
    id: int
    serial_number: str
    ip_address: str
    unit_id: int
    baud_rate: Optional[int]
    model: Optional[str]
    site_name: Optional[str]
    enabled: bool
    last_collected: Optional[datetime]
    last_timesync: Optional[datetime]
    last_drift_seconds: Optional[int]
    created: Optional[datetime]
    updated: Optional[datetime]

    # Newly added columns:
    last_record_index: int          # REQUIRED
    output_folder: Optional[str]    # REQUIRED
