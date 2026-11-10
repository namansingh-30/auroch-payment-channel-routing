def make_payment(graph, sender, receiver, channel_id, amount):

    # 1. Validate nodes
    if sender not in graph or receiver not in graph:
        print("Sender or receiver does not exist!")
        return False

    if sender == receiver:
        print("Sender and receiver cannot be the same!")
        return False

    # 2. Find the exact physical channel
    edge_data = graph.get_edge_data(sender, receiver, channel_id)

    if edge_data is None:
        print("Channel does not exist!")
        return False

    capacity = edge_data["capacity"]

    # 3. Identify payment direction
    if sender == edge_data["node1_pub"] and receiver == edge_data["node2_pub"]:
        forward_liquidity = "liquidity_1_to_2"
        reverse_liquidity = "liquidity_2_to_1"

        forward_label = f"{sender} -> {receiver}"
        reverse_label = f"{receiver} -> {sender}"

        policy = edge_data.get("node1_policy")

    elif sender == edge_data["node2_pub"] and receiver == edge_data["node1_pub"]:
        forward_liquidity = "liquidity_2_to_1"
        reverse_liquidity = "liquidity_1_to_2"

        forward_label = f"{sender} -> {receiver}"
        reverse_label = f"{receiver} -> {sender}"

        policy = edge_data.get("node2_policy")

    else:
        print("Invalid channel endpoints!")
        return False

    # 4. Check direction policy
    if policy is None or policy.get("disabled", False):
        print("Payment direction is disabled!")
        return False

    # 5. Check amount and available liquidity
    if amount <= 0:
        print("Payment amount must be positive!")
        return False

    liquidity = edge_data[forward_liquidity]

    if amount > liquidity:
        print("Insufficient liquidity!")
        print("Available:", liquidity)
        print("Requested:", amount)
        return False

    # 6. Capture directional liquidity BEFORE payment
    before_forward = edge_data[forward_liquidity]
    before_reverse = edge_data[reverse_liquidity]

    # 7. Update directional liquidity
    edge_data[forward_liquidity] -= amount
    edge_data[reverse_liquidity] += amount

    # 8. Capture directional liquidity AFTER payment
    after_forward = edge_data[forward_liquidity]
    after_reverse = edge_data[reverse_liquidity]

    # 9. Verify channel capacity is preserved
    total = (
        edge_data["liquidity_1_to_2"]
        + edge_data["liquidity_2_to_1"]
    )

    assert abs(total - capacity) < 1e-6, (
        f"Liquidity conservation failed for channel {channel_id}"
    )

    # 10. Print before-and-after liquidity report
    print("\n========== CHANNEL LIQUIDITY REPORT ==========")
    print("Channel ID:", channel_id)
    print("Payment direction:", sender, "->", receiver)
    print("Amount transferred:", amount, "sats")

    print("\nBEFORE PAYMENT")
    print(f"{forward_label}: {before_forward:.2f} sats")
    print(f"{reverse_label}: {before_reverse:.2f} sats")

    print("\nAFTER PAYMENT")
    print(f"{forward_label}: {after_forward:.2f} sats")
    print(f"{reverse_label}: {after_reverse:.2f} sats")

    print("\nCAPACITY CHECK")
    print(f"Total directional liquidity: {total:.2f} sats")
    print(f"Channel capacity: {capacity:.2f} sats")
    print("Capacity preserved:", abs(total - capacity) < 1e-6)
    print("==============================================")

    print("Payment successful!")

    return True


