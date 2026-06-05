#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "agent_work" / "algebraic_simplify"
RESULTS_DIR = OUT_DIR / "results"

GATE_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*)\s*(?:\(([^)]*)\))?\s+(.*);$")
Q_RE = re.compile(r"q\[(\d+)\]")
QREG_RE = re.compile(r"qreg\s+q\[(\d+)\];")
ANGLE_CALL_RE = re.compile(r"\b(r[xyz])\(([^()]*)\)")
CHALLENGE_RE = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")


@dataclass(frozen=True)
class Gate:
    op: str
    qubits: tuple[int, ...]
    angle: float | None
    angle_expr: str | None
    line_no: int


@dataclass
class SimpleGate:
    op: str
    qubits: tuple[int, ...]
    angle: float | None = None


def challenge_sort_key(path: Path) -> tuple[str, int, int, str]:
    m = CHALLENGE_RE.search(path.name)
    if m:
        return (path.parent.name, int(m.group(2)), int(m.group(1)), str(path))
    return (path.parent.name, 10**9, 10**9, str(path))


def parse_angle(expr: str | None) -> float | None:
    if expr is None:
        return None
    try:
        return float(eval(expr, {"__builtins__": {}}, {"pi": math.pi}))
    except Exception:
        return None


def format_pi_fraction(value: float, max_den: int = 16) -> str:
    frac = Fraction(value / math.pi).limit_denominator(max_den)
    num = frac.numerator
    den = frac.denominator
    if num == 0:
        return "0"
    if den == 1:
        if num == 1:
            return "pi"
        if num == -1:
            return "-pi"
        return f"{num}*pi"
    if num == 1:
        return f"pi/{den}"
    if num == -1:
        return f"-pi/{den}"
    return f"{num}*pi/{den}"


def nearest_pi_fraction(value: float, max_den: int = 16) -> tuple[float, int, int, float]:
    frac = Fraction(value / math.pi).limit_denominator(max_den)
    approx = float(frac) * math.pi
    return abs(value - approx), frac.numerator, frac.denominator, approx


def normalize_angle(value: float, tol: float = 1e-10) -> float:
    wrapped = math.fmod(value + math.pi, 2 * math.pi)
    if wrapped < 0:
        wrapped += 2 * math.pi
    wrapped -= math.pi
    if abs(wrapped) < tol or abs(abs(wrapped) - 2 * math.pi) < tol:
        return 0.0
    if abs(wrapped - math.pi) < tol:
        return math.pi
    if abs(wrapped + math.pi) < tol:
        return math.pi
    return wrapped


def is_near_mod(value: float, target: float, tol: float) -> bool:
    return abs(normalize_angle(value - target, tol=0.0)) <= tol


def bitstring_from_bits(bits: list[int]) -> str:
    return "".join(str(bits[i] & 1) for i in range(len(bits) - 1, -1, -1))


def parse_qasm(path: Path) -> tuple[int, list[Gate], Counter[str]]:
    text = path.read_text()
    qreg = QREG_RE.search(text)
    if not qreg:
        raise ValueError(f"no qreg in {path}")
    n = int(qreg.group(1))
    skipped: Counter[str] = Counter()
    gates: list[Gate] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("OPENQASM", "include", "qreg", "creg", "measure", "barrier")):
            continue
        m = GATE_RE.match(line)
        if not m:
            skipped[line] += 1
            continue
        op, angle_expr, args = m.groups()
        qubits = tuple(map(int, Q_RE.findall(args)))
        gates.append(Gate(op=op, qubits=qubits, angle=parse_angle(angle_expr), angle_expr=angle_expr, line_no=line_no))
    return n, gates, skipped


def count_ops(gates: Iterable[Gate | SimpleGate]) -> dict[str, int]:
    return dict(Counter(g.op for g in gates))


