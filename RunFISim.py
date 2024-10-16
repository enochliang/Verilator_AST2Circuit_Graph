import os
import json

class GenFaultList:
    def __init__(self,cycle:int,_sig_dict:dict):
        self.total_cyc = cycle
        self.sig_dict = _sig_dict

    def get_fault_list(self):
        self.all_fault_list = []
        for cyc in range(self.total_cyc):
            for idx,sig_name in enumerate(self.sig_dict["ff"]):
                width = self.sig_dict["ff"][sig_name]
                for bit in range(width):
                    self.all_fault_list.append((cyc,idx,bit))

        #pprint.pp(self.all_fault_list)

if __name__ == "__main__":

    f = open("sig_dict.json","r")
    sig_dict = json.load(f)
    f.close()
    fl = GenFaultList(1037,sig_dict)
    fl.get_fault_list()
    for fi_case in fl.all_fault_list:
        f = open("control.txt","w")
        f.write(f"{fi_case[0]}\n{fi_case[1]}\n{fi_case[2]}")
        f.close()
        os.system("./Vfi_tb")
