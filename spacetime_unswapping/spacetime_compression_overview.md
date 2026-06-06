# Horizontal and Spacetime Compression for Peaked-Circuit MPO Attacks

## 0. Purpose

This document is a consolidated design brief for a coding agent. It explains the issue, the mathematics, the intended algorithmic theory, and a proposed implementation plan for two related approaches:

1. **Horizontal-only compression**: exploit temporal/depth structure in obfuscated peaked circuits.
2. **Combined horizontal + vertical spacetime compression**: exploit both temporal cancellation and qubit/separator structure, including horizontal and vertical unswapping mechanisms.

The target setting is an attack on obfuscated peaked quantum circuits. These circuits are designed so that, when applied to the all-zero input state, one output bitstring has unusually large probability:

\[
s^\star = \arg\max_{s \in \{0,1\}^N} |\langle s|C|0^N\rangle|^2.
\]

The practical goal is to recover \(s^\star\) without brute-force statevector simulation.

The central thesis is:

\[
\boxed{
\text{Graph and symbolic heuristics propose structure; real MPO compression must validate it.}
}
\]

No graph cut, symbolic inverse match, or local window statistic should be treated as proof of low tensor-network complexity. They are proposal mechanisms only.

---

## 1. The Core Issue

Earlier separator-style approaches split the circuit by qubits. Given a qubit partition

\[
V_Q = A \sqcup B,
\]

they classify gates as:

- internal to \(A\),
- internal to \(B\),
- crossing the \(A|B\) boundary.

This gives useful diagnostics, but it is not enough. The largest correctness risk is to rewrite the circuit as if

\[
C \approx C_A C_B C_{\partial},
\]

where \(C_A\) contains all \(A\)-internal gates, \(C_B\) contains all \(B\)-internal gates, and \(C_{\partial}\) contains all cross-boundary gates.

This is generally false.

Quantum gates do not commute just because they belong to different bookkeeping categories. If an internal gate and a boundary gate touch a shared qubit, changing their order changes the unitary. For generic circuits using `rx`, `rz`, `cx`, and `swap`, this reorder is physically invalid.

Any implementation must preserve the original causal order, or only reorder gates after proving the relevant commutation relation.

### 1.1 Why Vertical Separators Are Not Enough

Vertical compression asks:

\[
\boxed{
\text{Can the qubits be divided into weakly interacting modules?}
}
\]

This is helpful if the circuit has spatial modularity. But peaked circuits often hide structure temporally. The challenge circuits are expected to contain identity-like blocks such as

\[
U U^\dagger \approx I,
\]

possibly obscured by swaps, masking, angle sweeping, and relabeling.

A purely vertical graph may see dense repeated interactions and conclude that no separator exists. But the operator may still simplify if contracted from the right temporal split.

Horizontal compression asks:

\[
\boxed{
\text{Where in circuit depth is the intermediate operator easiest to represent?}
}
\]

Combined spacetime compression asks:

\[
\boxed{
\text{Which regions of the circuit tensor network are cheap in both qubit and time directions?}
}
\]

---

## 2. Peaked-Circuit Structure

A peaked circuit \(C\) on \(N\) qubits satisfies:

\[
\max_s |\langle s|C|0^N\rangle|^2 \geq \delta,
\]

where \(\delta\) is noticeably larger than the uniform probability \(2^{-N}\).

A simplified construction is:

\[
C_{\text{ideal}}
=
R \; U_1 U_1^\dagger \; P_1 \; U_2 U_2^\dagger \; P_2 \; U_3 U_3^\dagger,
\]

where:

- \(R\) is a random or shallow scrambling prefix,
- each \(U_i U_i^\dagger\) is an identity block,
- \(P_1,P_2\) are peaking layers,
- the combined effect of peaking layers encodes the hidden bitstring.

Obfuscation may:

- insert or move swaps,
- relabel qubits,
- sweep or transform angles,
- mask obvious inverse-pair structure,
- route gates through long-range interactions,
- apply some rewrites that preserve output probabilities but hide syntactic cancellation.

The implementation should assume that syntactic simplification will often fail.

---

## 3. Tensor-Network View

A circuit is a spacetime tensor network. It has:

- a **qubit/spatial axis**,
- a **time/depth axis**.

An MPS-style state simulator compresses the quantum state along the qubit axis. An MPO-style operator simulator compresses operators along the qubit axis. But the choice of temporal split or temporal grouping can dramatically affect MPO bond dimensions.

For a circuit decomposed into layers,

\[
C = L_T L_{T-1} \cdots L_1,
\]

