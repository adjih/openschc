#!/usr/bin/env python

import argparse
import json
import requests
import asyncio
from aiohttp import web
import ssl
import logging
import pcap
import os

# from base_import import *
from gen_rulemanager import *
from net_compression import AnalyzePkt
from net_sim_core import SimulLayer2, Simul
import protocol

PROG_NAME = "net_gw_lorawan"

config_default = {
    "debug_level": 0,
    "enable_sim_lpwa": False,
    "bind_addr": "::",
    "bind_port": 51225,
    "ifname": "eth0",
    "eth_dst": None,
    "eth_src": None,
    "downlink_url": None,
    "ssl_verify": True,
    "my_cert": None,
    "rule_file": None,
    }

def find_file(file_name):
    if os.path.exists(file_name) is False:
        file_path = "{}/{}".format(os.environ.get("OPENSCHCDIR",".."),file_name)
        if os.path.exists(file_path) is False:
            raise ValueError("No such file {}".format(file_name))
        return file_path
    else:
        return file_name


def post_data(url, data, verify):
    headers = {"content-type": "text/json"}
    requests.post(url, headers=headers, data=data, verify=verify)


class gwLayer2():

    def __init__(self, system, config=None):
        self.system = system
        self.config = config
        self.devaddr = b"\x00\x11\x22\x33"

    def send_packet(self, data, dev_L2addr, callback=None,
                    callback_args=tuple()):
        self._log("send data for {}".format(dev_L2addr))
        if self.config.enable_sim_lpwa is True:
            body = json.dumps({"hexSCHCData": data.hex(),
                               "devL2Addr": dev_L2addr})
        else:
            body = data
        self.system.scheduler.loop.run_in_executor(
                None, post_data, self.config.downlink_url, body,
                self.config.ssl_verify)
        status = 0
        #
        if callback is not None:
            # XXX status should be taken from the run_in_executor().
            args = callback_args + (status,)
            callback(*args)

    def _log(self, message):
        self.log("GWL2", message)

    def log(self, name, message):
        self.system.log(name, message)

    def get_mtu_size(self):
        # XXX how to know the MTU of the LPWA link beyond the NS.
        return 56

    def _set_protocol(self, protocol):
        self.protocol = protocol

    def get_address(self):
        return self.devaddr

class gwLayer3:
    def __init__(self, system, config=None):
        self.system = system
        self.config = config
        if "lo" in self.config.ifname:
            eth_dst = b""
            eth_src = b""
            eth_type = bytearray.fromhex("1e000000")
        else:
            # XXX
            eth_dst = bytearray.fromhex(
                    self.config.eth_dst.replace(":", ""))
            eth_src = bytearray.fromhex(
                    self.config.eth_src.replace(":", ""))
            eth_type = bytearray.fromhex("86dd")
        self.eth_hdr = eth_dst + eth_src + eth_type
        self.pcap = pcap.pcap(self.config.ifname, immediate=True)
        self.pcap.setdirection(pcap.PCAP_D_OUT)

    async def async_pcap_send(self, data):
        self.system.scheduler.loop.run_in_executor(
                None, self.pcap.sendpacket, data)

    def recv_packet(self, dev_L2addr, raw_packet):
        self._log("recv packet Devaddr={} Packet={}".format(
                dev_L2addr, raw_packet.get_content().hex()))
        asyncio.ensure_future(self.async_pcap_send(self.eth_hdr +
                                                   raw_packet.get_content()))

    def _set_protocol(self, protocol):
        self.protocol = protocol

    def _log(self, message):
        self.log("GWL3", message)

    def log(self, name, message):
        self.system.log(name, message)


class Scheduler:
    def __init__(self, loop):
        self.loop = loop

    def add_event(self, sec, func, args):
        return self.loop.call_later(sec, func, *args)

    def cancel_event(self, ev_h):
        ev_h.cancel()


class System:
    """
    self.get_scheduler(): provide the handler of the scheduler.
    self.log(): show the messages.  It is called by all modules.
    """
    def __init__(self, loop, logger=None, config=None):
        self.scheduler = Scheduler(loop)
        self.config = config
        if logger is None:
            self.logger = logging.getLogger(PROG_NAME)
        else:
            self.logger = logger

    def get_scheduler(self):
        return self.scheduler

    def log(self, name, message):
        # XXX should set a logging level.
        self.logger.debug("{} {}".format(name, message))

def get_json_data(body, key_list):
    for k in key_list:
        if k in body:
            return body[k]
    else:
        logger.debug("no data for {}".format(key_list))
        return None

