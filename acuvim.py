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
    kwh_import: float
    kwh_export: float
    kvarh_import: float
    kvarh_export: float
    crc: int                  # raw CRC / trailing word


class AcuvimClient:
    """
    High-level helper for Acuvim CL historical log retrieval
    using the "window" mechanism on 0x6000..0x6004.
    """

    def __init__(self, host: str, port: int = 502, unit: int = 1, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.unit = unit
        self.timeout = timeout

        self._client = ModbusTcpClient(self.host, port=self.port, timeout=self.timeout)
        # pymodbus 3.11.x uses unit_id / device_id attributes
        self._client.unit_id = self.unit
        if hasattr(self._client, "device_id"):
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

    def _program_window(self, offset: int, records_per_window: int) -> None:
        """
        Configure the "window" for historical log retrieval:

          6000: log type (0 = Historical Log 1)
          6001: hi = records_per_window, lo = status (0)
          6002: offset_hi
          6003: offset_lo

        After this, the meter fills 6004.. with the requested records.
        """
        if records_per_window <= 0:
            records_per_window = 1
        if records_per_window > 255:
            records_per_window = 255

        log_type = 0x0000  # Historical Log 1
        rec_hi = (records_per_window & 0xFF) << 8
        val_6001 = rec_hi | 0x00

        offset_hi = (offset >> 16) & 0xFFFF
        offset_lo = offset & 0xFFFF

        values = [log_type, val_6001, offset_hi, offset_lo]

        rq = self._client.write_registers(address=REG_LOG_TYPE, values=values)
        self._log(
            f"Wrote 6000..6003 = {[f'0x{v:04X}' for v in values]} -> {rq}"
        )
        if rq.isError():
            raise RuntimeError(f"Window write error at 0x{REG_LOG_TYPE:04X}: {rq}")

    def _wait_ready(self, timeout_sec: float = 5.0) -> None:
        """
        Poll 6001 until low byte == 0x0B (READY), or timeout.
        """
        deadline = time.time() + timeout_sec

        while True:
            rr = self._client.read_holding_registers(address=REG_REC_NUM_STATUS, count=1)
            if rr.isError():
                raise RuntimeError(f"Read error at 0x{REG_REC_NUM_STATUS:04X}: {rr}")

            val = rr.registers[0]
            recs_hi = (val >> 8) & 0xFF
            status = val & 0x00FF

            self._log(f"6001 = 0x{val:04X} (recs={recs_hi}, status=0x{status:02X})")

            if status == 0x0B:
                self._log("Window READY (status=0x0B).")
                return

            if time.time() > deadline:
                raise TimeoutError(
                    f"Timeout waiting for ready; 6001=0x{val:04X} (status=0x{status:02X})"
                )

            time.sleep(0.2)

    def _read_window_data(self, records_per_window: int) -> List[int]:
        """
        Read raw data from 6004.. for the given number of records.
        Returns a flat list of 16-bit words.
        """
        total_record_words = records_per_window * RECORD_SIZE_WORDS
        count = min(WINDOW_MAX_WORDS, total_record_words)

        rr = self._client.read_holding_registers(address=REG_WINDOW, count=count)
        if rr.isError():
            raise RuntimeError(f"Error reading window from 0x{REG_WINDOW:04X}: {rr}")

        regs = rr.registers
        self._log(
            f"Read {len(regs)} words starting at 0x{REG_WINDOW:04X}: "
            + " ".join(f"{w:04X}" for w in regs)
        )
        return regs

    # ------------- record parsing -------------

    @staticmethod
    def _parse_timestamp(w2: int, w3: int, w4: int) -> datetime:
        """
        Decode timestamp from words as plain hex-decimal bytes (NOT BCD):
          w2: YYMM
          w3: DDHH
          w4: MMSS
        """
        yy = (w2 >> 8) & 0xFF
        mm = w2 & 0xFF
        dd = (w3 >> 8) & 0xFF
        hh = w3 & 0xFF
        minute = (w4 >> 8) & 0xFF
        sec = w4 & 0xFF

        year = 2000 + yy
        return datetime(year, mm, dd, hh, minute, sec)

    @staticmethod
    def _parse_record(words: List[int]) -> AcuvimRecord:
        """
        Parse a single 14-word record according to the confirmed
        Acuvim CL layout (4 accumulators).
        """
        if len(words) != RECORD_SIZE_WORDS:
            raise ValueError(f"Expected {RECORD_SIZE_WORDS} words, got {len(words)}")

        idx_hi = words[0]
        idx_lo = words[1]
        idx_combined = (idx_hi << 16) | idx_lo
        seq = idx_lo  # convenient low 16 bits

        ts = AcuvimClient._parse_timestamp(words[2], words[3], words[4])

        # 4 x 32-bit signed accumulators (kWh/kVARh)
        kwh_imp_raw = _decode_s32(words[5], words[6])
        kwh_exp_raw = _decode_s32(words[7], words[8])
        kvarh_imp_raw = _decode_s32(words[9], words[10])
        kvarh_exp_raw = _decode_s32(words[11], words[12])

        # Apply scaling (see ENERGY_SCALE_KWH)
        kwh_imp = kwh_imp_raw * ENERGY_SCALE_KWH
        kwh_exp = kwh_exp_raw * ENERGY_SCALE_KWH
        kvarh_imp = kvarh_imp_raw * ENERGY_SCALE_KWH
        kvarh_exp = kvarh_exp_raw * ENERGY_SCALE_KWH

        crc = words[13]

        return AcuvimRecord(
            index=idx_combined,
            seq=seq,
            timestamp=ts,
            kwh_import=kwh_imp,
            kwh_export=kwh_exp,
            kvarh_import=kvarh_imp,
            kvarh_export=kvarh_exp,
            crc=crc,
        )

    # ------------- high-level retrieval -------------

    def latch_log(self) -> None:
        """
        Placeholder for compatibility with non-CL devices.
        For CL "window" mode this is a no-op.
        """
        self._log("latch_log(): no-op for CL window mode.")

    def read_records_range(
        self,
        offset: int,
        count: int,
        records_per_window: int = MAX_RECORDS_PER_WINDOW,
    ) -> List[AcuvimRecord]:
        """
        Read 'count' historical records starting at 'offset' (0 = oldest)
        using the window mechanism, chunked into windows of up to
        records_per_window (max 8).

        Returns records in chronological order.
        """
        if count <= 0:
            return []

        if records_per_window <= 0 or records_per_window > MAX_RECORDS_PER_WINDOW:
            records_per_window = MAX_RECORDS_PER_WINDOW

        records: List[AcuvimRecord] = []

        remaining = count
        current_offset = offset

        while remaining > 0:
            chunk = min(records_per_window, remaining)

            self._log(
                f"Reading window: offset={current_offset}, records={chunk}"
            )

            # 1) program window for this chunk
            self._program_window(offset=current_offset, records_per_window=chunk)

            # 2) wait for READY
            self._wait_ready()

            # 3) read raw window data and parse records
            raw_words = self._read_window_data(records_per_window=chunk)

            if len(raw_words) < chunk * RECORD_SIZE_WORDS:
                raise RuntimeError(
                    f"Meter returned too few words: got {len(raw_words)}, "
                    f"expected at least {chunk * RECORD_SIZE_WORDS}"
                )

            for i in range(chunk):
                start = i * RECORD_SIZE_WORDS
                end = start + RECORD_SIZE_WORDS
                rec_words = raw_words[start:end]
                rec = self._parse_record(rec_words)
                records.append(rec)

            current_offset += chunk
            remaining -= chunk

        return records
