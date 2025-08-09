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