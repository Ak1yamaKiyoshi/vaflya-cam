from dataclasses import dataclass
import threading


from typing import List
class NodeNoSuchCallbackMethodError(Exception):
    pass


@dataclass
class Subscriber:
    node: "Node"
    key_expect: str
    key_input: str

class Node:
    def __init__(self, name, **params):
        self._name:str = name
        self._subscirbers:List["Node"] = []
        self._is_failed:threading.Event = threading.Event()
        self._error_message:str = ""

        if params:
            self._init(**params)
        else: 
            self._init()

        if hasattr(self, "mainloop"):
            self._thread = threading.Thread(target=self.mainloop, daemon=True)
    
    def _init(self):
        pass
    
    def exit_with_error(self, message):
        self._is_failed.set()
        self._error_message = message
    
    def _emit(self, key, value):
        for sub in self._subscirbers:
            sub: Subscriber
            if key == sub.key_expect:
                try:
                    getattr(sub.node, "set_"+sub.key_input)(value)
                except AttributeError:
                    raise NodeNoSuchCallbackMethodError(f"Node {sub.node._name} has no method 'set_{sub.key_input}'")
            
    def add_subscriber(self, sub:"Node", key_expect:str, key_input):
        self._subscirbers.append(Subscriber(sub, key_expect, key_input ))
