"""Build REPORT.md + per-challenge bitstring probability distributions (figures + CSVs)
from outputs/opus_combined/*/*.json. Safe to re-run as results land."""
import os, json, glob, csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = "/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
OUT = os.path.join(REPO, "outputs/opus_combined")
FIG = os.path.join(OUT, "figures")
DIST = os.path.join(OUT, "distributions")
os.makedirs(FIG, exist_ok=True); os.makedirs(DIST, exist_ok=True)

KNOWN = {  # exact / high-confidence references for validation
    "challenge-24_13": "111110011111001011010001", "challenge-28_4": "1111111000101010110110011111",
    "challenge-8_1": "10101101", "challenge-8_11": "01001110", "challenge-8_27": "11001001",
}


def perm_rev(d, kind):
    return (d.get(kind) or {}).get("perm_rev")


def distribution(d):
    """Return list of {bitstring, prob} (challenge order). Handles new + legacy fields."""
    if d.get("sample_distribution"):
        return d["sample_distribution"]
    # legacy: only had sample_top5 in site order -> can't reorder reliably; skip
    return []


def trust_score(d):
    if d.get("status") == "error":
        return -1e9
    s = 0.0
    v = d.get("validation") or {}
    if v.get("solved"):
        s += 1000
    sp, mp = perm_rev(d, "sample_orderings"), perm_rev(d, "marginal_orderings")
    if sp and sp == mp:
        s += 50
    tf = d.get("sample_top_fraction") or 0
    s += 100 * tf
    if d.get("converged") and (d.get("forced_absorptions") or 0) == 0:
        s += 30
    if (d.get("forced_absorptions") or 0) > 0:
        s -= 20
    if tf < 0.01:
        s -= 50  # noise floor
    return s


def confidence_label(best, runs):
    ch = (best.get("challenge") or "").replace(".qasm", "")
    cand = perm_rev(best, "sample_orderings")
    if ch in KNOWN:
        # any run match the known answer (any ordering)?
        for r in runs:
            for kind in ("sample_orderings", "marginal_orderings"):
                if KNOWN[ch] in (r.get(kind) or {}).values():
                    return "VALIDATED (matches known answer)"
        return "INCORRECT vs known answer (best persisted run is wrong; see runs)"
    if (best.get("validation") or {}).get("solved"):
        return "VALIDATED (matches known answer)"
    # agreement across distinct trusted runs (different cutoff/seed/snap)
    agree = sum(1 for r in runs if perm_rev(r, "sample_orderings") == cand
                and (r.get("sample_top_fraction") or 0) > 0.05)
    tf = best.get("sample_top_fraction") or 0
    natural = best.get("converged") and (best.get("forced_absorptions") or 0) == 0
    if tf < 0.01:
        return "untrusted (noise floor)"
    if agree >= 2 and tf > 0.2:
        return f"high ({agree} runs agree, top={tf:.2f})"
    if natural and tf > 0.2 and perm_rev(best, "sample_orderings") == perm_rev(best, "marginal_orderings"):
        return f"medium (natural convergence, top={tf:.2f}, sample==marginal)"
    return f"low (top={tf:.2f})"


def make_fig(ch, dist, cand, conf):
    if not dist:
        return None
    probs = [x["prob"] for x in dist][:24]
    plt.figure(figsize=(10, 3))
    plt.bar(range(len(probs)), probs, color="#3366cc")
    plt.xlabel("bitstring rank (most probable first)")
    plt.ylabel("probability")
    plt.title(f"{ch}  top candidate={cand}  [{conf}]", fontsize=9)
    plt.tight_layout()
    p = os.path.join(FIG, f"{ch}_dist.png")
    plt.savefig(p, dpi=110); plt.close()
    return p


