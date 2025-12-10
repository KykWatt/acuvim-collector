from pymodbus.client import ModbusTcpClient

LOG_STATUS_BASE = 0x6100
REG_LOG_TYPE = 0x6000
REG_REC_NUM_STATUS = 0x6001
REG_OFFSET_HI = 0x6002
REG_OFFSET_LO = 0x6003
REG_WINDOW = 0x6004

WINDOW_MAX_WORDS = 123
RECORD_SIZE_WORDS = 14

host = "192.168.68.43"
unit = 1
last_record_index = 0    # test baseline
offset_words = last_record_index * RECORD_SIZE_WORDS

client = ModbusTcpClient(host, port=502, timeout=3.0)
client.connect()

hi = (offset_words >> 16) & 0xFFFF
lo = offset_words & 0xFFFF

print("\nWriting offset registers...")
client.write_register(address=REG_OFFSET_HI, value=hi, device_id=unit)
client.write_register(address=REG_OFFSET_LO, value=lo, device_id=unit)

print("\nReading LOG_STATUS_BASE...")
s = client.read_holding_registers(address=LOG_STATUS_BASE, count=5, device_id=unit)
print("Status:", s.registers)

print("\nReading 6001 (HEADER + window)...")
w1 = client.read_holding_registers(address=REG_REC_NUM_STATUS, count=50, device_id=unit)
print("6001:", " ".join(f"{x:04X}" for x in w1.registers))

print("\nReading 6004 (DATA only)...")
w2 = client.read_holding_registers(address=REG_WINDOW, count=WINDOW_MAX_WORDS, device_id=unit)
print("6004:", " ".join(f"{x:04X}" for x in w2.registers))

client.close()
print("\nDone.")
