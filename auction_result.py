

from collections import defaultdict
from scipy.optimize import linprog


# =====================================================
# 1. VALIDATE ALLOCATIONS
# =====================================================

def validate_allocations(auction_results, bid_messages):

    bid_lookup = {}

    for bid in bid_messages:

        key = (
            bid["txid"],
            bid["auction_id"],
            bid["auctioneer"],
            bid["bidder"]
        )

        bid_lookup[key] = bid

    groups = defaultdict(list)

    for allocation in auction_results:

        key = (
            allocation["txid"],
            allocation["auction_id"]
        )

        groups[key].append(allocation)

    all_valid = True

    for key, allocations in groups.items():

        total_allocated = sum(
            item["allocated_capacity"]
            for item in allocations
        )

        first = allocations[0]

        first_bid_key = (
            first["txid"],
            first["auction_id"],
            first["auctioneer"],
            first["bidder"]
        )

        max_cap = bid_lookup[first_bid_key]["auctioneer_max_capacity"]

        # Constraint 6b:
        # Total allocation <= auctioneer MaxCap
        capacity_valid = (
            total_allocated <= max_cap + 1e-6
        )

        # Constraint 6c and 6d:
        # 0 <= allocation <= BidCap
        individual_valid = True

        for item in allocations:

            bid_key = (
                item["txid"],
                item["auction_id"],
                item["auctioneer"],
                item["bidder"]
            )

            bid = bid_lookup[bid_key]

            if not (
                -1e-6 <= item["allocated_capacity"]
                <= bid["bid_cap"] + 1e-6
            ):
                individual_valid = False

        print("\nValidating auction:", key)
        print("Auctioneer:", first["auctioneer"])
        print("Total capacity constraint:", capacity_valid)
        print("Individual bid capacity constraint:", individual_valid)

        if not capacity_valid or not individual_valid:
            all_valid = False

    print("\nOverall allocation validation:", all_valid)

    return all_valid


# =====================================================
# 2. VERIFY LP OPTIMALITY
# =====================================================

def verify_optimality(bids, max_cap, lp_allocations, tolerance=1e-5):

    # Objective value obtained from LP.
    lp_objective = sum(
        bid["bid_price"] * allocated
        for bid, allocated in zip(bids, lp_allocations)
    )

    # Independent theoretical optimum.
    remaining_capacity = max_cap
    expected_objective = 0

    sorted_bids = sorted(
        bids,
        key=lambda bid: bid["bid_price"],
        reverse=True
    )

    for bid in sorted_bids:

        if remaining_capacity <= 0:
            break

        if bid["bid_price"] <= 0:
            break

        allocated = min(
            bid["bid_cap"],
            remaining_capacity
        )

        expected_objective += (
            bid["bid_price"] * allocated
        )

        remaining_capacity -= allocated

    is_optimal = abs(
        lp_objective - expected_objective
    ) <= tolerance * max(1, abs(expected_objective))

    print("\nOptimality Verification:")
    print("LP Objective Value:", lp_objective)
    print("Expected Optimal Objective:", expected_objective)
    print("Optimality Check:", is_optimal)

    return is_optimal


# =====================================================
# 3. ALLOCATE CAPACITY
# =====================================================

