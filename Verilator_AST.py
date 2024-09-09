from lxml import etree
import pprint 
pp = pprint.PrettyPrinter(indent=4)

class AST_Parser:
    def __init__(self, ast: etree._ElementTree):
       self.ast = ast
       self.signal_list = None

    def get_signal(self,output=True):
        # Make a List of All Signals Including WIRE & Flip-Flop.
        signals = set()
        for var in self.ast.findall(".//var"):
            if "param" in var.attrib:
                continue
            elif "localparam" in var.attrib:
                continue
            else:
                signals.add(var.attrib["name"])
        if output:
            print("Print All Signals Including WIRE & Flip-Flop...")
            for sig in signals:
                print("  "+sig)


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

    def check_all_left_values_are_single_var(self):
        assignments = self.ast.findall(".//assign") + self.ast.findall(".//assigndly") + self.ast.findall(".//contassign")
        flag = False
        for assign in assignments:
            tag = assign.getchildren()[1].tag
            if not tag == "varref":
                print("Found a Left Value Not a Single <varref>!")
                print("  Tag = "+tag)
                print(assign.getchildren()[1].getchildren()[0].attrib["name"])
                flag = True
        if not flag:
            print("All Left Values are Single <varref>")


def Verilator_AST_Tree(ast_file_path:str) -> etree._ElementTree:
    return etree.parse(ast_file_path)


if __name__ == "__main__":
    ast = Verilator_AST_Tree("./ast/Vsha1_core.xml")

    #pp.pprint(AST_Parser.__dict__)
    parser = AST_Parser(ast)
    #parser.get_all_tags_under("always//if")
    parser.check_all_left_values_are_single_var()
    #parser.check_tag_all_x_are_under_y("assign","always")

