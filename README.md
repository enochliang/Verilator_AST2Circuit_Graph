# Verilator_AST2Circuit_Graph

1. Verilator_AST.py
    Input: A flattened verilator Abstract Syntax Tree(Vast.xml)
    Content:
    The script parses the AST.xml, and analysis it.
    Defines of some functions to analyze the AST.
    Defines a design checker to make sure the RTL design has the specific coding style that I want.
2. AST2Simulator.py
    Run RTL checker from Verilator_AST.py first.
    Than Convert the AST into an RTL circuit graph.
