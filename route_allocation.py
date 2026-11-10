
from scipy.optimize import linprog


def get_directional_channel_liquidity(graph, sender, receiver, channel_id):
    """
    Return currently available liquidity for one exact directed channel.

    The channel is identified by channel_id, not merely by the
    pair of nodes. This is important because Lightning can have
    parallel channels between the same two nodes.
    """

    if not graph.has_edge(sender, receiver):
        raise ValueError(
            f"Channel endpoints not found: {sender} -> {receiver}"
        )

    parallel_edges = graph.get_edge_data(sender, receiver)

    selected_attributes = None

    for key, attributes in parallel_edges.items():
        if str(key) == str(channel_id):
            selected_attributes = attributes
            break

    if selected_attributes is None:
        raise ValueError(
            f"Channel ID {channel_id} not found between "
            f"{sender} and {receiver}"
        )

    node1 = selected_attributes["node1_pub"]
    node2 = selected_attributes["node2_pub"]

    if sender == node1 and receiver == node2:
        liquidity = float(selected_attributes["liquidity_1_to_2"])
        policy = selected_attributes.get("node1_policy")

    elif sender == node2 and receiver == node1:
        liquidity = float(selected_attributes["liquidity_2_to_1"])
        policy = selected_attributes.get("node2_policy")

    else:
        raise ValueError(
            "Channel endpoints do not match the requested direction."
        )

    # A missing or disabled policy means this direction
    # is not considered usable for payment.
    if policy is None or policy.get("disabled", False):
        return 0.0

    return liquidity