define the state at depth \(t\):

\[
|\psi_t\rangle = L_t L_{t-1}\cdots L_1 |0^N\rangle.
\]

If represented as an MPS, the bond dimensions are:

\[
\chi_k^{\text{state}}(t),
\qquad k=1,\dots,N-1.
\]

A state-entanglement proxy is:

\[
\mathcal{E}_{\text{state}}(t)
=
\sum_{k=1}^{N-1} \log \chi_k^{\text{state}}(t).
\]

However, for hidden identity blocks, state entanglement may be the wrong diagnostic. The important object is often operator entanglement.

For a segment

\[
U_{a:b} = L_b L_{b-1}\cdots L_a,
\]

represent \(U_{a:b}\) as an MPO with bond dimensions

\[
\chi_k^{\text{op}}(a,b).
\]

Then define:

\[
\mathcal{E}_{\text{op}}(a,b)
=
\sum_k \log \chi_k^{\text{op}}(a,b),
\]

or:

\[
\mathcal{E}_{\max}^{\text{op}}(a,b)
=
\max_k \log \chi_k^{\text{op}}(a,b).
\]

Identity-like operators should have low operator entanglement:

\[
U U^\dagger = I,
\qquad
\chi_k^{\text{op}}(I)=1.
\]

If a block is a permuted identity, it may look expensive in the wrong ordering but become cheap after extracting permutations.

---

## 4. Horizontal-Only Compression

Horizontal-only compression ignores qubit partitioning initially and focuses on circuit depth.

It asks:

\[
\boxed{
\text{Can temporal windows or split points expose low-rank operator cancellation?}
}
\]

### 4.1 Layerization

The circuit should first be converted into greedy non-overlapping layers.

Each gate is represented by:

```python
@dataclass(frozen=True)
class GateInfo:
    time: int
    layer: int | None
    name: str
    qubits: tuple[int, ...]
    params: tuple[float, ...]
    operation: object
```

Important assumptions:

- `time` preserves original instruction order.
- `layer` is a causal depth coordinate, not merely instruction index.
- Barriers and measurements should be removed for unitary analysis.
- Measurements must not be inserted into intermediate subcircuits before quantum-state combination.

### 4.2 Temporal Center Search

The original middle-MPO attack chooses a split near the midpoint:

\[
C = C_L C_R.
\]

It inserts an identity MPO at the split:

\[
C = C_L M C_R,
\qquad
M=I.
\]

Then it absorbs gates inward from the left and right. For a clean mirror circuit, \(M\) remains close to identity. For an obfuscated circuit, hidden permutations can inflate the MPO.

Horizontal center search generalizes this by scanning candidate centers:

\[
c \in \mathcal{C}.
\]

For each center \(c\):

1. initialize \(M_c=I\),
2. absorb a trial depth \(K\) from both sides,
3. optionally test local unswaps,
4. compute a cost:

\[
\mathcal{S}_{\text{center}}(c)
=
\sum_k \log \chi_k(M_c)
+
\eta \log(\mathrm{size}(M_c)).
\]

Then choose:

\[
c^\star
=
\arg\min_c \mathcal{S}_{\text{center}}(c).
\]

If real MPO scoring is not yet implemented, use a proxy but record:

```text
proxy_mpo_score_no_tensor_validation
```

### 4.3 Temporal Windows

Divide the circuit into windows:

\[
C = W_m W_{m-1}\cdots W_1.
\]

Each window is a contiguous range of layers:

\[
W_r = L_{t_r} L_{t_r-1}\cdots L_{t_{r-1}+1}.
\]

Window construction modes:

1. fixed number of layers,
2. approximately fixed number of two-qubit gates,
3. multiple offsets for the same window size,
4. adaptive windows around candidate centers.

Fixed windows are dangerous because they can split an inverse patch. Therefore always support multiple offsets:

```python
for window_size in params.window_sizes:
    for offset in range(window_size):
        evaluate_windowing(window_size, offset)
```

### 4.4 Window Product Compression

For neighboring or mirrored windows \(W_a,W_b\), build approximate MPOs:

\[
M_a \approx W_a,
\qquad
M_b \approx W_b.
\]

If the product compresses:

\[
\mathcal{L}(M_b M_a)
<
\mathcal{L}(M_a)+\mathcal{L}(M_b),
\]

then the windows may contain cancellation.

Use:

\[
\mathcal{L}(M)
=
\sum_k \log \chi_k(M)
+
\eta \log(\mathrm{size}(M)).
\]

