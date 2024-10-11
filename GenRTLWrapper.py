from lxml import etree
from Verilator_AST import *

def _gen_line(line:str,indent:int=0)->str:
    return " "*indent + line

class Gen_FF_Wrapper:
    def __init__(self,ast):
        parser = AST_Parser(ast)
        sig_dict = parser.get_signal_dicts()
        self.clk_name = "clk"
        self.rst_name = "reset_n"
        self.tb_clk_name = "tb_clk"
        self.tb_rst_name = "tb_reset_n"
        self.input_port_dict = sig_dict["input"]
        self.ff_dict = sig_dict["ff"]
        self.output_port_dict = sig_dict["output"]
        self.input_port_dict.pop(self.clk_name)
        self.input_port_dict.pop(self.rst_name)

        # Verilog Variable Declaration Name
        self.fault_free_input_tag_name = "FFI"
        self.golden_output_tag_name = "GO"
        self.cycle_cnt = ("cycle",32)


    def gen_cnt(self)->list:
        cyc = self.cycle_cnt[0]
        clk = self.tb_clk_name
        rst = self.tb_rst_name
        string = [f'reg [{self.cycle_cnt[1]}:0] {self.cycle_cnt[0]};',
                  f'initial {cyc} = 0;',
                  f'always@(posedge {clk}) begin',
                  f'  if(!{rst}) {cyc} <= 0;',
                  f'  else            {cyc} <= {cyc} + 1;',
                  f'end']
        return string


    def gen_tasks(self)->list:
        string = ["task cycle2num;",
                  "  input [31:0] cyc;",
                  "  output [39:0] num;",
                  "  begin",
                  "    num2char(cyc/10000,num[39:32]);",
                  "    cyc = cyc % 10000;",
                  "    num2char(cyc/1000,num[31:24]);",
                  "    cyc = cyc % 1000;",
                  "    num2char(cyc/100,num[23:16]);",
                  "    cyc = cyc % 100;",
                  "    num2char(cyc/10,num[15:8]);",
                  "    cyc = cyc % 10;",
                  "    num2char(cyc,num[7:0]);",
                  "  end",
                  "endtask",
                  "",
                  "task num2char;",
                  "  input [31:0] num;",
                  "  output [7:0] ch;",
                  "  begin",
                  "    case(num)",
                  "      'd0:ch=8'd48;",
                  "      'd1:ch=8'd49;",
                  "      'd2:ch=8'd50;",
                  "      'd3:ch=8'd51;",
                  "      'd4:ch=8'd52;",
                  "      'd5:ch=8'd53;",
                  "      'd6:ch=8'd54;",
                  "      'd7:ch=8'd55;",
                  "      'd8:ch=8'd56;",
                  "      'd9:ch=8'd57;",
                  "    endcase",
                  "  end",
                  "endtask",
                  ""]
        return string


    def gen_ff_input_dump_code(self)->str:
        clk = self.tb_clk_name
        rst = self.tb_rst_name
        ffi = self.fault_free_input_tag_name
        cyc = self.cycle_cnt[0]
        input_list = list(self.input_port_dict.keys())
        input_ff_list = list(self.input_port_dict.keys()) + list(self.ff_dict.keys())
        for i,var in enumerate(input_list):
            if "sha1." in var:
                input_list[i] = var.replace("sha1.","dut.")
            else:
                input_list[i] = "dut."+var
        for i,var in enumerate(input_ff_list):
            if "sha1." in var:
                input_ff_list[i] = var.replace("sha1.","dut.")
            else:
                input_ff_list[i] = "dut."+var
                

        string = [f'reg [31:0] tail = ".txt";',
                  f'reg [135:0] {ffi}_head = "FaultFree_Input_C";',
                  f'reg [39:0] {ffi}_num;',
                  f'integer {ffi}_f;',
                  f'always@(posedge {clk}) begin',
                  f'  if({rst} && {cyc}>=0)begin',
                  f'    if({cyc}>0)begin']
        string = string + [f'      $fwrite({ffi}_f,"%b\\n",{varname});' for varname in input_list]
        string = string + [f'      $fclose({ffi}_f);',
                           f'    end',
                           f'    if({cyc}<1037)begin',
                           f'      cycle2num({cyc},{ffi}_num);',
                           f'      {ffi}_f = $fopen('+'{'+f'{ffi}_head,{ffi}_num,tail'+'},"w");']
        string = string + [f'      $fwrite({ffi}_f,"%b\\n",{varname});' for varname in input_ff_list]
        string = string + [f'    end',
                           f'  end',
                           f'end',
                           ""]

        return string
    
    def gen_golden_output_dump_code(self)->list:
        clk = self.tb_clk_name
        rst = self.tb_rst_name
        go = self.golden_output_tag_name
        cyc = self.cycle_cnt[0]
        ff_output_list = list(self.ff_dict.keys()) + list(self.output_port_dict.keys())
        for i,var in enumerate(ff_output_list):
            if "sha1." in var:
                ff_output_list[i] = var.replace("sha1.","dut.")
            else:
                ff_output_list[i] = "dut."+var
        string =           [f'reg [119:0] {go}_head = "Golden_Output_C";',
                           f'reg [39:0] {go}_num;',
                           f'integer {go}_f;',
                           f'always@(posedge {clk}) begin',
                           f'  if({rst} && {cyc}>0)begin',
                           f'    {cyc}2num({cyc},{go}_num);',
                           f'    {go}_f = $fopen('+'{'+f'{go}_head,{go}_num,tail'+'},"w");']
        string = string + [f'    $fwrite({go}_f,"%b\\n",{varname});' for varname in ff_output_list]
        string = string + [f'    $fclose({go}_f);',
                           f'  end',
                           f'end',
                           ""]
        return string

    def generate(self):
        print("====================================")
        print("Start Generating Fault Free Wrapper:")
        print("====================================")
        string = []
        string = string + self.gen_cnt()
        string = string + self.gen_tasks()
        string = string + self.gen_ff_input_dump_code()
        string = string + self.gen_golden_output_dump_code()
        for s in string:
            print(s)

