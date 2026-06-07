"""Aggregate outputs/opus_combined/*/*.json into a confidence-ranked candidate table.

Confidence logic (the peak is the global argmax; we never have ground truth on
targets, so we gate on convergence + agreement):
  - HARD GATE: converged (remaining_layers==0). A non-converged run's readout is
    a truncation artifact -> confidence 'untrusted'.
  - The canonical candidate is the `perm_rev` ordering (validated on known answers).
  - Strong signals: sample-top and Z-sign-marginal perm_rev AGREE; multiple
    seeds/configs agree; high sample_top_fraction; high marginal_min_margin.
"""
import os, json, glob, sys
from collections import defaultdict, Counter

REPO = "/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
OUT = os.path.join(REPO, "outputs/opus_combined")


def cand(d, kind):
    return (d.get(kind) or {}).get("perm_rev")


def main():
    runs = defaultdict(list)
    for p in glob.glob(os.path.join(OUT, "*", "*.json")):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        runs[d.get("challenge", os.path.basename(os.path.dirname(p)))].append(d)

    rows = []
    for ch in sorted(runs):
        ds = runs[ch]
        # vote over converged runs' perm_rev candidates (sample + marginal)
        votes = Counter()
        conv_runs = [d for d in ds if d.get("converged")]
        for d in conv_runs:
            s, m = cand(d, "sample_orderings"), cand(d, "marginal_orderings")
            if s:
                votes[s] += 1
            if m:
                votes[m] += 1
        best = votes.most_common(1)[0] if votes else (None, 0)
        # per-run summary
        run_lines = []
        for d in sorted(ds, key=lambda x: x.get("label", "")):
            s, m = cand(d, "sample_orderings"), cand(d, "marginal_orderings")
            agree = (s is not None and s == m)
            run_lines.append({
                "label": d.get("label"), "status": d.get("status"),
                "converged": d.get("converged"), "remaining": d.get("remaining_layers"),
                "stopped": d.get("stopped_reason"),
                "top_frac": d.get("sample_top_fraction"),
                "min_margin": d.get("marginal_min_margin"),
                "forced": d.get("forced_absorptions"), "bond": d.get("mpo_max_bond"),
                "sample_perm_rev": s, "marg_perm_rev": m, "sample_marg_agree": agree,
                "secs": d.get("compress_seconds"), "validation": d.get("validation"),
            })
        n_conv = len(conv_runs)
        # confidence
        if best[0] is None:
            conf = "untrusted (no converged run)"
        elif best[1] >= 3:
            conf = "high (>=3 converged sample/marg votes agree)"
        elif best[1] == 2:
            conf = "medium (2 votes agree)"
        else:
            conf = "low (single converged vote)"
        rows.append({"challenge": ch, "n_runs": len(ds), "n_converged": n_conv,
                     "best_candidate": best[0], "votes": best[1], "confidence": conf,
                     "runs": run_lines})

    print(json.dumps(rows, indent=2))
    with open(os.path.join(OUT, "COLLECTED.json"), "w") as f:
        json.dump(rows, f, indent=2)

    # markdown summary
    md = ["# opus_combined candidates\n",
          "| challenge | runs | conv | best `perm_rev` candidate | votes | confidence |",
          "| --- | ---: | ---: | --- | ---: | --- |"]
    for r in rows:
        bc = f"`{r['best_candidate']}`" if r["best_candidate"] else "(none)"
        md.append(f"| {r['challenge']} | {r['n_runs']} | {r['n_converged']} | {bc} | {r['votes']} | {r['confidence']} |")
    with open(os.path.join(OUT, "COLLECTED.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md), file=sys.stderr)


if __name__ == "__main__":
    main()
