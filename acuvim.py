from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List

from pymodbus.client import ModbusTcpClient

# -----------------------------
# Modbus register map constants
# -----------------------------

LOG_STATUS_BASE = 0x6100  # 6100..6104: status block
REG_LOG_TYPE = 0x6000     # 6000: log type
REG_REC_NUM_STATUS = 0x6001
REG_OFFSET_HI = 0x6002
REG_OFFSET_LO = 0x6003
REG_WINDOW = 0x6004       # window data base (data only)

RECORD_SIZE_WORDS = 14     # 28 bytes / 2
WINDOW_MAX_WORDS = 123
MAX_RECORDS_PER_WINDOW = WINDOW_MAX_WORDS // RECORD_SIZE_WORDS  # = 8

RECORD_INTERVAL_MINUTES = 1

# Energy scaling:
# Raw accumulators are in "0.1 kWh / 0.1 kVARh" units (100x bigger than before).
ENERGY_SCALE_KWH = 0.1     # 1 LSB = 0.1 kWh / 0.1 kVARh

# Time registers (Table 6-17)
YEAR_REG = 0x1040
MONTH_REG = 0x1041
DAY_REG = 0x1042
HOUR_REG = 0x1043
MIN_REG = 0x1044
SEC_REG = 0x1045
TIME_REG_BASE = YEAR_REG


def _decode_s32(hi: int, lo: int) -> int:
    """Decode signed 32-bit big-endian from hi/lo 16-bit words."""
    val = (hi << 16) | (lo & 0xFFFF)
    if val & 0x8000_0000:
        val -= 0x1_0000_0000
    return val


@dataclass
class LogStatus:
    max_records: int
    used_records: int
    record_size_bytes: int

    # Backward compatibility: older callers referenced ``total_records``.
    @property
    def total_records(self) -> int:  # pragma: no cover - passthrough helper
        return self.max_records


@dataclass
class AcuvimRecord:
    """
    Single historical log record from the Acuvim CL.

    Layout (words, 14 total):
      0: index_hi
      1: index_lo
      2: YYMM (hex-decimal bytes)
      3: DDHH (hex-decimal bytes)
      4: MMSS (hex-decimal bytes)
      5: kWh_import_hi
      6: kWh_import_lo
      7: kWh_export_hi
      8: kWh_export_lo
      9: kVARh_import_hi
      10: kVARh_import_lo
      11: kVARh_export_hi
      12: kVARh_export_lo
      13: CRC / status
    """
    index: int                # combined index_hi/index_lo
    seq: int                  # low 16 bits
    timestamp: datetime
@@ -95,50 +109,85 @@ class AcuvimClient:
            self._client.device_id = self.unit

    # ------------- lifecycle -------------

    def connect(self) -> bool:
        return self._client.connect()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AcuvimClient":
        if not self.connect():
            raise RuntimeError(f"Could not connect to {self.host}:{self.port}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------- logging helpers -------------

    @staticmethod
    def _log(msg: str) -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        print(f"[{ts}] {msg}")

    # ------------- time operations -------------

    def read_meter_time(self) -> datetime:
        """
        Read the meter's date/time from registers 0x1040..0x1045.
        Returns a datetime constructed from the raw values.
        """
        rr = self._client.read_holding_registers(address=TIME_REG_BASE, count=6)
        if rr.isError():
            raise RuntimeError(f"Time read error at 0x{TIME_REG_BASE:04X}: {rr}")

        year, month, day, hour, minute, second = rr.registers

        try:
            return datetime(year, month, day, hour, minute, second)
        except Exception as e:  # pragma: no cover - defensive
            raise RuntimeError(
                f"Invalid timestamp from meter: {rr.registers} ({e})"
            ) from e

    def write_meter_time(self, new_time: datetime) -> None:
        """Write a datetime into registers 0x1040..0x1045."""
        regs = [
            new_time.year,
            new_time.month,
            new_time.day,
            new_time.hour,
            new_time.minute,
            new_time.second,
        ]

        rq = self._client.write_registers(address=TIME_REG_BASE, values=regs)
        if rq.isError():
            raise RuntimeError(f"Time write error at 0x{TIME_REG_BASE:04X}: {rq}")

    # ------------- core Modbus operations -------------

    def read_log_status(self) -> LogStatus:
        """
        Read 6100..6104 status block:
          6100: max_records_hi
          6101: max_records_lo
          6102: used_records_hi
          6103: used_records_lo
          6104: record_size_bytes
        """
        rr = self._client.read_holding_registers(address=LOG_STATUS_BASE, count=5)
        if rr.isError():
            raise RuntimeError(f"Status read error at 0x{LOG_STATUS_BASE:04X}: {rr}")

        regs = rr.registers
        max_records = (regs[0] << 16) | regs[1]
        used_records = (regs[2] << 16) | regs[3]
        record_size = regs[4]

        self._log(
            f"Log status: max={max_records}, used={used_records}, "
            f"recordSize={record_size}B"
        )
        return LogStatus(max_records=max_records, used_records=used_records, record_size_bytes=record_size)