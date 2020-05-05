import jsonpickle
import graphviz as gv
import pathlib

# Specify if the node added directly to graph,
# or indirectly as remote party (LLDP neighbor) of direct node
# Direct node is always preferable and replace indirect node during Graph building
# [Constants]
DIRECT_NODE   = 0
INDIRECT_NODE = 1


# Dictionary with device type - icon image filename prefix association
pwd = str(pathlib.Path().absolute())
DEVTYPE_FILES = {"": pwd+"/devtype/l2switch",
                 "router": pwd+"/devtype/router",
                 "l2switch": pwd+"/devtype/l2switch",
                 "l3switch": pwd+"/devtype/l3switch",
                 "station": pwd+"/devtype/station",
                 "phone": pwd+"/devtype/phone",
                 "phonewithswitch": pwd+"/devtype/phonewithswitch",
                 "ap": pwd+"/devtype/ap"
                 }


class GLink:
    # Constructor
    def __init__(self, local_ifname, remote_ifname, remote_hostname, capabilities):
        self.local_ifname = local_ifname
        self.remote_ifname = remote_ifname
        # get only hostname part
        self.remote_hostname = remote_hostname.split('.')[0]
        # device type on the link
        self.capabilities = capabilities
        # attribute for Graph comparison; values: 'added', 'removed', <empty> if no changes; link level
        self.comp = ""
        # attribute to check if the link has already drawn
        self.drawn = False

    # set '.comp' attribute
    def set_comp(self, comp):
        self.comp = comp

    # set '.drawn' attribute and return this link object
    def set_drawn(self, drawn):
        self.drawn = drawn
        return self

    def print(self):
        print(f"    local_if={self.local_ifname} --- remote_if={self.remote_ifname} ON "
              f"rem_hostname={self.remote_hostname}, compare={self.comp}, "
              f"cap={self.capabilities}, drawn={self.drawn}")


class GNode:
    # Constructor
    def __init__(self, hostname, direct=INDIRECT_NODE):
        self.direct = direct
        # Count number of neighbors
        self.num_neighbors = 0
        # List of GLink objects
        self.links = []
        # hostname is local hostname for device like "primary" key
        # using 'hostname' as LLDP is using it; important for topology
        # get only hostname part
        self.hostname = hostname.split('.')[0]
        # attribute for Graph comparison; values: 'added', 'removed', <empty> if no changes; node level
        self.comp = ""
        # device type, by default - ''
        self.device_type = ""

    # set '.comp' attribute for node and all node's links
    def set_comp(self, comp):
        self.comp = comp
        for l in self.links:
            l.comp = comp

    # set device type
    def set_device_type(self, capabilities):
        # never set empty device type (it is empty by default)
        if capabilities == "":
            return

        if "R" in capabilities:
            if "B" in capabilities:
                self.device_type = "l3switch"
            else:
                self.device_type = "router"
        elif "T" in capabilities:
            if "B" in capabilities:
                self.device_type = "phonewithswitch"
            else:
                self.device_type = "phone"
        elif "S" in capabilities:
            self.device_type = "station"
        elif "B" in capabilities:
            self.device_type = "l2switch"
        elif "W" in capabilities:
            self.device_type = "ap"
        else:
            self.device_type = capabilities

    # add link with GLink object
    def add_link(self, link: GLink):
        self.links.append(link)
        self.num_neighbors += 1

    # add link, creating GLink object from string arguments
    def add_link_str(self, local_ifname: str, remote_ifname: str, remote_hostname: str, capabilities: str):
        self.add_link(GLink(local_ifname.split(":")[-1], remote_ifname.split(":")[-1], remote_hostname, capabilities))

    # Check if link presented in the node
    def check_link(self, link: GLink):
        for l in self.links:
            if l.local_ifname == link.local_ifname and l.remote_ifname == link.remote_ifname and l.remote_hostname == link.remote_hostname:
                return True
        return False

    # Find and set link 'drawn' attribute
    def set_link_drawn(self, link: GLink, hostname: str):
        for l in self.links:
            if l.local_ifname == link.remote_ifname and l.remote_ifname == link.local_ifname and l.remote_hostname == hostname:
                l.set_drawn(True)
                return l
        return None

    def append(self, node):
        # Append to this node distinct links from another node
        for link in node.links:
            if not self.check_link(link):
                self.add_link(link)
        return None

    # compare 2 GNodes for links equality
    def compare(self, n):
        n_res = GNode(self.hostname, self.direct)
        n_res.device_type = self.device_type

        for l_self in self.links:
            comp = "added"
            for l_n in n.links:
                # if link is found, then it is not added
                if l_self.local_ifname == l_n.local_ifname and l_self.remote_ifname == l_n.remote_ifname and l_self.remote_hostname == l_n.remote_hostname:
                    comp = ""
                    break
            l_self.set_comp(comp)
            n_res.add_link(l_self)

        for l_n in n.links:
            comp = "removed"
            for l_self in self.links:
                # if link is found, then it is not removed
                if l_self.local_ifname == l_n.local_ifname and l_self.remote_ifname == l_n.remote_ifname and l_self.remote_hostname == l_n.remote_hostname:
                    comp = ""
                    break
            # add to result only 'removed' links as .comp='' already were added
            if comp != "":
                l_n.set_comp(comp)
                n_res.add_link(l_n)

        return n_res

    def print(self):
        print(f"NODE: hostname={self.hostname}, indirect={self.direct}, num_neighbors={self.num_neighbors}, compare={self.comp}, dev_type={self.device_type}")
        for link in self.links:
            link.print()


