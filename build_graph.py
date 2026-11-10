
import json
import networkx as nx

file_path = "data/lngraph_2021_11_27__00_00.json"

with open(file_path, "r", encoding="utf-8") as file:
    data = json.load(file)

# MultiGraph preserves parallel payment channels
G = nx.MultiGraph()

# Add nodes
for node in data["nodes"]:
    G.add_node(
        node["pub_key"],
        alias=node["alias"]
    )

# Add all payment channels
for edge in data["edges"]:
    G.add_edge(
        edge["node1_pub"],
        edge["node2_pub"],
        key=edge["channel_id"],
        channel_id=edge["channel_id"],
        capacity=int(edge["capacity"]),
        node1_policy=edge["node1_policy"],
        node2_policy=edge["node2_policy"]
    )

print("========== MULTIGRAPH SUMMARY ==========")
print("Nodes:", G.number_of_nodes())
print("Edges:", G.number_of_edges())

print("\nDataset edges:", len(data["edges"]))

print("\n========== FIRST CHANNEL ==========")

u, v, key, attributes = next(iter(G.edges(keys=True, data=True)))

print("Node 1:", u)
print("Node 2:", v)
print("Channel ID:", key)
print("Capacity:", attributes["capacity"])
print("Node 1 policy:", attributes["node1_policy"])
print("Node 2 policy:", attributes["node2_policy"])

