# collector/process_meter.py
#
# High-level per-meter logic:
#   1) Read log status (0x6100 block)
#   2) Read the latest log window (0x6004)
#   3) Decode records via log_parser.retrieve_records(...)
#   4) Infer global indices for that window from "used records"
#   5) Filter out records already processed (based on last_record_index)
#   6) Write new records to CSV
#   7) Update DB pointer (last_record_index) and timestamps

from datetime import datetime
import os
from typing import Tuple

from pymodbus.client import ModbusTcpClient

from .db import update_meter_pointer
from .log_parser import retrieve_records

# ------------------------------
# Modbus constants
# ------------------------------
LOG_STATUS_BASE = 0x6100
REG_OFFSET_HI = 0x6002
REG_OFFSET_LO = 0x6003
REG_WINDOW = 0x6004

RECORD_SIZE_WORDS = 14
WINDOW_MAX_WORDS = 123
MAX_RECORDS_PER_WINDOW = WINDOW_MAX_WORDS // RECORD_SIZE_WORDS  # 8


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


# ------------------------------------------------------------
# Read log status block (0x6100..)
# ------------------------------------------------------------

def read_log_status(client: ModbusTcpClient, unit_id: int) -> Tuple[int, int, int]:
    """
    Read the status block at 0x6100 and return:
        (max_records, used_records, record_size_bytes)

    Based on your scan_log_status.py output:
        0x6100 : log_type         (2)
        0x6101 : max_records      (187200)
        0x6102 : reserved/0
        0x6103 : used_records     (grows with new entries)
        0x6104 : record_size      (28 bytes)
        0x6105 : 0
        0x6106..6108 : first record timestamp
        0x6109..6111 : last record timestamp (not read in our 10-word scan)
    """
    res = client.read_holding_registers(
        address=LOG_STATUS_BASE,
        count=10,
        device_id=unit_id,
    )
    if not res or res.isError():
        raise RuntimeError("Failed to read LOG_STATUS_BASE (0x6100)")

    regs = res.registers
    log_type = regs[0]
    max_records = regs[1]
    used_records = regs[3]
    record_size = regs[4]

    log(f"[DEBUG] read_log_status: log_type={log_type}, "
        f"max_records={max_records}, used_records={used_records}, "
        f"record_size_bytes={record_size}")

    if record_size != 28:
        log(f"[WARN] Unexpected record_size={record_size} (expected 28)")

    return max_records, used_records, record_size


# ------------------------------------------------------------
# Read one window from REG_WINDOW (0x6004)
# ------------------------------------------------------------

def read_window(client: ModbusTcpClient, unit_id: int, offset_words: int) -> list[int]:
    """
    Read a raw window (up to 123 words) from the log.

    We assume:
        - 0x6002 = offset_hi, 0x6003 = offset_lo
        - 0x6004 returns a block of up to 123 words starting at that offset.
    """
    hi = (offset_words >> 16) & 0xFFFF
    lo = offset_words & 0xFFFF

    log(f"[DEBUG] read_window: offset_words={offset_words} (hi=0x{hi:04X}, lo=0x{lo:04X})")

    # Set offset
    w1 = client.write_register(address=REG_OFFSET_HI, value=hi, device_id=unit_id)
    w2 = client.write_register(address=REG_OFFSET_LO, value=lo, device_id=unit_id)
    if (not w1 or w1.isError()) or (not w2 or w2.isError()):
        raise RuntimeError("Failed to write window offset (6002/6003)")

    # Read the window
    res = client.read_holding_registers(
        address=REG_WINDOW,
        count=WINDOW_MAX_WORDS,
        device_id=unit_id,
    )
    if not res or res.isError():
        raise RuntimeError("Failed to read window data from 0x6004")

    regs = res.registers
    log(f"[DEBUG] read_window: got {len(regs)} words, "
        f"first 20 = {' '.join(f'{w:04X}' for w in regs[:20])}")
    return regs


# ------------------------------------------------------------
# Main per-meter logic
# ------------------------------------------------------------

def process_meter(meter, conn):
    """
    High-level per-meter processing:
        - Reads the latest log window,
        - decodes up to 8 records,
        - filters by meter.last_record_index,
        - writes any *new* records to CSV,
        - updates last_record_index in the DB.

    last_record_index is treated as:
        "the NEXT global record index to process".
    So on first run it will be 0, and we treat all records in the window
    as new; after processing index N-1 we store last_record_index = N.
    """
    log(f"Processing {meter.serial_number}...")

    client = ModbusTcpClient(meter.ip_address, port=502, timeout=3.0)
    if not client.connect():
        raise RuntimeError(f"Cannot connect to {meter.serial_number} at {meter.ip_address}")

    try:
        # 1) Read log status
        _, used_records, record_size = read_log_status(client, meter.unit_id)

        if used_records == 0:
            log("[INFO] Log is empty (used_records=0). Nothing to do.")
            return None

        # Pointer semantics: this is "next index to process"
        next_index = meter.last_record_index or 0
        log(f"[DEBUG] DB pointer last_record_index (next index) = {next_index}")

        # We'll read ONLY the latest window (last up to 8 records).
        # These correspond to global indices:
        #   first_idx = used_records - window_size
        #   last_idx  = used_records - 1
        #
        # That is exactly what Acuview shows as the "last N records".
        window_size = min(MAX_RECORDS_PER_WINDOW, used_records)
        first_idx = used_records - window_size
        last_idx = used_records - 1

        log(f"[DEBUG] Window indices: first_idx={first_idx}, last_idx={last_idx}, "
            f"window_size={window_size}")

        # 2) Read that window
        offset_words = first_idx * RECORD_SIZE_WORDS
        raw_window = read_window(client, meter.unit_id, offset_words)

        # 3) Decode records from the window
        decoded = retrieve_records(raw_window)
        if not decoded:
            log("[DEBUG] Decoded 0 records from window – nothing to write.")
            return None

        # 4) Attach indices and filter on pointer
        new_records = []
        for i, rec in enumerate(decoded):
            global_index = first_idx + i  # 0-based index within the full log

            if global_index < next_index:
                # Already processed – skip
                continue

            # Add index + seq (for now seq == index; we can refine later if needed)
            rec_with_idx = {
                "index": global_index,
                "seq": global_index,
                **rec,
            }
            new_records.append(rec_with_idx)

        log(f"[DEBUG] New records in this window after pointer filter: "
            f"{len(new_records)}")

        if not new_records:
            log("No new records since last_record_index pointer.")
            return None

        # 5) Ensure output folder exists
        output_folder = meter.output_folder or "./data"
        os.makedirs(output_folder, exist_ok=True)

        # 6) Build CSV path
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(output_folder, f"{meter.serial_number}_{ts}.csv")

        # 7) Write CSV with your preferred columns
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("serial,index,seq,timestamp,kwh_import,kwh_export,kvarh_import,kvarh_export\n")
            for rec in new_records:
                f.write(
                    f"{meter.serial_number},"
                    f"{rec['index']},"
                    f"{rec['seq']},"
                    f"{rec['timestamp']},"
                    f"{rec['kwh_import']},"
                    f"{rec['kwh_export']},"
                    f"{rec['kvarh_import']},"
                    f"{rec['kvarh_export']}\n"
                )

        log(f"CSV written: {csv_path}")

        # 8) Update DB pointer:
        #     we have now processed everything up to used_records-1,
        #     so the NEXT index to process is used_records.
        new_pointer = used_records
        update_meter_pointer(conn, meter.id, new_pointer, datetime.now())
        log(f"[DEBUG] Updated DB last_record_index -> {new_pointer}")

        return csv_path

    finally:
        client.close()
