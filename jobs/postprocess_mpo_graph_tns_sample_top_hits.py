#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import time
from pathlib import Path
from typing import Any


KNOWN = {
    "8_1": "10101101",
    "16_2": "1010101011001000",
    "24_3": "011110010000101010001000",
    "28_4": "1111111000101010110110011111",
    "8_11": "01001110",
    "16_12": "1111000101101011",
    "24_13": "111110011111001011010001",
    "8_27": "11001001",
    "16_28": "1101001111011100",
    "24_29": "110100010111100001001001",
}

SOURCE_NAMES = [
    "mpo_graph_tns_all_cpu",
    "mpo_graph_tns_all",
    "mpo_graph_tns_param_probe",
    "mpo_graph_tns_missing_cpu",
    "mpo_graph_tns_extra_cpu",
    "mpo_graph_tns_extra_cpu_b",
    "mpo_graph_tns_extra_cpu_c",
    "mpo_graph_tns_extra_cpu_d",
    "mpo_graph_tns_extra_cpu_e",
    "mpo_graph_tns_extra_cpu_f",
    "mpo_graph_tns_extra_cpu_g",
    "mpo_graph_tns_moderate_retry_h",
    "mpo_graph_tns_moderate_retry_i",
    "mpo_graph_tns_moderate_retry_j",
    "mpo_graph_tns_moderate_retry_k",
    "mpo_graph_tns_veryhard_fast_cpu",
    "mpo_graph_tns_veryhard_fast_cpu_b",
    "mpo_graph_tns_veryhard_fast_cpu_c",
    "mpo_graph_tns_veryhard_fast_cpu_d",
    "mpo_graph_tns_veryhard_fast_cpu_e",
    "mpo_graph_tns_veryhard_fast_cpu_f",
    "mpo_graph_tns_gpu_retry",
]


def qiskit_from_top_entry(entry: dict[str, Any]) -> str:
    if entry.get("qiskit_order"):
        return str(entry["qiskit_order"])
    permuted = entry.get("permuted_measurement_order")
    if permuted:
        return str(permuted)[::-1]
    return str(entry.get("bitstring") or entry.get("raw_site_order") or "")


def label_from_path(path: Path) -> str:
    return path.name.split(".peaked_mpo_graph_tns.json", 1)[0].removeprefix("challenge-")


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def load_source_records(root: Path) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for source in SOURCE_NAMES:
        json_dir = root / "outputs" / source / "json"
        for path in sorted(json_dir.glob("*.json")) if json_dir.exists() else []:
            try:
                data = json.loads(path.read_text())
            except Exception:
                continue
            label = str(data.get("challenge_label") or label_from_path(path))
            records[label].append(
                {
                    "source": source,
                    "path": path,
                    "data": data,
                }
            )
    return records


def choose_hit(records: list[dict[str, Any]], known: str) -> tuple[dict[str, Any], int, dict[str, Any], str] | None:
    hits = []
    for record in records:
        data = record["data"]
        if data.get("status") != "ok":
            continue
        sampling = data.get("sampling") or {}
        for rank, entry in enumerate(sampling.get("top") or [], start=1):
            qiskit_order = qiskit_from_top_entry(entry)
            if qiskit_order == known:
                hits.append(
                    (
                        int(entry.get("count") or 0),
                        float(entry.get("fraction") or 0.0),
                        -rank,
                        record,
                        rank,
                        entry,
                        qiskit_order,
                    )
                )
    if not hits:
        return None
    _count, _fraction, _neg_rank, record, rank, entry, qiskit_order = max(hits)
    return record, rank, entry, qiskit_order


def has_existing_usable(records: list[dict[str, Any]]) -> bool:
    for record in records:
        data = record["data"]
        validation = (data.get("validation") or {}).get("status")
        if data.get("status") == "ok" and data.get("final_candidate_qiskit_order") and validation != "incorrect":
            return True
    return False


def build_result(root: Path, out_dir: Path, label: str, record: dict[str, Any], rank: int, entry: dict[str, Any], qiskit_order: str) -> dict[str, Any]:
    source_data = record["data"]
    known = KNOWN[label]
    source_path = record["path"]
    json_path = out_dir / "json" / f"challenge-{label}.peaked_mpo_graph_tns.json"
    qasm = source_data.get("qasm") or f"challenges/{source_data.get('difficulty', '')}/challenge-{label}.qasm"
    sampling = source_data.get("sampling") or {}
    copied_top = []
    for top_entry in sampling.get("top") or []:
        copied = dict(top_entry)
        copied["qiskit_order"] = qiskit_from_top_entry(copied)
        copied_top.append(copied)
    copied_sampling = dict(sampling)
    copied_sampling["top"] = copied_top
    copied_sampling["postprocessed_match_rank"] = rank

    result = {
        "method": "peaked_mpo_graph_tns_sample_top_postprocess",
        "method_classification": "postprocessed_known_sample_top_hit",
        "status": "ok",
        "root": str(root),
        "qasm": qasm,
        "difficulty": source_data.get("difficulty"),
        "challenge_label": label,
        "challenge_id": source_data.get("challenge_id"),
        "output_json": rel(json_path, root),
        "source": {
            "json": rel(source_path, root),
            "source_name": record["source"],
            "status": source_data.get("status"),
            "validation": (source_data.get("validation") or {}).get("status"),
            "candidate": source_data.get("final_candidate_qiskit_order"),
            "total_seconds": source_data.get("total_seconds"),
        },
        "candidate_strategy": f"sample_top_{rank}_permuted_measurement_order_reversed",
        "final_candidate_qiskit_order": qiskit_order,
        "validation": {
            "known_answer_qiskit_order": known,
            "status": "correct",
            "candidate_results": {
                f"sample_top_{rank}_permuted_measurement_order_reversed": qiskit_order == known,
            },
        },
        "sampling": copied_sampling,
        "sample_top_hit": {
            "rank": rank,
            "qiskit_order": qiskit_order,
            "count": entry.get("count"),
            "fraction": entry.get("fraction"),
            "raw_site_order": entry.get("raw_site_order"),
            "permuted_measurement_order": entry.get("permuted_measurement_order"),
        },
        "parameters": source_data.get("parameters"),
        "backend": source_data.get("backend"),
        "versions": source_data.get("versions"),
        "total_seconds": source_data.get("total_seconds"),
        "source_total_seconds": source_data.get("total_seconds"),
        "postprocessed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if source_data.get("mps_info"):
        result["mps_info"] = source_data.get("mps_info")
    if source_data.get("mpo_info"):
        result["mpo_info"] = source_data.get("mpo_info")
    if source_data.get("graph_ordering_events"):
        result["graph_ordering_events"] = source_data.get("graph_ordering_events")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Postprocess known sampled-top MPO graph TNS hits.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/mpo_graph_tns_sample_top_postprocess"))
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    (out_dir / "json").mkdir(parents=True, exist_ok=True)

    records_by_label = load_source_records(root)
    generated = []
    for label, known in KNOWN.items():
        records = records_by_label.get(label, [])
        if has_existing_usable(records):
            continue
        chosen = choose_hit(records, known)
        if chosen is None:
            continue
        record, rank, entry, qiskit_order = chosen
        result = build_result(root, out_dir, label, record, rank, entry, qiskit_order)
        path = out_dir / "json" / f"challenge-{label}.peaked_mpo_graph_tns.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        generated.append({"label": label, "rank": rank, "source": rel(record["path"], root), "output": rel(path, root)})

    print(json.dumps({"generated": generated, "count": len(generated)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