async def app_downlink(request):
    """ downlink """
    if request.content_type == "application/x-rawip":
        if request.can_read_body:
            packet_hex = await request.read()
            logger.debug(packet_hex)
        else:
            logger.debug("http request body is not ready.")
            return web.json_response({"Status": "Error"}, status=503)
    elif request.content_type == "application/json":
        if request.can_read_body:
            body = await request.json()
            logger.debug(body)
            packet_hex = get_json_data(body, ["hex_payload", "hexIPData",
                                              "Data", "data"])
            if packet_hex is None:
                logger.debug("no IP data found.")
                return
        else:
            logger.debug("http request body is not ready.")
            return web.json_response({"Status": "Error"}, status=503)
    else:
        logger.debug("content-type must be json or x-raw, but {}"
                     .format(request.content_type))
        return web.json_response({"Status": "Error"}, status=405)
    #
    logger.debug(packet_hex)
    packet = bytearray.fromhex(packet_hex)
    protocol.schc_send(packet[24:40], packet, direction="down")
    return web.json_response({"Status": "OK"}, status=202)


async def app_uplink(request):
    """ check the message posted. process it as a uplink message.
    """
    if request.content_type == "application/json":
        if request.can_read_body:
            body = await request.json()
            logger.debug(body)
            l2_addr = get_json_data(body, ["devL2Addr", "L2Addr", "DevAddr"])
            if l2_addr is None:
                return
            app_data = get_json_data(body, ["hex_payload", "hexSCHCData",
                                            "Data", "data"])
            if app_data is None:
                return
            app_data = bytearray.fromhex(app_data)
            protocol.schc_recv(l2_addr, app_data)
            return web.json_response({"Status": "OK"}, status=202)
        else:
            logger.debug("http request body is not ready.")
            return web.json_response({"Status": "Error"}, status=503)
    else:
        logger.debug("content-type must be JSON")
        return web.json_response("Error", status=405)


def set_logger(logging, config):
    LOG_FMT = "%(asctime)s.%(msecs)d %(message)s"
    LOG_DATE_FMT = "%Y-%m-%dT%H:%M:%S"
    logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATE_FMT)
    logger = logging.getLogger(PROG_NAME)

    if config.debug_level:
        logger.setLevel(logging.DEBUG)
        logger_urllib3 = logging.getLogger("requests.packages.urllib3")
        logger_urllib3.setLevel(logging.DEBUG)
        logger_urllib3.propagate = True
    else:
        logger.setLevel(logging.INFO)

    return logger


def update_config():
    """
    priority order:
        1. arguments.
        2. config file.
        3. default.
    """
    if config.config_file is not None:
        config_from_file = json.loads(open(config.config_file).read())
    else:
        config_from_file = None
    for k, v in config_default.items():
        if getattr(config, k, None) is None:
            if config_from_file is not None:
                setattr(config, k, config_from_file.get(k, None))
            if getattr(config, k, None) is None:
                setattr(config, k, v)


#  main
ap = argparse.ArgumentParser(
        description="""a SCHC GW implementation""",
        epilog="still in progress.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
ap.add_argument("-c", action="store", dest="config_file",
                help="specify the config file.")
ap.add_argument("--downlink-url", action="store", dest="downlink_url",
                help="specify the URL of the NS agent for downlink.")
ap.add_argument("--bind-addr", action="store", dest="bind_addr",
                help="specify the address to be bound.")
ap.add_argument("--bind-port", action="store", dest="bind_port",
                type=int, default=None,
                help="specify the port number to be bound.")
ap.add_argument("--my-cert", action="store", dest="my_cert",
                help="specify the certificate of mine.")
ap.add_argument("--untrust", action="store_false", dest="ssl_verify",
                default=None,
                help="disable to check the server certificate.")
ap.add_argument("-d", action="store_true", dest="debug_level", default=None,
                help="specify debug level.")
config = ap.parse_args()
update_config()

# set the logger object.
logger = set_logger(logging, config)
if not config.debug_level:
    requests.packages.urllib3.disable_warnings()

# create the schc protocol object.
rule_manager = RuleManager()
rule_manager.Add(device=b"\x00\x11\x22\x33",
                 file=find_file(config.rule_file),
                 compression=True)
#
loop = asyncio.get_event_loop()
if config.debug_level > 1:
    loop.set_debug(True)
system = System(loop, logger=logger, config=config)
layer2 = gwLayer2(system, config=config)
layer3 = gwLayer3(system, config=config)
protocol = protocol.SCHCProtocol(config, system, layer2, layer3)
protocol.set_rulemanager(rule_manager)
#
ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ctx.load_cert_chain(find_file(config.my_cert))
app = web.Application(loop=loop, debug=True)
app.router.add_route("POST", "/ul", app_uplink)
app.router.add_route("POST", "/dl", app_downlink)
web.run_app(app, host=config.bind_addr, port=config.bind_port,
            ssl_context=ctx)
