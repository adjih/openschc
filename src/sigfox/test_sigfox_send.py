# Code to run on a LoPy/FiPy to send a packet:
#
# You can run this code with something like:
#   ampy -p /dev/ttyACM0 run test_sigfox_send.py
#
# Mostly from: https://docs.pycom.io/firmwareapi/pycom/network/sigfox.html

from network import Sigfox
import socket
import ubinascii

# init Sigfox for RCZ1 (Europe)
sigfox = Sigfox(mode=Sigfox.SIGFOX, rcz=Sigfox.RCZ1)

# create a Sigfox socket
s = socket.socket(socket.AF_SIGFOX, socket.SOCK_RAW)

print("sigfox mac:", ubinascii.hexlify(sigfox.mac()))
print("sigfox id: ", ubinascii.hexlify(sigfox.id()))
print("sigfox pac:", ubinascii.hexlify(sigfox.pac()))

# make the socket blocking
s.setblocking(True)

# configure it as uplink only
s.setsockopt(socket.SOL_SIGFOX, socket.SO_RX, False)

# send some bytes
status = s.send(bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]))

print(status)
