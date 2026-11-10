
from scipy.optimize import linprog


def select_routes(route_messages, payment_amount):
    """
    Route Selection - Auroch Protocol 4, Equation 7.

    Each route message must contain:
        txid
        path
        capacity
        cost

    payment_amount: Original payment amount.
    """

    if not route_messages:
        print("No available routes!")
        return None

    if payment_amount <= 0:
        raise ValueError("Payment amount must be positive.")

    # Extract route information
    paths = []
    capacities = []
    costs = []

    for message in route_messages:

        capacity = float(message["capacity"])
        cost = float(message["cost"])

        if capacity < 0 or cost < 0:
            raise ValueError("Capacity and cost cannot be negative.")

        if capacity == 0:
            continue

        paths.append(message["path"])
        capacities.append(capacity)
        costs.append(cost)

    if not paths:
        print("No route has positive capacity!")
        return None

    number_of_routes = len(paths)

    # Equation 7a: Minimize total forwarding cost
    objective = costs

    # Equation 7b: Sum of partial payments >= original amount
    constraint_payment = [-1.0] * number_of_routes
    bound_payment = -float(payment_amount)

    # Equation 7c:
    # Sum of partial payments <=
    # amount + sum(capacity_k * cost_k)
    max_payment = (
        float(payment_amount)
        + sum(
            capacities[i] * costs[i]
            for i in range(number_of_routes)
        )
    )

    constraint_upper = [1.0] * number_of_routes

    # Equation 7d and 7e:
    # 0 <= partial payment on route k <= route capacity
    bounds = [
        (0, capacities[i])
        for i in range(number_of_routes)
    ]

    # Solve the linear optimization problem
    result = linprog(
        c=objective,
        A_ub=[
            constraint_payment,
            constraint_upper
        ],
        b_ub=[
            bound_payment,
            max_payment
        ],
        bounds=bounds,
        method="highs"
    )

    if not result.success:
        print("Route selection failed:", result.message)
        return None

    # Construct route allocation results
    selected_routes = []

    for i in range(number_of_routes):

        partial_payment = float(result.x[i])

        if partial_payment > 1e-7:
            selected_routes.append({
                "path": paths[i],
                "capacity": capacities[i],
                "cost": costs[i],
                "partial_payment": partial_payment,
                "forwarding_cost": partial_payment * costs[i]
            })

    total_payment = sum(
        route["partial_payment"]
        for route in selected_routes
    )

    total_forwarding_cost = sum(
        route["forwarding_cost"]
        for route in selected_routes
    )

    print("\n========== AUROCH ROUTE SELECTION ==========")

    for i, route in enumerate(selected_routes, start=1):
        print(f"\nRoute {i}: {route['path']}")
        print("Available capacity:", route["capacity"])
        print("Route cost:", route["cost"])
        print("Allocated payment:", route["partial_payment"])
        print("Forwarding cost:", route["forwarding_cost"])

    print("\nOriginal payment:", payment_amount)
    print("Total allocated payment:", total_payment)
    print("Total forwarding cost:", total_forwarding_cost)

    print(
        "Payment constraint satisfied:",
        total_payment >= payment_amount - 1e-6
    )

    print(
        "Capacity constraints satisfied:",
        all(
            route["partial_payment"] <= route["capacity"] + 1e-6
            for route in selected_routes
        )
    )

    return {
        "selected_routes": selected_routes,
        "total_payment": total_payment,
        "total_forwarding_cost": total_forwarding_cost,
        "optimization_success": result.success
    }


# Test independently
if __name__ == "__main__":

    test_routes = [
        {
            "txid": 123,
            "path": ["Alice", "Peter", "Ivan", "Chloe"],
            "capacity": 50,
            "cost": 2
        },
        {
            "txid": 123,
            "path": ["Alice", "Alexa", "Sam", "Chloe"],
            "capacity": 70,
            "cost": 3
        },
        {
            "txid": 123,
            "path": ["Alice", "Bob", "Chloe"],
            "capacity": 40,
            "cost": 5
        }
    ]

    select_routes(
        route_messages=test_routes,
        payment_amount=100
    )
