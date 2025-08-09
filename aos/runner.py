from .node import Node
from .parser import parse
from pprint import pprint
import threading

from .parser import SubscriptionEntry

import time 
import os 
def main(txt):
    print(os.curdir)
    initialized_nodes = []
    parsed_node_configs = parse(txt)

    for node in parsed_node_configs:
        path = node.path.replace(".py", "").replace("/", ".")
        cls = getattr(__import__(path, fromlist=[node.node_class]), node.node_class)
        initialized_node = cls(name=node.name, **node.params)
        initialized_nodes.append(initialized_node)
        
    for parsed, initialized in zip(parsed_node_configs, initialized_nodes):
        initialized:Node
        for sub in parsed.subscribers:
            sub: SubscriptionEntry            
            for node in initialized_nodes:
                if node._name == sub.node_recv_name:
                    initialized.add_subscriber(node, sub.node_send_key, sub.node_recv_key )        

    threads = []    
    for node in initialized_nodes:
        if hasattr(node, "mainloop"):
            threads.append(threading.Thread(target=node.mainloop, daemon=True))
            threads[-1].start()

    while True:
        someone_errored = False
        for node in initialized_nodes:
            node:Node
            if node._is_failed.is_set():
                print(f"Node {node._name} error: {node._error_message}")
                someone_errored = True
        if someone_errored: break
        time.sleep(0.5)

    for thread in threads:
        thread.join()
