import igraph as ig
from Verilator_AST import *

class ASTNodeClassify:
    def __init__(self):
        self.should_not_numbered = {"always", "exprstmt", "begin", "sentree", "if", "scope", "comment", "topscope", "senitem", "assign", "contassign", "assigndly", "assignalias", "case", "caseitem"}
        
        self.not_commutable_arith_op = {"sub"}
        self.commutable_arith_op = {"add","mul"}
        self.arith_op = self.not_commutable_arith_op | self.commutable_arith_op 
        self.logic_op = {"and", "or", "xor", "not"}
        self.red_logic_op = {"redand", "redor", "redxor"}
        self.eq_op= {"eq", "neq"}
        self.less_n_greater_op = {"gt", "gte", "lt", "lte"}
        self.merge_op = {"extend","concat","replicate"}
        self.cond_op = {"cond"}
        self.var_node = {"varref", "varscope", "sel"}
        self.const_node = {"const"}

        self.tag_as_name_node = self.arith_op | self.logic_op | self.red_logic_op | self.eq_op | self.less_n_greater_op | self.merge_op | self.cond_op
        self.name_as_name_node = self.var_node | self.const_node
        self.same_input_link_node = self.logic_op | self.red_logic_op | self.eq_op | self.commutable_arith_op

class AST2CircuitGraph(AST_Parser,ASTNodeClassify):
    def __init__(self, ast: etree._ElementTree):
        AST_Parser.__init__(self,ast)
        ASTNodeClassify.__init__(self)


        # Graph Declaration
        self.graph = ig.Graph()
        self.graph.vs["name"] = []
        self.graph.vs["width"] = []


        self.total_node_num = 0
        # numbering all nodes that need to be included in the Graph.


    def insert_graph_node(self,node):
        self.graph.add_vertices(1)
        if node.tag in self.tag_as_name_node:
            self.graph.vs["name"][self.total_node_num] = node.tag
        elif node.tag in self.name_as_name_node:
            if node.tag == "sel":
                print(node.getchildren())
                self.graph.vs["name"][self.total_node_num] = node.getchildren()[0].attrib["name"] + "[" + node.getchildren()[1].attrib["name"] + ":" + node.getchildren()[2].attrib["name"] + "]"
            else:
                self.graph.vs["name"][self.total_node_num] = node.attrib["name"]
        else:
            print("Error: Undefined Class to Insert! Node Tag: "+node.tag)

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
                if tag in self.should_not_numbered:
                    pass
                elif tag == "const" and node.getparent().tag == "sel":
                    pass
                elif tag == "varref" and not node.attrib["name"] in sig_set:
                    print("Error: <varref> not on the signal list! var name = "+node.attrib["name"])
                else:
                    node.attrib["node_id"] = str(self.total_node_num)
                    self.insert_graph_node(node)
                    self.total_node_num = self.total_node_num + 1

        # Number Nodes Under <assignalias>
        for assign in self.ast.findall(".//assignalias"):
            for node in assign.iter():
                tag = node.tag
                if tag in self.should_not_numbered:
                    pass
                elif tag == "const" and node.getparent().tag == "sel":
                    pass
                elif tag == "varref" and not node.attrib["name"] in sig_set:
                    # Check if the var name in the list of signal names.
                    print("Error: <varref> not on the signal list!  var name = "+node.attrib["name"])
                else:
                    node.attrib["node_id"] = str(self.total_node_num)
                    self.insert_graph_node(node)
                    self.total_node_num = self.total_node_num + 1

        # Number Nodes Under <always//assign> that doesn't have <sentree> under it.
        for always in self.ast.findall(".//always"):
            if always.getchildren()[0].tag == "sentree":
                continue
            for node in always.iter():
                tag = node.tag
                if tag in self.should_not_numbered:
                    pass
                elif tag == "const" and node.getparent().tag == "sel":
                    pass
                elif tag == "varref" and not node.attrib["name"] in sig_set:
                    print("Error: <varref> not on the signal list!  var name = "+node.attrib["name"])
                else:
                    node.attrib["node_id"] = str(self.total_node_num)
                    self.insert_graph_node(node)
                    self.total_node_num = self.total_node_num + 1

        # Number Nodes Under <always//assign> that have <sentree> under it.
        for always in self.ast.findall(".//always"):
            if always.getchildren()[0].tag != "sentree":
                continue
            for node in always.iter():
                tag = node.tag
                if tag in self.should_not_numbered:
                    pass
                elif "sentree" in self.ast.getpath(node):
                    pass
                elif tag == "const" and node.getparent().tag == "sel":
                    pass
                elif tag == "varref" and not node.attrib["name"] in sig_set:
                    print("Error: <varref> not on the signal list!  var name = "+node.attrib["name"])
                else:
                    # Add a node
                    node.attrib["node_id"] = str(self.total_node_num)
                    self.insert_graph_node(node)
                    self.total_node_num = self.total_node_num + 1

        print("DONE!")
        print("    Total Node Number = "+str(self.total_node_num))



    def connect_operator(self):
        for node in self.ast.iter():
            if "node_id" in node.attrib:
                # There is no different between the input links of these kinds of nodes.
                if node.tag in self.same_input_link_node:
                    cur_node_id = int(node.attrib["node_id"])
                    for parent_node in node.getchildren():
                        if "node_id" in parent_node.attrib:
                            parent_node_id = int(parent_node.attrib["node_id"])
                            self.graph.add_edges([(cur_node_id, parent_node_id)])
                        else:
                            print("Parent node without number!")
        print(self.graph.summary())
                    

    def graph_construct(self):
        self.numbering_node()
        self.connect_operator()


if __name__ == "__main__":
    ast = Verilator_AST_Tree("./ast/Vsha1.xml")

    circuit = AST2CircuitGraph(ast)
    circuit.graph_construct()