def static_stats(path: Path, n: int, gates: list[Gate]) -> dict:
    op_counts = Counter(g.op for g in gates)
    angle_counts_by_tol: dict[str, int] = {}
    rx_pi_by_tol: dict[str, int] = {}
    rz_pi2_by_tol: dict[str, int] = {}
    cliffordish_by_tol: dict[str, int] = {}
    frac_counter: Counter[str] = Counter()
    angle_errors: list[float] = []
    rx_pi_lines_exact: list[int] = []
    rx_pi_qubits_exact: Counter[int] = Counter()
    entangling_positions: list[int] = []
    exact_rx_pi_positions: list[int] = []
    exact_rx_pi_after_last_ent = 0
    for idx, gate in enumerate(gates):
        if gate.op in {"cx", "swap"}:
            entangling_positions.append(idx)
        if gate.angle is None:
            continue
        err, num, den, approx = nearest_pi_fraction(gate.angle, 16)
        angle_errors.append(err)
        if err <= 1e-3:
            frac_counter[f"{num}/{den}"] += 1
        for tol in (1e-12, 1e-9, 1e-7, 1e-5, 1e-3, 1e-2):
            key = f"{tol:g}"
            if err <= tol:
                angle_counts_by_tol[key] = angle_counts_by_tol.get(key, 0) + 1
            if gate.op == "rx" and is_near_mod(gate.angle, math.pi, tol):
                rx_pi_by_tol[key] = rx_pi_by_tol.get(key, 0) + 1
            if gate.op == "rz" and is_near_mod(abs(gate.angle), math.pi / 2, tol):
                rz_pi2_by_tol[key] = rz_pi2_by_tol.get(key, 0) + 1
            if is_near_mod(gate.angle, round(gate.angle / (math.pi / 2)) * (math.pi / 2), tol):
                cliffordish_by_tol[key] = cliffordish_by_tol.get(key, 0) + 1
        if gate.op == "rx" and gate.angle_expr is not None and gate.angle_expr.replace(" ", "") in {"pi", "+pi", "-pi"}:
            rx_pi_lines_exact.append(gate.line_no)
            exact_rx_pi_positions.append(idx)
            rx_pi_qubits_exact[gate.qubits[0]] += 1
    last_ent = entangling_positions[-1] if entangling_positions else -1
    if last_ent >= 0:
        exact_rx_pi_after_last_ent = sum(1 for pos in exact_rx_pi_positions if pos > last_ent)
    line_density = len(gates) / max(1, n)
    return {
        "path": str(path),
        "difficulty": path.parent.name,
        "qreg": n,
        "gate_count": len(gates),
        "gate_density_per_qubit": line_density,
        "op_counts": dict(op_counts),
        "angle_counts_near_pi_fraction": angle_counts_by_tol,
        "rx_pi_counts_by_tol": rx_pi_by_tol,
        "rz_pi_over_2_counts_by_tol": rz_pi2_by_tol,
        "cliffordish_counts_by_tol": cliffordish_by_tol,
        "top_pi_fractions_tol_1e-3": frac_counter.most_common(16),
        "angle_error_quantiles": quantiles(angle_errors),
        "exact_rx_pi_count": len(rx_pi_lines_exact),
        "exact_rx_pi_lines_first20": rx_pi_lines_exact[:20],
        "exact_rx_pi_qubits": dict(sorted(rx_pi_qubits_exact.items())),
        "exact_rx_pi_after_last_entangler": exact_rx_pi_after_last_ent,
        "leading_single_qubit_gates": entangling_positions[0] if entangling_positions else len(gates),
        "trailing_single_qubit_gates": len(gates) - last_ent - 1 if last_ent >= 0 else 0,
    }


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p50": None, "p90": None, "p99": None, "max": None}
    vals = sorted(values)
    def pick(q: float) -> float:
        return vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))]
    return {"min": vals[0], "p50": pick(0.5), "p90": pick(0.9), "p99": pick(0.99), "max": vals[-1]}


