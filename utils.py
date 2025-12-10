# utils.py

from __future__ import annotations

from datetime import datetime
from typing import List


def log(msg: str) -> None:
    """
    Simple timestamped logger used across the project.
    """
    ts = datetime.now().isoformat(timespec="seconds")
    print(f"[{ts}] {msg}")


def decode_log_timestamp(words: List[int]) -> datetime:
    """
    Decode Acuvim CL historical log timestamp from 3 words.

    Confirmed mapping from Wireshark + debug runs:

      w0 = 0xYYMM  -> high byte = year offset from 2000, low byte = month
      w1 = 0xDDHH  -> high byte = day, low byte = hour
      w2 = 0xMMSS  -> high byte = minute, low byte = second

    Example from your meter:
      190C 0512 1800  ->  2025-12-05 18:24:00
      190C 0817 1000  ->  2025-12-08 23:16:00
    """
    if len(words) != 3:
        raise ValueError(f"Expected 3 words for timestamp, got {len(words)}")

    w0, w1, w2 = words

    year_off = (w0 >> 8) & 0xFF
    month = w0 & 0xFF

    day = (w1 >> 8) & 0xFF
    hour = w1 & 0xFF

    minute = (w2 >> 8) & 0xFF
    second = w2 & 0xFF

    year = 2000 + year_off

    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError as e:
        # Surface the raw words to help debugging if something is weird
        raise ValueError(
            f"Invalid timestamp from words: "
            f"[0x{w0:04X}, 0x{w1:04X}, 0x{w2:04X}] "
            f"-> year={year}, month={month}, day={day}, "
            f"hour={hour}, minute={minute}, second={second}"
        ) from e

def format_dt(dt_obj):
    """
    Formatting helper used by main.py
    """
    if dt_obj is None:
        return ""
    return dt_obj.isoformat(sep=" ", timespec="seconds")
