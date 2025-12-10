# scan_log_status.py
from pymodbus.client import ModbusTcpClient

IP = "192.168.68.43"
UNIT = 1

client = ModbusTcpClient(IP, port=502, timeout=3.0)
client.connect()

print("Reading register block 0x6100 – 0x6120 ...")

res = client.read_holding_registers(address=0x6100, count=10, device_id=UNIT)

if not res or res.isError():
    print("ERROR reading registers")
else:
    for i, val in enumerate(res.registers):
        print(f"{hex(0x6100 + i)} : {val} (0x{val:04X})")

client.close()
