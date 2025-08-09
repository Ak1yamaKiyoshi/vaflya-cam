from node import Node 
import time

class Tea(Node):
    def _init(self, type:str):
        self._type = type
        
    def mainloop(self):
        while True:
            time.sleep(0.1)
            #print(f"emitting {self._type} tee")
            self._emit("out_tea", self._type)
            self._emit("smell_of_tea", None)
    
    def set_cup_is_full(self, value=None):
        print("set cup is full")