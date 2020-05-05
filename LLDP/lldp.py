from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_command
from Graph import *
import json
import sys
import datetime


timestamp = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")


def host_lldp_neighbor(task):
    task.run(netmiko_send_command, command_string="term len 0", enable=True)

    # Get device hostname, if it is empty - setup hostname from Nornir config
    output = task.run(netmiko_send_command, command_string="show run | i hostname", enable=True)

    # check hostname result: take only first line and split " "
    if len(output[0].result.split("\n")[0].split(" ")) < 2:
        task.host["hostname"] = task.host.name
    else:
        task.host["hostname"] = output[0].result.split("\n")[0].split(" ")[1]

    # No idea why, but 'sh lldp nei det' for OLD(?) IOS doesn't contain local iface information,
    # so will use not 'detail' version
    output = task.run(netmiko_send_command, command_string="show lldp neighbor", enable=True, use_textfsm=True)

    # DEBUG code: save JSON for LLDP output
    with open(f"./lldp/{task.host['hostname']}-{timestamp}.json", "w") as file:
        json.dump(output[0].result, file)

    task.host["lldp"] = output[0].result


def main(g2_fn: str):
    g = GGraph("testme")
    nr = InitNornir(config_file="./templates/inventory.yaml")
    nr.run(host_lldp_neighbor)

    for host in nr.inventory.dict()["hosts"]:
        output = json.loads(str(nr.inventory.dict()["hosts"][host]["data"]["lldp"]).replace("'", '"'))
        gn = GNode(str(nr.inventory.dict()["hosts"][host]["data"]["hostname"]), DIRECT_NODE)
        # add links to node
        for link in output:
            gn.add_link_str(link["local_interface"], link["neighbor_interface"], link["neighbor"], link["capabilities"])

        # add node to graph
        g.add_node(gn)

    g.save(f"./graph/graph-{timestamp}")

    if g2_fn != "":
        print(f"Got input graph '{g2_fn}' for comparison")
        g2 = GGraph.load(g2_fn)
        # g2.print()
        g_res = g.compare(g2)

        # keep only filename now in var
        g2_fn = g2_fn.split("/")[-1].split(".")[0]
        g_res.save(f"./graph/COMPARE--graph-{timestamp}--{g2_fn}")
        g_res.draw(f"./img/COMPARE--graph-{timestamp}--{g2_fn}")
        # g_res.print()
    else:
        print(f"No input graph for comparison")
        g.draw(f"./img/graph-{timestamp}")
        # g.print()


if __name__ == '__main__':
    g2_fn = ""
    if len(sys.argv) > 1:
        # assume that second argument is another Graph filename to compare
        g2_fn = sys.argv[1]

    main(g2_fn)