def main():
    runs = {}
    for p in glob.glob(os.path.join(OUT, "*", "*.json")):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        ch = (d.get("challenge") or os.path.basename(os.path.dirname(p))).replace(".qasm", "")
        runs.setdefault(ch, []).append(d)

    order = ["challenge-48_37", "challenge-56_38", "challenge-64_40", "challenge-64_41",
             "challenge-48_42", "challenge-56_43", "challenge-64_44", "challenge-72_45",
             "challenge-80_46", "challenge-88_47", "challenge-96_48", "challenge-104_49"]
    others = sorted(c for c in runs if c not in order)
    ordered = [c for c in order if c in runs] + others

    md = ["# Opus Combined Cracker — Results Report", "",
          "Method: **snap angles (tol 1e-2) → consolidate 2q blocks → MPO unswap-to-convergence "
          "(Kremer–Dupuis + robust RCM graph reordering + force-absorb/time-budget) → "
          "sample + per-qubit Z-sign readout** (bit order `perm_rev`).", "",
          "Trust: a candidate is believable when it matches a known answer, OR multiple "
          "cutoffs/seeds agree with high top-fraction, OR natural low-bond convergence "
          "(forced_absorptions=0) with sample==marginal agreement. `converged=True` reached via "
          "force-absorb under a loose cutoff is NOT trusted (it truncates real amplitude).", "",
          "| challenge | q | best candidate (`perm_rev`) | top frac | conv | forced | bond | confidence | dist |",
          "| --- | ---: | --- | ---: | :-: | ---: | ---: | --- | --- |"]

    summary = []
    for ch in ordered:
        rs = runs[ch]
        rs_sorted = sorted(rs, key=trust_score, reverse=True)
        best = rs_sorted[0]
        cand = perm_rev(best, "sample_orderings") or "(none)"
        conf = confidence_label(best, rs)
        nq = best.get("n_qubits", "?")
        tf = best.get("sample_top_fraction")
        dist = distribution(best)
        fig = make_fig(ch, dist, cand, conf)
        figcell = f"![{ch}](figures/{ch}_dist.png)" if fig else "—"
        md.append(f"| {ch} | {nq} | `{cand}` | {tf if tf is None else round(tf,4)} | "
                  f"{'Y' if best.get('converged') else 'N'} | {best.get('forced_absorptions','?')} | "
                  f"{best.get('mpo_max_bond','?')} | {conf} | {figcell} |")
        # per-challenge distribution CSV
        if dist:
            with open(os.path.join(DIST, f"{ch}.csv"), "w", newline="") as f:
                w = csv.writer(f); w.writerow(["rank", "bitstring", "prob", "count"])
                for i, x in enumerate(dist):
                    w.writerow([i, x["bitstring"], x.get("prob"), x.get("count")])
        summary.append((ch, cand, conf, tf))

    # per-challenge detail sections
    md += ["", "## Per-challenge detail", ""]
    for ch in ordered:
        rs = sorted(runs[ch], key=trust_score, reverse=True)
        best = rs[0]
        md.append(f"### {ch}  (q={best.get('n_qubits','?')})")
        kv = KNOWN.get(ch)
        if kv:
            md.append(f"- known answer: `{kv}`")
        md.append(f"- best candidate (`perm_rev`): `{perm_rev(best,'sample_orderings')}`")
        md.append(f"- confidence: {confidence_label(best, runs[ch])}")
        dist = distribution(best)
        if dist:
            md.append(f"- top bitstrings: " + ", ".join(f"`{x['bitstring'][:12]}…`={x['prob']:.3f}"
                      for x in dist[:5]))
            md.append(f"- full distribution: `outputs/opus_combined/distributions/{ch}.csv`, "
                      f"figure `outputs/opus_combined/figures/{ch}_dist.png`")
        md.append(f"- runs ({len(runs[ch])}):")
        for r in rs:
            md.append(f"    - `{r.get('label')}`: cutoff={r.get('params',{}).get('cutoff')} "
                      f"conv={r.get('converged')} forced={r.get('forced_absorptions')} "
                      f"bond={r.get('mpo_max_bond')} top={r.get('sample_top_fraction')} "
                      f"sample==marg={perm_rev(r,'sample_orderings')==perm_rev(r,'marginal_orderings')}")
        md.append("")

    with open(os.path.join(OUT, "REPORT.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("wrote", os.path.join(OUT, "REPORT.md"))
    for ch, cand, conf, tf in summary:
        print(f"  {ch}: {cand}  [{conf}]")


if __name__ == "__main__":
    main()
