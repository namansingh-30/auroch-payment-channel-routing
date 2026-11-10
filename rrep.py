
# =====================================================
# 1. INITIAL RREP GENERATION
# =====================================================

def create_rrep_messages(rreq_result):

    if rreq_result is None:
        print("No RREQ result available!")
        return []

    txid = rreq_result["txid"]
    destination = rreq_result["destination"]

    parents = rreq_result["parents"].get(destination, set())

    rrep_messages = []

    print("\n========== INITIAL RREP GENERATION ==========")

    for parent in sorted(parents):

        rrep = {
            "txid": txid,
            "path": [destination, parent],

            # Channel IDs will be populated during propagation.
            # Same order as path edges: destination -> source.
            "channel_ids": [],

            "capacity": None,
            "cost": 0,
            "receiver": parent,
            "destination": destination,
            "complete": False
        }

        rrep_messages.append(rrep)

        print("\nRREP sent to:", parent)
        print("Path:", rrep["path"])
        print("Channel IDs:", rrep["channel_ids"])

    print("\nTotal initial RREP messages:", len(rrep_messages))

    return rrep_messages


# =====================================================
# 2. EXTEND ONE RREP USING AN ALLOCATION
# =====================================================

def extend_rrep_message(rrep, allocation, rreq_result):

    if rrep is None or allocation is None or rreq_result is None:
        return None

    allocated_capacity = allocation["allocated_capacity"]

    if allocated_capacity <= 0:
        return None

    current_path = list(rrep["path"])

    auctioneer = rrep["receiver"]
    bidder = allocation["bidder"]

    # Check allocation belongs to this RREP.
    if allocation["auctioneer"] != auctioneer:
        return None

    if allocation["path"] != current_path:
        return None

    # Prevent cycles.
    if bidder in current_path:
        print("Cycle prevented:", bidder)
        return None

    # Bidder must be one BFS level closer to source.
    distance = rreq_result["distance"]

    if bidder not in distance or auctioneer not in distance:
        return None

    if distance[bidder] != distance[auctioneer] - 1:
        print("Invalid backward RREP movement:", bidder)
        return None

    # Verify next hop.
    expected_next_hop = current_path[-2]

    if allocation.get("next_hop") != expected_next_hop:
        print("Allocation next-hop mismatch!")
        return None

    # =================================================
    # BOTTLENECK CAPACITY
    # =================================================

    capacity_values = [
        allocated_capacity,
        allocation["auctioneer_max_capacity"]
    ]

    if rrep["capacity"] is not None:
        capacity_values.append(rrep["capacity"])

    path_capacity = min(capacity_values)

    if path_capacity <= 0:
        return None

    # =================================================
    # CUMULATIVE PER-UNIT PATH COST
    # =================================================

    # BidPrice already includes downstream WinPrice.
    path_cost = allocation["bid_price"]

    # =================================================
    # PRESERVE CHANNEL IDs
    # =================================================

    channel_ids = list(rrep.get("channel_ids", []))

    # The first extension must record the AUC-selected
    # downstream channel (auctioneer -> next_hop).
    if not channel_ids:

        downstream_channel_id = allocation.get(
            "downstream_channel_id"
        )

        if downstream_channel_id is None:
            print(
                "Missing downstream_channel_id. "
                "Update bidding.py before running the simulation."
            )
            return None

        channel_ids.append(downstream_channel_id)

    # Record the BID-selected channel connecting
    # the new bidder to the current auctioneer.
    bid_channel_id = allocation.get("channel_id")

    if bid_channel_id is None:
        print("Missing BID channel ID!")
        return None

    channel_ids.append(bid_channel_id)

    # =================================================
    # CREATE EXTENDED RREP
    # =================================================

    new_path = current_path + [bidder]

    source = rreq_result["source"]

    new_rrep = {
        "txid": rrep["txid"],
        "path": new_path,
        "channel_ids": channel_ids,

        "capacity": path_capacity,
        "cost": path_cost,

        "receiver": bidder,
        "destination": rrep["destination"],
        "complete": bidder == source
    }

    print("\n========== RREP PATH EXTENDED ==========")
    print("Transaction ID:", new_rrep["txid"])
    print("Auctioneer:", auctioneer)
    print("New bidder:", bidder)
    print("Extended path:", new_rrep["path"])
    print("Channel IDs:", new_rrep["channel_ids"])
    print("Allocated capacity:", allocated_capacity)
    print("Bottleneck path capacity:", path_capacity)
    print("Cumulative per-unit path cost:", path_cost)
    print("Reached source:", new_rrep["complete"])

    return new_rrep


# =====================================================
# 3. EXTEND MULTIPLE RREPs
# =====================================================

def extend_rrep_messages(rrep_messages, auction_results, rreq_result):

    extended_rreps = []

    if not rrep_messages or not auction_results:
        print("No RREP messages or auction allocations available.")
        return extended_rreps

    print("\n========== RREP PROPAGATION ROUND ==========")

    for rrep in rrep_messages:

        for allocation in auction_results:

            if allocation["txid"] != rrep["txid"]:
                continue

            if allocation["auctioneer"] != rrep["receiver"]:
                continue

            if allocation["path"] != rrep["path"]:
                continue

            new_rrep = extend_rrep_message(
                rrep,
                allocation,
                rreq_result
            )

            if new_rrep is not None:
                extended_rreps.append(new_rrep)

    print("\nRREPs before extension:", len(rrep_messages))
    print("Successfully extended RREPs:", len(extended_rreps))

    return extended_rreps


# =====================================================
# 4. SEPARATE COMPLETE AND INCOMPLETE RREPs
# =====================================================

def separate_completed_rreps(rrep_messages):

    completed = []
    incomplete = []

    for rrep in rrep_messages:

        if rrep["complete"]:
            completed.append(rrep)
        else:
            incomplete.append(rrep)

    print("\n========== RREP COMPLETION STATUS ==========")
    print("Completed paths:", len(completed))
    print("Incomplete paths:", len(incomplete))

    return completed, incomplete


# =====================================================
# 5. CONVERT PATH TO SOURCE-DESTINATION ORDER
# =====================================================

def convert_to_forward_path(rrep):

    return list(reversed(rrep["path"]))


def convert_channel_ids_to_forward_order(rrep):

    return list(reversed(rrep.get("channel_ids", [])))


# =====================================================
# 6. TEST
# =====================================================

if __name__ == "__main__":

    test_rreq = {
        "source": "S",
        "destination": "D",
        "distance": {
            "S": 0,
            "B": 1,
            "A": 2,
            "D": 3
        }
    }

    test_rrep = {
        "txid": "TX001",
        "path": ["D", "A"],
        "channel_ids": [],
        "capacity": None,
        "cost": 0,
        "receiver": "A",
        "destination": "D",
        "complete": False
    }

    test_allocation = {
        "txid": "TX001",
        "auction_id": "PATH_A",
        "auctioneer": "A",
        "bidder": "B",
        "next_hop": "D",
        "path": ["D", "A"],
        "auctioneer_max_capacity": 80000,
        "bid_cap": 60000,
        "allocated_capacity": 50000,
        "bid_price": 7,

        # Example channel IDs for this isolated test.
        "downstream_channel_id": "CHANNEL_A_D",
        "channel_id": "CHANNEL_B_A"
    }

    extended = extend_rrep_message(
        test_rrep,
        test_allocation,
        test_rreq
    )

    if extended is not None:

        print("\nForward path:", convert_to_forward_path(extended))

        print(
            "Forward channel IDs:",
            convert_channel_ids_to_forward_order(extended)
        )