Define merge gain:

\[
G(a,b)
=
\mathcal{L}(M_a)
+
\mathcal{L}(M_b)
-
\mathcal{L}(M_bM_a).
\]

Accept a merge only if:

\[
G(a,b) > \Gamma_{\min}.
\]

For proxy mode, replace \(\mathcal{L}\) with feature scores but keep the same interface.

### 4.5 Horizontal Unswapping

Horizontal unswapping acts between temporal windows.

Suppose two windows are hidden inverses:

\[
W_b \approx W_a^\dagger.
\]

With obfuscated qubit relabeling:

\[
W_b \approx P_L W_a^\dagger P_R.
\]

Then a good permutation \(P\) should make:

\[
W_b P W_a \approx I.
\]

Candidate horizontal moves include:

- identity permutation,
- degree-based qubit matching,
- graph-matching permutation,
- support-overlap permutation,
- adjacent swaps in MPO ordering,
- long-range qubit swaps proposed by interaction graphs,
- block swaps for modular structure.

For a candidate permutation \(P\), define:

\[
\Delta_{\text{horiz}}(P)
=
\mathcal{L}(M_b P M_a)
-
\left[
\mathcal{L}(M_a)+\mathcal{L}(M_b)
\right].
\]

Accept if:

\[
\Delta_{\text{horiz}}(P) < -\tau_{\text{horiz}}.
\]

In proxy mode:

- compare gate histograms,
- compare reversed gate names,
- compare self-inverse gates such as `cx`, `cz`, `swap`,
- compare opposite signed angles for parameterized rotations,
- compare interaction graph similarity under permutation,
- compare angle signatures.

But symbolic matching is unreliable. Angle sweeping and masking may deliberately destroy it.

Risk flag:

```text
symbolic_inverse_score_requires_real_mpo_validation
```

### 4.6 Horizontal-Only Objective

A proxy center score may be:

\[
\mathcal{S}_{\text{horizontal}}(c)
=
\alpha_{\text{mpo}} S_{\text{mpo-proxy}}(c)
-
\beta_{\text{inv}} S_{\text{inverse}}(c)
-
\gamma_{\text{graph}} S_{\text{graph-sim}}(c)
+
\lambda_{\text{imb}} I(c)
+
\rho R(c),
\]

where:

- \(S_{\text{inverse}}\) is symbolic inverse similarity,
- \(S_{\text{graph-sim}}\) is interaction graph similarity,
- \(I(c)\) penalizes asymmetric absorption windows,
- \(R(c)\) is a risk penalty,
- lower is better.

Recommended default parameters:

```python
window_sizes = [4, 8, 12, 16]
target_twoq_per_window = 32
center_stride = 1
center_margin = 2
trial_absorb_layers = 8
max_horizontal_candidates = 64
alpha_mpo = 1.0
beta_inverse = 0.75
gamma_graph = 0.5
lambda_imbalance = 0.25
risk_penalty = 1.0
horizontal_acceptance_margin = 1e-6
```

Assumptions:

- These are diagnostics defaults, not physics constants.
- Parameters must be tuned against known validation circuits.
- Real MPO bond dimensions should replace proxies as early as possible.

---

## 5. Vertical Compression

Vertical compression partitions qubits.

Build an interaction graph:

\[
G_Q=(V_Q,E_Q,w),
\]

where:

- \(V_Q\) is the set of qubits,
- each edge \((i,j)\) represents two-qubit interactions,
- \(w_{ij}\) is a weight derived from gate counts, gate types, time, or trial MPO cost.

A bipartition is:

\[
V_Q = A \sqcup B.
\]

The weighted cut is:

\[
\mathrm{cut}(A,B)
=
\sum_{i\in A,j\in B} w_{ij}.
\]

The cut ratio is:

\[
\mathrm{cut\_ratio}(A,B)
=
\frac{\mathrm{cut}(A,B)}
{\sum_{(i,j)\in E_Q} w_{ij}}.
\]

Boundary vertices are:

\[
\partial A = \{i\in A:\exists j\in B,(i,j)\in E_Q\},
\]

\[
\partial B = \{j\in B:\exists i\in A,(i,j)\in E_Q\}.
\]

Boundary size:

\[
b_\partial = |\partial A|+|\partial B|.
\]

### 5.1 Aggressive Warning About SWAPs

Do not treat SWAP as a weak interaction just because it is not entangling.

A SWAP across a proposed partition exchanges logical quantum states between sides. For a decomposition that assumes fixed qubit membership, this is severe. A low SWAP weight can make the partition look artificially good while destroying its physical meaning.

