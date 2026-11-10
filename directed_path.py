
import json
import networkx as nx

file_path = "data/lngraph_2021_11_27__00_00.json"

with open(file_path, "r", encoding="utf-8") as file:
    data = json.load(file)

DG = nx.MultiDiGraph()

# Add all nodes
for node in data["nodes"]:
    DG.add_node(
        node["pub_key"],
        alias=node["alias"]
    )

# Add directed edges based on channel policies
for edge in data["edges"]:

    node1 = edge["node1_pub"]
    node2 = edge["node2_pub"]
    channel_id = edge["channel_id"]
    capacity = int(edge["capacity"])

    # Direction: node1 -> node2
    policy1 = edge["node1_policy"]

    if policy1 is not None and not policy1["disabled"]:
        DG.add_edge(
            node1,
            node2,
            key=channel_id,
            channel_id=channel_id,
            capacity=capacity,
            policy=policy1
        )

    # Direction: node2 -> node1
    policy2 = edge["node2_policy"]

    if policy2 is not None and not policy2["disabled"]:
        DG.add_edge(
            node2,
            node1,
            key=channel_id,
            channel_id=channel_id,
            capacity=capacity,
            policy=policy2
        )

print("========== DIRECTED GRAPH ==========")
print("Nodes:", DG.number_of_nodes())
print("Directed edges:", DG.number_of_edges())

print("\n========== CONNECTIVITY ==========")
print("Is directed:", DG.is_directed())

print("\n========== FIRST DIRECTED EDGE ==========")

u, v, key, attributes = next(
    iter(DG.edges(keys=True, data=True))
)

print("From:", u)
print("To:", v)
print("Channel ID:", key)
print("Capacity:", attributes["capacity"])
print("Policy:", attributes["policy"])