from lxml import etree
import json
import igraph as ig
from Verilator_AST import *
from ASTNodeClassify import *
from copy import deepcopy
import pprint
import pandas as pd

class SimulationError(Exception):
    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        return f"{self.args[0]} (Error Code: {self.error_code})"

class Node:
    def __init__(self,name:str,width:int,value:str,node_type:str,fault_list:dict):
        self.name = name # "Signal_B"
        self.width = width # 5
        self.value = value # "xxxxx"
        self.node_type = node_type # "Wire", "FF_in", "FF_out", "OP"
        self.fault_list = fault_list # {"Signal_A":0.9 , ...}
        self.ready_flag = False
        self.attrib = dict()

    def set_fault_list(self,fault_list:dict):
        self.fault_list = fault_list
    def set_value(self,value:str):
        if "x" in value:
            raise SimulationError("Error: Set X Value",1)
        self.value = value
    def set_attrib(self,attrib:dict):
        for key in attrib.keys():
            self.attrib[key] = attrib[key]
    def get_info(self):
        pprint.pp(self.__dict__)

def gt_propagate_prob_mul_bit(var:str,cnst:str):
    #   var > const
    # !(var <= const)
    width = len(var)
    var_range = pow(2,width)
    if int(var,2) > int(cnst,2):
        prob = float(int(cnst,2) + 1) / float(var_range)
    else:
        prob = float(var_range - int(cnst,2) - 1) / float(var_range)
    return prob


def lt_propagate_prob_mul_bit(var:str,cnst:str):
    #   var < const
    # !(var >= const)
    width = len(var)
    var_range = pow(2,width)
    if int(var,2) < int(cnst,2):
        prob = float(int(cnst,2)) / float(var_range)
    else:
        prob = float(var_range - int(cnst,2)) / float(var_range)
    return prob

def eq_propagate_prob_mul_bit(var:str,cnst:str):
    #   var == const
    # !(var != const)
    width = len(var)
    var_range = pow(2,width)
    if int(var,2) == int(cnst,2):
        prob = float(var_range - 1) / float(var_range)
    else:
        prob = float(1.0) / float(var_range)
    return prob



def verilog_num2num(num:str):
    width = None
    sign = None
    if "'" in num:
        split_num = num.split("'")
        width = split_num[0]
        if "s" in split_num[1]:
            radix = split_num[1][0:2]
            new_num = split_num[1][2:]
            sign = "1"
        else:
            radix = split_num[1][0]
            new_num = split_num[1][1:]
            sign = "0"
        if (radix == "h" or radix == "sh"):
            new_num = str(int(new_num,16))
        elif (radix == "d"):
            new_num = str(int(new_num,10))
        elif (radix == "o"):
            new_num = str(int(new_num,8))
        elif(radix == "b"):
            new_num = str(int(new_num,2))
        else:
            print("Error: Unknown Radix!")
            print(f"    Num = {num}")

    else:
        print("Warning: Not A Verilog Formatted Number.")
        print(f"    Num = {num}")
        new_num = num
    return {"width":width,"val":new_num,"sign":sign}

