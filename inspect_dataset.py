
# import json

# file_path = "data/lngraph_2021_11_27__00_00.json"

# with open(file_path, "r", encoding="utf-8") as file:
#     data = json.load(file)

# # Count nodes and edges
# print("Total nodes:", len(data["nodes"]))
# print("Total edges:", len(data["edges"]))

# # Inspect first node
# print("\n========== FIRST NODE ==========")
# print(data["nodes"][0])

# # Inspect first edge
# print("\n========== FIRST EDGE ==========")
# print(data["edges"][0])

# # Inspect available attributes
# print("\n========== NODE ATTRIBUTES ==========")
# print(data["nodes"][0].keys())

# print("\n========== EDGE ATTRIBUTES ==========")
# print(data["edges"][0].keys())



import json

file_path = "data/lngraph_2021_11_27__00_00.json"

with open(file_path, "r", encoding="utf-8") as file:
    data = json.load(file)

edges = data["edges"]

# Count missing policies
node1_missing = sum(
    edge["node1_policy"] is None for edge in edges
)

node2_missing = sum(
    edge["node2_policy"] is None for edge in edges
)

print("Total edges:", len(edges))

print("\nMissing node1 policies:", node1_missing)
print("Missing node2 policies:", node2_missing)

# Find an edge having both policies
for edge in edges:
    if edge["node1_policy"] is not None and edge["node2_policy"] is not None:
        print("\n========== EDGE WITH BOTH POLICIES ==========")
        print(edge)
        break

# Inspect channel capacity
capacities = [int(edge["capacity"]) for edge in edges]

print("\n========== CAPACITY STATISTICS ==========")
print("Minimum capacity:", min(capacities))
print("Maximum capacity:", max(capacities))
print("Average capacity:", sum(capacities) / len(capacities))