def simple_greedy_reduce(gates: list[Gate], n: int, snap_tol: float | None = None, snap_den: int = 16) -> dict:
    reduced: list[SimpleGate | None] = []
    wire_stack: list[list[int]] = [[] for _ in range(n)]
    removed = Counter()
    merged = Counter()

    def live_last(q: int) -> int | None:
        stack = wire_stack[q]
        while stack and reduced[stack[-1]] is None:
            stack.pop()
        return stack[-1] if stack else None

    def append_gate(gate: SimpleGate) -> None:
        idx = len(reduced)
        reduced.append(gate)
        for q in gate.qubits:
            wire_stack[q].append(idx)

    def delete_gate(idx: int, why: str) -> None:
        gate = reduced[idx]
        if gate is None:
            return
        removed[why] += 1
        reduced[idx] = None
        for q in gate.qubits:
            live_last(q)

    for gate in gates:
        angle = gate.angle
        if snap_tol is not None and angle is not None:
            err, _num, _den, approx = nearest_pi_fraction(angle, snap_den)
            if err <= snap_tol:
                angle = approx
        if gate.op in {"rx", "rz"} and len(gate.qubits) == 1 and angle is not None:
            q = gate.qubits[0]
            last_idx = live_last(q)
            if last_idx is not None:
                prev = reduced[last_idx]
                if prev is not None and prev.op == gate.op and prev.qubits == gate.qubits and prev.angle is not None:
                    prev.angle = normalize_angle(prev.angle + angle, tol=max(1e-10, snap_tol or 0.0))
                    merged[f"{gate.op}_same_axis"] += 1
                    if abs(prev.angle) <= max(1e-10, snap_tol or 0.0):
                        delete_gate(last_idx, f"{gate.op}_zero_after_merge")
                    continue
            angle = normalize_angle(angle, tol=max(1e-10, snap_tol or 0.0))
            if abs(angle) <= max(1e-10, snap_tol or 0.0):
                removed[f"{gate.op}_zero"] += 1
                continue
            append_gate(SimpleGate(gate.op, gate.qubits, angle))
        elif gate.op in {"cx", "swap"} and len(gate.qubits) == 2:
            q0, q1 = gate.qubits
            last0 = live_last(q0)
            last1 = live_last(q1)
            if last0 is not None and last0 == last1:
                prev = reduced[last0]
                same_cx = prev is not None and gate.op == "cx" and prev.op == "cx" and prev.qubits == gate.qubits
                same_swap = prev is not None and gate.op == "swap" and prev.op == "swap" and set(prev.qubits) == set(gate.qubits)
                if same_cx or same_swap:
                    delete_gate(last0, f"{gate.op}_self_inverse_pair")
                    removed[f"{gate.op}_self_inverse_pair_current"] += 1
                    continue
            append_gate(SimpleGate(gate.op, gate.qubits, None))
        else:
            append_gate(SimpleGate(gate.op, gate.qubits, angle))

    live = [g for g in reduced if g is not None]
    return {
        "snap_tol": snap_tol,
        "snap_den": snap_den,
        "gate_count": len(live),
        "op_counts": count_ops(live),
        "removed": dict(removed),
        "merged": dict(merged),
        "reduction_fraction": 1.0 - (len(live) / max(1, len(gates))),
    }


def linear_window_stats(gates: list[Gate], n: int, max_matrix_n: int = 160) -> dict:
    windows: list[list[Gate]] = []
    cur: list[Gate] = []
    for gate in gates:
        if gate.op in {"cx", "swap"} and len(gate.qubits) == 2:
            cur.append(gate)
        else:
            if cur:
                windows.append(cur)
                cur = []
    if cur:
        windows.append(cur)

    identity = 0
    pure_perm = 0
    general_linear = 0
    hist = Counter()
    top_windows = []
    for win in windows:
        hist[len(win)] += 1
        kind = classify_linear_window(win, n) if n <= max_matrix_n else "skipped"
        if kind == "identity":
            identity += 1
        elif kind == "permutation":
            pure_perm += 1
        elif kind == "linear":
            general_linear += 1
        if len(top_windows) < 20:
            top_windows.append({"start_line": win[0].line_no, "end_line": win[-1].line_no, "length": len(win), "kind": kind})
        else:
            min_len = min(w["length"] for w in top_windows)
            if len(win) > min_len:
                idx = next(i for i, w in enumerate(top_windows) if w["length"] == min_len)
                top_windows[idx] = {"start_line": win[0].line_no, "end_line": win[-1].line_no, "length": len(win), "kind": kind}
    top_windows.sort(key=lambda w: (-w["length"], w["start_line"]))
    return {
        "window_count": len(windows),
        "entangling_gates_in_windows": sum(len(w) for w in windows),
        "length_hist_top": hist.most_common(20),
        "max_window": max(hist) if hist else 0,
        "identity_windows": identity,
        "pure_permutation_windows": pure_perm,
        "general_linear_windows": general_linear,
        "top_windows": top_windows,
    }


