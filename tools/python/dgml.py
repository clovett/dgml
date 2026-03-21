from typing import Dict, List
import xml.etree.ElementTree as XT


class GraphObject:
    def __init__(self, id: str, label: str| None , category: str| None ):
        self.id = id
        self.label = label
        self.category = category
        self.properties: dict[str, str] = {}


class GraphNode(GraphObject):
    def __init__(self, id: str, label: str | None , category: str | None ):
        super().__init__(id, label, category)

    def is_group(self) -> bool:
        return "Group" in self.properties

    def set_group(self, state="Collapsed"):
        self.properties["Group"] = state


class GraphLink(GraphObject):
    def __init__(self, source: GraphNode, target: GraphNode, label: str| None , category: str | None , index: int = 0):
        id = f"{source.id}->{target.id}({index})"
        super().__init__(id, label, category)
        self.source = source
        self.target = target


class GraphStyleSetter:
    def __init__(self, property: str, value: str):
        self.property = property
        self.value = value


class GraphStyle:
    def __init__(self, target_type: str, group_label: str | None = None, value_label: str | None = None, condition: str | None = None):
        self.target_type = target_type
        self.group_label = group_label
        self.value_label = value_label
        self.condition = condition
        self.setters: List[GraphStyleSetter] = []


class DirectedGraph:
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.links: Dict[str, GraphLink] = {}
        self.styles: List[GraphStyle] = []
        self.ns = "http://schemas.microsoft.com/vs/2009/dgml"

    def get_or_create_node(self, id: str, label: str | None = None, category: str | None = None) -> GraphNode:
        if id not in self.nodes:
            self.nodes[id] = GraphNode(id, label, category)
        node = self.nodes[id]
        if node.label is None:
            node.label = label
        if node.category is None:
            node.category = category
        return node

    def get_or_create_link(
        self, source: GraphNode, target: GraphNode, label: str | None = None, category: str | None = None
    ) -> GraphLink:
        link = GraphLink(source, target, label, category)
        if link.id not in self.links:
            self.links[link.id] = link
        link = self.links[link.id]
        if link.label is None:
            link.label = label
        if link.category is None:
            link.category = category
        return link

    def add_style(self, style: GraphStyle):
        self.styles.append(style)

    def get_container(self, node: GraphNode) -> GraphNode | None:
        if node.is_group():
            return node
        for link in self.links.values():
            if link.source.is_group() and link.target == node and link.category == "Contains":
                return link.source
        return None

    def get_container_graph(self) -> "DirectedGraph":
        container_graph = DirectedGraph()
        for node in self.nodes.values():
            if node.is_group():
                container_graph.get_or_create_node(node.id, node.label)

        for link in self.links.values():
            if link.category != "Contains":
                c1 = self.get_container(link.source)
                c2 = self.get_container(link.target)
                if c1 is not None and c2 is not None and c1 != c2:
                    cg1 = container_graph.get_or_create_node(c1.id, c1.label)
                    cg2 = container_graph.get_or_create_node(c2.id, c2.label)
                    container_graph.get_or_create_link(cg1, cg2)

        return container_graph

    def copy(self, other: "DirectedGraph"):
        """Copy all the nodes and links from the other graph into this graph."""
        for node in other.nodes.values():
            imported_node = self.get_or_create_node(node.id, node.label, node.category)
            for key, value in node.properties.items():
                imported_node.properties[key] = value
        for link in other.links.values():
            source = self.get_or_create_node(link.source.id)
            target = self.get_or_create_node(link.target.id)
            imported_link = self.get_or_create_link(source, target, link.label, link.category)
            for key, value in link.properties.items():
                imported_link.properties[key] = value
        for style in other.styles:
            self.styles.append(style)

    def is_empty(self) -> bool:
        return len(self.nodes) == 0 and len(self.links) == 0

    def compare(self, other: "DirectedGraph") -> "DirectedGraph":
        """Return all nodes and links in this graph that are not in the other graph"""
        diff = DirectedGraph()
        for node in self.nodes.values():
            if node.id not in other.nodes:
                diff_node = diff.get_or_create_node(node.id, node.label, node.category)
                for key, value in node.properties.items():
                    diff_node.properties[key] = value
        for link in self.links.values():
            if link.id not in other.links:
                source = diff.get_or_create_node(link.source.id)
                target = diff.get_or_create_node(link.target.id)
                diff_link = diff.get_or_create_link(source, target, link.label, link.category)
                for key, value in link.properties.items():
                    diff_link.properties[key] = value
        return diff

    def to_xml(self, value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def save_dgml(self, filename: str):
        with open(filename, "w") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            f.write(f'<DirectedGraph xmlns="{self.ns}">\n')
            f.write("  <Nodes>\n")
            for node in self.nodes.values():
                f.write(f'    <Node Id="{self.to_xml(node.id)}"')
                if node.label:
                    f.write(f' Label="{self.to_xml(node.label)}"')
                if node.category:
                    f.write(f' Category="{self.to_xml(node.category)}"')
                for key, value in node.properties.items():
                    f.write(f' {self.to_xml(key)}="{self.to_xml(value)}"')
                f.write("/>\n")
            f.write("  </Nodes>\n")
            f.write("  <Links>\n")
            for link in self.links.values():
                f.write(f'    <Link Source="{self.to_xml(link.source.id)}" Target="{self.to_xml(link.target.id)}"')
                if link.label:
                    f.write(f' Label="{self.to_xml(link.label)}"')
                if link.category:
                    f.write(f' Category="{self.to_xml(link.category)}"')
                for key, value in link.properties.items():
                    f.write(f' {self.to_xml(key)}="{self.to_xml(value)}"')
                f.write("/>\n")
            f.write("  </Links>\n")
            f.write("  <Styles>\n")
            for style in self.styles:
                f.write(f'    <Style TargetType="{self.to_xml(style.target_type)}"')
                if style.group_label:
                    f.write(f' GroupLabel="{self.to_xml(style.group_label)}"')
                if style.value_label:
                    f.write(f' ValueLabel="{self.to_xml(style.value_label)}"')
                f.write(">\n")
                if style.condition:
                    f.write(f'      <Condition Expression="{self.to_xml(style.condition)}"/>\n')
                for setter in style.setters:
                    f.write(
                        f'      <Setter Property="{self.to_xml(setter.property)}"'
                        + f' Value="{self.to_xml(setter.value)}" />\n'
                    )
                f.write("    </Style>\n")
            f.write("  </Styles>\n")
            f.write("</DirectedGraph>\n")

    def load_dgml(self, filename: str):
        tree = XT.parse(filename)
        root = tree.getroot()
        root_tag = f"{{{self.ns}}}DirectedGraph"
        if root.tag != root_tag:
            raise ValueError("Invalid DGML file, expecting {root_tag} but got {root.tag}")
        for e in root.findall(f"./{{{self.ns}}}Nodes/{{{self.ns}}}Node"):
            id = e.get("Id")
            label = e.get("Label", None)
            category = e.get("Category", None)
            node = self.get_or_create_node(id, label, category)
            for key, value in e.items():
                if key not in ["Id", "Label", "Category"]:
                    node.properties[key] = value

        for e in root.findall(f"./{{{self.ns}}}Links/{{{self.ns}}}Link"):
            source = self.get_or_create_node(e.get("Source"))
            target = self.get_or_create_node(e.get("Target"))
            label = e.get("Label", None)
            category = e.get("Category", None)
            link = self.get_or_create_link(source, target, label, category)
            for key, value in e.items():
                if key not in ["Source", "Target", "Label", "Category"]:
                    link.properties[key] = value

        for e in root.findall(f"./{{{self.ns}}}Styles/{{{self.ns}}}Style"):
            target_type = e.get("TargetType")
            group_label = e.get("GroupLabel", None)
            value_label = e.get("ValueLabel", None)
            condition = e.get("Condition", None)
            style = GraphStyle(target_type, group_label, value_label, condition)
            for setter in e.findall(f"./{{{self.ns}}}Setter"):
                property = setter.get("Property")
                value = setter.get("Value")
                style.setters.append(GraphStyleSetter(property, value))

    def _scc_util(
        self,
        nodes,
        u: int,
        low: List[int],
        disc: List[int],
        stack_member: List[bool],
        st: List[int],
        st_index: List[int],
        time: int,
        results: List[List[GraphNode]],
    ) -> int:
        disc[u] = time
        low[u] = time
        time += 1
        stack_member[u] = True
        st[st_index[0]] = u
        st_index[0] += 1

        source = nodes[u]
        outgoing = [e.target for e in self.links.values() if e.source == source and e.category != "Contains"]
        for n in outgoing:
            v = nodes.index(n)
            if disc[v] == -1:
                time = self._scc_util(nodes, v, low, disc, stack_member, st, st_index, time, results)
                low[u] = min(low[u], low[v])
            elif stack_member[v]:
                low[u] = min(low[u], disc[v])
        w = -1
        if low[u] == disc[u]:
            row: List[GraphNode] = []
            while w != u:
                w = st[st_index[0] - 1]
                st_index[0] -= 1
                stack_member[w] = False
                row.append(nodes[w])
            if len(row) > 1:
                results.append(row)
        return time

    def _scc(self) -> List[List[GraphNode]]:
        # Tarjan's algorithm for strongly connected components
        # See https://en.wikipedia.org/wiki/Tarjan%27s_strongly_connected_components_algorithm
        nodes = list(self.nodes.values())
        V = len(nodes)
        disc = [-1] * V
        low = [-1] * V
        stack_member = [False] * V
        st = [-1] * V
        st_index = [0]
        time = 0
        results: List[List[GraphNode]] = []
        for i in range(V):
            if disc[i] == -1:
                time = self._scc_util(nodes, i, low, disc, stack_member, st, st_index, time, results)
        return results

    def analyze_cyclic_dependencies(self) -> "DirectedGraph":
        # Run Tarjan's algorithm to find the strongly connected components on every
        # graph and combine the results into one output cycles graph.
        cycles = DirectedGraph()
        is_scc_property = "IsStronglyConnected"
        node_style = GraphStyle("Node", "Circular References", "Nodes", is_scc_property)
        node_style.setters.append(GraphStyleSetter("Stroke", "#D02030"))
        node_style.setters.append(GraphStyleSetter("StrokeThickness", "2"))
        cycles.add_style(node_style)
        is_circular_property = "IsCircularLink"
        link_style = GraphStyle("Link", "Circular References", "Links", is_circular_property)
        link_style.setters.append(GraphStyleSetter("Stroke", "#D02030"))
        link_style.setters.append(GraphStyleSetter("StrokeThickness", "2"))
        cycles.add_style(link_style)

        components = self._scc()
        if len(components):
            for row in components:
                for node in row:
                    node = cycles.get_or_create_node(node.id, node.label)
                    node.properties[is_scc_property] = "True"
                    for link in self.links.values():
                        if link.source in row and link.target in row:
                            link = cycles.get_or_create_link(link.source, link.target)
                            link.properties[is_circular_property] = "True"
        return cycles