class AST2Simulator(ASTNodeClassify):
    def __init__(self,ast: etree._ElementTree):
        ASTNodeClassify.__init__(self)
        self._ast = ast
        self.total_node_num = 0
        self.total_var_num = 0

        self.lv_set = set()
        self.varname2varid_map = dict()
        self.varid2varname_map = dict()
        self.lv2treeid_map = dict()
        self.treeid2lv_map = dict()
        self.nodeid2varid_map = dict()

        self.decision_tree_list = list()
        self.scheduled_decision_tree_list = list()

        # Signal Sets
        self.ff_set = set()
        self.input_set = set()

    def build_simulator(self):
        # Check Design
        parser = AST_Parser(self._ast)
        parser.check_simple_design()

        s = "Start Building Simulator"
        print("#"*(len(s)+4))
        print("# "+s+" #")
        print("#"*(len(s)+4))

        # Modifying Attributes
        self.merge_aliased_var()
        self.modify_always_ff()
        self.modify_sel_node()
        self.remove_params()
        self.get_whole_attrib()
        self.get_width()
        
        self.find_lv()
        self.find_input()

        # Modifying Structure
        self.name_circuit_tree()
        self.numbering_circuit_tree()
        self.numbering_var()

        # Check Modified AST
        self.check_modified_ast()
        self.modify_const_node()

        # Scheduling
        self.numbering_circuit_graph_node()
        self.dump_graph_sig_list()
        self.load_node()
        self.load_edge()
        self.schedule_tree()
        self.schedule_node()
        self.output()

    def check_modified_ast(self):
        s = "Check Modified AST"
        print("#"*(len(s)+4))
        print("# "+s+" #")
        print("#"*(len(s)+4))

        self.check_varnum_match_treenum()
        self.check_always_child_num()
        

    def check_varnum_match_treenum(self):
        print("Checking Var Number matches Tree Number")
        if len(self.varname2varid_map) == len(self.decision_tree_list):
            print("Pass: Match!!!")
        else:
            print("Warning: Not Match!!!")
            print(f"    Var Number  = {len(self.varname2varid_map)},")
            print(f"    Tree Number = {len(self.decision_tree_list)}")
            if len(self.varname2varid_map) > len(self.decision_tree_list):
                for v in self.varname2varid_map:
                    if not v in [n["lv_name"] for n in self.decision_tree_list]:
                        print("    >> "+v)
            else:
                for v in [n["lv_name"] for n in self.decision_tree_list]:
                    if not v in self.varname2varid_map:
                        print("    >> "+v)
        print("-"*80)

    def check_always_child_num(self):
        print("Checking each <always> only have 1 child")
        for always in self._ast.findall(".//always_ff") + self._ast.findall(".//always"):
            if len(always.getchildren()) > 1:
                print("     Found <always> with more than 1 child.")
                print(f"    >> {always.attrib['lv_name']}")
        print("-"*80)

    def numbering_circuit_tree(self):
        # Numbering All <always> & <contassign>
        print("Start Numbering RTL Decision Tree...")
        self.total_circuit_tree_num = 0
        for c_tree in self._ast.findall(".//always_ff") + self._ast.findall(".//always") + self._ast.findall(".//contassign"):
            c_tree.attrib["tree_id"] = str(self.total_circuit_tree_num)
            if c_tree.tag == "always_ff":
                tp = "FF"
            else:
                tp = "comb"
            self.decision_tree_list.append( {"tree_id": str(self.total_circuit_tree_num),"lv_name":c_tree.attrib["lv_name"],"type":tp} )
            self.total_circuit_tree_num += 1

        print("    => Total Tree Number = "+str(self.total_circuit_tree_num))
        print("-"*80)

        #pprint.pp(self.decision_tree_list)

    def name_circuit_tree(self):
        print("Start Naming RTL Decision Tree...")
        for always in self._ast.findall(".//always_ff"):
            lv_name = always.find(".//assigndly").getchildren()[1].attrib["name"]
            always.attrib["lv_name"] = lv_name + "(FF_in)"
            varscope = self._ast.find(f".//topscope//varscope[@name='{lv_name}']")
            varscope.attrib["type"] = "FF_out"
            parent = varscope.getparent()
            new_varscope = etree.SubElement(parent, "varscope")
            for key in varscope.attrib:
                new_varscope.attrib[key] = varscope.attrib[key]
            #new_varscope.attrib = varscope.attrib
            new_varscope.attrib["type"] = "FF_in"
            new_varscope.attrib["name"] = lv_name + "(FF_in)"


            for assign in always.findall(".//assigndly"):
                assign.remove(assign.getchildren()[1])

        for always in self._ast.findall(".//always"):
            lv_name = always.find(".//assign").getchildren()[1].attrib["name"]
            always.attrib["lv_name"] = lv_name

            for assign in always.findall(".//assign"):
                assign.remove(assign.getchildren()[1])

        for contassign in self._ast.findall(".//contassign"):
            lv_name = contassign.getchildren()[1].attrib["name"]
            contassign.attrib["lv_name"] = lv_name

            contassign.remove(contassign.getchildren()[1])
        print("Removed LV <varref> under assignments.")
        print("-"*80)
    
    def find_input(self):
        # get comb lv
        for inp in self._ast.findall(".//var[@dir='input']"):
            self.input_set.add(inp.attrib["name"])

    def find_lv(self):
        # get comb lv
        for assign in self._ast.findall(".//always//assign"):
            self.lv_set.add(assign.getchildren()[1].attrib["name"])
        # get FF lv
        for assign in self._ast.findall(".//always_ff//assigndly"):
            self.ff_set.add(assign.getchildren()[1].attrib["name"])
            self.lv_set.add(assign.getchildren()[1].attrib["name"])
        # get wire lv
        for assign in self._ast.findall(".//contassign"):
            self.lv_set.add(assign.getchildren()[1].attrib["name"])

    def modify_sel_node(self):
        print("Modifying <sel>")
        for sel in self._ast.findall(".//sel"):
            start_bit = int(verilog_num2num(sel.getchildren()[1].attrib["name"])["val"])
            width = int(verilog_num2num(sel.getchildren()[2].attrib["name"])["val"])
            end_bit = start_bit + width - 1
            sel.attrib["name"] = f"[{end_bit}:{start_bit}]"
            sel.remove(sel.getchildren()[1])
            sel.remove(sel.getchildren()[1])
            print(f"    Modified <sel> of ({sel.getchildren()[0].attrib['name']})")
        print("-"*80)

    def modify_const_node(self):
        for const in self._ast.findall(".//always_ff//const") + self._ast.findall(".//always//const") + self._ast.findall(".//contassign//const"):
            num_dict = verilog_num2num(const.attrib["name"])
            width = int(num_dict["width"])
            name = int(num_dict["val"])
            name = bin(name).split("b")[-1]
            name = (width - len(name))*"0" + name
            const.attrib["name"] = name
            const.attrib["signed"] = num_dict["sign"]

    def get_whole_attrib(self):
        for always in self._ast.findall(".//always_ff"):
            assign = always.find(".//assigndly")
            dtype_id = assign.getchildren()[1].attrib["dtype_id"]
            for node in always.findall(".//if") + always.findall(".//case"):
                node.attrib["dtype_id"] = dtype_id
        for always in self._ast.findall(".//always"):
            assign = always.find(".//assign")
            dtype_id = assign.getchildren()[1].attrib["dtype_id"]
            for node in always.findall(".//if") + always.findall(".//case"):
                node.attrib["dtype_id"] = dtype_id
        for var in self._ast.findall(".//module//var[@dir='input']"):
            var_name = var.attrib["name"]
            print(var_name)
            varscope = self._ast.find(f".//topscope//varscope[@name='{var_name}']")
            varscope.attrib["type"] = "input"


    def get_width(self):
        print("Getting Width into Node Attribute.")
        for ast_node in self._ast.find(".//topscope//scope").iter():
            if "dtype_id" in ast_node.attrib:
                dtype_id = ast_node.attrib["dtype_id"]
                dtype = self._ast.find(f".//typetable//basicdtype[@id='{dtype_id}']")
                if "left" in dtype.attrib:
                    width = int(dtype.attrib["left"]) - int(dtype.attrib["right"]) + 1
                else:
                    width = 1
                ast_node.attrib["width"] = str(width)
        print("Done.")
        print("-"*80)

    def merge_aliased_var(self):
        print("Start Merging Multi-named Signals...")
        idx = 0
        signal_num_dict = dict()
        signal_merge_dict = dict()
        lv_signal_set = set()
        input_set = set()
        all_signal_set = set()
        signal_buckets = list()
        for var in self._ast.findall(".//var[@dir='input']"):
            if not var.attrib["name"] in signal_num_dict:
                input_set.add(var.attrib["name"])

        for assign in self._ast.findall(".//always//assign") + self._ast.findall(".//always//assigndly") + self._ast.findall(".//contassign"):
            var = assign.getchildren()[1]
            if var.tag != "varref":
                print("Error: LV is not varref.")
                print(var.attrib)
            else:
                lv_signal_set.add(var.attrib["name"])

        all_signal_set = input_set | lv_signal_set

        for assignalias in self._ast.findall(".//topscope//assignalias"):
            v1 = assignalias.getchildren()[0].attrib["name"]
            v2 = assignalias.getchildren()[1].attrib["name"]
            bucket_idx = [i for i,s in enumerate(signal_buckets) if (v1 in s or v2 in s)]
            bucket_idx = bucket_idx if bucket_idx == [] else bucket_idx[0]
            if bucket_idx == []:
                i = len(signal_buckets)
                signal_buckets.append(set())
                signal_buckets[i].add(v1)
                signal_buckets[i].add(v2)
            else:
                signal_buckets[bucket_idx].add(v1)
                signal_buckets[bucket_idx].add(v2)
         
        for i,s in enumerate(signal_buckets):
            main_signal = [v for v in s if v in all_signal_set][0]
            signal_merge_dict[main_signal] = s

        # Merging Node with Same Name
        for main_sig in signal_merge_dict:
            print(f"    Merge: {main_sig} <= {signal_merge_dict[main_sig]}")
            for sig in signal_merge_dict[main_sig]:
                # Remove <varscope>
                if sig != main_sig:
                    varscope = self._ast.find(".//topscope//varscope[@name='"+sig+"']")
                    varscope.getparent().remove(varscope)

                for var in self._ast.findall(".//varref[@name='"+sig+"']"):
                    var.attrib["name"] = main_sig
        
        print("Removing <assignalias> blocks...")
        for assignalias in self._ast.findall(".//topscope//assignalias"):
            v1 = assignalias.getchildren()[0].attrib["name"]
            v2 = assignalias.getchildren()[1].attrib["name"]
            if v1 == v2:
                assignalias.getparent().remove(assignalias)
            else:
                print("Error: Found An Un-merged Node!")
        print("-"*80)

    def modify_always_ff(self):
        print("Start Modifying sequential <always> tag to <always_ff>")
        print("Removing <sentree> under <always_ff>")
        for sentree in self._ast.findall(".//always/sentree"):
            always = sentree.getparent()
            always.tag = "always_ff"
            always.remove(sentree)
        print("-"*80)


    def numbering_var(self):
        print("Start Numbering <varscope> Nodes...")
        for varscope in self._ast.findall(".//topscope//varscope"):
            varscope.attrib["var_id"] = str(self.total_var_num)
            var_name = varscope.attrib["name"]

            # Set var_id to all reference of this signal.
            for varref in self._ast.findall(f".//varref[@name='{var_name}']"):
                varref.attrib["var_id"] = str(self.total_var_num)

            self.varid2varname_map[str(self.total_var_num)] = var_name
            self.varname2varid_map[var_name] = str(self.total_var_num)
            self.total_var_num += 1

        print("    => Total <varscope> Number = "+str(self.total_var_num))
        print("-"*80)

    def remove_params(self):
        print("Start Removing Parameters...")
        for var in self._ast.findall(".//module//var"):
            var_name = var.attrib["name"]
            # Removing Declaration of Parameter
            if ("param" in var.attrib) or ("localparam" in var.attrib):
                for v in self._ast.findall(f".//var[@name='{var_name}']") + self._ast.findall(f".//varscope[@name='{var_name}']"):
                    v.getparent().remove(v)
        print("Done.")
        print("-"*80)
    

    def numbering_circuit_graph_node(self):
        #Numbering Signals
        print("Start Numbering Node that should be included in Circuit Graph...")
        node_num = 0
        for var in self._ast.findall(".//topscope//varscope"):
            var_name = var.attrib["name"]
            var.attrib["node_id"] = str(node_num)
            # Give other reference of this node the same node_id
            for varref in self._ast.findall(f".//varref[@name='{var_name}']"):
                varref.attrib["node_id"] = str(node_num)
            # Give the Circuit Tree Root the same node_id
            if self._ast.find(f".//*[@lv_name='{var_name}']") != None:
                self._ast.find(f".//*[@lv_name='{var_name}']").attrib["node_id"] = str(node_num)
            node_num += 1
        self.var_num = node_num

        # Tree
        for c_tree in self._ast.findall(".//always_ff") + self._ast.findall(".//always") + self._ast.findall(".//contassign"):
            for node in c_tree.iter():
                if not node.tag in self.should_not_numbered and node.tag != "varref":
                    if not (node.tag == "const" and node.getparent().tag == "caseitem"):
                        node.attrib["node_id"] = str(node_num)
                        node_num += 1
        self.node_num = node_num
        print("Done.")
        print(f"    => Total Node Number = {node_num}")

    def dump_graph_sig_list(self):
        sig_dict = {}
        total_sig_num = len(self._ast.findall(".//topscope//varscope"))
        for sig_num in range(total_sig_num):
            var = self._ast.find(f".//topscope//varscope[@node_id='{sig_num}']")
            if not ("type" in var.attrib and var.attrib["type"] == "FF_in"):
                width = int(var.attrib["width"])
                sig_dict[var.attrib["name"]] = width

        f = open("graph_sig_dict.json","w")
        f.write(json.dumps(sig_dict, indent=4))
        f.close()
        

    def load_node(self):
        self.circuit_graph_node = []
        for idx in range(self.var_num):
            var = self._ast.find(f".//varscope[@node_id='{idx}']")
            name = var.attrib["name"]
            width = int(var.attrib["width"])
            value = "x"*width
            if "type" in var.attrib:
                node_type = var.attrib["type"]
            else:
                node_type = "WIRE"
            n_node = Node(
                       name = name,
                       width = width,
                       value = value,
                       node_type = node_type,
                       fault_list = dict()
                     )
            self.circuit_graph_node.append(n_node)

        for idx in range(self.var_num,self.node_num):
            node = self._ast.find(f".//*[@node_id='{idx}']")
            name = node.tag
            width = int(node.attrib["width"])
            if name == "const":
                value = node.attrib["name"]
            else:
                value = "x"*width
            node_type = "OP"
            n_node = Node(
                       name = name,
                       width = width,
                       value = value,
                       node_type = node_type,
                       fault_list = dict()
                     )
            if name == "sel":
                n_node.set_attrib({"bits":node.attrib["name"]})
            self.circuit_graph_node.append(n_node)
        print(f"    Loaded {len(self.circuit_graph_node)} Nodes.")
    
    def load_edge(self):
        self.circuit_graph_edge = []
        edge_cnt = 0
        for c_tree in self._ast.findall(".//always_ff") + self._ast.findall(".//always") + self._ast.findall(".//contassign"):
            for node in c_tree.iter():
                if "node_id" in node.attrib:
                    cur_node_id = int(node.attrib["node_id"])
                    if node.tag == "if":
                        children = node.getchildren()
                        child = children[0]
                        if "node_id" in child.attrib:
                            child_node_id = int(child.attrib["node_id"])
                            self.circuit_graph_edge.append((cur_node_id,"ctrl",child_node_id))
                            edge_cnt += 1
                        else:
                            print(f"Error: Found a node at <if/*[1]> doesn't have node node_id.")
                        # Connect <if> & <if/begin[1]>
                        child = children[1].getchildren()[0]
                        if "node_id" in child.attrib:
                            child_node_id = int(child.attrib["node_id"])
                            self.circuit_graph_edge.append((cur_node_id,"1",child_node_id))
                            edge_cnt += 1
                        elif "assign" in child.tag:
                            child = child.getchildren()[0]
                            child_node_id = int(child.attrib["node_id"])
                            self.circuit_graph_edge.append((cur_node_id,"1",child_node_id))
                            edge_cnt += 1
                        else:
                            print(f"Error: Found a node at <if/begin[1]/assign> doesn't have node node_id.")
                        # Connect <if> & <if/begin[2]>
                        if len(children) == 3:
                            child = children[2].getchildren()[0]
                            if "node_id" in child.attrib:
                                child_node_id = int(child.attrib["node_id"])
                                self.circuit_graph_edge.append((cur_node_id,"0",child_node_id))
                                edge_cnt += 1
                            elif "assign" in child.tag:
                                child = child.getchildren()[0]
                                #print(child.attrib)
                                if "node_id" in child.attrib:
                                    child_node_id = int(child.attrib["node_id"])
                                    self.circuit_graph_edge.append((cur_node_id,"0",child_node_id))
                                    edge_cnt += 1
                                else:
                                    print(f"Warning: Found a node under <if/begin[2]/assign> doesn't have node node_id.")
                            else:
                                print(f"Warning: Found a node under <if/begin[2]> doesn't have node node_id which is not a <assign>.")
                    elif node.tag == "case":
                        children = node.getchildren()
                        child = children[0]
                        # Connect The Control Signal & <case>
                        if "node_id" in child.attrib:
                            child_node_id = int(child.attrib["node_id"])
                            self.circuit_graph_edge.append((cur_node_id,"ctrl",child_node_id))
                            edge_cnt += 1
                        else:
                            print(f"Error: Found a node at <case/*[1]> doesn't have node node_id.")

                        # Connect The <caseitem>s & <case>
                        for caseitem in children[1:]:
                            # When caseitem is not default.
                            if caseitem.getchildren()[0].tag == "const":
                                child = caseitem.getchildren()[-1]
                                if not "node_id" in child.attrib:
                                    child = child.getchildren()[0]
                                child_node_id = int(child.attrib["node_id"])
                                for const in caseitem.getchildren()[:-1]:
                                    self.circuit_graph_edge.append((cur_node_id,const.attrib["name"],child_node_id))
                                    edge_cnt += 1
                            # When caseitem is default.
                            else:
                                child = caseitem.getchildren()[-1]
                                if not "node_id" in child.attrib:
                                    child = child.getchildren()[0]
                                child_node_id = int(child.attrib["node_id"])
                                self.circuit_graph_edge.append((cur_node_id,"default",child_node_id))
                                edge_cnt += 1
                    elif node.tag == "cond":
                        children = node.getchildren()
                        child = children[0]
                        if "node_id" in child.attrib:
                            child_node_id = int(child.attrib["node_id"])
                            self.circuit_graph_edge.append((cur_node_id,"ctrl",child_node_id))
                            edge_cnt += 1
                        else:
                            print(f"Error: Found a node at <cond/*[0]> doesn't have node node_id.")
                        # Connect <cond> & <cond/*[1]>
                        child = children[1]
                        if "node_id" in child.attrib:
                            child_node_id = int(child.attrib["node_id"])
                            self.circuit_graph_edge.append((cur_node_id,"1",child_node_id))
                            edge_cnt += 1
                        else:
                            print(f"Error: Found a node at <cond/*[1]/assign> doesn't have node node_id.")
                        # Connect <cond> & <cond/*[2]>
                        #if len(children) == 3:
                        child = children[2]
                        if "node_id" in child.attrib:
                            child_node_id = int(child.attrib["node_id"])
                            self.circuit_graph_edge.append((cur_node_id,"0",child_node_id))
                            edge_cnt += 1
                        else:
                            print(f"Warning: Found a node under <cond/*[2]> doesn't have node node_id which is not a <assign>.")
                    else:
                        if node.tag in self.diff_2_input_link_node:
                            # Connect Left Parent
                            child = node.getchildren()[0]
                            if "node_id" in child.attrib:
                                child_node_id = int(child.attrib["node_id"])
                                self.circuit_graph_edge.append((cur_node_id,"left",child_node_id))
                                edge_cnt += 1
                            elif "assign" in child.tag:
                                n_child = child.getchildren()[0]
                                if "node_id" in n_child.attrib:
                                    child_node_id = int(n_child.attrib["node_id"])
                                    self.circuit_graph_edge.append((cur_node_id,"assign",child_node_id))
                                    edge_cnt += 1
                                else:
                                    print(f"Warning: Found a node under <always/assign> doesn't have node node_id.")
                            else:
                                print(f"Warning: Found a node under a operator doesn't have node_id which is not an <assign>.")
                            # Connect Right Parent
                            child = node.getchildren()[1]
                            if "node_id" in child.attrib:
                                child_node_id = int(child.attrib["node_id"])
                                self.circuit_graph_edge.append((cur_node_id,"right",child_node_id))
                                edge_cnt += 1
                            elif "assign" in child.tag:
                                n_child = child.getchildren()[0]
                                if "node_id" in n_child.attrib:
                                    child_node_id = int(n_child.attrib["node_id"])
                                    self.circuit_graph_edge.append((cur_node_id,"assign",child_node_id))
                                    edge_cnt += 1
                                else:
                                    print(f"Warning: Found a node under <always/assign> doesn't have node node_id.")
                            else:
                                print(f"Warning: Found a node under a operator doesn't have node_id which is not an <assign>.")
                        else:
                            for child in node.getchildren():
                                if "node_id" in child.attrib:
                                    child_node_id = int(child.attrib["node_id"])
                                    self.circuit_graph_edge.append((cur_node_id,"x",child_node_id))
                                    edge_cnt += 1
                                elif "assign" in child.tag:
                                    n_child = child.getchildren()[0]
                                    if "node_id" in n_child.attrib:
                                        child_node_id = int(n_child.attrib["node_id"])
                                        self.circuit_graph_edge.append((cur_node_id,"assign",child_node_id))
                                        edge_cnt += 1
                                    else:
                                        print(f"Warning: Found a node under <always/assign> doesn't have node node_id.")
                                else:
                                    print(f"Warning: Found a node under a operator doesn't have node_id which is not an <assign>.")
        self.circuit_graph_edge = sorted(self.circuit_graph_edge,key = lambda link: link[0])
        print("Done.")
        print(f"    => Total Edge Number = {edge_cnt}")

    def schedule_tree(self):
        print("Start Scheduling Circuit Trees...")
        self.schedule_ast = deepcopy(self._ast)

        # First Remove All Input Leaves
        for var in list(self.input_set):
            for varref in self.schedule_ast.findall(".//varref[@name='"+var+"']"):
                varref.getparent().remove(varref)
        # First Remove All FF Leaves
        for var in list(self.ff_set):
            for varref in self.schedule_ast.findall(".//varref[@name='"+var+"']"):
                varref.getparent().remove(varref)
        # Move FF Decision Trees into tmp_decision_tree_list_ff
        tmp_decision_tree_list_ff = []
        idx = 0
        while (idx<len(self.decision_tree_list)):
            if self.decision_tree_list[idx]["type"] == "FF":
                tmp_decision_tree_list_ff.append(self.decision_tree_list[idx])
                self.decision_tree_list.remove(self.decision_tree_list[idx])
            else:
                idx += 1

        while (self.decision_tree_list != []):
            new_prepared_tree = list()
            # Go Through decision_tree_list move prepared trees to prepared_decision_tree_list
            for tree_attr in self.decision_tree_list:
                # Find Current Decision Tree in AST
                this_tree = self.schedule_ast.find(".//*[@tree_id='"+tree_attr["tree_id"]+"']")

                # If Prepared, Turn This Tree to Prepared, move this tree to Prepared List
                if this_tree.find(".//varref") is None:
                    new_prepared_tree.append(tree_attr)
                    
            for tree_attr in new_prepared_tree:
                # Remove All of this Node
                for varref in self.schedule_ast.findall(".//varref[@name='"+tree_attr["lv_name"]+"']"):
                    varref.getparent().remove(varref)
            self.scheduled_decision_tree_list += new_prepared_tree
            for tree_attr in new_prepared_tree:
                self.decision_tree_list.remove(tree_attr)

        self.scheduled_decision_tree_list += tmp_decision_tree_list_ff
            
    def schedule_node(self):
        self.scheduled_node_num_list = []
        tail = []
        for var in self.schedule_ast.findall(".//topscope//varscope"):
            if "type" in var.attrib:
                if var.attrib["type"] == "FF_out" or var.attrib["type"] == "input":
                    self.scheduled_node_num_list.append(int(var.attrib["node_id"]))
                if var.attrib["type"] == "FF_in":
                    tail.append(int(var.attrib["node_id"]))
        for tree_info in self.scheduled_decision_tree_list:
            tree_id = tree_info["tree_id"]
            c_tree = self.schedule_ast.find(f".//*[@tree_id='{tree_id}']")
            while (len(c_tree.getchildren()) > 0):
                for node in c_tree.iter():
                    if len(node.getchildren()) == 0:
                        if "node_id" in node.attrib:
                            node_id = int(node.attrib["node_id"])
                            if not node_id in self.scheduled_node_num_list:
                                self.scheduled_node_num_list.append(node_id)
                                node.getparent().remove(node)
                                break
                            else:
                                print("Error: Found Repeated Node When Scheduling.")
                                print(f"    Node ID = {node_id}.")
                                print(f"    Node Tag = {node.tag}.")
                        else:
                            node.getparent().remove(node)
            self.scheduled_node_num_list.append(int(c_tree.attrib["node_id"]))
        if len(self.scheduled_node_num_list) != len(self.circuit_graph_node):
            print("Error: scheduled node number != circuit graph node.")
        else:
            print("Pass: scheduled node number == circuit graph node.")

    def get_circuit_graph(self):
        return (self.circuit_graph_node, self.circuit_graph_edge)
    def get_node_order(self):
        return self.scheduled_node_num_list
    def get_signal_table(self):
        signal_table = dict()
        for var in self._ast.findall(".//topscope//varscope"):
            signal_table[var.attrib["name"]] = {"width":var.attrib["width"],"node_id":var.attrib["node_id"]}
        #pprint.pp(list(signal_table.keys()))
        return signal_table

    def output(self):
        with open("output.xml","wb") as fp:
            fp.write(etree.tostring(self._ast.find(".")))