Recommended handling:

1. Track logical wire permutation through explicit SWAPs where possible.
2. Or assign cross-partition SWAPs a high penalty.
3. Or use SWAPs as unswapping candidates rather than ordinary graph edges.

Default:

```python
swap_weight = 4.0
cx_weight = 1.0
rz_weight = 0.0
rx_weight = 0.0
cross_swap_boundary_penalty = 8.0
```

If the challenge circuits use sparse SWAPs as obfuscation, this point matters a lot.

### 5.2 Vertical Boundary Density Over Time

Given temporal windows \(W_r\), define:

\[
d_r(A,B)
=
\#\{g\in W_r:\ g\text{ is a two-qubit gate crossing }A|B\}.
\]

Temporal spread:

\[
\mathrm{spread}(A,B)
=
|\{r:d_r(A,B)>0\}|.
\]

Temporal entropy:

\[
H(A,B)
=
-
\sum_r p_r\log p_r,
\qquad
p_r = \frac{d_r}{\sum_s d_s}.
\]

Interpretation:

- low spread: boundary interactions are localized in time,
- high spread: repeated re-entanglement risk,
- high entropy: boundary gates are distributed broadly.

Boundary gates clustered in one region may be manageable. Boundary gates spread across the whole circuit are dangerous.

### 5.3 Vertical Unswapping

Vertical unswapping refines a partition by testing membership swaps:

\[
a\in A,\quad b\in B,
\]

\[
A'=(A\setminus\{a\})\cup\{b\},
\]

\[
B'=(B\setminus\{b\})\cup\{a\}.
\]

A vertical objective:

\[
\mathcal{J}_{\text{vert}}
=
\alpha_{\text{cut}}\mathrm{cut}(A,B)
+
\beta_{\partial}\mathcal{L}_{\text{MPO},\partial}
+
\gamma_b b_\partial
+
\lambda_{\text{spread}}\mathrm{spread}
+
\lambda_H H
+
\lambda_{\text{bal}}||A|-|B||.
\]

Accept a swap if:

\[
\mathcal{J}_{\text{vert}}(A',B')
<
\mathcal{J}_{\text{vert}}(A,B) - \tau_{\text{vert}}.
\]

Candidate generation:

- boundary-only membership swaps first,
- optional block swaps for communities,
- optional long-range swaps proposed by graph matching,
- avoid empty partitions,
- preserve balance unless explicitly allowed.

Recommended defaults:

```python
max_vertical_refinement_iter = 50
boundary_only_candidates = True
max_size_imbalance = 2
alpha_cut = 1.0
beta_boundary_mpo = 0.5
gamma_boundary_size = 0.5
lambda_temporal_spread = 0.75
lambda_temporal_entropy = 0.25
lambda_balance = 1.0
vertical_acceptance_margin = 1e-9
```

Again, these are starting points, not validated constants.

---

## 6. Combined Horizontal + Vertical Spacetime Compression

The combined method treats the circuit as a spacetime tensor network.

It searches for blocks of the form:

\[
\text{qubit block} \times \text{time window}.
\]

For each temporal window \(W_r\), there may be a qubit partition:

\[
V_Q = A_r \sqcup B_r.
\]

The partition may be:

- global and fixed across all \(r\),
- local to each window,
- slowly varying between neighboring windows,
- inferred only in selected regions.

The full dynamic version is hard. Start staged and conservative.

### 6.1 Spacetime Gate Classification

For each window \(W_r\) and partition \((A_r,B_r)\), classify gates:

1. internal to \(A_r\),
2. internal to \(B_r\),
3. crossing \(A_r|B_r\),
4. temporal boundary interactions between \(W_r\) and \(W_{r+1}\).

Do not reorder the circuit as all internals followed by all boundaries.

Instead, preserve a schedule:

```text
for window in temporal_order:
    apply/contract local gates in original order
    apply/contract boundary gates in original order
    record compression telemetry
```

If blockwise contraction is used, boundary gates must be inserted at their original temporal location or within a window where the reordering is known to be valid.

### 6.2 Spacetime Objective

A general spacetime plan consists of:

- temporal windows \(W_r\),
- qubit partitions \((A_r,B_r)\),
- accepted horizontal unswaps,
- accepted vertical unswaps,
- window merges,
- candidate contraction blocks,
- fallback decision.

The combined objective:

\[
\mathcal{J}_{\text{ST}}
=
\sum_r
\Big[
\alpha_Q \mathrm{cut}_Q(A_r,B_r;W_r)
+
\beta_{\text{op}}\mathcal{L}_{\text{MPO}}(W_r)
+
\gamma_b b_\partial(A_r,B_r;W_r)
+
\lambda_T \mathcal{L}_{\text{time}}(W_r,W_{r+1})
+
\lambda_D D_r(A_r,B_r)
+
\eta \mathrm{cost}(P_r)
\Big].
\]

Where:

- \(\mathrm{cut}_Q(A_r,B_r;W_r)\) is the qubit cut inside window \(r\),
- \(\mathcal{L}_{\text{MPO}}(W_r)\) is operator cost for the window,
- \(b_\partial\) is boundary size,
- \(\mathcal{L}_{\text{time}}\) penalizes poor temporal cancellation between windows,
- \(D_r\) penalizes boundary density/spread,
- \(P_r\) is any accepted permutation or unswap cost.

A simpler proxy:

\[
\mathcal{J}_{\text{proxy}}
=
\alpha_Q \mathrm{vertical\_cut}
+
\beta_T \mathrm{temporal\_mpo\_proxy}
+
\gamma_b \mathrm{boundary\_size}
+
\lambda_s \mathrm{temporal\_spread}
+
\lambda_H \mathrm{temporal\_entropy}
-
\mu_I \mathrm{inverse\_match}
-
\mu_G \mathrm{graph\_similarity}.
\]

Lower is better.

Recommended defaults:

```python
alpha_Q = 1.0
beta_T = 1.0
gamma_b = 0.5
lambda_s = 0.75
lambda_H = 0.25
mu_I = 0.75
mu_G = 0.5
eta_permutation_cost = 0.05
proxy_risk_penalty = 1.0
```

### 6.3 Horizontal Unswapping in the Combined Method

Horizontal unswapping should be evaluated inside the spacetime planner, not only globally.

For candidate window pair \((W_a,W_b)\):

1. propose permutations from window interaction graphs,
2. test whether \(W_b P W_a\) is more compressible,
3. record accepted/rejected moves,
4. update the temporal plan if the move is accepted.

Move types:

```text
horizontal_identity
horizontal_window_permutation
horizontal_adjacent_order_swap
horizontal_long_range_qubit_swap
horizontal_block_swap
```

The accepted move must store:

```python
@dataclass(frozen=True)
class UnswapMove:
    kind: str
    side: str | None
    qubits: tuple[int, ...]
    permutation: dict[int, int] | None
    window_pair: tuple[int, int] | None
    score_before: float
    score_after: float
    proxy_used: bool
    risk_flags: list[str]
```

### 6.4 Vertical Unswapping in the Combined Method

Vertical unswapping may be global or per-window.

Global:

\[
(A,B)\text{ fixed for all windows.}
\]

Per-window:

\[
(A_r,B_r)\text{ selected independently for each }W_r.
\]

Slowly varying:

\[
(A_{r+1},B_{r+1})
\text{ may differ from }
(A_r,B_r)
\text{ only by cheap swaps.}
\]

Start with global and per-window diagnostics. Avoid dynamic partitions in the first implementation unless diagnostics show a clear need.

Move types:

```text
vertical_boundary_membership_swap
vertical_block_swap
vertical_ordering_adjacent_swap
vertical_swap_logical_wire_update
```

Vertical unswapping should not be sold as actual physical SWAP insertion. It is a refinement of the decomposition/ordering, unless the implementation explicitly modifies the tensor network with permutation operators.

### 6.5 Central MPO Unswapping

Central MPO unswapping is the bridge to the original attack.

For a candidate temporal center \(c\):

1. insert identity MPO,
2. absorb gates from left and right,
3. when bond dimensions grow, test unswap moves,
4. accept moves that reduce:

\[
\mathcal{L}_{\text{MPO}}(M)
=
\sum_k \log \chi_k(M)
+
\eta \log(\mathrm{size}(M)).
\]

The best center is:

\[
c^\star
=
\arg\min_c \mathcal{L}_{\text{trial}}(c).
\]

The spacetime planner should expose this as a scorer hook:

```python
class MPOScorer:
    def score_center(self, qc, layers, center, params) -> MPOScore:
        ...

    def score_window(self, window, params) -> MPOScore:
        ...

    def score_window_product(self, window_a, window_b, permutation, params) -> MPOScore:
        ...

    def score_boundary(self, qc, A, B, windows, params) -> MPOScore:
        ...
```

### 6.6 Planner Modes

Implement three planner modes.

#### Horizontal-first