class Gen_FI_Wrapper:
    def __init__(self,ast):
        parser = AST_Parser(ast)
        sig_dict = parser.get_signal_dicts()
        self.clk_name = "clk"
        self.rst_name = "reset_n"
        self.tb_clk_name = "tb_clk"
        self.tb_rst_name = "tb_reset_n"
        self.input_port_dict = sig_dict["input"]
        self.ff_dict = sig_dict["ff"]
        self.output_port_dict = sig_dict["output"]
        self.input_port_dict.pop(self.clk_name)
        self.input_port_dict.pop(self.rst_name)

        # Verilog Variable Declaration Name
        self.fault_free_input_tag_name = "FFI"
        self.golden_output_tag_name = "GO"
        self.cycle_cnt = ("cycle",32)
    
    def gen_input_port(self):
        ffi = self.fault_free_input_tag_name
        clk = self.tb_clk_name
        string = []
        
        # Input Buffer Declaration
        string = string + ["// Input Buffer Declaration"]
        for in_var,width in self.input_port_dict.items():
            w = int(width)
            string = string + [f'reg [{w-1}:0] tb_i_{in_var};']
        # Input Port Buffer Declaration
        string = string + ["// Input Port Buffer Declaration"]
        for in_var,width in self.input_port_dict.items():
            w = int(width)
            string = string + [f'reg [{w-1}:0] in_buffer_{in_var};']
        # Next Input Buffer Declaration
        string = string + ["// Next Input Buffer Declaration"]
        for in_var,width in self.input_port_dict.items():
            w = int(width)
            string = string + [f'reg [{w-1}:0] tb_i_{in_var}_next;']
        # FF Buffer Declaration
        string = string + ["// FF Buffer Declaration"]
        for ff_var,width in self.ff_dict.items():
            var = ff_var.replace("sha1.","dut.").replace(".","__")
            w = int(width)
            string = string + [f'reg [{w-1}:0] ff_buffer_{var};']
        # Golden Buffer Declaration
        string = string + ["// Golden Buffer Declaration"]
        for ff_var,width in self.ff_dict.items():
            var = ff_var.replace("sha1.","dut.").replace(".","__")
            w = int(width)
            string = string + [f'reg [{w-1}:0] golden_{var};']

        # Load Fault Free Input Pattern
        string = string + ["// Load Fault Free Input Pattern"]
        for in_var,width in self.input_port_dict.items():
            string = string + [f'$fscanf(f,"%s",in_buffer_{in_var});']
        for ff_var,width in self.ff_dict.items():
            var = ff_var.replace("sha1.","dut.").replace(".","__")
            string = string + [f'$fscanf(f,"%s",ff_buffer_{var});']
        for in_var,width in self.input_port_dict.items():
            string = string + [f'$fscanf(f,"%s",tb_i_{in_var}_next);']

        # Load Golden Output Value to Golden Buffer
        string = string + ["// Load Golden Output Value to Golden Buffer"]
        for ff_var,width in self.ff_dict.items():
            var = ff_var.replace("sha1.","dut.").replace(".","__")
            string = string + [f'$fscanf(f,"%s",golden_{var});']

        # Load Fault Free Values
        string = string + [f"always@(posedge input_flag)begin"]
        string = string + [f'  tb_i_{in_var} <= in_buffer_{in_var};' for in_var in self.input_port_dict.keys()]
        string = string + ["end"]
        string = string + [f"always@(posedge {clk})begin"]
        string = string + [f'  tb_i_{in_var} <= tb_i_{in_var}_next;' for in_var in self.input_port_dict.keys()]
        string = string + ["end"]
        string = string + [f"always@(posedge input_flag)begin"]
        for ff_var in self.ff_dict.keys():
            var = ff_var.replace("sha1.","dut.")
            b_var = var.replace(".","__")
            string = string + [f'  {var} <= ff_buffer_{b_var};']
        string = string + ["end"]

        # Fault Injection
        string = string + ["always@(posedge inject_flag) begin"]
        string = string + ["  case(inject_reg)"]
        for i,ff_var in enumerate(self.ff_dict):
            var = ff_var.replace("sha1.","dut.")
            w = int(self.ff_dict[ff_var])
            string = string + [f"    32'd{i}:{var}<={var}^mask[{w-1}:0];"]
        string = string + ["  endcase"]
        string = string + ["end"]



        # Observation Part
        for ff_var,width in self.ff_dict.items():
            var = ff_var.replace("sha1.","dut.")
            g_var = var.replace(".","__")
            string = string + [f'$fwrite(f,"%b\\n",{g_var}^{var});']


        return string
    
    def generate(self):
        string = []
        string = string + self.gen_input_port()
        for s in string:
            print(s)



if __name__ == "__main__":
    ast_file = "./ast/Vsha1.xml"
    ast = Verilator_AST_Tree(ast_file)
    parser = AST_Parser(ast)
    #gen = Gen_FF_Wrapper(ast)
    #gen.generate()
    gen = Gen_FI_Wrapper(ast)
    gen.generate()