class Simulator(ASTNodeClassify):
    def __init__(self):
        ASTNodeClassify.__init__(self)
        ast = Verilator_AST_Tree("./ast/Vsha1.xml")
        sim = AST2Simulator(ast)
        sim.build_simulator()
        self.circuit_graph_node, self.circuit_graph_edge = sim.get_circuit_graph()
        self.circuit_graph_edge_grouped = [None]*len(self.circuit_graph_node)
        cur_id = None
        cur_edges = []
        for edge in self.circuit_graph_edge:
            if cur_id == edge[0]:
                cur_edges.append(edge)
            else:
                if cur_id != None:
                    self.circuit_graph_edge_grouped[cur_id] = cur_edges
                cur_id = edge[0]
                cur_edges = [edge]
        self.circuit_graph_edge_grouped[cur_id] = cur_edges

        self.scheduled_node_num_list = sim.get_node_order()
        self.signal_table = sim.get_signal_table()
        self.cycle = 207

    def _load_logic_value(self):
        f = open("graph_sig_dict.json","r")
        self.sig_dict = json.load(f)
        f.close()
        self.sig_dict.pop("clk")
        self.unknown_sig_list = [sig for sig in self.sig_dict.keys() if "__Vdfg" in sig]
        for sig in self.unknown_sig_list:
            self.sig_dict.pop(sig)

        f = open(f"../sha1/run_graph/pattern/FaultFree_Signal_Value_C{self.cycle:05}.txt","r")
        logic_values = f.readlines()
        for i,v in enumerate(logic_values):
            logic_values[i] = logic_values[i].replace("\n","")
        f.close()
        # Loading Logic Values
        for idx, sig in enumerate(self.sig_dict.keys()):
            width = int(self.signal_table[sig]["width"])
            node_id = int(self.signal_table[sig]["node_id"])
            if self.circuit_graph_node[node_id].width != width:
                # Check the Loaded Value Has Correct Width
                print("Error: width incorrect!!!")
            else:
                if self.circuit_graph_node[node_id].node_type == "FF_out":
                    sig_name = self.circuit_graph_node[node_id].name
                    self.circuit_graph_node[node_id].set_fault_list({sig_name:1.0})
                self.circuit_graph_node[node_id].value = logic_values[idx]
                self.circuit_graph_node[node_id].ready_flag = True

    def _compute(self,node_id):
        name = self.circuit_graph_node[node_id].name
        edges = self.circuit_graph_edge_grouped[node_id]
        width = self.circuit_graph_node[node_id].width
        if name in self.sim_commutable_2in_op:
            a_id = edges[0][2]
            b_id = edges[1][2]
            a = self.circuit_graph_node[a_id].value
            b = self.circuit_graph_node[b_id].value
            # Check if all inputs are ready.
            if not (self.circuit_graph_node[a_id].ready_flag and self.circuit_graph_node[b_id].ready_flag):
                raise SimulationError(f"Error: Scheduling Incorrect. NODE_ID = {node_id}, OP_NAME = {name}",2)
           
            if name in {'xor','and','or','add','eq'}:
                if len(a) != len(b):
                    raise SimulationError(f"Error: Input Widths Don't Match. NODE_ID = {node_id}, OP_NAME = {name}",1)
            elif name in {'logor','logand'}:
                pass
            else:
                raise SimulationError(f"Error: Unrecognized OP Node! Node Name = {name}",1)

            # Compute OP Result
            if "x" in a or "x" in b:
                result = "x"*width
            elif "z" in a or "z" in b:
                result = "z"*width
            else:
                if name == 'xor':
                    result = int(a, 2) ^ int(b, 2)
                    result = f"{result:0{len(a)}b}"
                elif name == 'and':
                    result = int(a, 2) & int(b, 2)
                    result = f"{result:0{len(a)}b}"
                elif name == 'or':
                    result = int(a, 2) | int(b, 2)
                    result = f"{result:0{len(a)}b}"
                elif name == 'add':
                    result = int(a, 2) + int(b, 2)
                    result = f"{result:0{width}b}"
                    if self.circuit_graph_node[node_id].width != len(result):
                        result = result[len(result)-width:]
                elif name == 'eq':
                    result = "1" if a == b else "0"
                elif name == 'logor':
                    a = "1" if "1" in a else "0"
                    b = "1" if "1" in b else "0"
                    result = int(a,2) | int(b,2)
                    result = f"{result:0{width}b}"
                elif name == 'logand':
                    a = "1" if "1" in a else "0"
                    b = "1" if "1" in b else "0"
                    result = int(a,2) & int(b,2)
                    result = f"{result:0{width}b}"

            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name in self.sim_not_commutable_2in_op:
            a_id = [edge[2] for edge in edges if edge[1] == "left"][0]
            b_id = [edge[2] for edge in edges if edge[1] == "right"][0]
            a = self.circuit_graph_node[a_id].value
            b = self.circuit_graph_node[b_id].value
            if not (self.circuit_graph_node[a_id].ready_flag and self.circuit_graph_node[b_id].ready_flag):
                raise SimulationError(f"Error: Scheduling Incorrect. NODE_ID = {node_id}, OP_NAME = {name}",2)
            if "x" in a or "x" in b:
                result = "x"*width
            elif "z" in a or "z" in b:
                result = "z"*width
            else:
                if name == 'gt':
                    result = "1" if int(a,2) > int(b,2) else "0"
                elif name == 'gte':
                    result = "1" if int(a,2) >= int(b,2) else "0"
                elif name == 'lt':
                    result = "1" if int(a,2) < int(b,2) else "0"
                elif name == 'lte':
                    result = "1" if int(a,2) <= int(b,2) else "0"
                elif name == 'concat':
                    result = a + b
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name in self.sim_1in_op:
            a_id = edges[0][2]
            a = self.circuit_graph_node[a_id].value
            if name == 'extend':
                result = "0"*(width - len(a)) + a
            elif name == 'not':
                mask = "1"*len(a)
                result = int(a,2) ^ int(mask,2)
                result = f"{result:0{width}b}"
            elif name == 'sel':
                bits = self.circuit_graph_node[node_id].attrib["bits"]
                bits = bits[1:-1].split(":")
                l_bit = int(bits[0])
                r_bit = int(bits[1])
                if l_bit == r_bit:
                    result = a[-1 - l_bit]
                elif r_bit == 0:
                    result = a[len(a)-1-l_bit:]
                else:
                    result = a[len(a)-1-l_bit:0-r_bit]
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name == 'const':
            self.circuit_graph_node[node_id].ready_flag = True
            return
        elif name == 'if':
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            if "x" in ctrl:
                ctrl = "x"
            elif "z" in ctrl:
                raise SimulationError(f"Error: ctrl = '{ctrl}'. NODE_ID = {node_id}, OP_NAME = {name}",2)
            else:
                ctrl = "1" if "1" in ctrl else "0"
            if "x" in ctrl:
                result = "x"*width
            else:
                tmp_edges = [edge[2] for edge in edges if edge[1] == ctrl]
                if tmp_edges == []: # The <if> is not fullcase
                    result = "z"*width
                    self._check_result_width(width,len(result))
                    self.circuit_graph_node[node_id].set_value(result)
                    self.circuit_graph_node[node_id].ready_flag = True
                    return
                src_id = [edge[2] for edge in edges if edge[1] == ctrl][0]
                result = self.circuit_graph_node[src_id].value
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name == 'case':
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            if "x" in ctrl:
                result = "x"*width
            elif "z" in ctrl:
                raise SimulationError(f"Error: ctrl = '{ctrl}'. NODE_ID = {node_id}, OP_NAME = {name}",2)
            else:
                tmp_edges = [edge[2] for edge in edges if edge[1] == ctrl]
                if tmp_edges == []:
                    tmp_edges = [edge[2] for edge in edges if edge[1] == "default"]
                    if tmp_edges == []: # The <case> is not fullcase
                        result = "z"*width
                        self._check_result_width(width,len(result))
                        self.circuit_graph_node[node_id].set_value(result)
                        self.circuit_graph_node[node_id].ready_flag = True
                        return
                src_id = tmp_edges[0]
                result = self.circuit_graph_node[src_id].value
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name == 'cond':
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            if "x" in ctrl:
                ctrl = "x"
            else:
                ctrl = "1" if "1" in ctrl else "0"

            if "x" in ctrl:
                result = "x"*width
            else:
                src_id = [edge[2] for edge in edges if edge[1] == ctrl][0]
                result = self.circuit_graph_node[src_id].value
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        else:
            self.circuit_graph_node[node_id].ready_flag = True
            print(f"Error: Unrecognized OP Node! Node Name = {name}")

    def _assign(self,node_id):
        name = self.circuit_graph_node[node_id].name
        edges = self.circuit_graph_edge_grouped[node_id]
        i_node_id = edges[0][2]
        value = self.circuit_graph_node[i_node_id].value
        if "x" in self.circuit_graph_node[node_id].value:
            self.circuit_graph_node[node_id].set_value(value)
        else:
            if self.circuit_graph_node[i_node_id].value != value:
                print("Warning: Computed Signal Values Don't Match Dumped Signal Values")
        self.circuit_graph_node[node_id].ready_flag = True
        if len(edges) != 1:
            raise SimulationError("Error: Signal assignment should only has 1 input.",1)

    def _check_result_width(self,a:int,b:int):
        if a != b:
            raise SimulationError("Error: Result Widths Don't Match.",1)
    
    def _sig_fault_propagate(self,node_id):
        edges = self.circuit_graph_edge_grouped[node_id]
        n_fault_list = {}
        src_node_ids = [edge[2] for edge in edges]
        for src_id in src_node_ids:
            src_fault_list = self.circuit_graph_node[src_id].fault_list
            for key in src_fault_list:
                n_fault_list[key] = src_fault_list[key]
        self.circuit_graph_node[node_id].set_fault_list(n_fault_list)

    def _op_fault_propagate(self,node_id):
        name = self.circuit_graph_node[node_id].name
        edges = self.circuit_graph_edge_grouped[node_id]
        n_fault_list = {}
        if name in {"if","cond","case"}:
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            tmp_edges = [edge[2] for edge in edges if edge[1] == ctrl]
            if tmp_edges == []:
                tmp_edges = [edge[2] for edge in edges if edge[1] == "default"]
            if tmp_edges == []:
                pass
            else:
                src_id = tmp_edges[0]
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = src_fault_list[key]
            ctrl_fault_list = self.circuit_graph_node[ctrl_id].fault_list
            for key in ctrl_fault_list:
                n_fault_list[key] = ctrl_fault_list[key]
        elif name == "const":
            pass
        else:
            src_node_ids = [edge[2] for edge in edges]
            for src_id in src_node_ids:
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = src_fault_list[key]
        self.circuit_graph_node[node_id].set_fault_list(n_fault_list)

    def _op_prob_fault_propagate(self,node_id):
        name = self.circuit_graph_node[node_id].name
        width = self.circuit_graph_node[node_id].width
        edges = self.circuit_graph_edge_grouped[node_id]
        if name in self.prob_always_prop:
            n_fault_list = {}
            prob = 1.0
            src_node_ids = [edge[2] for edge in edges]
            for src_id in src_node_ids:
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = src_fault_list[key] * prob
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)
        elif name == "const":
            pass
        elif name in {"if","cond","case"}: 
            n_fault_list = {}
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            tmp_edges = [edge[2] for edge in edges if edge[1] == ctrl]
            if tmp_edges == []:
                tmp_edges = [edge[2] for edge in edges if edge[1] == "default"]
            if tmp_edges == []:
                pass
            else:
                src_id = tmp_edges[0]
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = src_fault_list[key]
            ctrl_fault_list = self.circuit_graph_node[ctrl_id].fault_list
            for key in ctrl_fault_list:
                n_fault_list[key] = ctrl_fault_list[key]
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)

        elif name == "and":
            num_of_1 = self.circuit_graph_node[node_id].value.count("1")
            prob = float(num_of_1) / float(width)
            src_node_ids = [edge[2] for edge in edges]
            n_fault_list = {}
            for src_id in src_node_ids:
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = src_fault_list[key] * prob
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)
        elif name == "or":
            num_of_0 = self.circuit_graph_node[node_id].value.count("0")
            prob = float(num_of_0) / float(width)
            src_node_ids = [edge[2] for edge in edges]
            n_fault_list = {}
            for src_id in src_node_ids:
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = src_fault_list[key] * prob
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)

        elif name == "logand":
            n_fault_list = {}
            if self.circuit_graph_node[node_id].value == "1":
                src_node_ids = [edge[2] for edge in edges]
                for src_id in src_node_ids:
                    if self.circuit_graph_node[src_id].value.count("1") == 1:
                        prob = 1.0 / float(self.circuit_graph_node[src_id].width)
                    else:
                        continue
                    src_fault_list = self.circuit_graph_node[src_id].fault_list
                    for key in src_fault_list:
                        n_fault_list[key] = src_fault_list[key] * prob
            else:
                prob = 1.0
                src_node_ids = [edge[2] for edge in edges]
                for src_id in src_node_ids:
                    src_fault_list = self.circuit_graph_node[src_id].fault_list
                    for key in src_fault_list:
                        n_fault_list[key] = src_fault_list[key] * prob
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)
        elif name == "logor":
            n_fault_list = {}
            if self.circuit_graph_node[node_id].value == "0":
                prob = 1.0
                src_node_ids = [edge[2] for edge in edges]
                for src_id in src_node_ids:
                    if self.circuit_graph_node[src_id].value.count("1") == 1:
                        prob = 1.0 / float(self.circuit_graph_node[src_id].width)
                    else:
                        continue
                    src_fault_list = self.circuit_graph_node[src_id].fault_list
                    for key in src_fault_list:
                        n_fault_list[key] = src_fault_list[key] * prob
            else:
                prob = 1.0
                src_node_ids = [edge[2] for edge in edges]
                for src_id in src_node_ids:
                    src_fault_list = self.circuit_graph_node[src_id].fault_list
                    for key in src_fault_list:
                        n_fault_list[key] = src_fault_list[key] * prob
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)

        elif name in {"gt","lt","gte","lte"}:
            src_node_ids = [edge[2] for edge in edges]
            if "const" in [self.circuit_graph_node[node_id].name for node_id in src_node_ids]: # 1 Variable Compare
                const_node_id = [node_id for node_id in src_node_ids if self.circuit_graph_node[node_id].name == "const"][0]
                var_node_id = [node_id for node_id in src_node_ids if self.circuit_graph_node[node_id].name != "const"][0]
                right_id = [edge[2] for edge in edges if edge[1] == "right"][0]
                left_id = [edge[2] for edge in edges if edge[1] == "left"][0]
                var_value = self.circuit_graph_node[var_node_id].value
                cnst_value = self.circuit_graph_node[const_node_id].value
                if left_id == var_node_id: # output = var ? const
                    if name in {"gt","lte"}:
                        prob = gt_propagate_prob_mul_bit(var_value,cnst_value)
                    else:
                        prob = lt_propagate_prob_mul_bit(var_value,cnst_value)
                else:                      # output = const ? var
                    if name in {"lt","gte"}:
                        prob = gt_propagate_prob_mul_bit(var_value,cnst_value)
                    else:
                        prob = lt_propagate_prob_mul_bit(var_value,cnst_value)
            else:
                raise SimulationError("Error: Comparator has not only 1 variable input.")
        elif name == "eq":
            src_node_ids = [edge[2] for edge in edges]
            if "const" in [self.circuit_graph_node[node_id].name for node_id in src_node_ids]: # 1 Variable Compare
                const_node_id = [node_id for node_id in src_node_ids if self.circuit_graph_node[node_id].name == "const"][0]
                var_node_id = [node_id for node_id in src_node_ids if self.circuit_graph_node[node_id].name != "const"][0]
                var_value = self.circuit_graph_node[var_node_id].value
                cnst_value = self.circuit_graph_node[const_node_id].value
                prob = eq_propagate_prob_mul_bit(var_value,cnst_value)
            else:
                raise SimulationError("Error: Comparator has not only 1 variable input.")
        elif name == "sel":
            src_id = edges[0][2]
            width_a = self.circuit_graph_node[src_id].width
            prob = float(width)/float(width_a)
            src_fault_list = self.circuit_graph_node[src_id].fault_list
            n_fault_list = {}
            for key in src_fault_list:
                n_fault_list[key] = src_fault_list[key] * prob
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)
        else:
            print(f"Probability Calculation Error: Unrecognized OP Node! Node Name = {name}")


    def simulate(self):
        print("=======================================")
        print(" Start Simulating Fault Propagation...")
        # Simulation Loop
        op_set = set()
        scheduled_node_num_list = self.scheduled_node_num_list[1:]
        cnt = 0
        cur_cyc_fault_list = {}
        #for node in self.circuit_graph_node:
        #    print(node,node.node_type)
        for node_id in scheduled_node_num_list:
            cnt +=1
            if self.circuit_graph_node[node_id].node_type in {"FF_out","input"}:
                # Check FF_out
                if self.circuit_graph_node[node_id].ready_flag:
                    pass
                else:
                    raise SimulationError("Warning: input FF not be set",1)
            elif self.circuit_graph_node[node_id].node_type == "OP":
                self._compute(node_id)
                #self._op_fault_propagate(node_id)
                self._op_prob_fault_propagate(node_id)
            else:
                self._assign(node_id)
                self._sig_fault_propagate(node_id)

            if self.circuit_graph_node[node_id].node_type == "FF_in":
                cur_cyc_fault_list[self.circuit_graph_node[node_id].name] = self.circuit_graph_node[node_id].fault_list
        
        fault_effect_dict = {}
        for dst_reg in cur_cyc_fault_list.keys():
            for src_reg in cur_cyc_fault_list[dst_reg]:
                prob = cur_cyc_fault_list[dst_reg][src_reg]
                if not src_reg in fault_effect_dict:
                    fault_effect_dict[src_reg] = [(dst_reg.replace("(FF_in)",""),prob)]
                else:
                    fault_effect_dict[src_reg].append((dst_reg.replace("(FF_in)",""),prob))
        cur_cyc_rw_events = []
        for (key, item) in fault_effect_dict.items():
            cur_cyc_rw_events.append({"r":key, "w":item})

        print(" Simulation Finish.")
        print("=======================================")
        return cur_cyc_rw_events

    def seq_simulate(self):
        self.rw_table_cycle_col = []
        self.rw_table_event_col = []

        for cyc in range(1037):
            self.cycle = cyc
            self._load_logic_value()
            self.rw_table_event_col.append(self.simulate())
            self.rw_table_cycle_col.append(cyc)

    def dump_rw_table(self):
        df = pd.DataFrame({"cycle":self.rw_table_cycle_col, "rw_event":self.rw_table_event_col})
        df.to_csv("prob_rw_table.csv")

    def single_cycle_simulate(self,cyc:int):
        self.cycle = cyc
        self._load_logic_value()
        self.simulate()

if __name__ == "__main__":

    sim = Simulator()
    sim.seq_simulate()
    sim.dump_rw_table()
