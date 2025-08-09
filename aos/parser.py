
from dataclasses import dataclass, field
import dataclasses
from pprint import pprint


from typing import List, Tuple
@dataclass
class SubscriptionEntry:
    node_recv_name: str
    node_recv_key: str
    node_send_name: str
    node_send_key: str


@dataclass
class NodeConfig:
    not_null:bool = False
    name:str = ""
    path:str =  ""
    node_class: str = ""
    params:dict = field(default_factory=dict)
    
    subscribers:List[SubscriptionEntry] = field(default_factory=list)


def parse(txt):
    nodes:list[NodeConfig]= []

    table = []

    current_node_config = NodeConfig()


    node_config_started = False
    comment_started = False
    for line in txt.split("\n"):
        # >>> begin comment logic 
        if comment_started and line.strip().startswith("*/"):
            comment_started = False
            continue
        elif comment_started:
            continue
        
        if line.strip().startswith("#"):
            continue
        
        if line.strip().startswith("/*") and not comment_started:
            comment_started = True
            continue
        # <<< end comment logic 
        
        
        # >>> begin node logic 
        if line and line.strip() == line:
            if current_node_config.not_null:
                nodes.append(current_node_config)
                current_node_config = NodeConfig()
            current_node_config.not_null = True
            current_node_config.name = line.split("#")[0] # remove comment part if present 
            continue
    
        elif line.strip().startswith("$$"):
            current_node_config.node_class, current_node_config.path = line.split("$$")[1].split()
            current_node_config.path = current_node_config.path.split("#")[0] # remove comment part if present 

        elif "=" in line:
            param, value = line.strip().split("=")
            param = param.strip()
            value = value.strip().split("#")[0].strip()
            current_node_config.params[param] = eval(value)
        
        elif "<<" in line:
            receiver_key, sender = line.strip().split("<<")
            sender_name, sender_key = sender.split(":")

            table.append(SubscriptionEntry(
                node_recv_name = current_node_config.name,
                node_recv_key = receiver_key.strip(),
                node_send_name = sender_name.strip(),
                node_send_key = sender_key.strip(),
            ))
        # <<< end node logic 

    # <<< end config process 
    
    if current_node_config.not_null:
        nodes.append(current_node_config)
    
    # >>> begin subscriber processing 
    
    for entry in table:
        entry: SubscriptionEntry
        found = False
        for node in nodes:
            
            if node.name == entry.node_send_name:
                found = True
                node.subscribers.append(entry)

        if not found:
            print(f"Mismatch in subscriber entry: {entry}")
    # <<< end subscriber processing 

    #pprint(nodes)
    pprint(nodes)
    return nodes
