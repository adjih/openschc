#---------------------------------------------------------------------------

from base_import import *  # used for now for differing modules in py/upy

import schc
import simsched
import simlayer2
import simul
from rulemanager import RuleManager

#---------------------------------------------------------------------------

l2_mtu = 56
data_size = 14

frag_rule1 = {
    "RuleLength": 6,
    "RuleID": 1,
    #XXX:put back cleanly: "profile": { "L2WordSize": 8 },
    "Fragmentation": {
        "FRMode": "ackOnError",
        "FRModeProfile": {
            "dtagSize": 2,
            "WSize": 5,
            "FCNSize": 3,
            "ackBehavior": "afterAll1",
            "tileSize": 9,
            "MICAlgorithm": "crc32",
            "MICWordSize": 8
        }
    }
}

frag_rule2 = {
    "RuleLength": 6,
    "RuleID": 2,
    #XXX:pub back cleanly: "profile": { "L2WordSize": 8 },
    "Fragmentation": {
        "FRMode": "ackOnError",
        "FRModeProfile": {
            "dtagSize": 2,
            "WSize": 5,
            "FCNSize": 3,
            "ackBehavior": "afterAll1",
            "tileSize": 9,
            "MICAlgorithm": "crc32",
            "MICWordSize": 8
        }
    }
}

#---------------------------------------------------------------------------

def make_node(sim, rule_manager, devaddr=None, extra_config={}):
    node = simul.SimulSCHCNode(sim, extra_config)
    node.protocol.set_rulemanager(rule_manager)
    if devaddr is None:
        devaddr = node.id
    node.layer2.set_devaddr(devaddr)
    return node

#---------------------------------------------------------------------------

rm0 = RuleManager()
#rm0.add_context(rule_context, compress_rule, frag_rule1, frag_rule2)
rm0.Add(dev_info=[frag_rule1, frag_rule2])

rm1 = RuleManager()
#rm1.add_context(rule_context, compress_rule, frag_rule1, frag_rule2)
rm1.Add(dev_info=[frag_rule1, frag_rule2])

#--------------------------------------------------

simul_config = {
    "log": True,
}
sim = simul.Simul(simul_config)

node0 = make_node(sim, rm0)                   # SCHC device
node1 = make_node(sim, rm1, devaddr=node0.id) # SCHC gw
sim.add_sym_link(node0, node1)
node0.layer2.set_mtu(l2_mtu)
node1.layer2.set_mtu(l2_mtu)

print("SCHC device L3={} L2={} RM={}".format(node0.layer3.L3addr, node0.id,
                                             rm0.__dict__))
print("SCHC gw     L3={} L2={} RM={}".format(node1.layer3.L3addr, node1.id,
                                             rm1.__dict__))

#--------------------------------------------------

payload = bytearray(range(1, 1+data_size))
node0.protocol.layer3.send_later(1, node1.layer3.L3addr, payload)

sim.run()

#---------------------------------------------------------------------------