def classify_linear_window(win: list[Gate], n: int) -> str:
    rows = [1 << i for i in range(n)]
    for gate in win:
        a, b = gate.qubits
        if gate.op == "swap":
            rows[a], rows[b] = rows[b], rows[a]
        elif gate.op == "cx":
            rows[b] ^= rows[a]
    if all(rows[i] == (1 << i) for i in range(n)):
        return "identity"
    seen = set()
    for row in rows:
        if row == 0 or row & (row - 1):
            return "linear"
        bit = row.bit_length() - 1
        if bit in seen:
            return "linear"
        seen.add(bit)
    return "permutation"


def structural_bit_candidates(gates: list[Gate], n: int, tol: float = 1e-9) -> dict:
    exact_lines: list[int] = []
    snapped_lines: list[int] = []

    bits_exact = [0] * n
    bits_snap = [0] * n
    bits_swap_only_exact = [0] * n
    bits_swap_only_snap = [0] * n
    perm_exact = list(range(n))
    perm_snap = list(range(n))

    for gate in gates:
        if gate.op == "swap":
            a, b = gate.qubits
            bits_exact[a], bits_exact[b] = bits_exact[b], bits_exact[a]
            bits_snap[a], bits_snap[b] = bits_snap[b], bits_snap[a]
            perm_exact[a], perm_exact[b] = perm_exact[b], perm_exact[a]
            perm_snap[a], perm_snap[b] = perm_snap[b], perm_snap[a]
            continue
        if gate.op == "cx":
            c, t = gate.qubits
            bits_exact[t] ^= bits_exact[c]
            bits_snap[t] ^= bits_snap[c]
            continue
        if gate.op != "rx" or gate.angle is None:
            continue
        q = gate.qubits[0]
        exact_pi = gate.angle_expr is not None and gate.angle_expr.replace(" ", "") in {"pi", "+pi", "-pi"}
        near_pi = is_near_mod(gate.angle, math.pi, tol)
        if exact_pi:
            exact_lines.append(gate.line_no)
            bits_exact[q] ^= 1
            bits_swap_only_exact[perm_exact[q]] ^= 1
        if near_pi:
            snapped_lines.append(gate.line_no)
            bits_snap[q] ^= 1
            bits_swap_only_snap[perm_snap[q]] ^= 1

    return {
        "tol": tol,
        "x_cxswap_exact_rxpi": bitstring_from_bits(bits_exact),
        "x_cxswap_near_rxpi": bitstring_from_bits(bits_snap),
        "x_swaponly_exact_rxpi_logical": bitstring_from_bits(bits_swap_only_exact),
        "x_swaponly_near_rxpi_logical": bitstring_from_bits(bits_swap_only_snap),
        "exact_rxpi_toggle_count": len(exact_lines),
        "near_rxpi_toggle_count": len(snapped_lines),
        "exact_rxpi_lines_first30": exact_lines[:30],
        "near_rxpi_lines_first30": snapped_lines[:30],
    }


def snap_qasm_text(text: str, tol: float, max_den: int) -> tuple[str, Counter[str]]:
    stats: Counter[str] = Counter()

    def repl(match: re.Match[str]) -> str:
        gate = match.group(1)
        expr = match.group(2)
        value = parse_angle(expr)
        if value is None:
            return match.group(0)
        err, _num, _den, approx = nearest_pi_fraction(value, max_den)
        if err <= tol:
            stats[f"{gate}_snapped"] += 1
            return f"{gate}({format_pi_fraction(approx, max_den)})"
        return match.group(0)

    return ANGLE_CALL_RE.sub(repl, text), stats