def allocate_capacity(bid_messages):

    if not bid_messages:
        print("No BID messages available!")
        return []

    # Group by transaction and path-specific auction ID.
    auction_groups = defaultdict(list)

    for bid in bid_messages:

        if "auction_id" not in bid:
            raise ValueError(
                "BID message is missing auction_id. "
                "Update bidding.py first."
            )

        key = (
            bid["txid"],
            bid["auction_id"]
        )

        auction_groups[key].append(bid)

    auction_results = []

    total_auctions = 0
    optimality_passed_count = 0
    optimality_failed_count = 0

    total_allocated_capacity = 0
    total_forwarding_cost = 0

    # Process each independent auction.
    for (txid, auction_id), bids in auction_groups.items():

        total_auctions += 1

        print("\n===================================")
        print("AUCTION RESULT")
        print("Transaction ID:", txid)
        print("Auction ID:", auction_id)
        print("Auctioneer:", bids[0]["auctioneer"])
        print("RREP path:", bids[0].get("path"))

        # MaxCap must be identical for every BID in this auction.
        max_cap = bids[0]["auctioneer_max_capacity"]

        if any(
            bid["auctioneer_max_capacity"] != max_cap
            for bid in bids
        ):
            raise ValueError(
                "Inconsistent MaxCap for auction: " + str(auction_id)
            )

        # All bids in this auction must refer to the same auctioneer.
        auctioneer = bids[0]["auctioneer"]

        if any(
            bid["auctioneer"] != auctioneer
            for bid in bids
        ):
            raise ValueError(
                "Multiple auctioneers found in one auction."
            )

        # -------------------------------------------------
        # LP OBJECTIVE
        # Maximize sum(BidPrice * allocated_capacity)
        # linprog minimizes, so negate bid prices.
        # -------------------------------------------------

        objective = [
            -bid["bid_price"]
            for bid in bids
        ]

        # Constraint 6b:
        # Sum of allocations <= MaxCap.
        A_ub = [[1] * len(bids)]
        b_ub = [max_cap]

        # Constraints 6c and 6d:
        # 0 <= allocation <= BidCap.
        bounds = [
            (0, bid["bid_cap"])
            for bid in bids
        ]

        result = linprog(
            c=objective,
            A_ub=A_ub,
            b_ub=b_ub,
            bounds=bounds,
            method="highs"
        )

        if not result.success:

            print("Optimization failed:", result.message)

            optimality_failed_count += 1
            continue

        # -------------------------------------------------
        # VERIFY OPTIMALITY
        # -------------------------------------------------

        optimality_passed = verify_optimality(
            bids,
            max_cap,
            result.x
        )

        if optimality_passed:
            optimality_passed_count += 1
        else:
            optimality_failed_count += 1
            print("WARNING: LP solution may not be optimal!")

        auction_allocated_capacity = 0
        auction_forwarding_cost = 0

        print("\nAllocation details:")

        for bid, allocated_capacity in zip(bids, result.x):

            allocated_capacity = max(
                0,
                allocated_capacity
            )

            # Total payment for this allocation.
            forwarding_cost = (
                bid["bid_price"] * allocated_capacity
            )

            auction_allocated_capacity += allocated_capacity
            auction_forwarding_cost += forwarding_cost

            total_allocated_capacity += allocated_capacity
            total_forwarding_cost += forwarding_cost

            # Preserve all information needed for RREP propagation.
            # Preserve all information needed for RREP propagation.
            allocation = {
               "txid": txid,
               "auction_id": auction_id,
               "path_id": bid.get("path_id", auction_id),

               "auctioneer": auctioneer,
               "bidder": bid["bidder"],
               "next_hop": bid.get("next_hop"),

               "path": list(bid.get("path", [])),

               # Channel: bidder -> auctioneer
               "channel_id": bid["channel_id"],

                # Channel: auctioneer -> next hop towards destination
               "downstream_channel_id": bid["downstream_channel_id"],

               "bid_price": bid["bid_price"],
               "bid_cap": bid["bid_cap"],

               "auctioneer_max_capacity": max_cap,

               "allocated_capacity": allocated_capacity,
               "forwarding_cost": forwarding_cost
            }
              

            auction_results.append(allocation)

            print("\nBidder:", bid["bidder"])
            print("Bid price:", bid["bid_price"])
            print("Bid capacity:", bid["bid_cap"])
            print("Allocated capacity:", allocated_capacity)
            print("Forwarding cost:", forwarding_cost)

        print("\nMaximum available capacity:", max_cap)
        print("Total allocated capacity:", auction_allocated_capacity)
        print("Total forwarding cost:", auction_forwarding_cost)

    # =================================================
    # 4. OVERALL AUCTION SUMMARY
    # =================================================

    print("\n")
    print("=" * 50)
    print("OVERALL PROTOCOL 3 AUCTION SUMMARY")
    print("=" * 50)

    print("Total Auctions Processed:", total_auctions)
    print("Optimality Checks Passed:", optimality_passed_count)
    print("Optimality Checks Failed:", optimality_failed_count)

    print("Total Allocated Capacity:", total_allocated_capacity)
    print("Total Forwarding Cost:", total_forwarding_cost)

    print("-" * 50)

    if optimality_failed_count == 0:
        print("Overall Optimality Status: PASSED")
    else:
        print("Overall Optimality Status: FAILED")

    print("=" * 50)

    # Validate all generated allocations.
    validation_passed = validate_allocations(
        auction_results,
        bid_messages
    )

    print("\nFinal Allocation Validation:", validation_passed)

    return auction_results


# =====================================================
# 5. TEST LP ALLOCATION
# =====================================================

if __name__ == "__main__":

    test_bids = [

        {
            "txid": "TX001",
            "auction_id": "PATH_A",
            "path_id": "PATH_A",
            "path": ["D", "A"],
            "auctioneer": "A",
            "bidder": "B1",
            "next_hop": "D",
            "channel_id": "CH1",
            "auctioneer_max_capacity": 100000,
            "bid_cap": 50000,
            "bid_price": 10
        },

        {
            "txid": "TX001",
            "auction_id": "PATH_A",
            "path_id": "PATH_A",
            "path": ["D", "A"],
            "auctioneer": "A",
            "bidder": "B2",
            "next_hop": "D",
            "channel_id": "CH2",
            "auctioneer_max_capacity": 100000,
            "bid_cap": 70000,
            "bid_price": 8
        },

        {
            "txid": "TX001",
            "auction_id": "PATH_A",
            "path_id": "PATH_A",
            "path": ["D", "A"],
            "auctioneer": "A",
            "bidder": "B3",
            "next_hop": "D",
            "channel_id": "CH3",
            "auctioneer_max_capacity": 100000,
            "bid_cap": 40000,
            "bid_price": 5
        }
    ]

    results = allocate_capacity(test_bids)


    
    