1. remove measurements,
2. layerize,
3. find best temporal center,
4. create windows around the center,
5. run horizontal window merge/unswapping,
6. build windowed interaction graphs,
7. run vertical partition diagnostics inside selected windows,
8. refine partitions by vertical unswapping,
9. output plan.

Use this when temporal identity structure is likely dominant.

#### Vertical-first

1. remove measurements,
2. layerize,
3. build global interaction graph,
4. find global partition,
5. refine by vertical unswapping,
6. compute boundary density by window,
7. identify clustered boundary regions,
8. run horizontal unswapping around those regions,
9. output plan.

Use this when modular qubit structure is likely dominant.

#### Alternating

1. initialize windows,
2. compute partitions per window,
3. refine vertical partitions,
4. use boundary-density profile to adjust windows,
5. run horizontal unswapping between candidate inverse windows,
6. repeat while the total score improves,
7. stop if only proxy improvements remain tiny.

Accepted moves must be monotonic under the currently selected score:

\[
\mathcal{J}_{t+1} \leq \mathcal{J}_t - \tau.
\]

### 6.7 Fallback Decision

Recommend fallback to global MPO-unswapping if:

- no good temporal center is found,
- horizontal unswaps do not improve score,
- vertical cut ratios are high,
- boundary density is spread across most windows,
- proxy-only risk flags dominate,
- dense-random diagnostics are severe,
- trial MPO scorer reports runaway bond growth.

Fallback is not failure. It means the spacetime planner did not find reliable exploitable structure.

---

## 7. Required Dataclasses

```python
@dataclass(frozen=True)
class GateInfo:
    time: int
    layer: int | None
    name: str
    qubits: tuple[int, ...]
    params: tuple[float, ...]
    operation: object
```

```python
@dataclass
class TemporalWindow:
    index: int
    layer_start: int
    layer_end: int
    gates: list[GateInfo]
```

```python
@dataclass
class MPOScore:
    cost: float
    max_bond_dim: int | None
    sum_log_bond_dim: float | None
    size: int | None
    discarded_weight: float | None
    proxy_used: bool
    risk_flags: list[str]
```

```python
@dataclass(frozen=True)
class UnswapMove:
    kind: str
    side: str | None
    qubits: tuple[int, ...]
    permutation: dict[int, int] | None
    window_pair: tuple[int, int] | None
    score_before: float
    score_after: float
    proxy_used: bool
    risk_flags: list[str]
```

```python
@dataclass
class SpacetimePlan:
    best_center: int | None
    windows: list[TemporalWindow]
    window_merges: list[dict]
    horizontal_unswaps: list[dict]
    vertical_partitions: dict[int, tuple[set[int], set[int]]]
    vertical_unswaps: list[dict]
    total_score: float
    fallback_recommended: bool
    risk_flags: list[str]
```

---

## 8. Suggested Package Structure

```text
spacetime_unswapping/
    __init__.py
    circuit_tools.py
    layer_tools.py
    window_tools.py
    feature_tools.py
    mpo_scoring.py
    horizontal_unswapping.py
    vertical_unswapping.py
    spacetime_planner.py
    diagnostics.py
    test_circuits.py
    run_spacetime_unswapping.py
    tests/
        test_layer_tools.py
        test_window_tools.py
        test_horizontal_unswapping.py
        test_vertical_unswapping.py
        test_spacetime_planner.py
```

---

## 9. Required Implementation Interfaces

### 9.1 Circuit Tools

```python
def remove_measurements(qc):
    """Return a copy without measurements, barriers, and delays if configured."""
```

```python
def load_circuit(path):
    """Load QASM or QPY circuit."""
```

```python
def iter_gate_infos(qc):
    """Yield GateInfo objects preserving original instruction order."""
```

```python
def count_two_qubit_gates(qc):
    """Return total two-qubit gate count."""
```

### 9.2 Layer Tools

```python
def greedy_layerize(qc):
    """Convert a circuit into greedy non-overlapping layers."""
```

```python
def layer_support(layer):
    """Return qubits touched by a layer."""
```

```python
def layer_twoq_count(layer):
    """Return number of two-qubit gates in a layer."""
```

### 9.3 Window Tools

```python
def make_fixed_layer_windows(layers, window_size):
    """Group layers into fixed-size windows."""
```

```python
def make_twoq_count_windows(layers, target_twoq):
    """Group layers by approximate two-qubit count."""
```

```python
def make_multi_offset_windows(layers, window_size, offset):
    """Create shifted windowing for offset scans."""
```