def qiskit_metrics(path: Path, snap_tol: float | None = None, max_den: int = 16) -> dict:
    start = time.time()
    try:
        from qiskit import QuantumCircuit, transpile
    except Exception as exc:
        return {"available": False, "error": repr(exc)}

    try:
        text = path.read_text()
        snap_stats: Counter[str] = Counter()
        if snap_tol is not None:
            text, snap_stats = snap_qasm_text(text, tol=snap_tol, max_den=max_den)
            qc = QuantumCircuit.from_qasm_str(text)
        else:
            qc = QuantumCircuit.from_qasm_file(str(path))
        qc = qc.remove_final_measurements(inplace=False)
    except Exception as exc:
        return {"available": True, "load_error": repr(exc), "seconds": time.time() - start}

    def metrics_for(label: str, **kwargs) -> dict:
        t0 = time.time()
        try:
            tqc = transpile(qc, seed_transpiler=12345, **kwargs)
            return {
                "ok": True,
                "size": int(tqc.size()),
                "depth": int(tqc.depth()),
                "ops": dict(tqc.count_ops()),
                "seconds": time.time() - t0,
            }
        except Exception as exc:
            return {"ok": False, "error": repr(exc), "seconds": time.time() - t0}

    result = {
        "available": True,
        "snap_tol": snap_tol,
        "snap_stats": dict(snap_stats),
        "original": {
            "size": int(qc.size()),
            "depth": int(qc.depth()),
            "ops": dict(qc.count_ops()),
        },
        "opt3_native": metrics_for(
            "opt3_native",
            basis_gates=["rx", "rz", "cx", "swap"],
            optimization_level=3,
        ),
        "opt3_auto": metrics_for("opt3_auto", optimization_level=3),
    }
    result["seconds"] = time.time() - start
    return result


def exact_statevector_peak(path: Path, n_limit: int = 16) -> dict:
    try:
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Statevector
    except Exception as exc:
        return {"available": False, "error": repr(exc)}
    n, _gates, _skipped = parse_qasm(path)
    if n > n_limit:
        return {"available": True, "skipped": True, "reason": f"qreg {n} > limit {n_limit}"}
    t0 = time.time()
    try:
        qc = QuantumCircuit.from_qasm_file(str(path)).remove_final_measurements(inplace=False)
        sv = Statevector.from_instruction(qc)
        probs = sv.probabilities_dict()
        peak = max(probs, key=probs.get)
        return {"available": True, "skipped": False, "peak": peak, "probability": float(probs[peak]), "seconds": time.time() - t0}
    except Exception as exc:
        return {"available": True, "skipped": False, "error": repr(exc), "seconds": time.time() - t0}


def analyze_one(path: Path, with_qiskit: bool, with_statevector: bool) -> dict:
    rel = path.relative_to(ROOT)
    n, gates, skipped = parse_qasm(path)
    static = static_stats(rel, n, gates)
    simple = {
        "exact": simple_greedy_reduce(gates, n, snap_tol=None),
        "snap_1e-7_den16": simple_greedy_reduce(gates, n, snap_tol=1e-7, snap_den=16),
        "snap_1e-5_den16": simple_greedy_reduce(gates, n, snap_tol=1e-5, snap_den=16),
        "snap_1e-3_den16": simple_greedy_reduce(gates, n, snap_tol=1e-3, snap_den=16),
    }
    candidates = {
        "tol_1e-9": structural_bit_candidates(gates, n, tol=1e-9),
        "tol_1e-5": structural_bit_candidates(gates, n, tol=1e-5),
        "tol_1e-3": structural_bit_candidates(gates, n, tol=1e-3),
    }
    result = {
        "path": str(rel),
        "n": n,
        "skipped_lines": dict(skipped),
        "static": static,
        "simple_greedy": simple,
        "linear_windows": linear_window_stats(gates, n),
        "structural_candidates": candidates,
    }
    if with_qiskit:
        result["qiskit"] = {
            "raw": qiskit_metrics(path, snap_tol=None),
            "snap_1e-7_den16": qiskit_metrics(path, snap_tol=1e-7, max_den=16),
            "snap_1e-5_den16": qiskit_metrics(path, snap_tol=1e-5, max_den=16),
            "snap_1e-3_den16": qiskit_metrics(path, snap_tol=1e-3, max_den=16),
        }
    if with_statevector:
        result["statevector_limit16"] = exact_statevector_peak(path, n_limit=16)
    return result


