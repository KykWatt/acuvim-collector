# acuvim_debug.py
#
# Minimal Modbus debug helper for Acuvim CL log window.
# Does NOT touch your main collector code.

from __future__ import annotations

import argparse
import time
from datetime import datetime

from pymodbus.client import ModbusTcpClient

LOG_STATUS_BASE = 0x6100  # status block
REG_LOG_TYPE = 0x6000     # 6000
REG_REC_NUM_STATUS = 0x6001
REG_OFFSET_HI = 0x6002
REG_OFFSET_LO = 0x6003
REG_WINDOW = 0x6004       # window data base

RECORD_SIZE_WORDS = 14    # 28 bytes / 2
WINDOW_MAX_WORDS = 123    # from manual


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}")


def read_status(client: ModbusTcpClient) -> None:
    rr = client.read_holding_registers(address=LOG_STATUS_BASE, count=5)
    if rr.isError():
        raise RuntimeError(f"Status read error at 0x{LOG_STATUS_BASE:04X}: {rr}")

    regs = rr.registers
    max_records = (regs[0] << 16) | regs[1]
    used_records = (regs[2] << 16) | regs[3]
    record_size = regs[4]

    log(f"Log status: max={max_records}, used={used_records}, recordSize={record_size}B")


def program_window(client: ModbusTcpClient, offset: int, records_per_window: int) -> None:
    """
    Program the log window exactly like AcuView2 style:

      6000: log type (0 = Data Log 1)
      6001: hi = records_per_window, lo = status (0)
      6002: offset_hi
      6003: offset_lo
    """
    if records_per_window <= 0:
        records_per_window = 1
    if records_per_window > 255:
        records_per_window = 255

    value_6000 = 0x0000  # Historical Log 1
    rec_hi = (records_per_window & 0xFF) << 8
    value_6001 = rec_hi | 0x00

    offset_hi = (offset >> 16) & 0xFFFF
    offset_lo = offset & 0xFFFF

    values = [value_6000, value_6001, offset_hi, offset_lo]
    rq = client.write_registers(address=REG_LOG_TYPE, values=values)
    log(f"Wrote 6000..6003 = {[f'0x{v:04X}' for v in values]} -> {rq}")
    if rq.isError():
        raise RuntimeError(f"Window write error at 0x{REG_LOG_TYPE:04X}: {rq}")


def wait_ready(client: ModbusTcpClient, timeout_sec: float = 5.0) -> None:
    """
    Poll 6001 until low byte == 0x0B (READY), or timeout.
    """
    deadline = time.time() + timeout_sec

    while True:
        rr = client.read_holding_registers(address=REG_REC_NUM_STATUS, count=1)
        if rr.isError():
            raise RuntimeError(f"Read error at 0x{REG_REC_NUM_STATUS:04X}: {rr}")

        val = rr.registers[0]
        recs_hi = (val >> 8) & 0xFF
        status = val & 0x00FF
        log(f"6001 = 0x{val:04X} (recs={recs_hi}, status=0x{status:02X})")

        if status == 0x0B:
            log("Window READY (status=0x0B).")
            return

        if time.time() > deadline:
            raise TimeoutError(
                f"Timeout waiting for ready; 6001=0x{val:04X} (status=0x{status:02X})"
            )

        time.sleep(0.2)


def read_window_views(client: ModbusTcpClient, records_per_window: int) -> None:
    """
    Read the window in two ways so we see how the CL actually presents data:
      1) From 6001 (header+offset+data)
      2) From 6004 (just data)
    """
    total_record_words = records_per_window * RECORD_SIZE_WORDS
    # Heuristic: header (3 words) + data
    words_from_6001 = min(WINDOW_MAX_WORDS, 3 + total_record_words)
    words_from_6004 = min(WINDOW_MAX_WORDS, total_record_words)

    # 1) Read from 6001
    rr1 = client.read_holding_registers(address=REG_REC_NUM_STATUS, count=words_from_6001)
    if rr1.isError():
        raise RuntimeError(f"Error reading window from 0x{REG_REC_NUM_STATUS:04X}: {rr1}")
    regs1 = rr1.registers
    log(f"Read {len(regs1)} words starting at 0x6001:")
    log("  " + " ".join(f"{w:04X}" for w in regs1))

    # 2) Read from 6004
    rr2 = client.read_holding_registers(address=REG_WINDOW, count=words_from_6004)
    if rr2.isError():
        raise RuntimeError(f"Error reading window from 0x{REG_WINDOW:04X}: {rr2}")
    regs2 = rr2.registers
    log(f"Read {len(regs2)} words starting at 0x6004:")
    log("  " + " ".join(f"{w:04X}" for w in regs2))


def main():
    parser = argparse.ArgumentParser(description="Acuvim CL log-window debug helper")
    parser.add_argument("--host", required=True, help="Meter IP")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port")
    parser.add_argument("--unit", type=int, default=1, help="Unit/device id")
    parser.add_argument("--offset", type=int, default=0, help="Record offset (0 = oldest)")
    parser.add_argument("--records", type=int, default=1, help="Records per window (1..8 suggested)")
    args = parser.parse_args()

    client = ModbusTcpClient(args.host, port=args.port, timeout=3.0)

    # pymodbus 3.11.x: set unit_id / device_id
    client.unit_id = args.unit
    if hasattr(client, "device_id"):
        client.device_id = args.unit

    log(f"Connecting to {args.host}:{args.port} (unit {args.unit})...")
    if not client.connect():
        log("ERROR: Could not connect.")
        return
    log("Connected.")

    try:
        # 1) show status
        read_status(client)

        # 2) program window
        program_window(client, offset=args.offset, records_per_window=args.records)

        # 3) wait ready
        wait_ready(client)

        # 4) read window two ways
        read_window_views(client, records_per_window=args.records)

    finally:
        client.close()
        log("Disconnected.")


if __name__ == "__main__":
    main()
