
import json
from collections import Counter

file_path = "data/lngraph_2021_11_27__00_00.json"

with open(file_path, "r", encoding="utf-8") as file:
    data = json.load(file)

nodes = data["nodes"]
edges = data["edges"]

node_ids = {node["pub_key"] for node in nodes}

channel_ids = [edge["channel_id"] for edge in edges]

invalid_endpoints = 0
invalid_capacity = 0

duplicate_channels = len(channel_ids) - len(set(channel_ids))

node1_status = Counter()
node2_status = Counter()

for edge in edges:

    # Check whether both endpoints exist
    if (edge["node1_pub"] not in node_ids or
            edge["node2_pub"] not in node_ids):
        invalid_endpoints += 1

    # Check channel capacity
    if int(edge["capacity"]) <= 0:
        invalid_capacity += 1

    # Count node1 policy status
    p1 = edge["node1_policy"]

    if p1 is None:
        node1_status["missing"] += 1
    elif p1["disabled"]:
        node1_status["disabled"] += 1
    else:
        node1_status["enabled"] += 1

    # Count node2 policy status
    p2 = edge["node2_policy"]

    if p2 is None:
        node2_status["missing"] += 1
    elif p2["disabled"]:
        node2_status["disabled"] += 1
    else:
        node2_status["enabled"] += 1


print("========== GRAPH VALIDATION ==========")

print("Total nodes:", len(nodes))
print("Total channels:", len(edges))

print("\nInvalid endpoints:", invalid_endpoints)
print("Invalid capacities:", invalid_capacity)
print("Duplicate channel IDs:", duplicate_channels)

print("\nNode1 policy status:", dict(node1_status))
print("Node2 policy status:", dict(node2_status))

print("\n========== VALIDATION RESULT ==========")

if (invalid_endpoints == 0 and
        invalid_capacity == 0 and
        duplicate_channels == 0):
    print("Basic graph validation PASSED")
else:
    print("Basic graph validation FAILED")