def result_path_for(challenge_path: Path) -> Path:
    rel = challenge_path.relative_to(ROOT)
    safe = "__".join(rel.with_suffix("").parts) + ".json"
    return RESULTS_DIR / safe


def run_one(args: argparse.Namespace) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path
    result = analyze_one(path, with_qiskit=not args.no_qiskit, with_statevector=args.statevector)
    out = result_path_for(path)
    out.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(f"wrote {out.relative_to(ROOT)}", flush=True)


def iter_result_files() -> list[Path]:
    return sorted(RESULTS_DIR.glob("challenges__*.json"))


def flatten_summary(record: dict) -> dict:
    static = record["static"]
    exact = record["simple_greedy"]["exact"]
    snap_1e3 = record["simple_greedy"]["snap_1e-3_den16"]
    row = {
        "path": record["path"],
        "difficulty": static["difficulty"],
        "n": record["n"],
        "gates": static["gate_count"],
        "rx": static["op_counts"].get("rx", 0),
        "rz": static["op_counts"].get("rz", 0),
        "cx": static["op_counts"].get("cx", 0),
        "swap": static["op_counts"].get("swap", 0),
        "exact_rx_pi": static["exact_rx_pi_count"],
        "near_rx_pi_1e-3": static["rx_pi_counts_by_tol"].get("0.001", 0),
        "cliffordish_1e-3": static["cliffordish_counts_by_tol"].get("0.001", 0),
        "greedy_exact_gates": exact["gate_count"],
        "greedy_exact_reduction": exact["reduction_fraction"],
        "greedy_snap_1e3_gates": snap_1e3["gate_count"],
        "greedy_snap_1e3_reduction": snap_1e3["reduction_fraction"],
        "linear_window_count": record["linear_windows"]["window_count"],
        "linear_identity_windows": record["linear_windows"]["identity_windows"],
        "linear_perm_windows": record["linear_windows"]["pure_permutation_windows"],
        "linear_max_window": record["linear_windows"]["max_window"],
        "candidate_x_cxswap_1e3": record["structural_candidates"]["tol_1e-3"]["x_cxswap_near_rxpi"],
        "candidate_x_swaponly_1e3": record["structural_candidates"]["tol_1e-3"]["x_swaponly_near_rxpi_logical"],
    }
    qiskit = record.get("qiskit")
    if qiskit:
        raw = qiskit.get("raw", {})
        row["qiskit_raw_native_size"] = raw.get("opt3_native", {}).get("size")
        row["qiskit_raw_native_depth"] = raw.get("opt3_native", {}).get("depth")
        row["qiskit_raw_auto_size"] = raw.get("opt3_auto", {}).get("size")
        row["qiskit_raw_auto_depth"] = raw.get("opt3_auto", {}).get("depth")
        snap = qiskit.get("snap_1e-3_den16", {})
        row["qiskit_snap_1e3_native_size"] = snap.get("opt3_native", {}).get("size")
        row["qiskit_snap_1e3_native_depth"] = snap.get("opt3_native", {}).get("depth")
        row["qiskit_snap_1e3_auto_size"] = snap.get("opt3_auto", {}).get("size")
        row["qiskit_snap_1e3_auto_depth"] = snap.get("opt3_auto", {}).get("depth")
        row["qiskit_snap_1e3_snapped"] = sum(snap.get("snap_stats", {}).values())
    sv = record.get("statevector_limit16")
    if sv and not sv.get("skipped") and "peak" in sv:
        row["sv_peak"] = sv["peak"]
        row["sv_peak_prob"] = sv["probability"]
        row["cand_cxswap_matches_sv"] = row["candidate_x_cxswap_1e3"] == sv["peak"]
        row["cand_swaponly_matches_sv"] = row["candidate_x_swaponly_1e3"] == sv["peak"]
    return row


