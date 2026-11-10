
import random


# =====================================================
# 1. CALCULATE BID CAPACITY
# =====================================================

def calculate_bid_capacity(graph, bidder, auctioneer):

    channels = graph.get_edge_data(bidder, auctioneer)

    if channels is None:
        return None

    available_channels = []

    for channel_id, attributes in channels.items():

        # Payment direction: bidder -> auctioneer
        if bidder == attributes["node1_pub"]:
            liquidity = attributes["liquidity_1_to_2"]
            policy = attributes["node1_policy"]

        elif bidder == attributes["node2_pub"]:
            liquidity = attributes["liquidity_2_to_1"]
            policy = attributes["node2_policy"]

        else:
            continue

        if policy is None or policy.get("disabled", False):
            continue

        if liquidity > 0:
            available_channels.append({
                "channel_id": channel_id,
                "bid_capacity": liquidity
            })

    if not available_channels:
        return None

    # Simulation assumption: select highest directional liquidity.
    return max(
        available_channels,
        key=lambda channel: channel["bid_capacity"]
    )


# =====================================================
# 2. PRICING RULE 2
# =====================================================

def calculate_pricing_rule_2(auctioneers):

    total_capacity = sum(
        auc["max_capacity"]
        for auc in auctioneers.values()
    )

    total_reservation_price = sum(
        auc["reservation_price"]
        for auc in auctioneers.values()
    )

    if total_capacity <= 0 or total_reservation_price <= 0:
        return {}

    pricing_results = {}

    f_min = 1
    f_max = 10

    for auction_key, auc in auctioneers.items():

        capacity = auc["max_capacity"]
        res_price = auc["reservation_price"]

        # Equation 3
        vt_price = (
            capacity / total_capacity
        ) * (
            1 - res_price / total_reservation_price
        )

        # Equation 5
        tau_2 = f_min + vt_price * (f_max - f_min)

        # Equation 4
        bid_price = res_price + tau_2

        pricing_results[auction_key] = {
            "vt_price": vt_price,
            "tau_2": tau_2,
            "bid_price": bid_price
        }

    return pricing_results


# =====================================================
# 3. BIDDING SETUP
# =====================================================

