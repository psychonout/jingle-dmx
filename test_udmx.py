import usb.core

dev = usb.core.find(idVendor=0x16c0, idProduct=0x05dc)

if dev is None:
    print("Device not found")
else:
    print("uDMX device attached successfully!")