def summarize(args: argparse.Namespace) -> None:
    files = iter_result_files()
    if not files:
        raise SystemExit("no result json files found")
    rows = [flatten_summary(json.loads(path.read_text())) for path in files]
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    csv_path = OUT_DIR / "summary.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)

    by_diff: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_diff[row["difficulty"]].append(row)

    rollup = {}
    for diff, diff_rows in sorted(by_diff.items()):
        rollup[diff] = summarize_rows(diff_rows)
    validation = {
        "statevector_rows": [
            {
                "path": r["path"],
                "peak": r.get("sv_peak"),
                "prob": r.get("sv_peak_prob"),
                "cxswap_match": r.get("cand_cxswap_matches_sv"),
                "swaponly_match": r.get("cand_swaponly_matches_sv"),
                "candidate_cxswap": r.get("candidate_x_cxswap_1e3"),
                "candidate_swaponly": r.get("candidate_x_swaponly_1e3"),
            }
            for r in rows
            if "sv_peak" in r
        ]
    }
    summary = {"rollup": rollup, "validation": validation, "rows": rows}
    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote {csv_path.relative_to(ROOT)}")
    print(f"wrote {summary_path.relative_to(ROOT)}")
    print(json.dumps({"rollup": rollup, "validation": validation}, indent=2, sort_keys=True))


def summarize_rows(rows: list[dict]) -> dict:
    def avg(key: str) -> float | None:
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return sum(vals) / len(vals) if vals else None

    def total(key: str) -> int | float:
        return sum(r.get(key, 0) or 0 for r in rows if isinstance(r.get(key, 0), (int, float)))

    return {
        "files": len(rows),
        "n_min": min(r["n"] for r in rows),
        "n_max": max(r["n"] for r in rows),
        "gates_avg": avg("gates"),
        "gates_min": min(r["gates"] for r in rows),
        "gates_max": max(r["gates"] for r in rows),
        "exact_rx_pi_total": total("exact_rx_pi"),
        "near_rx_pi_1e-3_total": total("near_rx_pi_1e-3"),
        "cliffordish_1e-3_avg": avg("cliffordish_1e-3"),
        "greedy_exact_reduction_avg": avg("greedy_exact_reduction"),
        "greedy_snap_1e3_reduction_avg": avg("greedy_snap_1e3_reduction"),
        "qiskit_raw_native_size_avg": avg("qiskit_raw_native_size"),
        "qiskit_raw_auto_size_avg": avg("qiskit_raw_auto_size"),
        "qiskit_snap_1e3_native_size_avg": avg("qiskit_snap_1e3_native_size"),
        "qiskit_snap_1e3_auto_size_avg": avg("qiskit_snap_1e3_auto_size"),
        "linear_identity_windows_total": total("linear_identity_windows"),
        "linear_perm_windows_total": total("linear_perm_windows"),
        "linear_max_window_max": max(r["linear_max_window"] for r in rows),
    }


def write_file_list(args: argparse.Namespace) -> None:
    paths = sorted((ROOT / "challenges").glob("*/*.qasm"), key=challenge_sort_key)
    out = OUT_DIR / "challenge_files.txt"
    out.write_text("\n".join(str(p.relative_to(ROOT)) for p in paths) + "\n")
    print(f"wrote {out.relative_to(ROOT)} with {len(paths)} files")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("one")
    one.add_argument("path")
    one.add_argument("--no-qiskit", action="store_true")
    one.add_argument("--statevector", action="store_true")
    sub.add_parser("summarize")
    sub.add_parser("write-file-list")
    args = parser.parse_args(argv)
    if args.cmd == "one":
        run_one(args)
    elif args.cmd == "summarize":
        summarize(args)
    elif args.cmd == "write-file-list":
        write_file_list(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
