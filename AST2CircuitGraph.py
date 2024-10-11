import igraph as ig
from ASTNodeClassify import *
from Verilator_AST import *

def verilog_num2num(num:str):
    width = None
    form = None
    if "'" in num:
        split_num = num.split("'")
        width = split_num[0]
        radix = split_num[1][0]
        new_num = split_num[1][1:]
        if (radix == "h"):
            new_num = str(int(new_num,16))
        elif (radix == "d"):
            new_num = str(int(new_num,10))
        elif (radix == "o"):
            new_num = str(int(new_num,8))
        elif(radix == "b"):
            new_num = str(int(new_num,2))
        else:
            print("Error: Unknown Radix!")

    else:
        new_num = num
    return new_num


class AST2CircuitGraph(AST_Parser,ASTNodeClassify):
    def __init__(self, ast: etree._ElementTree):
        AST_Parser.__init__(self,ast)
        ASTNodeClassify.__init__(self)


        # Graph Declaration
        self.graph = ig.Graph()
        self.graph.vs["name"] = []
        self.graph.vs["width"] = []
        self.graph.es["attrib"] = []


        self.total_node_num = 0
        self.total_edge_num = 0
        # numbering all nodes that need to be included in the Graph.


    def insert_graph_node(self,node):
        self.graph.add_vertices(1)
        if node.tag in self.tag_as_name_node:
            self.graph.vs["name"][self.total_node_num] = node.tag
            self.total_node_num = self.total_node_num + 1
        elif node.tag in self.name_as_name_node:
            if node.tag == "sel":
                self.graph.vs["name"][self.total_node_num] = "sel" + "[" + node.attrib["start_bit"] + ":" + node.attrib["end_bit"] + "]"
            else:
                self.graph.vs["name"][self.total_node_num] = node.attrib["name"]
            self.total_node_num = self.total_node_num + 1
        else:
            print("Error: Undefined Class to Insert! Node Tag: "+node.tag)


    def insert_graph_edge(self,edge:tuple,attrib=""):
        self.graph.add_edges([edge])
        self.graph.es["attrib"][self.total_edge_num] = attrib
        self.total_edge_num = self.total_edge_num + 1


    def modify_ast(self):
        for sel in self.ast.findall(".//sel"):
            start_bit = int(verilog_num2num(sel.getchildren()[1].attrib["name"]))
            width = int(verilog_num2num(sel.getchildren()[2].attrib["name"]))
            end_bit = start_bit + width - 1
            sel.attrib["start_bit"] = str(start_bit) 
            sel.attrib["end_bit"] = str(end_bit)
            sel.remove(sel.getchildren()[1])
            sel.remove(sel.getchildren()[1])

    # Number the nodes with tag of <var>, which is the signal of the circuit design.
    def numbering_node(self):
        # Find the list of signal names
        sig_set = self.get_sig_nodes(False)
        
        s = set()
        print("Numbering Var Nodes...")

        # Number Nodes Under <contassign>
        for assign in self.ast.findall(".//contassign") + self.ast.findall(".//assign") + self.ast.findall(".//assigndly") + self.ast.findall(".//assignalias"):
            for node in assign.iter():
                tag = node.tag
                if tag in self.should_not_numbered:
                    pass
                elif tag == "const" and node.getparent().tag == "sel":
                    pass
                elif tag == "varref" and not node.attrib["name"] in sig_set:
                    print("Error: <varref> not on the signal list!  var name = "+node.attrib["name"])
                else:
                    # Add a node
                    node.attrib["node_id"] = str(self.total_node_num)
                    self.insert_graph_node(node)

        print("DONE!")
        print("    Total Node Number = "+str(self.total_node_num))

    def connect_operator(self):
        for assign in self.ast.findall(".//contassign") + self.ast.findall(".//assign") + self.ast.findall(".//assigndly") + self.ast.findall(".//assignalias"):
            for node in assign.getchildren()[0].iter():
                if "node_id" in node.attrib:
                    # There is no different between the input links of these kinds of nodes.
                    if node.tag in self.same_input_link_node:
                        cur_node_id = int(node.attrib["node_id"])
                        for parent_node in node.getchildren():
                            if "node_id" in parent_node.attrib:
                                parent_node_id = int(parent_node.attrib["node_id"])
                                self.insert_graph_edge((cur_node_id, parent_node_id),"")
                            else:
                                print("Parent node without number!")
                    else:
                        # Different Link node
                        if node.tag in self.diff_2_input_link_node:
                            cur_node_id = int(node.attrib["node_id"])
                            parent = node.getchildren()
                            if "node_id" in parent[0].attrib:
                                parent_node_id = int(parent[0].attrib["node_id"])
                                self.insert_graph_edge((cur_node_id, parent_node_id),"left")
                            else:
                                print("Left parent node without number!")
                            if "node_id" in parent[1].attrib:
                                parent_node_id = int(parent[1].attrib["node_id"])
                                self.insert_graph_edge((cur_node_id, parent_node_id),"right")
                            else:
                                print("Right parent node without number!")
                        else:
                            print(node.tag)
        print(self.graph.summary())

    def connect_comb_assign(self):
        for assign in self.ast.findall(".//contassign") + self.ast.findall(".//assign") + self.ast.findall(".//assignalias"):
            parent_id = int(assign.getchildren()[0].attrib["node_id"])
            child_id = int(assign.getchildren()[1].attrib["node_id"])
            self.insert_graph_edge((child_id, parent_id),"")
        print(self.graph.summary())
        
    def connect_block_assign(self):
        for assign in self.ast.findall(".//assigndly"):
            pass
            # TODO

    def graph_construct(self):
        self.modify_ast()
        self.numbering_node()
        self.connect_operator()
        self.connect_comb_assign()


if __name__ == "__main__":
    ast = Verilator_AST_Tree("./ast/Vsha1.xml")

    circuit = AST2CircuitGraph(ast)
    circuit.graph_construct()
