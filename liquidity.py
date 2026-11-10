import copy
import json
import networkx as nx

from payment import make_payment
from rreq import rreq_discovery
from rrep import (
    create_rrep_messages,
    extend_rrep_messages,
    separate_completed_rreps,
)
from auction import create_auc_message
from bidding import bidding_setup
from auction_result import allocate_capacity
from route_allocation import allocate_payment_across_routes


# =====================================================
# 1. BUILD LIQUIDITY GRAPH
# =====================================================

def build_liquidity_graph(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # MultiGraph preserves parallel physical payment channels.
    G = nx.MultiGraph()

    # Add Lightning nodes.
    for node in data["nodes"]:
        G.add_node(
            node["pub_key"],
            alias=node.get("alias")
        )

    # Add physical payment channels.
    for edge in data["edges"]:
        node1 = edge["node1_pub"]
        node2 = edge["node2_pub"]

        capacity = int(edge["capacity"])
        channel_id = edge["channel_id"]

        # Simulation assumption: initial directional liquidity is 50:50.
        liquidity_1_to_2 = capacity // 2
        liquidity_2_to_1 = capacity - liquidity_1_to_2

        G.add_edge(
            node1,
            node2,
            key=channel_id,
            channel_id=channel_id,
            capacity=capacity,
            node1_pub=node1,
            node2_pub=node2,
            liquidity_1_to_2=liquidity_1_to_2,
            liquidity_2_to_1=liquidity_2_to_1,
            node1_policy=edge.get("node1_policy"),
            node2_policy=edge.get("node2_policy")
        )

    return G


# =====================================================
# 2. CALCULATE DIRECTIONAL LIQUIDITY RATIO
# =====================================================

def calculate_liquidity_ratio(attributes, direction):
    capacity = attributes["capacity"]

    if capacity <= 0:
        return 0

    if direction == "forward":
        liquidity = attributes["liquidity_1_to_2"]
    elif direction == "reverse":
        liquidity = attributes["liquidity_2_to_1"]
    else:
        raise ValueError("Direction must be forward or reverse")

    return liquidity / capacity


# =====================================================
# 3. VALIDATE LIQUIDITY OF ALL CHANNELS
# =====================================================

def validate_all_liquidity(graph):
    invalid_channels = 0

    for _, _, _, attributes in graph.edges(keys=True, data=True):
        total_liquidity = (
            attributes["liquidity_1_to_2"]
            + attributes["liquidity_2_to_1"]
        )

        if total_liquidity != attributes["capacity"]:
            invalid_channels += 1

    print("\n========== GLOBAL LIQUIDITY VALIDATION ==========")
    print("Total channels:", graph.number_of_edges())
    print("Invalid channels:", invalid_channels)

    if invalid_channels == 0:
        print("All channels preserve their total capacity!")
    else:
        print("WARNING: Some channels do not preserve total capacity!")


# =====================================================
# 4. GENERATE AUC MESSAGES
# =====================================================



# =====================================================
# FINAL PAYMENT LIQUIDITY AUDIT
# =====================================================

def snapshot_used_channels(graph, allocations):
    used_ids = {
        cid
        for item in allocations if item["allocated_amount"] > 0
        for cid in item["channel_ids"]
    }
    snapshot = {}
    for _, _, cid, attrs in graph.edges(keys=True, data=True):
        if cid in used_ids:
            snapshot[cid] = {
                "node1_pub": attrs["node1_pub"],
                "node2_pub": attrs["node2_pub"],
                "capacity": attrs["capacity"],
                "liquidity_1_to_2": attrs["liquidity_1_to_2"],
                "liquidity_2_to_1": attrs["liquidity_2_to_1"],
            }
    return snapshot


def audit_payment_liquidity(initial_snapshot, final_graph, allocations):
    expected_sent = {
        cid: {"liquidity_1_to_2": 0.0, "liquidity_2_to_1": 0.0}
        for cid in initial_snapshot
    }

    for item in allocations:
        amount = item["allocated_amount"]
        if amount <= 0:
            continue
        path = item["path"]
        for hop, cid in enumerate(item["channel_ids"]):
            sender, receiver = path[hop], path[hop + 1]
            before = initial_snapshot[cid]

            if sender == before["node1_pub"] and receiver == before["node2_pub"]:
                direction = "liquidity_1_to_2"
            elif sender == before["node2_pub"] and receiver == before["node1_pub"]:
                direction = "liquidity_2_to_1"
            else:
                print(f"AUDIT ERROR: Endpoint mismatch for channel {cid}")
                return False

            expected_sent[cid][direction] += amount

    final_channels = {
        cid: attrs for _, _, cid, attrs in final_graph.edges(keys=True, data=True)
    }

    passed = True
    print("\n========== FINAL PAYMENT LIQUIDITY AUDIT ==========")

    for cid, before in initial_snapshot.items():
        after = final_channels.get(cid)
        if after is None:
            print(f"FAIL: Channel {cid} missing from final graph")
            passed = False
            continue

        sent_forward = expected_sent[cid]["liquidity_1_to_2"]
        sent_reverse = expected_sent[cid]["liquidity_2_to_1"]

        expected_forward = before["liquidity_1_to_2"] - sent_forward + sent_reverse
        expected_reverse = before["liquidity_2_to_1"] - sent_reverse + sent_forward

        direction_ok = (
            abs(after["liquidity_1_to_2"] - expected_forward) < 1e-6
            and abs(after["liquidity_2_to_1"] - expected_reverse) < 1e-6
        )
        capacity_ok = abs(
            after["liquidity_1_to_2"] + after["liquidity_2_to_1"]
            - before["capacity"]
        ) < 1e-6
        nonnegative_ok = (
            after["liquidity_1_to_2"] >= -1e-6
            and after["liquidity_2_to_1"] >= -1e-6
        )

        channel_ok = direction_ok and capacity_ok and nonnegative_ok
        passed = passed and channel_ok

        print(f"\nChannel: {cid}")
        print("Initial 1->2:", before["liquidity_1_to_2"])
        print("Initial 2->1:", before["liquidity_2_to_1"])
        print("Expected final 1->2:", expected_forward)
        print("Actual final 1->2:", after["liquidity_1_to_2"])
        print("Expected final 2->1:", expected_reverse)
        print("Actual final 2->1:", after["liquidity_2_to_1"])
        print("Directional changes correct:", direction_ok)
        print("Capacity preserved:", capacity_ok)
        print("Balances non-negative:", nonnegative_ok)
        print("Channel audit:", "PASS" if channel_ok else "FAIL")

    print("\nFINAL AUDIT:", "PASSED" if passed else "FAILED")
    print("===================================================")
    return passed



def generate_auc_messages(graph, rreq_result, rrep_messages):
    """
    Generate one AUC message per auctioneer.

    The auctioneer's AUC parameters (MaxCap, WinPrice, tau_fee,
    ReservationPrice) are calculated once. Identical copies are
    addressed to all bidders that sent an RREQ to that auctioneer.

    This prevents a different random tau_fee being generated for
    every bidder of the same auctioneer.
    """
    auc_messages = []
    parents = rreq_result["parents"]

    for rrep in rrep_messages:
        auctioneer = rrep["receiver"]

        # Nodes that sent an RREQ to this auctioneer.
        bidders = parents.get(auctioneer, set())

        if not bidders:
            continue

        # Create the auctioneer's AUC parameters only once.
        base_auc = create_auc_message(
            rreq_result,
            rrep,
            graph
        )

        if base_auc is None:
            continue

        # Address identical AUC parameter copies to each bidder.
        for bidder in bidders:
            auc = copy.deepcopy(base_auc)
            auc["bidder"] = bidder
            auc_messages.append(auc)

            print("\nAUC message generated")
            print("Transaction ID:", auc["txid"])
            print("Auctioneer:", auc["auctioneer"])
            print("Bidder:", auc["bidder"])
            print("Selected channel:", auc["channel_id"])
            print("Maximum capacity:", auc["max_capacity"])
            print("Win price:", auc["win_price"])
            print("Tau fee:", auc["tau_fee"])
            print("Reservation price:", auc["reservation_price"])

    return auc_messages


# =====================================================
# 5. MAIN EXECUTION
# =====================================================

def main():
    file_path = "data/lngraph_2021_11_27__00_00.json"

    # -------------------------------------------------
    # Build graph
    # -------------------------------------------------
    G = build_liquidity_graph(file_path)
    routing_graph = copy.deepcopy(G)  # Preserve clean initial balances.

    print("\n========== LIQUIDITY GRAPH ==========")
    print("Nodes:", G.number_of_nodes())
    print("Channels:", G.number_of_edges())

    # -------------------------------------------------
    # Inspect first channel
    # -------------------------------------------------
    u, v, key, attributes = next(iter(G.edges(keys=True, data=True)))

    print("\n========== FIRST CHANNEL ==========")
    print("Node 1:", u)
    print("Node 2:", v)
    print("Channel ID:", key)
    print("Total capacity:", attributes["capacity"])
    print("Node1 -> Node2 liquidity:", attributes["liquidity_1_to_2"])
    print("Node2 -> Node1 liquidity:", attributes["liquidity_2_to_1"])

    # -------------------------------------------------
    # Payment test
    # -------------------------------------------------
    print("\n========== BEFORE PAYMENT ==========")
    print("Node1 -> Node2:", attributes["liquidity_1_to_2"])
    print("Node2 -> Node1:", attributes["liquidity_2_to_1"])

    make_payment(G, u, v, key, 10000)

    print("\n========== AFTER PAYMENT ==========")
    print("Node1 -> Node2:", attributes["liquidity_1_to_2"])
    print("Node2 -> Node1:", attributes["liquidity_2_to_1"])
    print(
        "Total liquidity:",
        attributes["liquidity_1_to_2"] + attributes["liquidity_2_to_1"]
    )

    # -------------------------------------------------
    # Insufficient liquidity test
    # -------------------------------------------------
    print("\n========== INSUFFICIENT LIQUIDITY TEST ==========")
    make_payment(G, u, v, key, 50000)

    # -------------------------------------------------
    # Reverse direction test
    # -------------------------------------------------
    print("\n========== REVERSE DIRECTION TEST ==========")
    make_payment(G, v, u, key, 10000)

    print("Node1 -> Node2:", attributes["liquidity_1_to_2"])
    print("Node2 -> Node1:", attributes["liquidity_2_to_1"])

    # -------------------------------------------------
    # Parallel channel test
    # -------------------------------------------------
    print("\n========== PARALLEL CHANNEL TEST ==========")

    parallel_pair = None

    for node, keyed_edges in G.adj.items():
        for neighbor, channels in keyed_edges.items():
            if len(channels) >= 2:
                parallel_pair = (node, neighbor, list(channels.items()))
                break
        if parallel_pair is not None:
            break

    if parallel_pair is None:
        print("No parallel channels found!")
    else:
        u_parallel, v_parallel, channels = parallel_pair

        channel_id_1, attributes_1 = channels[0]
        channel_id_2, attributes_2 = channels[1]

        print("Node 1:", u_parallel)
        print("Node 2:", v_parallel)
        print("\nChannel 1:", channel_id_1)
        print("Channel 2:", channel_id_2)

        channel_2_before = (
            attributes_2["liquidity_1_to_2"],
            attributes_2["liquidity_2_to_1"]
        )

        policy_1 = attributes_1["node1_policy"]

        if policy_1 is not None and not policy_1.get("disabled", False):
            print("\nMaking payment through Channel 1...")
            make_payment(G, u_parallel, v_parallel, channel_id_1, 100)
        else:
            print("\nChannel 1 does not permit payment in this direction.")

        channel_2_after = (
            attributes_2["liquidity_1_to_2"],
            attributes_2["liquidity_2_to_1"]
        )

        print("\nChannel 2 liquidity before:", channel_2_before)
        print("Channel 2 liquidity after:", channel_2_after)

        if channel_2_before == channel_2_after:
            print("\nSUCCESS: Channel 2 remained unchanged!")
        else:
            print("\nERROR: Channel 2 liquidity changed!")

    # -------------------------------------------------
    # Liquidity ratio test
    # -------------------------------------------------
    print("\n========== LIQUIDITY RATIO TEST ==========")

    _, _, key_first, first_attributes = next(
        iter(G.edges(keys=True, data=True))
    )

    forward_ratio = calculate_liquidity_ratio(first_attributes, "forward")
    reverse_ratio = calculate_liquidity_ratio(first_attributes, "reverse")

    print("Channel ID:", key_first)
    print("Forward liquidity ratio:", forward_ratio)
    print("Reverse liquidity ratio:", reverse_ratio)
    print("Sum of ratios:", forward_ratio + reverse_ratio)

    # -------------------------------------------------
    # Global liquidity validation
    # -------------------------------------------------
    validate_all_liquidity(G)

    # -------------------------------------------------
    # Discard mutations from preliminary payment tests.
    G = routing_graph

    # RREQ: select a source-destination pair 3 hops apart
    # -------------------------------------------------
    print("\n========== AUROCH RREQ TEST ==========")

    source = None
    destination = None
    target_hops = 3

    # Prefer a 3-hop pair so that we can observe multiple
    # RREP propagation rounds. Fall back to 2 hops if needed.
    for required_hops in (3, 2):
        for candidate in G.nodes:
            lengths = nx.single_source_shortest_path_length(
                G,
                candidate,
                cutoff=required_hops
            )

            destinations = [
                node for node, hops in lengths.items()
                if hops == required_hops
            ]

            if destinations:
                source = candidate
                destination = destinations[0]
                target_hops = required_hops
                break

        if source is not None:
            break

    result = None
    active_rreps = []
    completed_rreps = []
    all_auc_messages = []
    all_bid_messages = []
    all_auction_results = []

    if source is not None:
        print("Selected Source:", source)
        print("Selected Destination:", destination)
        print("Shortest-path distance:", target_hops)

        result = rreq_discovery(
            G,
            source,
            destination,
            txid="TX001"
        )
    else:
        print("No suitable source-destination pair found!")

    # -------------------------------------------------
    # Initial RREP generation
    # -------------------------------------------------
    print("\n========== INITIAL RREP GENERATION ==========")

    if result is not None:
        active_rreps = create_rrep_messages(result)
        print("Initial RREP messages:", len(active_rreps))
    else:
        print("RREP cannot be generated because RREQ failed!")

    # -------------------------------------------------
    # ITERATIVE AUC -> BID -> ALLOCATION -> RREP
    # -------------------------------------------------
    round_number = 1

    while active_rreps:

        print(f"\n\n========== ROUTING ROUND {round_number} ==========")
        print("Active RREP paths:", len(active_rreps))

        # 1. Generate AUC messages for each active RREP.
        print("\n---------- AUC GENERATION ----------")

        auc_messages = generate_auc_messages(
            G,
            result,
            active_rreps
        )

        print("AUC messages:", len(auc_messages))
        all_auc_messages.extend(auc_messages)

        if not auc_messages:
            print("No AUC messages generated. Stopping propagation.")
            break

        # 2. Generate BID messages.
        print("\n---------- BIDDING SETUP ----------")

        bid_messages = bidding_setup(G, auc_messages)

        print("BID messages:", len(bid_messages))
        all_bid_messages.extend(bid_messages)

        if not bid_messages:
            print("No BID messages generated. Stopping propagation.")
            break

        # 3. Solve the auction allocation LP.
        print("\n---------- AUCTION CAPACITY ALLOCATION ----------")

        auction_results = allocate_capacity(bid_messages)

        print("Allocation records:", len(auction_results))
        all_auction_results.extend(auction_results)

        if not auction_results:
            print("No allocation records returned. Stopping propagation.")
            break

        # 4. Extend paths only through positive allocations.
        print("\n---------- RREP PATH EXTENSION ----------")

        next_rreps = extend_rrep_messages(
            active_rreps,
            auction_results,
            result
        )

        if not next_rreps:
            print("No RREP could be extended. Stopping propagation.")
            active_rreps = []
            break

        # 5. Separate paths that reached the source.
        newly_completed, active_rreps = separate_completed_rreps(
            next_rreps
        )

        completed_rreps.extend(newly_completed)

        print("\nRound", round_number, "summary")
        print("Newly completed paths:", len(newly_completed))
        print("Paths continuing to next round:", len(active_rreps))

        round_number += 1

        # The BFS distance strictly decreases at every extension,
        # so a valid path cannot continue indefinitely.
        if round_number > G.number_of_nodes():
            print("Safety stop: exceeded the graph node count.")
            break

    # -------------------------------------------------
    # FINAL ROUTING SUMMARY
    # -------------------------------------------------
    print("\n========== AUROCH ROUTING SUMMARY ==========")
    print("RREQ successful:", result is not None)
    print("Total routing rounds:", round_number - 1)
    print("Total AUC messages:", len(all_auc_messages))
    print("Total BID messages:", len(all_bid_messages))
    print("Total allocation records:", len(all_auction_results))
    print("Completed routes:", len(completed_rreps))

    if completed_rreps:
        print("\n========== COMPLETED ROUTES ==========")

        for index, route in enumerate(completed_rreps, start=1):
            forward_path = list(reversed(route["path"]))

            print(f"\nRoute {index}")
            print("Path (source to destination):", forward_path)
            print("Path capacity:", route["capacity"])
            print("Per-unit path cost:", route["cost"])
    else:
        print("\nNo complete route reached the source.")
        print("Possible reasons: no positive allocation, unavailable")
        print("directional liquidity, or no valid shortest predecessor.")

    # Note: Equation 7 final route selection is not implemented here.
    # This stage propagates RREPs and collects completed candidate routes.
    # ==============================================
    # FINAL PAYMENT ALLOCATION: EQUATION 7
    # ==============================================

    
    # ==============================================
    # FINAL PAYMENT ALLOCATION: EQUATION 7
    # ==============================================

    if completed_rreps:

        payment_amount = 100000  # satoshi

        allocation_result = allocate_payment_across_routes(
            completed_rreps,
            amount=payment_amount,
            graph=G
        )

        # ==============================================
        # EXECUTE THE ALLOCATED PAYMENTS
        # ==============================================

        if allocation_result is not None:

            allocations = allocation_result["allocations"]

            print("\n========== PAYMENT EXECUTION ==========")

            # Work on a temporary graph first.
            # Original G remains unchanged if execution fails.
            working_graph = copy.deepcopy(G)
            initial_liquidity_snapshot = snapshot_used_channels(
                working_graph, allocations
            )

            execution_success = True
            total_executed = 0

            for index, allocation in enumerate(allocations, start=1):

                allocated_amount = allocation["allocated_amount"]

                # Skip routes receiving zero allocation.
                if allocated_amount <= 0:
                    continue

                path = allocation["path"]
                channel_ids = allocation["channel_ids"]

                print(f"\nExecuting Route {index}")
                print("Allocated amount:", allocated_amount)
                print("Path:", path)

                if len(channel_ids) != len(path) - 1:
                    print("ERROR: Channel count does not match path edges!")
                    execution_success = False
                    break

                # Execute payment hop by hop.
                for hop in range(len(path) - 1):

                    sender = path[hop]
                    receiver = path[hop + 1]
                    channel_id = channel_ids[hop]

                    print(
                        f"\nHop {hop + 1}: "
                        f"{sender} -> {receiver}"
                    )

                    success = make_payment(
                        working_graph,
                        sender,
                        receiver,
                        channel_id,
                        allocated_amount
                    )

                    if not success:
                        print("Payment failed at this hop!")
                        execution_success = False
                        break

                if not execution_success:
                    break

                total_executed += allocated_amount

            # Commit only if every allocated route succeeded.
            if execution_success and total_executed == payment_amount:

                G = working_graph

                print("\nSUCCESS: Complete payment executed!")
                print("Total amount transferred:", total_executed)

                validate_all_liquidity(G)
                audit_payment_liquidity(
                    initial_liquidity_snapshot, G, allocations
                )

            else:

                print("\nPAYMENT EXECUTION FAILED!")
                print("Original graph has been preserved.")
                print("Executed amount before rollback:", total_executed)

        else:
            print("\nEquation 7 did not return a valid allocation.")

    else:
        print("\nEquation 7 skipped: No completed routes.")



if __name__ == "__main__":
    main()







