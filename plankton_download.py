import struct
import math
import matplotlib.pyplot as plt
import os
import pickle
import time

i2c_clock_speed = 200e3

try:
    os.environ["BLINKA_FT232H"] = "1" #set environment variable
    import board # pip install board
    import busio # pip install wheel, adafruit-circuitpython-busdevice
        # it may be necessary to use Zadig to force the device to use a libusb driver
except RuntimeError as e:
    print("Got Exception:\n>>\t%s" % e)
    print("Make sure the USB-I2C cable is plugged in...")
    exit()


def get_eeprom_i2c_address(data_addr, width7bit=True):
    return (0xA0 + ((data_addr >> 16) << 1)) >> int(width7bit)


def datapoint_is_valid(dp):
    if max(dp) == 0:
        return False
    b = struct.pack(datapoint_fmt, *dp)
    if b.count(0xAA) > datapoint_size / 2:
        return False
    if b.count(0xFF) > datapoint_size / 2:
        return False
    return True


def plot(dps, *, xkey, ykey):
    x = []
    y = []
    for d in dps:
        x.append(d[xkey])
        y.append(d[ykey])

    plt.plot(x, y)
    plt.xlabel(xkey)
    plt.ylabel(ykey)
    plt.show()

# Datapoint structure
# struct {
#   int16_t acc[3];
#   int16_t ang[3];
#   int16_t mag[3];
# }
datapoint_fmt = "<hhhhhhhhh"
datapoint_size = 18 # bytes
eeprom_size = 1 << 18

i2c = busio.I2C(board.SCL, board.SDA, i2c_clock_speed)
print("Testing bus...")
while not i2c.try_lock():
    time.sleep(1)
    print("...")
    # do nothing
print("Bus is free")

slaves = i2c.scan()
if len(slaves) == 0:
    print("Didn't find any slave devices...")
    exit()
else:
    ee_found = False
    for addr in slaves:
        print("Found slave at 0x%X" % (addr << 1))
        if addr == 0x50:
            ee_found = True
    print("Found %d slave devices" % len(slaves))
    if not ee_found:
        print("EEPROM is not responding...")
        exit()

print("Reading data into buffer...")
data_ba = bytearray(eeprom_size)
addr = 0
addr_ba = int(addr & 0xFFFF).to_bytes(2, "big")
i2c.writeto(get_eeprom_i2c_address(addr), addr_ba)

while True:
    try:
        inp = input("How many 256b pages do you want to read? [All] ")
        if inp == "":
            num_pages = eeprom_size >> 8
        else:
            num_pages = int(inp)
    except ValueError as e:
        print("Invalid input.")
        continue
    break

pages = range(num_pages)
for page in pages:
    if page % 100 == 0: 
        print("\t Page %d of %d" % (page + 1, len(pages)))
    i2c.readfrom_into(get_eeprom_i2c_address(addr), data_ba, start=page * 256, end=(1 + page) * 256)

i2c.unlock()

print("Unpacking metadata")
meta_size = 4
meta_fmt = "BBBB"
meta = struct.unpack_from(meta_fmt, data_ba)
sample_frequency = meta[0]

X_fullscale_g = 0
if meta[1] == 0:
    X_fullscale_g = 2.0
elif meta[1] == 1:
    X_fullscale_g = 16.0
elif meta[1] == 2:
    X_fullscale_g = 4.0
elif meta[1] == 3:
    X_fullscale_g = 8.0

G_fullscale_dps = 0
if meta[2] == 0:
    G_fullscale_dps = 245.0
elif meta[2] == 1:
    G_fullscale_dps = 500.0
elif meta[2] == 2:
    throw: ValueError()
elif meta[2] == 3:
    G_fullscale_dps = 2000

M_fullscale_Ga = 0
if meta[3] == 0:
    M_fullscale_Ga = 4.0
elif meta[3] == 1:
    M_fullscale_Ga = 8.0
elif meta[3] == 2:
    M_fullscale_Ga = 12.0
elif meta[3] == 3:
    M_fullscale_Ga = 16.0

X_resolution_g = X_fullscale_g / (1 << 15)
G_resolution_dps = G_fullscale_dps / (1 << 15)
M_resolution_Ga = M_fullscale_Ga / (1 << 15)

