import igraph as ig
from Verilator_AST import *

class AST2CircuitGraph(AST_Parser):
    def __init__(self, ast: etree._ElementTree):
        super().__init__(ast)
        self.total_node_num = 0
        # numbering all nodes that need to be included in the Graph.

    # Number the nodes with tag of <var>, which is the signal of the circuit design.
    def numbering_node(self):
        # Find the list of signal names
        sig_set = self.get_sig_nodes(False)
        
        s = set()
        print("Numbering Var Nodes...")

        # Number Nodes Under <contassign>
        for contassign in self.ast.findall(".//contassign"):
            for node in contassign.iter():
                tag = node.tag
                if tag == "contassign":
                    pass
                elif tag == "const" and node.getparent().tag == "sel":
                    pass
                elif tag == "varref":
                    # Check if the var name in the list of signal names.
                    if not node.attrib["name"] in sig_set:
                        print("Noooo!!")
                else:
                    node.attrib["node_id"] = str(self.total_node_num)
                    self.total_node_num = self.total_node_num + 1

        # Number Nodes Under <contassign>
        for assign in self.ast.findall(".//assignalias"):
            for node in assign.iter():
                tag = node.tag
                if tag == "assignalias":
                    pass
                elif tag == "const" and node.getparent().tag == "sel":
                    pass
                elif tag == "varref":
                    # Check if the var name in the list of signal names.
                    if not node.attrib["name"] in sig_set:
                        print("Noooo!!")
                else:
                    node.attrib["node_id"] = str(self.total_node_num)
                    self.total_node_num = self.total_node_num + 1

        # Number Nodes Under <always>
        for always in self.ast.findall(".//always"):
            for node in always.iter():
                tag = node.tag
                if tag == "assign" or tag == "assigndly":
                    pass
                elif "sentree" in self.ast.getpath(node):
                    pass
                elif tag == "const" and node.getparent().tag == "sel":
                    pass
                elif tag == "varref":
                    if not node.attrib["name"] in sig_set:
                        print("Noooo!!")
                else:
                    node.attrib["node_id"] = str(self.total_node_num)
                    self.total_node_num = self.total_node_num + 1


        print("DONE!")
        print("    Total Node Number = "+str(self.total_node_num))


if __name__ == "__main__":
    ast = Verilator_AST_Tree("./Vr8051.xml")
    s = set()
    print("Numbering Var Nodes...")

    print(s)
    circuit = AST2CircuitGraph(ast)
    circuit.numbering_node()
