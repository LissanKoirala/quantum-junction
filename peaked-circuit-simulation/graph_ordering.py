import networkx as nx
import numpy as np


def build_interaction_graph(qc, gate_weight_fn=None):
    n = qc.num_qubits
    G = nx.Graph()
    G.add_nodes_from(range(n))
    if gate_weight_fn is None:
        gate_weight_fn = lambda op, t: 1.0
    qubit_to_index = {q: i for i, q in enumerate(qc.qubits)}
    for t, inst in enumerate(qc.data):
        op = inst.operation
        qargs = inst.qubits
        if len(qargs) != 2:
            continue
        i = qubit_to_index[qargs[0]]
        j = qubit_to_index[qargs[1]]
        if i == j:
            continue
        w = gate_weight_fn(op, t)
        if G.has_edge(i, j):
            G[i][j]["weight"] += w
            G[i][j]["count"] += 1
        else:
            G.add_edge(i, j, weight=w, count=1)
    return G


def gate_aware_weight(op, t):
    if op.name == "swap":
        return 0.2
    if op.name in {"rzz", "rzx", "rxx", "ryy", "rzz", "xx_plus_yy", "cx", "cz", "ecr", "iswap"}:
        return 1.0
    if op.name in {"unitary"}:
        return 1.0
    return 0.5


def ordering_to_position(ordering):
    """ordering[pos] = qubit  →  position[qubit] = pos"""
    return {q: pos for pos, q in enumerate(ordering)}


def weighted_bandwidth_cost(G, ordering):
    pos = ordering_to_position(ordering)
    cost = 0.0
    for i, j, data in G.edges(data=True):
        cost += data.get("weight", 1.0) * abs(pos[i] - pos[j])
    return cost


def rcm_ordering(G):
    """Reverse Cuthill-McKee ordering, handles disconnected graphs."""
    if nx.is_connected(G):
        return list(nx.utils.reverse_cuthill_mckee_ordering(G, heuristic=None))
    ordering = []
    for comp in nx.connected_components(G):
        sub = G.subgraph(comp)
        ordering.extend(nx.utils.reverse_cuthill_mckee_ordering(sub, heuristic=None))
    return ordering


def refine_ordering_by_adjacent_swaps(G, ordering, max_sweeps=10):
    ordering = list(ordering)
    best_cost = weighted_bandwidth_cost(G, ordering)
    for _ in range(max_sweeps):
        improved = False
        for k in range(len(ordering) - 1):
            ordering[k], ordering[k + 1] = ordering[k + 1], ordering[k]
            c = weighted_bandwidth_cost(G, ordering)
            if c < best_cost:
                best_cost = c
                improved = True
            else:
                ordering[k], ordering[k + 1] = ordering[k + 1], ordering[k]
        if not improved:
            break
    return ordering


def refine_ordering_by_insert_moves(G, ordering, max_sweeps=2):
    ordering = list(ordering)
    best_cost = weighted_bandwidth_cost(G, ordering)
    n = len(ordering)
    for _ in range(max_sweeps):
        improved = False
        for old_pos in range(n):
            q = ordering[old_pos]
            for new_pos in range(n):
                if new_pos == old_pos:
                    continue
                proposal = list(ordering)
                proposal.pop(old_pos)
                proposal.insert(new_pos, q)
                c = weighted_bandwidth_cost(G, proposal)
                if c < best_cost:
                    ordering = proposal
                    best_cost = c
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return ordering


def compute_graph_ordering(qc, gate_weight_fn=None, refine=True):
    G = build_interaction_graph(qc, gate_weight_fn=gate_weight_fn)
    if G.number_of_edges() == 0:
        return list(range(qc.num_qubits)), G
    ordering = rcm_ordering(G)
    if refine:
        ordering = refine_ordering_by_adjacent_swaps(G, ordering)
        ordering = refine_ordering_by_insert_moves(G, ordering)
    return ordering, G


# ── Tree TNS diagnostics ────────────────────────────────────────────


def maximum_spanning_tree(G):
    return nx.maximum_spanning_tree(G, weight="weight")


def best_tree_dfs_ordering(G, T):
    best_order = None
    best_cost = float("inf")
    for root in T.nodes:
        order = list(nx.dfs_preorder_nodes(T, source=root))
        cost = weighted_bandwidth_cost(G, order)
        if cost < best_cost:
            best_order = order
            best_cost = cost
    return best_order, best_cost


def block_score(G, block, eps=1e-12):
    block = set(block)
    win = wout = 0.0
    for i, j, data in G.edges(data=True):
        w = data.get("weight", 1.0)
        if i in block and j in block:
            win += w
        elif (i in block) != (j in block):
            wout += w
    return win / (wout + eps)


def candidate_blocks_from_tree(T, min_size=2, max_size=6):
    blocks = set()
    for edge in list(T.edges()):
        T_copy = T.copy()
        T_copy.remove_edge(*edge)
        for comp in nx.connected_components(T_copy):
            if min_size <= len(comp) <= max_size:
                blocks.add(tuple(sorted(comp)))
    return list(blocks)


def rank_blocks(G, blocks):
    scored = [(block_score(G, b), b) for b in blocks]
    scored.sort(reverse=True)
    return scored


def tree_tns_diagnostic(G, b_max=4, eta=3.0):
    n = G.number_of_nodes()
    if G.number_of_edges() == 0:
        return {"tree": None, "tree_ordering": list(range(n)), "blocks": [], "tree_cost": 0.0}

    T = maximum_spanning_tree(G)
    tree_order, tree_cost = best_tree_dfs_ordering(G, T)

    blocks_raw = candidate_blocks_from_tree(T, min_size=2, max_size=b_max)
    ranked = rank_blocks(G, blocks_raw)

    accepted_blocks = []
    used: set = set()
    for score, block in ranked:
        if score < eta:
            continue
        if used.intersection(set(block)):
            continue
        accepted_blocks.append(block)
        used.update(block)

    return {"tree": T, "tree_ordering": tree_order, "blocks": accepted_blocks, "tree_cost": tree_cost}
