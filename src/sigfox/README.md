
## Sigfox connections through FiPy/LoPy/...

 - Status: nothing yet

## Useful tools:

 - [Adafruit MicroPython Tool](https://github.com/pycampers/ampy)


## In progress: `pctool`, pycom tool based on ampy

### SigFox

 * `./pctool sigfox-info`
   Get sigfox mac, sigfox id, sigfox pac

 * `./pctool show`
   TODO

 * `./pctool sigfox-send <utf-8 string>`
   Send the string in the packet as UTF-8 on Sigfox network

### LoRa

 * `./pctool lora-info`
   Get mac address from LoRa radio

### LoRa/TTN

## Test sending one Sigfox packet (will be replaced by ./pctool sigfox-send)

 * `ampy -p /dev/ttyACM0 run test_sigfox_send.py`
