import struct
import os
os.environ["BLINKA_FT232H"] = "1" #set environment variable

try:
    import board
    import busio
except RuntimeError as e:
    print("Got Exception:\n>>\t%s" % e)
    print("Make sure the USB-I2C cable is plugged in...")
    exit()


def get_eeprom_i2c_address(data_addr, width7bit=True):
    return (0xA0 + ((data_addr >> 16) << 1)) >> int(width7bit)


def datapoint_is_valid(dp):
    if max(dp) == 0:
        return False
    # b = struct.pack(datapoint_fmt, *dp)
    # if b.count(0xAA) == datapoint_size:
    #     return False
    # if b.count(0xFF) == datapoint_size:
    #     return False
    return True


# Datapoint structure
# struct {
#   uint16_t time;
#   int16_t acc[3];
#   int16_t ang[3];
#   int16_t mag[3];
# }
datapoint_fmt = "Hhhhhhhhhh"
datapoint_size = 20 # bytes
eeprom_size = 1 << 18

i2c = busio.I2C(board.SCL, board.SDA)
for addr in i2c.scan():
    print("Found slave at 0x%X" % (addr))

print("Reading data into buffer...")
ba = bytearray(eeprom_size)
# i2c.writeto_then_readfrom()
# ^^^^^^^^^^^^^^^^^^^^^^^^^^
# Use this to ensure we are reading from beginning of EEPROM
i2c.readfrom_into(get_eeprom_i2c_address(0), ba, start=0, end=100)

print("Unpacking data points")
print("T\txX\txY\txZ\tgX\tgY\tgZ\tmX\tmY\tmZ")
data = []
read_p = 0
while read_p <= len(ba)-datapoint_size:
    datapoint = struct.unpack_from(datapoint_fmt, ba, read_p)
    if datapoint_is_valid(datapoint):
        data.append(datapoint)
        read_p += datapoint_size
        print(("%d\t"*9 + "%d") % datapoint)
    else:
        print(("Invalid Datapoint: %X" % ba[read_p])
              + "".join("-%X" % b for b in ba[read_p+1:read_p+datapoint_size]))
        break

print("Datapoints: %d" % len(data))