def allocate_payment_across_routes(completed_routes, amount, graph):
    """
    Equation 7: Final payment allocation across completed routes.

    Adds shared directed-channel capacity constraints so that
    overlapping routes cannot consume the same liquidity twice.

    Each completed RREP contains:
        path        : destination-to-source order
        channel_ids : destination-to-source order
        capacity    : maximum route capacity
        cost        : cumulative per-unit routing cost
    """

    if not completed_routes:
        print("No completed routes available.")
        return None

    if amount <= 0:
        raise ValueError("Payment amount must be positive.")

    if graph is None:
        raise ValueError("A liquidity graph is required.")

    number_of_routes = len(completed_routes)

    capacities = []
    costs = []
    forward_paths = []
    forward_channel_ids = []
    route_channel_keys = []

    # -------------------------------------------------
    # 1. PREPARE ROUTE INFORMATION
    # -------------------------------------------------

    for index, route in enumerate(completed_routes, start=1):

        capacity = float(route.get("capacity") or 0)
        cost = float(route.get("cost") or 0)

        if capacity < 0 or cost < 0:
            raise ValueError(
                f"Invalid capacity or cost in route {index}"
            )

        # RREP stores paths in destination-to-source order.
        path = list(reversed(route["path"]))
        channel_ids = list(reversed(route["channel_ids"]))

        if len(channel_ids) != len(path) - 1:
            raise ValueError(
                f"Route {index}: number of channel IDs does not "
                "match the number of path edges."
            )

        capacities.append(capacity)
        costs.append(cost)
        forward_paths.append(path)
        forward_channel_ids.append(channel_ids)

        keys_used_by_route = set()

        for hop in range(len(path) - 1):

            sender = path[hop]
            receiver = path[hop + 1]
            channel_id = channel_ids[hop]

            # Include direction in the key. Opposite directions
            # have separate liquidity balances.
            channel_key = (str(channel_id), sender, receiver)

            keys_used_by_route.add(channel_key)

        route_channel_keys.append(keys_used_by_route)

    total_capacity = sum(capacities)

    # -------------------------------------------------
    # 2. ORIGINAL EQUATION 7 CONSTRAINTS
    # -------------------------------------------------

    upper_bound_eq7 = amount + sum(
        cap * cost
        for cap, cost in zip(capacities, costs)
    )

    # scipy uses A_ub @ x <= b_ub.
    A_ub = [
        [-1.0] * number_of_routes,
        [1.0] * number_of_routes
    ]

    b_ub = [
        -float(amount),
        float(upper_bound_eq7)
    ]

    # -------------------------------------------------
    # 3. ADD SHARED DIRECTED-CHANNEL CONSTRAINTS
    # -------------------------------------------------

    all_channel_keys = set()

    for keys in route_channel_keys:
        all_channel_keys.update(keys)

    shared_channel_constraints = []

    for channel_key in all_channel_keys:

        channel_id, sender, receiver = channel_key

        available_liquidity = get_directional_channel_liquidity(
            graph,
            sender,
            receiver,
            channel_id
        )

        # A route contributes its allocated payment amount
        # to every directed channel it traverses.
        constraint_row = [
            1.0 if channel_key in route_keys else 0.0
            for route_keys in route_channel_keys
        ]

        A_ub.append(constraint_row)
        b_ub.append(available_liquidity)

        shared_channel_constraints.append({
            "channel_id": channel_id,
            "sender": sender,
            "receiver": receiver,
            "available_liquidity": available_liquidity
        })

    # -------------------------------------------------
    # 4. ROUTE CAPACITY BOUNDS
    # -------------------------------------------------

    bounds = [
        (0.0, capacity)
        for capacity in capacities
    ]

    # -------------------------------------------------
    # 5. SOLVE THE LINEAR PROGRAM
    # -------------------------------------------------

    result = linprog(
        c=costs,
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=bounds,
        method="highs"
    )

    if not result.success:
        print("\nEquation 7 optimization failed.")
        print("Reason:", result.message)
        print(
            "The requested payment may exceed the capacity "
            "available after accounting for shared channels."
        )
        return None

    # -------------------------------------------------
    # 6. BUILD ALLOCATION RESULTS
    # -------------------------------------------------

    allocations = []
    total_allocated = 0.0
    total_cost = 0.0

    for index, (route, allocated, capacity, cost) in enumerate(
        zip(completed_routes, result.x, capacities, costs),
        start=1
    ):

        allocated = max(0.0, float(allocated))
        route_cost = allocated * cost

        total_allocated += allocated
        total_cost += route_cost

        allocations.append({
            "route_index": index,
            "path": forward_paths[index - 1],
            "channel_ids": forward_channel_ids[index - 1],
            "capacity": capacity,
            "unit_cost": cost,
            "allocated_amount": allocated,
            "total_route_cost": route_cost
        })

    # -------------------------------------------------
    # 7. PRINT RESULTS
    # -------------------------------------------------

    print("\n========== EQUATION 7: FINAL ROUTE ALLOCATION ==========")

    print("Requested payment:", amount, "satoshi")
    print("Sum of individual route capacities:", total_capacity)
    print("Equation 7 upper bound:", upper_bound_eq7)
    print("Total allocated:", total_allocated, "satoshi")
    print("Minimum total routing cost:", total_cost)

    print("\n---------- SHARED CHANNEL CONSTRAINTS ----------")

    for item in shared_channel_constraints:
        print(
            f"Channel {item['channel_id']}: "
            f"{item['sender'][:12]} -> {item['receiver'][:12]} | "
            f"Available liquidity: {item['available_liquidity']}"
        )

    print("\n---------- ROUTE ALLOCATIONS ----------")

    for item in allocations:
        print(f"\nRoute {item['route_index']}")
        print("Path:", item["path"])
        print("Channel IDs:", item["channel_ids"])
        print("Route capacity:", item["capacity"])
        print("Per-unit cost:", item["unit_cost"])
        print("Allocated amount:", item["allocated_amount"])
        print("Total route cost:", item["total_route_cost"])

    if total_allocated + 1e-6 < amount:
        print("\nWARNING: Payment allocation is insufficient.")
        return None

    print("\nSUCCESS: Payment allocation satisfies all constraints.")

    return {
        "requested_amount": float(amount),
        "total_allocated": total_allocated,
        "total_cost": total_cost,
        "allocations": allocations,
        "shared_channel_constraints": shared_channel_constraints,
        "solver_message": result.message
    }


