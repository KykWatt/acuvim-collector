# collector/time_sync_integration.py

from pymodbus.client import ModbusTcpClient
import datetime as dt
import os

YEAR_REG = 0x1040
MONTH_REG = 0x1041
DAY_REG = 0x1042
HOUR_REG = 0x1043
MIN_REG = 0x1044
SEC_REG = 0x1045
TIME_REG_BASE = YEAR_REG

SECONDS_ALLOWED_DRIFT = 60   # 1-minute tolerance


def log(msg: str):
    ts = dt.datetime.now().isoformat(timespec="seconds")
    entry = f"[{ts}] {msg}"
    print(entry)

    os.makedirs("./diagnostics", exist_ok=True)
    with open("./diagnostics/time_sync.log", "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def read_meter_time(client: ModbusTcpClient):
    """Reads the timestamp registers using positional arguments only."""

    rr = client.read_holding_registers(TIME_REG_BASE, count=6)
    if not rr or rr.isError():
        raise RuntimeError("Failed to read meter time")

    year, month, day, hour, minute, second = rr.registers
    return dt.datetime(year, month, day, hour, minute, second)


def write_meter_time(client: ModbusTcpClient, new_time: dt.datetime):
    """Writes timestamp to meter registers."""

    regs = [
        new_time.year,
        new_time.month,
        new_time.day,
        new_time.hour,
        new_time.minute,
        new_time.second,
    ]

    res = client.write_registers(TIME_REG_BASE, regs)
    if not res or res.isError():
        raise RuntimeError("Failed to write meter time")


def perform_time_sync_if_needed(client: ModbusTcpClient):
    """Compares meter time vs system time; sync if required."""
    log("Reading meter time for sync check...")

    meter_time = read_meter_time(client)
    system_time = dt.datetime.now().replace(microsecond=0)

    drift = abs((system_time - meter_time).total_seconds())
    log(f"Meter time = {meter_time}, System = {system_time}, Drift = {drift:.1f}s")

    if drift > SECONDS_ALLOWED_DRIFT:
        log("Drift too large → performing time sync...")
        write_meter_time(client, system_time)
        log("Meter clock updated.")
        return system_time, drift

    log("Clock drift within tolerance.")
    return None, drift