def bidding_setup(graph, auc_messages):

    bidder_auctions = {}
    bid_messages = []

    rule1_count = 0
    rule2_count = 0

    # Group AUC messages by bidder.
    for auc in auc_messages:

        bidder = auc["bidder"]

        auction_key = (
            auc.get("auction_id", auc["auctioneer"]),
            auc["auctioneer"]
        )

        bidder_auctions.setdefault(bidder, {})
        bidder_auctions[bidder][auction_key] = auc

    # Process each bidder.
    for bidder, auctions in bidder_auctions.items():

        print("\n===================================")
        print("BIDDER:", bidder)
        print("Number of AUC messages:", len(auctions))

        # Placeholder: actual ECDSA verification
        # is not implemented yet.
        signature_valid = True

        if not signature_valid:
            print("Invalid AUC signature. Skipping bidder.")
            continue

        # -------------------------------------------------
        # CASE 1: ONE AUC -> PRICING RULE 1
        # -------------------------------------------------

        if len(auctions) == 1:

            rule1_count += 1

            auction_key, auc = next(iter(auctions.items()))

            auctioneer = auc["auctioneer"]

            channel = calculate_bid_capacity(
                graph,
                bidder,
                auctioneer
            )

            if channel is None:
                print("No usable channel to auctioneer:", auctioneer)
                continue

            tau_1 = random.randint(1, 10)

            bid_price = auc["reservation_price"] + tau_1

            bid = {
                "txid": auc["txid"],
                "auction_id": auc.get("auction_id", auction_key[0]),
                "path_id": auc.get("path_id", auction_key[0]),
                "path": list(auc.get("path", [])),

                "bidder": bidder,
                "auctioneer": auctioneer,
                "next_hop": auc.get("next_hop"),

                # Channel selected by bidder:
                # bidder -> auctioneer
                "channel_id": channel["channel_id"],

                # Channel selected by auctioneer:
                # auctioneer -> next hop towards destination
                "downstream_channel_id": auc["channel_id"],

                "bid_cap": channel["bid_capacity"],
                "auctioneer_max_capacity": auc["max_capacity"],

                "tau_1": tau_1,
                "bid_price": bid_price
            }

            bid_messages.append(bid)

            print("Pricing Rule 1 selected")
            print("Auction ID:", bid["auction_id"])
            print("Path:", bid["path"])
            print("Bidder channel:", bid["channel_id"])
            print("Downstream channel:", bid["downstream_channel_id"])
            print("Bid capacity:", bid["bid_cap"])
            print("Tau 1:", tau_1)
            print("Bid price:", bid_price)

        # -------------------------------------------------
        # CASE 2: MULTIPLE AUCs -> PRICING RULE 2
        # -------------------------------------------------

        else:

            rule2_count += 1

            pricing_results = calculate_pricing_rule_2(auctions)

            print("Pricing Rule 2 selected")

            for auction_key, auc in auctions.items():

                auctioneer = auc["auctioneer"]

                channel = calculate_bid_capacity(
                    graph,
                    bidder,
                    auctioneer
                )

                if channel is None:
                    print("No usable channel to auctioneer:", auctioneer)
                    continue

                pricing = pricing_results.get(auction_key)

                if pricing is None:
                    continue

                bid = {
                    "txid": auc["txid"],
                    "auction_id": auc.get("auction_id", auction_key[0]),
                    "path_id": auc.get("path_id", auction_key[0]),
                    "path": list(auc.get("path", [])),

                    "bidder": bidder,
                    "auctioneer": auctioneer,
                    "next_hop": auc.get("next_hop"),

                    # Channel selected by bidder:
                    # bidder -> auctioneer
                    "channel_id": channel["channel_id"],

                    # Channel selected by auctioneer:
                    # auctioneer -> next hop towards destination
                    "downstream_channel_id": auc["channel_id"],

                    "bid_cap": channel["bid_capacity"],
                    "auctioneer_max_capacity": auc["max_capacity"],

                    "vt_price": pricing["vt_price"],
                    "tau_2": pricing["tau_2"],
                    "bid_price": pricing["bid_price"]
                }

                bid_messages.append(bid)

                print("\nAuctioneer:", auctioneer)
                print("Auction ID:", bid["auction_id"])
                print("Path:", bid["path"])
                print("Bidder channel:", bid["channel_id"])
                print("Downstream channel:", bid["downstream_channel_id"])
                print("Bid capacity:", bid["bid_cap"])
                print("VtPrice:", pricing["vt_price"])
                print("Tau 2:", pricing["tau_2"])
                print("Bid price:", pricing["bid_price"])

    # -------------------------------------------------
    # FINAL STATISTICS
    # -------------------------------------------------

    print("\n========== BIDDING STATISTICS ==========")
    print("Pricing Rule 1 bidders:", rule1_count)
    print("Pricing Rule 2 bidders:", rule2_count)
    print("Total bidders:", rule1_count + rule2_count)
    print("Total BID messages:", len(bid_messages))

    return bid_messages


# =====================================================
# 4. TEST PRICING RULE 2
# =====================================================

if __name__ == "__main__":

    test_auctioneers = {

        ("PATH_A", "Auctioneer_A"): {
            "max_capacity": 40000,
            "reservation_price": 2
        },

        ("PATH_B", "Auctioneer_B"): {
            "max_capacity": 60000,
            "reservation_price": 4
        }
    }

    results = calculate_pricing_rule_2(test_auctioneers)

    for auction_key, result in results.items():

        print("\n", auction_key)
        print("VtPrice:", result["vt_price"])
        print("Tau 2:", result["tau_2"])
        print("Bid price:", result["bid_price"])


