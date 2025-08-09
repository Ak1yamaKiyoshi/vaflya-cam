
## Syntax
```
# comment 
node
    $$ className path/from/main/level/main.py
    param = value # comment 
    key << node:key  

/*
multiline comment 
*/
```

## Example
### Node1 
```py
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
```
### Node2 
```py
from node import Node

class Cup(Node):
    def _init(self):
        self.capacity = 100
        self.current = 0 
        
    def set_tea(self, tea):
        #print(f"receiving tea: {tea}")
        self.current += 10
        if self.current >= self.capacity:
            self._emit("cup_state", "sometext")
            print("cup is full")
        #print(self.current)
```
### Config
```
teapot
    $$ Tea testnodes/tea.py
    type = "black"
    cup_is_full << cup:cup_state

cup
    $$ Cup testnodes/cup.py
    tea << teapot:out_tea

```