```python
def flatten_window(window):
    """Return all GateInfo objects in a temporal window."""
```

### 9.4 Feature Tools

```python
def window_gate_histogram(window):
    """Return gate-name counts."""
```

```python
def window_interaction_graph(window):
    """Build weighted qubit graph for two-qubit gates in the window."""
```

```python
def window_support(window):
    """Return qubits touched by the window."""
```

```python
def angle_signature(window, rounding=6):
    """Return coarse gate-angle signature."""
```

```python
def inverse_symbolic_score(window_a, window_b):
    """
    Score whether window_b looks like inverse(window_a).
    Normalize to [0,1].
    """
```

```python
def permuted_inverse_symbolic_score(window_a, window_b, permutation):
    """Apply qubit relabeling and compute inverse score."""
```

```python
def interaction_graph_similarity(window_a, window_b, permutation=None):
    """Compare weighted interaction graphs."""
```

### 9.5 MPO Scoring

```python
class MPOScorer:
    def score_center(self, qc, layers, center, params) -> MPOScore:
        raise NotImplementedError

    def score_window(self, window, params) -> MPOScore:
        raise NotImplementedError

    def score_window_product(self, window_a, window_b, permutation, params) -> MPOScore:
        raise NotImplementedError

    def score_boundary(self, qc, A, B, windows, params) -> MPOScore:
        raise NotImplementedError
```

Proxy implementation:

```python
class ProxyMPOScorer(MPOScorer):
    """
    Uses gate counts, support size, graph similarity, symbolic inverse score,
    and boundary density. Always emits proxy risk flags.
    """
```

Real implementation placeholder:

```python
class RealMPOScorer(MPOScorer):
    """
    Future implementation:
    - trial MPO absorption,
    - SVD compression,
    - local unswapping,
    - actual bond dimensions,
    - discarded weights.
    """
```

---

## 10. Tests

Required synthetic circuits:

1. clean mirror:

\[
C = U U^\dagger.
\]

Expected: best center near true midpoint.

2. shifted mirror:

\[
C = A U U^\dagger B.
\]

Expected: best center differs from literal midpoint if padding is asymmetric.

3. swapped mirror:

\[
C = U P U^\dagger P^{-1}
\]

or equivalent hidden permutation structure.

Expected: permutation-aware horizontal score improves over identity.

4. modular mirror:

\[
C = (U_A\otimes U_B)(U_A^\dagger\otimes U_B^\dagger)
\]

with sparse cross gates.

Expected: horizontal center and vertical partition are both useful.

5. temporal boundary cluster:

Cross-boundary gates occur in one temporal region.

Expected: boundary density concentrated in few windows.

6. temporally spread boundary:

Cross-boundary gates occur throughout the circuit.

Expected: high temporal spread risk flag.

7. dense random:

No expected structure.

Expected: fallback recommended.

8. masked toy inverse:

Near-inverse circuit with symbolic signatures partially destroyed.

Expected: weak symbolic match and risk flag requiring real MPO validation.

9. bad initial partition:

Expected: vertical boundary unswapping improves cut or score.

10. alternating monotonicity:

Expected: accepted moves do not increase selected total score.

---

## 11. Parameters

Recommended initial parameter dataclass:

```python
@dataclass
class SpacetimeParams:
    # Windowing
    window_sizes: tuple[int, ...] = (4, 8, 12, 16)
    target_twoq_per_window: int = 32
    center_stride: int = 1
    center_margin: int = 2
    trial_absorb_layers: int = 8

    # Candidate limits
    max_horizontal_candidates: int = 64
    max_vertical_candidates: int = 256
    max_horizontal_refinement_iter: int = 20
    max_vertical_refinement_iter: int = 50
    max_alternating_iter: int = 10

    # Scoring weights
    alpha_q_cut: float = 1.0
    beta_temporal_mpo: float = 1.0
    gamma_boundary_size: float = 0.5
    lambda_temporal_spread: float = 0.75
    lambda_temporal_entropy: float = 0.25
    lambda_balance: float = 1.0
    mu_inverse_match: float = 0.75
    mu_graph_similarity: float = 0.5
    eta_permutation_cost: float = 0.05
    proxy_risk_penalty: float = 1.0

    # Acceptance thresholds
    horizontal_acceptance_margin: float = 1e-6
    vertical_acceptance_margin: float = 1e-9
    alternating_acceptance_margin: float = 1e-6
    max_cut_ratio: float = 0.15
    max_boundary_fraction: float = 0.35
    max_temporal_spread_fraction: float = 0.4
    max_size_imbalance: int = 2

    # Gate weights
    cx_weight: float = 1.0
    cz_weight: float = 1.0
    swap_weight: float = 4.0
    cross_swap_boundary_penalty: float = 8.0

    # MPO compression
    max_bond: int = 8192
    cutoff_window: float = 1e-5
    cutoff_final: float = 1e-3
    unswap_threshold: float = 1e6

    # Reproducibility
    seed: int | None = 0

    # Modes
    score_mode: str = "proxy"  # "proxy" | "real"
    planner_mode: str = "horizontal_first"
```

