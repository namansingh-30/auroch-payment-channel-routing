
import random


# =====================================================
# 1. LEGACY AUCTION SETUP
# =====================================================

def auction_setup(rreq_result, rrep_messages):

    if rreq_result is None:
        print("RREQ result not available!")
        return []

    auc_messages = []
    parents = rreq_result["parents"]

    print("\n========== AUCTION SETUP ==========")

    for rrep in rrep_messages:

        auctioneer = rrep["receiver"]
        bidders = parents.get(auctioneer, set())

        print("\nAuctioneer:", auctioneer)
        print("Bidder set:", bidders)

        for bidder in bidders:

            auc = {
                "txid": rrep["txid"],
                "auctioneer": auctioneer,
                "bidder": bidder,
                "path": rrep["path"]
            }

            auc_messages.append(auc)

    return auc_messages


# =====================================================
# 2. CALCULATE CAPACITY TOWARDS THE NEXT HOP
# =====================================================

def calculate_max_capacity(graph, auctioneer, next_hop):

    # Get all physical channels between auctioneer and next hop.
    channels = graph.get_edge_data(auctioneer, next_hop)

    if channels is None:
        return None

    available_channels = []

    for channel_id, attributes in channels.items():

        # Determine payment direction: auctioneer -> next_hop.
        if auctioneer == attributes.get("node1_pub"):

            liquidity = attributes["liquidity_1_to_2"]
            policy = attributes["node1_policy"]

        elif auctioneer == attributes.get("node2_pub"):

            liquidity = attributes["liquidity_2_to_1"]
            policy = attributes["node2_policy"]

        else:
            continue

        # Ignore missing or disabled directional policies.
        if policy is None or policy.get("disabled", False):
            continue

        if liquidity > 0:

            available_channels.append({
                "channel_id": channel_id,
                "capacity": attributes["capacity"],
                "available_liquidity": liquidity
            })

    if not available_channels:
        return None

    # Simulation assumption:
    # Select the physical channel with highest directional liquidity.
    best_channel = max(
        available_channels,
        key=lambda channel: channel["available_liquidity"]
    )

    return best_channel


# =====================================================
# 3. RESERVATION PRICE
# =====================================================

def calculate_reservation_price(win_price, tau_fee):

    return win_price + tau_fee


# =====================================================
# 4. CREATE AUC MESSAGE
# =====================================================

def create_auc_message(rreq_result, rrep, graph):

    if rreq_result is None or rrep is None:
        return None

    path = rrep.get("path", [])

    if len(path) < 2:
        print("Invalid RREP path!")
        return None

    auctioneer = rrep["receiver"]

    # The path is stored in destination-to-source order.
    # The node immediately before the auctioneer is its next hop.
    next_hop = path[-2]

    # Verify that the receiver is actually the last path node.
    if path[-1] != auctioneer:
        print("RREP receiver does not match the path!")
        return None

    # Calculate capacity towards the next hop, not always
    # towards the final destination.
    best_channel = calculate_max_capacity(
        graph,
        auctioneer,
        next_hop
    )

    if best_channel is None:
        print(
            "No usable channel from",
            auctioneer,
            "to",
            next_hop
        )
        return None

    # Carry the downstream path cost as WinPrice.
    # For the initial destination-adjacent auction, this is zero.
    win_price = rrep.get("cost")

    if win_price is None:
        win_price = 0

    # Original Auroch fee range.
    tau_fee = random.randint(1, 10)

    reservation_price = calculate_reservation_price(
        win_price,
        tau_fee
    )

    # Unique identifier for this particular RREP path.
    path_id = (
        str(rrep["txid"])
        + "::"
        + "->".join(str(node) for node in path)
    )

    auc = {
        "txid": rrep["txid"],
        "auction_id": path_id,
        "path_id": path_id,

        "auctioneer": auctioneer,
        "next_hop": next_hop,
        "destination": rreq_result["destination"],

        "path": list(path),

        "channel_id": best_channel["channel_id"],
        "max_capacity": best_channel["available_liquidity"],

        "win_price": win_price,
        "tau_fee": tau_fee,
        "reservation_price": reservation_price
    }

    print("\n========== AUC MESSAGE ==========")
    print("Transaction ID:", auc["txid"])
    print("Auction ID:", auc["auction_id"])
    print("Auctioneer:", auc["auctioneer"])
    print("Next hop:", auc["next_hop"])
    print("Path:", auc["path"])
    print("Selected channel:", auc["channel_id"])
    print("Maximum capacity:", auc["max_capacity"])
    print("Win price:", auc["win_price"])
    print("Tau fee:", auc["tau_fee"])
    print("Reservation price:", auc["reservation_price"])

    return auc


