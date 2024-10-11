class ASTNodeClassify:
    def __init__(self):
        self.should_not_numbered = {"always", "always_ff", "exprstmt", "begin", "sentree", "scope", "comment", "topscope", "senitem", "assign", "contassign", "assigndly", "assignalias", "caseitem"}
        
        self.not_commutable_arith_op = {"sub"}
        self.commutable_arith_op = {"add","mul"}
        self.arith_op = self.not_commutable_arith_op | self.commutable_arith_op 
        self.logic_op = {"and", "or", "xor", "not"}
        self.red_logic_op = {"redand", "redor", "redxor"}
        self.eq_op= {"eq", "neq"}
        self.less_n_greater_op = {"gt", "gte", "lt", "lte"}
        self.extend_op = {"extend","replicate"}
        self.merge_op = {"concat"}
        self.cond_op = {"cond"}
        self.var_node = {"varref", "varscope", "sel"}
        self.const_node = {"const"}

        self.tag_as_name_node = self.arith_op | self.logic_op | self.red_logic_op | self.eq_op | self.less_n_greater_op | self.merge_op | self.cond_op | self.extend_op
        self.name_as_name_node = self.var_node | self.const_node
        self.same_input_link_node = self.logic_op | self.red_logic_op | self.eq_op | self.commutable_arith_op | self.extend_op
        self.diff_2_input_link_node = self.less_n_greater_op | self.merge_op | self.not_commutable_arith_op
