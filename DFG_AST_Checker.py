from Verilator_AST import *
from Verilator_DFG import *

if __name__ == "__main__":
    dfg = Verilator_DFG_Graph("Vibex_top_1540___024root-postinline-whole-input.dot")
    ast = Verilator_AST_Tree("Vibex_top_flatten.xml")
    dfg_node_name = []
    ast_var_name = set()
    assigns = ast.findall(".//always//assign") + ast.findall(".//always//assigndly") + ast.findall(".//contassign") + ast.findall(".//initial//assign")
    for ass in assigns:
        lv = ass.getchildren()[1]
        if lv.tag == "varref":
            ast_var_name.add(lv.attrib["name"])
        else:
            for var in lv.findall(".//varref"):
                ast_var_name.add(var.attrib["name"])
    #print(dfg.vs["sig_name"])
    remained_sig = set()
    for v in dfg.vs["sig_name"]:
        if v == None:
            continue
        else:
            if not v in ast_var_name:
                remained_sig.add(v)

    assigns = ast.findall(".//assignalias")
    ast_var_name = set()
    for ass in assigns:
        lv = ass.getchildren()[0]
        if lv.tag == "varref":
            ast_var_name.add(lv.attrib["name"])
        else:
            for var in lv.findall(".//varref"):
                ast_var_name.add(var.attrib["name"])
    for v in remained_sig:
        if v == None:
            continue
        else:
            if not v in ast_var_name:
                print(v)

