from lxml import etree
import igraph as ig
from Verilator_AST import *
from ASTNodeClassify import *
from copy import deepcopy
import pprint

class Node:
    def __init__(self,name:str,width:int,value:str,node_type:str,fault_list:dict):
        self.name = name # "Signal_B"
        self.width = width # 5
        self.value = value # "xxxxx"
        self.node_type = node_type # "Wire", "FF_in", "FF_out", "OP"
        self.fault_list = fault_list # {"Signal_A":0.9 , ...}


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
            value = "x"*width
            node_type = "OP"
            n_node = Node(
                       name = name,
                       width = width,
                       value = value,
                       node_type = node_type,
                       fault_list = dict()
                     )
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
                                self.circuit_graph_edge.append((cur_node_id,"1",child_node_id))
                                edge_cnt += 1
                            elif "assign" in child.tag:
                                child = child.getchildren()[0]
                                #print(child.attrib)
                                if "node_id" in child.attrib:
                                    child_node_id = int(child.attrib["node_id"])
                                    self.circuit_graph_edge.append((cur_node_id,"1",child_node_id))
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
                                self.circuit_graph_edge.append((cur_node_id,const.attrib["name"],child_node_id))
                                edge_cnt += 1
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
        #pprint.pp(self.circuit_graph_edge)
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
        #pprint.pp(self.scheduled_decision_tree_list)
            
    def schedule_node(self):
        self.scheduled_node_num_list = []
        tail = []
        for var in self.schedule_ast.findall(".//topscope//varscope"):
            if "type" in var.attrib:
                if var.attrib["type"] == "FF_out" or var.attrib["type"] == "input":
                    self.scheduled_node_num_list.append(int(var.attrib["node_id"]))
                if var.attrib["type"] == "FF_in":
                    tail.append(int(var.attrib["node_id"]))
        #pprint.pp(self.scheduled_node_num_list)
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

    def output(self):
        with open("output.xml","wb") as fp:
            fp.write(etree.tostring(self._ast.find(".")))


class Simulator:
    pass

if __name__ == "__main__":
    ast = Verilator_AST_Tree("./ast/Vsha1.xml")

    sim = AST2Simulator(ast)
    sim.build_simulator()

    sim.get_circuit_graph()
    sim.get_node_order()
