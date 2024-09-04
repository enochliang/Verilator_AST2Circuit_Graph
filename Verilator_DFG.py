import graphviz
import re
import igraph as ig

def get_outer_bracket(string:str) -> str:
    new_string = ""
    flag = 0
    for c in string:
        if flag < 0:
            raise "Error: flag < 0"

        if c == "[":
            flag = flag + 1
        elif c == "]":
            flag = flag - 1

        if flag > 0:
            if flag == 1 and c == "[":
                continue
            new_string = new_string + c
    return new_string.strip()

def split_comma(string:str) -> list:
    return [element.strip() for element in string.split(",")]

def parse_key_n_val(string:str):
    kv = string.split("=")
    return kv[0], kv[1]

def split_node_id_n_attr(node_line:str):
    node_id = node_line.split(" ")[0]
    node_attr = node_line.replace(node_id+" ","")
    return node_id, node_attr

class Verilator_dot_DFG_Parser():
    def __init__(self,dot_file_path:str):
        self.node_dict = {}
        self.edge_dict = {}
        self.node_id_to_num_dict = {}
        self.edge_num_list = []
        self.node_type = []
        self.sig_name = []
        self.op_type = []
        self._load_dot(dot_file_path)
        self._load_attr()
    def _load_dot(self,dot_file_path:str):
        graph_txt = open(dot_file_path, "r").read()
        new_graph_txt = ""
        flag = 0
        for c in graph_txt:
            if flag < 0:
                raise "Error: flag < 0"
            if c == "[":
                flag = flag + 1
            elif c == "]":
                flag = flag - 1
            if flag != 0 and c == "\n":
                new_graph_txt = new_graph_txt + " "
            else:
                new_graph_txt = new_graph_txt + c
        graph_txt = new_graph_txt
        # Get the Content within Braces.
        new_graph_txt = ""
        flag = 0
        for line in graph_txt.split("\n"):
            if flag < 0:
                raise "Error: flag < 0"

            if "{" in line:
                flag = flag + 1
                continue
            elif "}" in line:
                flag = flag - 1
                continue
            if flag > 0:
                new_graph_txt = new_graph_txt + line + "\n"
        graph_txt = new_graph_txt
        del new_graph_txt
        # Parse the .dot file
        # There should only be two kinds of lines. They should be node & edge.
        node_lines = []
        edge_lines = []
        node_dict = {}
        edge_dict = {}
        for line in graph_txt.split("\n"):
            if "->" in line:
                edge_lines.append(line)
            else:
                if line != "":
                    node_lines.append(line)
        for node_line in node_lines:
            node_id, node_attr_txt = split_node_id_n_attr(node_line)
            node_id = node_id.replace('"',"")
            node_dict[node_id] = {}
            attr_list = split_comma(get_outer_bracket(node_attr_txt))
            for attr in attr_list:
                key, val = parse_key_n_val(attr)
                node_dict[node_id][key] = val.replace('"','')
        for edge_line in edge_lines:
            line = [ele.strip() for ele in edge_line.split("->")]
            src = line[0].replace('"',"")
            dst = line[1].replace('"',"")
            e_type = None
            if " [" in dst:
                e_type = get_outer_bracket(dst.split(" ")[1])
                dst = dst.split(" ")[0]
            if e_type == None:
                edge_dict[(src,dst)] = None
            else:
                key, val = parse_key_n_val(e_type)
                edge_dict[(src,dst)] = {key:val.replace('"',"")}
        node_id_to_num_dict = {}
        num = 0
        for node in node_dict.keys():
            node_id_to_num_dict[node] = num
            num = num + 1
        edge_num_list = []
        for edge in edge_dict.keys():
            edge_num_list.append((node_id_to_num_dict[edge[0]], node_id_to_num_dict[edge[1]]))
        self.node_dict = node_dict
        self.edge_dict = edge_dict
        self.node_id_to_num_dict = node_id_to_num_dict
        self.edge_num_list = edge_num_list

    # Node Attribute
    def _load_attr(self):
        # Node Type
        node_type = [None]*len(self.node_dict)
        for node in self.node_dict.keys():
            if "shape" in self.node_dict[node].keys():
                shape = self.node_dict[node]["shape"]
                if shape == "circle":
                    node_type[self.node_id_to_num_dict[node]] = "op"
                elif shape == "box":
                    node_type[self.node_id_to_num_dict[node]] = "sig"
        self.node_type = node_type

        # Signal Name
        sig_name = [None]*len(self.node_dict)
        for node in self.node_dict.keys():
            if "shape" in self.node_dict[node].keys():
                shape = self.node_dict[node]["shape"]
                if shape == "box":
                    label = self.node_dict[node]["label"]
                    sig_name[self.node_id_to_num_dict[node]] = label.split(" ")[0].replace("__DOT__",".").replace("__BRA__","[").replace("__KET__","]")
        self.sig_name = sig_name
        
        # OP Name
        op_type = [None]*len(self.node_dict)
        for node in self.node_dict.keys():
            if "shape" in self.node_dict[node].keys():
                shape = self.node_dict[node]["shape"]
                if shape == "circle":
                    label = self.node_dict[node]["label"]
                    op_type[self.node_id_to_num_dict[node]] = label.split(" ")[0]
        self.op_type = op_type

#class Verilator_DFG_Graph(ig.Graph):
#    def __init__(self):
#        super()



# Load Graph Structures and Attributes into iGraph object.
def Verilator_DFG_Graph(dot_file_path:str) -> ig.Graph:
    dot = Verilator_dot_DFG_Parser(dot_file_path)
    g = ig.Graph(n=len(dot.node_dict), edges=dot.edge_num_list,directed=True)
    g.vs["node_type"] = dot.node_type
    g.vs["sig_name"] = dot.sig_name
    g.vs["op_type"] = dot.op_type

    return g


if __name__ == "__main__":
    g = Verilator_DFG_Graph("Vibex_top_1540___024root-postinline-whole-input.dot")

    print(g.average_path_length())
    
    cnt = {}
    for op in g.vs["op_type"]:
        if not op in cnt.keys():
            cnt[op] = 1
        else:
            cnt[op] = cnt[op] + 1
    print(cnt)