class GGraph:
    # Constructor
    def __init__(self, name):
        # Graph name (not used)
        self.name = name
        # List of GNode objects
        self.nodes = []

    # checking if NODE already exists in the list of nodes
    def find_nodename(self, hostname: str):
        for idx, n in enumerate(self.nodes):
            if n.hostname == hostname:
                return idx
        return -1

    # get graph node names
    def get_node_names(self):
        return [n.hostname for n in self.nodes]

    # Add INDIRECT nodes for DIRECT node only
    def add_indirect_nodes(self, node):
        # Build INDIRECT object GNode, but only for DIRECT objects
        if node.direct == DIRECT_NODE:
            for link in node.links:
                gn = GNode(link.remote_hostname, INDIRECT_NODE)
                # in 'link' reverse local and remote ifnames as per view of remote node
                gn.add_link_str(link.remote_ifname, link.local_ifname, node.hostname, "")
                # set device_type only for INDIRECT nodes
                gn.set_device_type(link.capabilities)
                self.add_node(gn)

    def add_node(self, node: GNode):
        # Check if this node already in the list
        idx = self.find_nodename(node.hostname)
        # new node to add
        if idx == -1:
            # Append this node and recursively all INDIRECT nodes that can be collected from this node
            self.nodes.append(node)
            self.add_indirect_nodes(node)
        else:
            # Replace INDIRECT node with DIRECT node and add new INDIRECT nodes
            if self.nodes[idx].direct == INDIRECT_NODE and node.direct == DIRECT_NODE:
                # copy device_type from INDIRECT to DIRECT node during replacement asd it is unknown in DIRECT node
                node.set_device_type(self.nodes[idx].device_type)
                self.nodes[idx] = node
                self.add_indirect_nodes(node)
            # Otherwise, append attributes to existing node
            else:
                # update device type
                self.nodes[idx].set_device_type(node.device_type)
                # append not yet presented links to device
                self.nodes[idx].append(node)

    # Compare 2 GGraphs and return union GGraph with marked '.comp' attribute
    def compare(self, g):
        self_node_names = self.get_node_names()
        g_node_names = g.get_node_names()
        set_self_minus_g = list(set(self_node_names)-set(g_node_names))
        set_g_minus_self = list(set(g_node_names)-set(self_node_names))

        # collect result (union) Graph will filled attribute '.comp' ("added", "removed", <empty>) for nodes and links
        g_res = GGraph("---COMPARISON RESULT---")

        # add nodes presented in this Graph but not in old Graph, mark them as "added"
        for name in set_self_minus_g:
            node = self.nodes[self.find_nodename(name)]
            node.set_comp("added")
            g_res.nodes.append(node)

        # add nodes not presented in this Graph but presented in old Graph, mark them "removed"
        for name in set_g_minus_self:
            node = g.nodes[g.find_nodename(name)]
            node.set_comp("removed")
            g_res.nodes.append(node)

        # for all rest nodes (intersected), compare node-by-node for links changes, keeping node '.comp' attribute empty
        for name in list(set(self_node_names)-set(set_self_minus_g)):
            node = self.nodes[self.find_nodename(name)].compare(g.nodes[g.find_nodename(name)])
            g_res.nodes.append(node)

        return g_res

    def print(self):
        for n in self.nodes:
            n.print()

    def save(self, filename):
        with open(filename, "w") as f:
            f.write(jsonpickle.encode(self))

    def load(filename):
        with open(filename, "r") as f:
            g = jsonpickle.decode(f.read())
        return g

    def draw(self, filename):
        draw = gv.Graph(format="png", engine="sfdp")

        for node in self.nodes:
            # add node with '.comp' attribute
            n_color = "blue"
            if node.comp == "added":
                n_color = "green"
            elif node.comp == "removed":
                n_color = "red"

            draw.node(node.hostname, image=f"{DEVTYPE_FILES[node.device_type]}_{n_color}.png",
                      penwidth="0", fontsize="12")

        for node in self.nodes:
            for link in node.links:
                # add link if it was not yet drawn by other neighbor
                if not link.drawn:
                    link.drawn = True
                    # find other end of the link and mark it as 'drawn' as well
                    n2 = self.nodes[self.find_nodename(link.remote_hostname)]
                    l2 = n2.set_link_drawn(link, node.hostname)
                    e_comp = ""
                    if link.comp != "":
                        e_comp = link.comp
                    else:
                        if l2 is not None and l2.comp != "":
                            e_comp = l2.comp

                    e_color = "blue"
                    if e_comp == "added":
                        e_color = "green"
                    elif e_comp == "removed":
                        e_color = "red"

                    draw.edge(node.hostname, n2.hostname, color=e_color,
                              headlabel=link.remote_ifname, taillabel=link.local_ifname,
                              fontsize="10")

        draw.render(filename)
