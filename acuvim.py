diff - -git
a / acuvim.py
b / acuvim.py
index
e206ae44075a6fd82b8fa7dce782afd954da932d.
.87
d962b5c088a29c49843b9c4fa74f6b0c870e19
100644
--- a / acuvim.py
+++ b / acuvim.py


@ @-29

, 6 + 29, 15 @ @ RECORD_INTERVAL_MINUTES = 1
# Raw accumulators are in "0.1 kWh / 0.1 kVARh" units (100x bigger than before).
ENERGY_SCALE_KWH = 0.1  # 1 LSB = 0.1 kWh / 0.1 kVARh

+  # Time registers (Table 6-17)
+YEAR_REG = 0x1040
+MONTH_REG = 0x1041
+DAY_REG = 0x1042
+HOUR_REG = 0x1043
+MIN_REG = 0x1044
+SEC_REG = 0x1045
+TIME_REG_BASE = YEAR_REG
+


def _decode_s32(hi: int, lo: int) -> int:
    """Decode signed 32-bit big-endian from hi/lo 16-bit words."""


@ @-117

, 6 + 126, 41 @ @


class AcuvimClient:
    ts = datetime.now().isoformat(timespec="seconds")
    print(f"[{ts}] {msg}")


+  # ------------- time operations -------------
+
+


def read_meter_time(self) -> datetime:
    +        """
+        Read the meter's date/time from registers 0x1040..0x1045.
+        Returns a datetime constructed from the raw values.
+        """


+        rr = self._client.read_holding_registers(address=TIME_REG_BASE, count=6)
+
if rr.isError():
    +
    raise RuntimeError(f"Time read error at 0x{TIME_REG_BASE:04X}: {rr}")
+
+        year, month, day, hour, minute, second = rr.registers
+
+
try:
    +
    return datetime(year, month, day, hour, minute, second)
+        except Exception as e:  # pragma: no cover - defensive
+
raise RuntimeError(
    +                f"Invalid timestamp from meter: {rr.registers} ({e})"
    +) from e
+
+


def write_meter_time(self, new_time: datetime) -> None:
    +        """Write a datetime into registers 0x1040..0x1045."""


+        regs = [
    +            new_time.year,
    +            new_time.month,
    +            new_time.day,
    +            new_time.hour,
    +            new_time.minute,
    +            new_time.second,
    +]
+
+        rq = self._client.write_registers(address=TIME_REG_BASE, values=regs)
+
if rq.isError():
    +
    raise RuntimeError(f"Time write error at 0x{TIME_REG_BASE:04X}: {rq}")
+


# ------------- core Modbus operations -------------

def read_log_status(self) -> LogStatus:
