"""Slurm array entrypoint: read config line N from a JSONL file, run crack(), write JSON.

Each config line is a dict with at least {"challenge": "<rel path under challenges/>", "label": "..."}
plus any crack() kwargs. The challenge field may be the basename (e.g. "challenge-48_37.qasm")
or a path; we resolve it under REPO/challenges/**.
"""
import sys, os, json, glob, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crack

REPO = crack.REPO
OUTROOT = os.path.join(REPO, "outputs/opus_combined")


def resolve_challenge(name):
    if os.path.isabs(name) and os.path.exists(name):
        return name
    cand = os.path.join(REPO, name)
    if os.path.exists(cand):
        return cand
    base = os.path.basename(name)
    hits = glob.glob(os.path.join(REPO, "challenges", "**", base), recursive=True)
    if hits:
        return hits[0]
    raise FileNotFoundError(name)


def main():
    cfg_file = sys.argv[1]
    idx = int(sys.argv[2])
    lines = [l for l in open(cfg_file).read().splitlines() if l.strip()]
    if idx >= len(lines):
        print(f"index {idx} >= {len(lines)} configs; nothing to do")
        return
    cfg = json.loads(lines[idx])
    label = cfg.pop("label", f"cfg{idx}")
    ch = resolve_challenge(cfg.pop("challenge"))
    chname = os.path.basename(ch).replace(".qasm", "")

    outdir = os.path.join(OUTROOT, chname)
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, f"{label}.json")

    print(f"[run_one] challenge={ch}\n[run_one] label={label} out={outpath}\n[run_one] cfg={cfg}", flush=True)

    # GPU sanity check if requested
    if cfg.get("use_gpu"):
        import torch
        ok = torch.cuda.is_available()
        dev = torch.cuda.get_device_name(0) if ok else "none"
        print(f"[run_one] cuda_available={ok} device={dev}", flush=True)
        try:
            _ = (torch.ones(8, 8, dtype=torch.complex128, device="cuda:0") @
                 torch.ones(8, 8, dtype=torch.complex128, device="cuda:0"))
            torch.cuda.synchronize()
            print("[run_one] cuda complex128 matmul OK", flush=True)
        except Exception as e:
            print(f"[run_one] GPU UNUSABLE: {e!r} -- falling back to CPU", flush=True)
            cfg["use_gpu"] = False

    t0 = time.time()
    try:
        res = crack.crack(ch, **cfg)
        chk = crack.check_known(res)
        if chk:
            res["validation"] = chk
        res["status"] = "ok"
    except Exception as e:
        res = {"challenge": os.path.basename(ch), "label": label, "status": "error",
               "error": repr(e), "traceback": traceback.format_exc()}
    res["label"] = label
    res["wall_seconds"] = round(time.time() - t0, 1)
    with open(outpath, "w") as f:
        json.dump(res, f, indent=2)
    print(f"[run_one] DONE status={res.get('status')} "
          f"remaining_layers={res.get('remaining_layers')} "
          f"top_frac={res.get('sample_top_fraction')} "
          f"min_margin={res.get('marginal_min_margin')} "
          f"validation={res.get('validation')}", flush=True)


if __name__ == "__main__":
    main()
