from lxml import etree
import pprint 
pp = pprint.PrettyPrinter(indent=4)

class AST_Parser:
    def __init__(self, ast: etree._ElementTree):
       self.ast = ast
       self.signal_list = None

    def get_all_signal(self,output=True):
        # Make a List of All Signals Including WIRE & Flip-Flop.
        signals = set()
        for var in self.ast.findall(".//assignalias//*[2]") + self.ast.findall(".//contassign//*[2]") + self.ast.findall(".//always//assign//*[2]") + self.ast.findall(".//always//assigndly//*[2]"):
            if var.tag != "varref":
                print("Error: LV is not a varref.")
                print("    Tag: "+var.tag)
            else:
                signals.add(var.attrib["name"])
        if output:
            print("Print All Signals Including WIRE & Flip-Flop...")
            for sig in signals:
                print("  "+sig)
        return signals


    def check_dtype(self,output=True) -> set:
        # Make a List of Packed dtype That Doesn't Start With Zero Bit.
        dtypes = set()
        for dtype in self.ast.findall(".//basicdtype"):
            if "right" in dtype.attrib:
                if not dtype.attrib["right"] == "0":
                    dtypes.add((("id",dtype.attrib["id"]),("left",dtype.attrib["left"]),("right",dtype.attrib["right"])))
        if output:
            print("Print Packed dtype That Doesn't Start With Zero Bit.")
            for dtype in dtypes:
                print(dtype)
        return dtypes


    def get_dtypetable_as_dict(self,output=True) -> dict:
        dtypes_dict = dict()
        for node in self.ast.find(".//typetable").getchildren():
            if node.tag == "voiddtype":
                continue
            if "name" in node.attrib:
                if node.attrib["id"] in dtypes_dict.keys():
                    raise Exception("Repeated dtype_id!")
                dtypes_dict[node.attrib["id"]] = node.attrib["name"]
            basic_node = self._search_basic_dtype(node)
            dtypes_dict[node.attrib["id"]] = basic_node.attrib["name"]
        if output:
            print("Dtypetable Dictionary:")
            for dtype in dtypes_dict.items():
                print("  "+str(dtype))
        return dtypes_dict

    def _search_basic_dtype(self,node):
        if node.tag == "structdtype":
            return self._search_basic_dtype(node.getchildren()[0])
        else:
            if "sub_dtype_id" in node.attrib:
                ref_id = node.attrib["sub_dtype_id"]
                next_node = self.ast.find(".//typetable/*[@id='"+ref_id+"']")
                return self._search_basic_dtype(next_node)
            else:
                return node

    def get_n_logic_dtype(self,output=True) -> set:
        # Get the List Dtypes That is Not a Logic or Bit.
        n_logic_dtypes = set()
        for dtype in self.ast.findall(".//typetable//basicdtype"):
            if dtype.attrib["name"] == "logic":
                pass
            elif dtype.attrib["name"] == "bit":
                pass
            else:
                n_logic_dtypes.add(dtype.attrib["name"])
        #for dtype in self.ast.findall(".//typetable//basicdtype"):
        if output:
            for dtype in n_logic_dtypes:
                print(dtype)


    def get_sig_nodes(self,output=True) -> set:
        var_set = set()
        dtype_dict = self.get_dtypetable_as_dict(output=False)
        for var in self.ast.findall(".//module//var"):
            if "param" in var.attrib:
                pass
            elif "localparam" in var.attrib:
                pass
            else:
                dtype = dtype_dict[var.attrib["dtype_id"]]
                if dtype == "int" or dtype == "integer":
                    pass
                else:
                    var_set.add(var.attrib['name'])
        if output:
            for var in var_set:
                print(var)
        return var_set

    def get_all_tags_under(self,target="verilator_xml",output=True) -> set:
        # Make a List of All Kinds of Tags.
        tags = set()
        target_nodes = self.ast.findall(".//"+target)
        if target_nodes:
            for t_node in target_nodes:
                for node in t_node.iter():
                    tags.add(node.tag)
            if output:
                print("get all tags under <"+target+">:")
                for tag in tags:
                    print("  <"+tag+">")
        return tags

    def get_unique_children_under(self,target="verilator_xml",output=True) -> list:
        # Make a List of All Kinds of Tags.
        children = []
        children = self.get_ordered_children_under(target,False)
        children_set = set()
        for ls in children:
            for c in ls:
                children_set.add(c)
        if output:
            pprint.pp(children_set)
        return children_set
    def get_ordered_children_under(self,target="verilator_xml",output=True) -> list:
        # Make a List of All Kinds of Tags.
        childrens = []
        target_nodes = self.ast.findall(".//"+target)
        if target_nodes:
            for t_node in target_nodes:
                children = []
                for node in t_node.getchildren():
                    children.append(node.tag)
                if not children in childrens:
                    childrens.append(children)
            if output:
                print("get ordered children under <"+target+">:")
                for c in childrens:
                    print("  "+str(c))
        return childrens

    def check_tag_all_x_are_under_y(self,x:str,y:str):
        target_nodes = self.ast.findall(".//"+x)
        flag = False
        for x_node in target_nodes:
            if not y in self.ast.getpath(x_node):
                print("Found a <"+x+"> not under <"+y+">")
                flag = True
        if not flag:
            print("ALL <"+x+"> are under <"+y+">")


    def _check_sel_no_muxdec(self):
        print("Start Checking No MUX or DEC in <sel>...")
        flag = False
        for sel in self.ast.findall(".//sel"):
            if not [c.tag for c in sel.getchildren()] == ["varref","const","const"]:
                print("  Warning: Found a <sel> with MUX or DEC!")
                flag = True
        if not flag:
            print("Pass: No MUX or DEC in <sel>")
        print("-"*80)


    def _check_lv_single_var(self):
        """Check all left value of assignment. 
        All of them should be a single <varref> on the left."""
        print("Start Checking Left Side of Assignment is A Single <varref>...")
        assignments = self.ast.findall(".//assign") + self.ast.findall(".//assigndly") + self.ast.findall(".//contassign")
        flag = False
        for assign in assignments:
            tag = assign.getchildren()[1].tag
            if not tag == "varref":
                print("  Warning: Found a Left Value Not a Single <varref>!")
                print("    Tag = "+tag)
                print(assign.getchildren()[1].getchildren()[0].attrib["name"])
                flag = True
        if not flag:
            print("Pass: All Left Values are Single <varref>")
        print("-"*80)


    def _check_no_array(self):
        print("Start Checking No Array in The Design...")
        if not self.ast.find(".//arraysel") == None:
            print("  Warning: Found <arraysel>.")
        else:
            print("Pass: No Array in Design.")
        print("-"*80)


    def _check_lv_only_left(self):
        print("Start Checking No Sequantial-Assignments Always-Block \n(All Left-Value Signals Should Be On the Left of Assignment in An Always-Block)...")
        for assign in self.ast.findall(".//always//assign") + self.ast.findall(".//always//assigndly"):
            assign.getchildren()[1].attrib["LV"] = "true"
        flag = False
        for always in self.ast.findall(".//always"):
            lv_set = set()
            for assign in always.findall(".//assign") + always.findall(".//assigndly"):
                lv_set.add(assign.getchildren()[1].attrib["name"])

            for node in always.iter():
                if(node.tag == "varref" and node.attrib["name"] in lv_set):
                    if("LV" in node.attrib):
                        pass
                    else:
                        print("  Warning: Found Left Value on the Right Side of Assignment.")
                        print("    Variable Name = "+node.attrib["name"])
                        flag = True
        if not flag:
            print("Pass: Left-Values Only on the Left of Assignment.")
        print("-"*80)


    def _check_ff_always_only_one_lv(self):
        print("Start checking each sequential <always> only has 1 Left-Value...")
        flag = False
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") == None:
                continue

            lv_set = set()
            for assign in always.findall(".//assign") + always.findall(".//assigndly"):
                lv_set.add(assign.getchildren()[1].attrib["name"])

            if len(lv_set) > 1:
                print("  Warning: More than 1 Left-Value in the <always>")
                print("    LVs in this <always> = ")
                pp.pprint(lv_set)
                flag = True

        if not flag:
            print("Pass: Each FF <always> only has 1 Left-Value")
        print("-"*80)
    def _check_comb_always_only_one_lv(self):
        print("Start checking each combinational <always> only has 1 Left-Value...")
        flag = False
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") != None:
                continue

            lv_set = set()
            for assign in always.findall(".//assign") + always.findall(".//assigndly"):
                lv_set.add(assign.getchildren()[1].attrib["name"])

            if len(lv_set) > 1:
                print("  Warning: More than 1 Left-Value in the <always>")
                print("    LVs in this <always> = ")
                pp.pprint(lv_set)
                flag = True

        if not flag:
            print("Pass: Each Comb <always> only has 1 Left-Value")
        print("-"*80)


    def _check_ff_always_fullcase(self):
        print("Start checking each sequential <always> is FULLCASE...")
        flag = False
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") == None:
                continue

            child = [i.tag for i in always.getchildren()]
            if "if" in child or "case" in child:
                if "assign" in child:
                    print("  Warning: Always not fullcase")
                    loc = always.find("assign").attrib["loc"]
                    file_id = loc.split(",")[0]
                    loc = ",".join(loc.split(",")[1:])
                    print("    Assignment: "+self.ast.find(".//files//file[@id='"+file_id+"']").attrib["filename"]+","+loc)
                    flag = True

        if not flag:
            print("Pass: Each FF <always> is FULLCASE")
        print("-"*80)
    def _check_comb_always_fullcase(self):
        print("Start checking each combinational <always> is FULLCASE...")
        flag = False
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") != None:
                continue

            child = [i.tag for i in always.getchildren()]
            if "if" in child or "case" in child:
                if "assign" in child:
                    print("  Warning: Always not fullcase")
                    loc = always.find("assign").attrib["loc"]
                    file_id = loc.split(",")[0]
                    loc = ",".join(loc.split(",")[1:])
                    print("    Assignment: "+self.ast.find(".//files//file[@id='"+file_id+"']").attrib["filename"]+","+loc)
                    flag = True

            for block in always.findall(".//begin") + always.findall(".//caseitem"):
                if len(block.findall("./if") + block.findall("./case")) > 1:
                    print("  Warning: Found Multiple <if> or <case> under <begin>")
                    print(f"    Always Block: {always.attrib}")
                    flag = True

        if not flag:
            print("Pass: Each Comb <always> is FULLCASE")
        print("-"*80)

    def _check_no_param_under_assign(self):
        print("Start checking no parameter under assignments...")
        flag = False
        for assign in self.ast.findall(".//contassign") + self.ast.findall(".//assignalias") + self.ast.findall(".//always//assign") + self.ast.findall(".//always//assigndly"):
            for var in assign.findall(".//varref"):
                if "param" in var.attrib or "localparam" in var.attrib:
                    print("Warning: Found Parameter under assignment!")
                    print("  parameter = "+var.attrib["name"])
                    flag = True

        if not flag:
            print("Pass: No parameter under assignments")
        print("-"*80)


    def _check_non_blocking_always_assignment(self):
        print("Start checking each non-blocking <always> only has <assigndly> in it...")
        flag = False
        for sentree in self.ast.findall(".//always/sentree"):
            nonblk_always = sentree.getparent()
            assign = nonblk_always.find(".//assign")
            if assign != None:
                print("  Warning: Found a <assign> in Non-blocking <always>.")
                flag = True
        if not flag:
            print("Pass: All Assignment in non-blocking <always> is <assigndly>")
        print("-"*80)


    def check_simple_design(self):
        print("#########################################")
        print("#    Start Checking Simple Design ...   #")
        print("#########################################")
        self._check_no_array()
        self._check_sel_no_muxdec()
        self._check_lv_single_var()
        self._check_lv_only_left()
        self._check_comb_always_only_one_lv()
        self._check_comb_always_fullcase()
        self._check_ff_always_only_one_lv()
        self._check_ff_always_fullcase()
        self._check_non_blocking_always_assignment()
        self._check_no_param_under_assign()
        self._check_param_not_in_circuit()
        #self._check_always_only_one_assign()

    def _check_always_only_one_assign(self):
        flag = False
        for always in self.ast.findall(".//always"):
            assign_num = len(always.findall(".//assign"))
            assigndly_num = len(always.findall(".//assigndly"))

            if assigndly_num + assign_num > 1:
                print("  Error: Found Multiple Assignment in <always>")
                if assigndly_num > 1:
                    lv_name = always.find(".//assigndly").getchildren()[1].attrib["name"]
                    print("    Error: Found Multiple <assigndly> in <always>")
                if assign_num > 1:
                    lv_name = always.find(".//assign").getchildren()[1].attrib["name"]
                    print("    Error: Found Multiple <assign> in <always>")
                flag = True

                print("    LV = "+lv_name)
        if not flag:
            print("Pass: Only 1 assignment in Each <always>.")
        print("-"*80)

    def _check_param_not_in_circuit(self):
        print("Start Checking Parameter are all replaced by <const>.")
        flag = False
        for var in self.ast.findall(".//var[@param='true']") + self.ast.findall(".//var[@localparam='true']"):
            var_name = var.attrib["name"]
            if self.ast.find(f".//varref[@name='{var_name}']") != None:
                flag = True
                print("    Warning: Found a parameter in <varref>.")
        if not flag:
            print("Pass: No Parameter in the Circuit.")
        print("-"*80)

    def get_signal_dicts(self):
        # Check AST Simple
        self.check_simple_design()

        print("Getting Signal Lists...")
        # Get Signal List
        input_var_list = self.get_input_port()
        ff_var_list = self.get_ff()
        output_var_list = self.get_output_port()
       
        #faultfree_input_list = input_var_list + ff_var_list
        #injection_list = ff_var_list
        #observation_list = ff_var_list + output_var_list

        input_var_dict = {}
        for var in input_var_list:
            dtype_id = self.ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = self.ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            input_var_dict[var] = left - right + 1
        ff_var_dict = {}
        for var in ff_var_list:
            dtype_id = self.ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = self.ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            ff_var_dict[var] = left - right + 1
        output_var_dict = {}
        for var in output_var_list:
            dtype_id = self.ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = self.ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            output_var_dict[var] = left - right + 1
        print("DONE!!!")
        return {"input":input_var_dict,"ff":ff_var_dict,"output":output_var_dict}


    def get_input_port(self):
        return [var.attrib["name"] for var in self.ast.findall(".//var[@dir='input']")]

    def get_ff(self):
        return [assigndly.getchildren()[1].attrib["name"] for assigndly in self.ast.findall(".//assigndly")]

    def get_output_port(self):
        ff_list = self.get_ff()
        return [var.attrib["name"] for var in self.ast.findall(".//var[@dir='output']") if not var.attrib["name"] in ff_list]

def Verilator_AST_Tree(ast_file_path:str) -> etree._ElementTree:
    return etree.parse(ast_file_path)


if __name__ == "__main__":
    ast_file = "./ast/Vsha1.xml"
    ast = Verilator_AST_Tree(ast_file)
    print("#"*len("# Start parsing ["+ast_file+"] #"))
    print("# Start parsing ["+ast_file+"] #")
    print("#"*len("# Start parsing ["+ast_file+"] #"))
    #pp.pprint(AST_Parser.__dict__)
    parser = AST_Parser(ast)
    #parser.get_all_tags_under("topscope")
    #parser.check_simple_design()
    parser.get_signal_dicts()


