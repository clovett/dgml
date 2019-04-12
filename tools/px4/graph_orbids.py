import sys


class GraphObject:
    def __init__(self):
        self.properties = {}

    def set_property(self, name, value):
        self.properties[name] = value

    def save_dgml_properties(self, f):
        for id in self.properties:
            f.write(' {}="{}"'.format(id, self.properties[id]))

    def save_dot_properties(self, f):
        for id in self.properties:
            f.write(' {}="{}"'.format(id.lower(), self.properties[id]))


class Node(GraphObject):
    def __init__(self, id):
        super(Node, self).__init__()
        self.id = id
        self.properties = {}

    def save_dgml(self, f):
        f.write('<Node Id="{}"'.format(self.id))
        self.save_dgml_properties(f)
        f.write("/>\n")

    def save_dot(self, f):
        f.write('    "{}" ['.format(self.id))
        self.save_dgml_properties(f)
        f.write("];\n")


class Link(GraphObject):
    def __init__(self, source, target):
        super(Link, self).__init__()
        self.source = source
        self.target = target

    def save_dgml(self, f):
        f.write('<Link Source="{}" Target="{}"'.format(self.source.id, self.target.id))
        self.save_dgml_properties(f)
        f.write("/>\n")

    def save_dot(self, f):
        f.write('    "{}" -> "{}" ['.format(self.source.id, self.target.id))
        self.save_dot_properties(f)
        f.write("];\n")


class Graph:
    def __init__(self):
        self.nodes = {}
        self.links = {}

    def get_or_create_node(self, id):
        if id not in self.nodes:
            node = Node(id)
            self.nodes[id] = node
        else:
            node = self.nodes[id]
        return node

    def get_or_create_link(self, source, target):
        id = source.id + "->" + target.id
        if id not in self.links:
            link = Link(source, target)
            self.links[id] = link
        else:
            link = self.links[id]
        return link

    def save_dgml(self, filename):
        with open(filename, "w") as f:
            f.write('<DirectedGraph xmlns="http://schemas.microsoft.com/vs/2009/dgml">\n')
            f.write('<Nodes>\n')
            for id in self.nodes:
                node = self.nodes[id]
                node.save_dgml(f)
            f.write('</Nodes>\n')
            f.write('<Links>\n')
            for id in self.links:
                link = self.links[id]
                link.save_dgml(f)
            f.write('</Links>\n')
            f.write('</DirectedGraph>\n')

    def save_dot(self, filename):
        with open(filename, "w") as f:
            f.write('digraph {\n')
            for id in self.nodes:
                node = self.nodes[id]
                node.save_dot(f)
            for id in self.links:
                link = self.links[id]
                link.save_dot(f)
            f.write('}\n')


class Parser:
    def parse(self, filename):
        graph = Graph()

        with open(filename, "r") as f:
            lines = f.readlines()

        for line in lines:
            if "(" not in line:
                print("Ignoring line: {}".format(line))
                continue

            i = line.index("(")
            file = line[:i].strip()
            id = self.get_node_id(file)
            node = graph.get_or_create_node(id)
            node.set_property("File", file)
            node.set_property("Category", "Class")

            orbid = None
            r = self.parse_line(line)
            if r:
                type, orbid = r
                topic = graph.get_or_create_node(orbid)
                topic.set_property("Category", "Topic")
                if type == "publish":
                    graph.get_or_create_link(node, topic)
                else:
                    graph.get_or_create_link(topic, node)
        return graph

    def parse_line(self, line):
        pub_prefixes = ["orb_publish(ORB_ID(", "orb_publish_auto(ORB_ID("]
        for prefix in pub_prefixes:
            if prefix in line:
                i = line.index(prefix)
                tail = line[i + len(prefix):]
                i = tail.index(")")
                return ("publish", tail[:i])

        sub_prefixes = ["orb_subscribe(ORB_ID(", "orb_subscription(ORB_ID(",
                        "orb_copy(ORB_ID(",  "copy_if_updated(ORB_ID("]
        for prefix in sub_prefixes:
            if prefix in line:
                i = line.index(prefix)
                tail = line[i + len(prefix):]
                i = tail.index(")")
                return ("subscribe", tail[:i])

        if "orb_subscribe_multi" in line:
            return None  # ignore these for now

        if "orb_advertise" in line:
            return None  # ignore this setup code.

        if "== ORB_ID" in line or "= ORB_ID" in line:
            return None

        print("What is this about? {}".format(line))
        return None

    def get_node_id(self, filename):
        parts = filename.split("\\")
        if len(parts) > 2:
            # return the directory name, not the file name
            return parts[len(parts) - 2]


if __name__ == "__main__":
    filename = sys.argv[1]
    p = Parser()
    graph = p.parse(filename)
    graph.save_dgml("graph.dgml")
    graph.save_dot("graph.dot")
