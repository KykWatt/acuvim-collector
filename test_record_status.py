from pymodbus.client import ModbusTcpClient

REG_LOG_TYPE = 0x6000
REG_REC_NUM_STATUS = 0x6001
REG_OFFSET_HI = 0x6002
REG_OFFSET_LO = 0x6003
LOG_STATUS_BASE = 0x6100

client = ModbusTcpClient("192.168.68.43", timeout=3)

if not client.connect():
    print("Cannot connect")
    exit()

# Read log status
res = client.read_holding_registers(address=LOG_STATUS_BASE, count=4, device_id=1)

if res.isError():
    print("Error:", res)
else:
    max_records = (res.registers[0] << 16) | res.registers[1]
    used_records = (res.registers[2] << 16) | res.registers[3]
    print("Max records :", max_records)
    print("Used records:", used_records)

client.close()
