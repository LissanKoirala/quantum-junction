#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import time
import traceback


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "agent_work" / "checkpoint_unswap_48_42"
HELPER = ROOT / "agent_work" / "checkpoint_unswap_48_42.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("checkpoint_unswap_48_42_mod", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper from {HELPER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result_path = RUN_DIR / "finalize_19180.json"
    started = time.perf_counter()
    try:
        state = mod.load_checkpoint(RUN_DIR)
        left_remaining = (
            state["layers_left"][state["ii_left"] :]
            if state["ii_left"] < len(state["layers_left"])
            else []
        )
        right_remaining = (
            state["layers_right"][state["ii_right"] :]
            if state["ii_right"] < len(state["layers_right"])
            else []
        )
        left_final = left_remaining + state["init_meas"]
        right_final = right_remaining + state["final_meas"]
        print(
            "state",
            state["total_u_consumed"],
            state["T_U"] - state["total_u_consumed"],
            "left_layers",
            len(left_remaining),
            "right_layers",
            len(right_remaining),
            flush=True,
        )
        mps, perm = mod.mpo_to_mps_measure_safe(
            state["mpo_core"],
            left_final,
            right_final,
            max_bond=512,
            cutoff=0.002,
        )
        print("mps_info", mod.tn_info(mps), "perm", perm, flush=True)
        marginal_raw, p0s = mod.extract_marginal_bitstring(mps)
        marginal_variants = mod.bit_variants(marginal_raw, perm)
        print("marginal_raw", marginal_raw, "variants", marginal_variants, flush=True)
        sampling = mod.sample_mps(mps, 4096, perm)
        result = {
            "status": "ok",
            "source_checkpoint_total_u_consumed": state["total_u_consumed"],
            "remaining_estimate": state["T_U"] - state["total_u_consumed"],
            "left_remaining_layers": len(left_remaining),
            "right_remaining_layers": len(right_remaining),
            "mps_info": mod.tn_info(mps),
            "perm": perm,
            "marginal": {
                "raw_site_order": marginal_raw,
                "variants": marginal_variants,
                "p0s_raw_site_order": p0s,
            },
            "sampling": sampling,
            "elapsed_seconds": time.perf_counter() - started,
        }
        result["final_candidate_qiskit_order"] = (
            sampling.get("top_bitstring_qiskit_order")
            or marginal_variants.get("permuted_measurement_order_reversed")
        )
        result_path.write_text(json.dumps(mod.json_safe(result), indent=2, sort_keys=True) + "\n")
        print("wrote", result_path, "final", result["final_candidate_qiskit_order"], flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": "error",
            "type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