print("Sample Frequency: %d Hz" % sample_frequency)
print("Accelerometer Resolution: %0.4f g / lsb" % X_resolution_g)
print("Gyroscope Resolution: %0.2f dps / lsb" % G_resolution_dps)
print("Magnetometer Resolution: %0.4f Ga / lsb" % M_resolution_Ga)
metadata = {
    'Frequency_Hz' : sample_frequency,
    'X_resolution_g': X_resolution_g,
    'G_resolution_dps': G_resolution_dps,
    'M_resolution_Ga': M_resolution_Ga,
}

data = {
    'Meta': metadata,
    'Data': []
}

print("Unpacking data points")
print("T\txX\txY\txZ\tgX\tgY\tgZ\tmX\tmY\tmZ")
read_p = meta_size
t = 0
while read_p <= len(data_ba)-datapoint_size:
    datapoint = struct.unpack_from(datapoint_fmt, data_ba, read_p)
    if datapoint_is_valid(datapoint):
        read_p += datapoint_size
        t += 1
        if (t % 100 == 1) or (t == 14563):
            print(("%d" % t) + ("\t%d"*9 % datapoint))
        dp = {
            'T_s': t / sample_frequency,
            'X_x_g': datapoint[0] * X_resolution_g,
            'X_y_g': datapoint[1] * X_resolution_g,
            'X_z_g': datapoint[2] * X_resolution_g,
            'X_mag_g': math.sqrt(
                math.pow(datapoint[0], 2) +
                math.pow(datapoint[1], 2) +
                math.pow(datapoint[2], 2)) * X_resolution_g,
            'G_x_dps': datapoint[3] * G_resolution_dps,
            'G_y_dps': datapoint[4] * G_resolution_dps,
            'G_z_dps': datapoint[5] * G_resolution_dps,
            'G_mag_dps': math.sqrt(
                math.pow(datapoint[3], 2) +
                math.pow(datapoint[4], 2) +
                math.pow(datapoint[5], 2)) * G_resolution_dps,
            'M_x_Ga': datapoint[6] * M_resolution_Ga,
            'M_y_Ga': datapoint[7] * M_resolution_Ga,
            'M_z_Ga': datapoint[8] * M_resolution_Ga,
            'M_mag_Ga': math.sqrt(
                math.pow(datapoint[6], 2) +
                math.pow(datapoint[7], 2) +
                math.pow(datapoint[8], 2)) * M_resolution_Ga
        }

        if dp['X_mag_g'] != 0:
            dp['X_dir'] = (
                dp['X_x_g']/dp['X_mag_g'],
                dp['X_y_g']/dp['X_mag_g'],
                dp['X_z_g']/dp['X_mag_g'])
        else:
            dp['X_dir'] = (0, 0, 0)

        if dp['G_mag_dps'] != 0:
            dp['G_dir'] = (
                dp['G_x_dps']/dp['G_mag_dps'],
                dp['G_y_dps']/dp['G_mag_dps'],
                dp['G_z_dps']/dp['G_mag_dps'])
        else:
            dp['G_dir'] = (0, 0, 0)

        if dp['M_mag_Ga'] != 0:
            dp['M_dir'] = (
                dp['M_x_Ga']/dp['M_mag_Ga'],
                dp['M_y_Ga']/dp['M_mag_Ga'],
                dp['M_z_Ga']/dp['M_mag_Ga'])
        else:
            dp['M_dir'] = (0, 0, 0)

        data['Data'].append(dp)
    else:
        print(("Invalid Datapoint:\n\t%X" % data_ba[read_p])
              + "".join("-%X" % b for b in data_ba[read_p+1:read_p+datapoint_size]))
        break

print("Datapoints: %d" % len(data['Data']))
plot(data['Data'], xkey='T_s', ykey='X_mag_g')

# file name dialog
while True:
    try:
        filename = input("Enter a file to save the data to: ")
        if len(filename.split("/")) > 1:
            os.mkdir(filename.split("/")[0])
        file = open(filename, "wb")

        # pickle data to file
        print("Saving to file: %s" % filename)
        pickle.dump(data, file)
        file.close()
    except KeyboardInterrupt:
        print("Data not saved")
    except Exception:
        print("Something went wrong. Try again.")
        continue
    break

