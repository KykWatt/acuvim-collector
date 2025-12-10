# parser.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from utils import decode_log_timestamp


# Each log record is 14 words (28 bytes) as confirmed:
#   w0-w1  : record number (u32)
#   w2-w4  : timestamp (3 words)
#   w5-w6  : Ep_Imp  (u32, energy)
#   w7-w8  : Ep_Exp  (u32, energy)
#   w9-w10 : Eq_Imp  (u32, energy)
#   w11-w12: Eq_Exp  (u32, energy)
#   w13    : CRC (ignored for now)

def _read_u32(words: List[int]) -> int:
    if len(words) != 2:
        raise ValueError(f"Need exactly 2 words for u32, got {len(words)}")
    return (words[0] << 16) | words[1]


def _scale_energy(raw: int) -> float:
    """
    Scale raw 32-bit energy counter to kWh / kvarh.

    From your previous work & manuals:
      - Energy counters are typically in 0.1 units (primary_0_1 mode).
      - If that ever changes, we can add a config flag later.
    """
    return raw / 10.0


@dataclass
class AcuvimRecord:
    record_number: int
    timestamp: datetime
    ep_imp_kwh: float
    ep_exp_kwh: float
    eq_imp_kvarh: float
    eq_exp_kvarh: float

    def to_row(self, device_serial: str) -> dict:
        """
        Convert to a flat dict suitable for CSV writing.
        """
        return {
            "device_serial": device_serial,
            "record_number": self.record_number,
            "timestamp": self.timestamp.isoformat(sep=" "),
            "ep_imp_kwh": self.ep_imp_kwh,
            "ep_exp_kwh": self.ep_exp_kwh,
            "eq_imp_kvarh": self.eq_imp_kvarh,
            "eq_exp_kvarh": self.eq_exp_kvarh,
        }


def parse_acuvim_record(words: List[int]) -> AcuvimRecord:
    """
    Parse ONE 14-word Acuvim CL historical log record.

    Layout (confirmed from your debug dump):

      [0]  rec_hi
      [1]  rec_lo
      [2]  ts_word0
      [3]  ts_word1
      [4]  ts_word2
      [5]  Ep_Imp_hi
      [6]  Ep_Imp_lo
      [7]  Ep_Exp_hi
      [8]  Ep_Exp_lo
      [9]  Eq_Imp_hi
      [10] Eq_Imp_lo
      [11] Eq_Exp_hi
      [12] Eq_Exp_lo
      [13] CRC (ignored)

    Example from your meter (oldest record):

      0000 0001  190C 0512 1800  0005 9FA1  0001 84CE  0000 0021  0008 08C1  C60D
    """
    if len(words) != 14:
        raise ValueError(f"Expected 14 words for one record, got {len(words)}")

    # Record number
    rec_num = _read_u32(words[0:2])

    # Timestamp
    ts_words = words[2:5]
    ts = decode_log_timestamp(ts_words)

    # Energies
    ep_imp_raw = _read_u32(words[5:7])
    ep_exp_raw = _read_u32(words[7:9])
    eq_imp_raw = _read_u32(words[9:11])
    eq_exp_raw = _read_u32(words[11:13])

    ep_imp = _scale_energy(ep_imp_raw)
    ep_exp = _scale_energy(ep_exp_raw)
    eq_imp = _scale_energy(eq_imp_raw)
    eq_exp = _scale_energy(eq_exp_raw)

    return AcuvimRecord(
        record_number=rec_num,
        timestamp=ts,
        ep_imp_kwh=ep_imp,
        ep_exp_kwh=ep_exp,
        eq_imp_kvarh=eq_imp,
        eq_exp_kvarh=eq_exp,
    )
