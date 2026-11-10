
from collections import deque


def rreq_discovery(graph, source, destination, txid):

    if source not in graph or destination not in graph:
        print("Source or destination does not exist!")
        return None

    distance = {source: 0}
    parents = {source: set()}

    queue = deque([source])

    print("\n========== RREQ BROADCASTING ==========")
    print("Transaction ID:", txid)
    print("Source:", source)
    print("Destination:", destination)

    # BFS traversal
    while queue:

        current = queue.popleft()

        for neighbor in graph.neighbors(current):

            new_distance = distance[current] + 1

            # First discovery: shortest distance found.
            if neighbor not in distance:

                distance[neighbor] = new_distance
                parents[neighbor] = {current}
                queue.append(neighbor)

            # Another predecessor at the same shortest distance.
            elif distance[neighbor] == new_distance:

                parents[neighbor].add(current)

    if destination not in distance:
        print("Destination not reachable!")
        return None

    print("\n========== RREQ COMPLETED ==========")
    print("Total nodes reached:", len(distance))
    print("Destination distance:", distance[destination])

    print("\nShortest-path predecessor information:")

    for node, predecessor_set in parents.items():

        if predecessor_set:
            print(
                "Node:", node,
                "| Distance:", distance[node],
                "| Parents:", predecessor_set
            )

    return {
        "txid": txid,
        "source": source,
        "destination": destination,
        "parents": parents,
        "distance": distance
    }


if __name__ == "__main__":

    import networkx as nx

    G = nx.Graph()

    G.add_edges_from([
        ("S", "A"),
        ("S", "B"),
        ("A", "C"),
        ("B", "C"),
        ("C", "D"),
        ("A", "D"),
        ("D", "T")
    ])

    result = rreq_discovery(
        G,
        source="S",
        destination="T",
        txid="TEST001"
    )

    print("\nTest result:", result)
