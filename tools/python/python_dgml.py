import argparse
import os
import sys
import ast
import subprocess
import tempfile
from typing import Set

from dgml import DirectedGraph, GraphNode

# Create a Directed Graph of type dependencies in a given python file or folder.

def group_node(graph: DirectedGraph, node: GraphNode, group_name: str):
    # create dgml group that is expanded by default
    group = graph.get_or_create_node(group_name)
    group.set_group(state="Expanded")
    graph.get_or_create_link(group, node).category = "Contains"
    return group


def process_file(file_path: str, group: str, graph: DirectedGraph):
    with open(file_path, "r", encoding='utf-8') as f:
        tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                graph_node = graph.get_or_create_node(node.name, category="class")
                graph_node.ast = node
                if group:
                    group_node(graph, graph_node, group)


def link_inheritance(graph: DirectedGraph):
    for node in graph.nodes.values():
        if not node.is_group() and hasattr(node.ast, "bases"):
            for base in node.ast.bases:
                if isinstance(base, ast.Name):
                    base_node = graph.nodes.get(base.id, None)
                    if base_node:
                        graph.get_or_create_link(node, base_node, category="inherits")

class TypeReferenceFinder(ast.NodeVisitor):
    """
    AST visitor that collects all type references from:
    - Class base types
    - Function argument/return annotations
    - Variable annotations
    - Instantiations (e.g., MyClass())
    """
    def __init__(self):
        self.type_names: Set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef):
        # Base classes
        for base in node.bases:
            self._add_type_from_expr(base)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Function argument annotations
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                self._add_type_from_expr(arg.annotation)
        # Return annotation
        if node.returns:
            self._add_type_from_expr(node.returns)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        # Variable annotations
        if node.annotation:
            self._add_type_from_expr(node.annotation)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Instantiations like MyClass()
        self._add_type_from_expr(node.func)
        self.generic_visit(node)

    def _add_type_from_expr(self, expr: ast.AST):
        """Extract type name from Name or Attribute nodes."""
        if isinstance(expr, ast.Name):
            self.type_names.add(expr.id)
        elif isinstance(expr, ast.Attribute):
            # Handle dotted names like module.Type
            parts = []
            while isinstance(expr, ast.Attribute):
                parts.append(expr.attr)
                expr = expr.value
            if isinstance(expr, ast.Name):
                parts.append(expr.id)
            self.type_names.add(".".join(reversed(parts)))
        elif isinstance(expr, ast.Subscript):
            # Handle generics like List[int]
            self._add_type_from_expr(expr.value)
            if hasattr(expr, 'slice'):
                self._add_type_from_expr(expr.slice)
        elif isinstance(expr, ast.Tuple):
            for elt in expr.elts:
                self._add_type_from_expr(elt)


def link_references(graph: DirectedGraph):
    for node in graph.nodes.values():
        if not node.is_group() and hasattr(node.ast, "body"):
            finder = TypeReferenceFinder()
            finder.visit(node.ast)
            for type_name in finder.type_names:
                ref_node = graph.nodes.get(type_name, None)
                if ref_node and ref_node.is_group():
                    continue
                if ref_node and ref_node != node:
                    graph.get_or_create_link(node, ref_node, category="references")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a DGML graph from Python source code.")
    parser.add_argument("folder_path", help="Path to the folder containing Python source files.")
    parser.add_argument("--git-history", action="store_true", help="Generate a DGML graph for each git commit in the history.")

    return parser.parse_args()

def process_folder(folder_path: str, file_name: str):
    # Create a new graph containing all the classes found in the server folder
    graph = DirectedGraph()    

    root = os.path.realpath(folder_path)

    # walk the given folder in sys.argv[1] and add all the classes to the graph    
    for dir, dirs, files in os.walk(root):
        dir = os.path.realpath(dir)
        for file in files:
            if file.endswith(".py"):
                group = dir.replace(root, "").strip(os.sep).replace(os.sep, ".")
                process_file(os.path.join(dir, file), group or "root", graph)

    link_inheritance(graph)
    link_references(graph)
    # save the graph to a file called architecture.dgml
    graph.save_dgml(file_name)


def process_git_history(folder_path: str):

    cmd = ["git", "log", "--pretty=format:%h %ad %s", "--date=short"]
    
    # Get the list of commits in the repository
    result = subprocess.run(cmd, check=True, text=True, encoding='utf-8', capture_output=True, cwd=folder_path)
    lines = result.stdout.splitlines()
    
    for line in lines:
        if len(line) < 18:
            continue
        id = line[0:7]
        date = line[8:18].replace("-", "_")       
        description = line[19:]
        file_name = f"architecture_{date}_{id}.dgml"

        print(f"Processing commit {id} {date} {description}...")
        # Checkout the specific commit
        subprocess.run(["git", "checkout", id], check=True, cwd=folder_path)
        # Process the folder at this commit
        process_folder(folder_path, file_name)

def main():
    args = parse_args()
    if args.git_history:
        process_git_history(args.folder_path)
    else:
        process_folder(args.folder_path, "architecture.dgml")


if __name__ == "__main__":
    main()