Important cutoff assumption:

\[
\epsilon_{\text{window}} < \epsilon_{\text{final}}.
\]

Window compression should be less lossy than final compression, because aggressive local truncation can destroy singular-vector information needed for later cancellation.

---

## 12. Aggressive Bug and Inaccuracy Checklist

A coding agent should actively question the following.

### 12.1 Physical Correctness

- Are gates being reordered across noncommuting operations?
- Are boundary gates applied at their original temporal locations?
- Are measurements inserted before final extraction?
- Are SWAPs treated as logical wire movement or merely weak edges?
- Are qubit permutations tracked consistently through MPS/MPO site ordering?
- Does bitstring output respect Qiskit's big-endian convention?

### 12.2 Mathematical Validity

- Is a graph cut being mistaken for entanglement cost?
- Is symbolic inverse matching being mistaken for operator cancellation?
- Is state entanglement being used when operator entanglement is required?
- Are fixed windows splitting inverse blocks?
- Is local compression discarding information needed for global cancellation?

### 12.3 Algorithmic Robustness

- Does the planner report fallback when evidence is weak?
- Are risk flags emitted for proxy-only scores?
- Are accepted moves monotonic under the selected objective?
- Are thresholds scaled by qubit count, depth, or window count?
- Are dense-random circuits rejected rather than overfit?
- Are all candidate moves recorded, including rejected moves?

### 12.4 Testing Gaps

- Is there an exact small-circuit equivalence test?
- Is there a test where invalid `C_A C_B C_boundary` reordering fails?
- Is there a swapped mirror test where identity permutation is not enough?
- Is there a test where symbolic matching fails but real MPO should succeed?
- Is there a temporally spread boundary test?
- Is there a dense random fallback test?

---

## 13. Development Stages

### Stage 1: Pure Diagnostics

Implement:

1. circuit loading,
2. measurement removal,
3. layerization,
4. windowing,
5. window features,
6. symbolic inverse score,
7. interaction graph similarity,
8. diagnostics JSON.

No real MPO required.

### Stage 2: Proxy Horizontal Compression

Implement:

1. temporal center search,
2. candidate window pairs,
3. proxy window-product score,
4. horizontal permutation proposals,
5. accepted/rejected horizontal moves.

### Stage 3: Proxy Vertical Compression

Implement:

1. windowed interaction graphs,
2. global and per-window partitions,
3. boundary density by window,
4. vertical membership swaps,
5. partition risk flags.

### Stage 4: Combined Planner

Implement:

1. horizontal-first,
2. vertical-first,
3. alternating,
4. fallback decision,
5. plan summary.

### Stage 5: Real MPO Scoring

Replace proxies with:

1. trial center MPO absorption,
2. window product MPO compression,
3. local unswapping,
4. boundary MPO scoring,
5. actual bond dimensions and discarded weights.

### Stage 6: Peak Recovery Integration

After a good plan is found:

1. run real MPO-unswapping on selected blocks,
2. combine blocks while preserving temporal order,
3. apply remaining boundary/window operators,
4. extract or sample candidate bitstring,
5. validate against known answers where available.

---

## 14. Final Coding-Agent Instruction

Implement the planner as diagnostics first, not as a solver that pretends to be correct.

The output should answer:

1. What temporal center or windows look promising?
2. What qubit partitions look promising inside those windows?
3. Which horizontal unswaps improved the score?
4. Which vertical unswaps improved the score?
5. Which scores are proxy-only?
6. Which risks make the plan unreliable?
7. Should the downstream attack use horizontal-only, vertical-only, combined spacetime, or global MPO-unswapping fallback?

The final design principle is:

\[
\boxed{
\text{MPO-unswapping generalized to spacetime, with proxies treated only as proposals.}
}
\]

Do not claim success from a low graph cut. Do not claim success from symbolic inverse matching. Do not reorder gates unless the physical semantics are preserved. Real compression telemetry is the final arbiter.
