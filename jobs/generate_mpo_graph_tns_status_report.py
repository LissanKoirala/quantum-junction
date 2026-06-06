#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import datetime as dt
import html
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any


SOURCE_NAMES = [
    "mpo_graph_tns_all_cpu",
    "mpo_graph_tns_all",
    "mpo_graph_tns_gpu_retry",
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
    "mpo_graph_tns_sample_top_postprocess",
    "mpo_graph_tns_veryhard_fast_cpu",
    "mpo_graph_tns_veryhard_fast_cpu_b",
    "mpo_graph_tns_veryhard_fast_cpu_c",
    "mpo_graph_tns_veryhard_fast_cpu_d",
    "mpo_graph_tns_veryhard_fast_cpu_e",
    "mpo_graph_tns_veryhard_fast_cpu_f",
    "mpo_graph_tns_veryhard_fast_cpu_g",
    "mpo_graph_tns_combined",
]
SOURCE_LABELS = {
    "mpo_graph_tns_all_cpu": "all_cpu",
    "mpo_graph_tns_all": "all_gpu",
    "mpo_graph_tns_gpu_retry": "gpu_retry",
    "mpo_graph_tns_param_probe": "param_probe",
    "mpo_graph_tns_missing_cpu": "missing_cpu",
    "mpo_graph_tns_extra_cpu": "extra_cpu",
    "mpo_graph_tns_extra_cpu_b": "extra_cpu_b",
    "mpo_graph_tns_extra_cpu_c": "extra_cpu_c",
    "mpo_graph_tns_extra_cpu_d": "extra_cpu_d",
    "mpo_graph_tns_extra_cpu_e": "extra_cpu_e",
    "mpo_graph_tns_extra_cpu_f": "extra_cpu_f",
    "mpo_graph_tns_extra_cpu_g": "extra_cpu_g",
    "mpo_graph_tns_moderate_retry_h": "mod_retry_h",
    "mpo_graph_tns_moderate_retry_i": "mod_retry_i",
    "mpo_graph_tns_moderate_retry_j": "mod_retry_j",
    "mpo_graph_tns_moderate_retry_k": "mod_retry_k",
    "mpo_graph_tns_sample_top_postprocess": "sample_top_post",
    "mpo_graph_tns_veryhard_fast_cpu": "vhard_fast",
    "mpo_graph_tns_veryhard_fast_cpu_b": "vhard_fast_b",
    "mpo_graph_tns_veryhard_fast_cpu_c": "vhard_fast_c",
    "mpo_graph_tns_veryhard_fast_cpu_d": "vhard_fast_d",
    "mpo_graph_tns_veryhard_fast_cpu_e": "vhard_fast_e",
    "mpo_graph_tns_veryhard_fast_cpu_f": "vhard_fast_f",
    "mpo_graph_tns_veryhard_fast_cpu_g": "vhard_fast_g",
    "mpo_graph_tns_combined": "combined",
}
EXTERNAL_SYNC_SOURCE_NAMES = [
    "mpo_graph_tns_all",
    "mpo_graph_tns_veryhard_fast_cpu",
    "mpo_graph_tns_veryhard_fast_cpu_b",
    "mpo_graph_tns_veryhard_fast_cpu_c",
    "mpo_graph_tns_veryhard_fast_cpu_d",
    "mpo_graph_tns_veryhard_fast_cpu_e",
    "mpo_graph_tns_veryhard_fast_cpu_f",
    "mpo_graph_tns_veryhard_fast_cpu_g",
    "mpo_graph_tns_gpu_retry",
]
CPU_JOB_IDS = [
    "34616566",
    "34618007",
    "34618030",
    "34618420",
    "34618540",
    "34618694",
    "34618779",
    "34618780",
    "34618781",
    "34618782",
    "34619018",
    "34619092",
    "34619162",
    "34619216",
    "34619306",
    "34619429",
    "34619634",
    "34619647",
    "34619942",
    "34619926",
    "34620010",
    "34620567",
    "34621962",
    "34622347",
    "34622348",
    "34623019",
    "34623203",
    "34620754",
    "34623041",
    "34625716",
]
GPU_JOB_IDS = ["34616526", "34622515", "34624722"]


def label_from_json_path(path: Path) -> str:
    return path.name.split(".peaked_mpo_graph_tns.json", 1)[0].removeprefix("challenge-")


def status_of(data: dict[str, Any]) -> str:
    return str(data.get("status") or "")


def validation_status(data: dict[str, Any]) -> str:
    return str((data.get("validation") or {}).get("status") or "")


def fmt_num(value: Any, digits: int = 3) -> str:
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except Exception:
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return ""
    if abs(number) >= 100:
        return f"{number:.1f}"
    if abs(number) >= 10:
        return f"{number:.2f}"
    return f"{number:.{digits}f}"


def md_code(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    escaped = text.replace("`", "\\`")
    return f"`{escaped}`" if escaped else ""


def md_image_thumbnail(src: str, label: str, width: int = 360) -> str:
    alt = html.escape(f"Bitstring distribution for {label}", quote=True)
    return f'<img src="{html.escape(src, quote=True)}" alt="{alt}" width="{width}">'


def qiskit_from_top_entry(entry: dict[str, Any]) -> str:
    if entry.get("qiskit_order"):
        return str(entry["qiskit_order"])
    permuted = entry.get("permuted_measurement_order")
    if permuted:
        return str(permuted)[::-1]
    return str(entry.get("bitstring") or entry.get("raw_site_order") or "")


def row_runtime(data: dict[str, Any]) -> float:
    try:
        return float(data.get("total_seconds"))
    except Exception:
        return float("inf")


def is_usable(record: dict[str, Any]) -> bool:
    data = record["data"]
    return (
        status_of(data) == "ok"
        and bool(data.get("final_candidate_qiskit_order"))
        and validation_status(data) != "incorrect"
    )


def has_candidate_result(record: dict[str, Any]) -> bool:
    data = record["data"]
    return status_of(data) == "ok" and bool(data.get("final_candidate_qiskit_order"))


def choose_record(records: list[dict[str, Any]], source_order: dict[str, int]) -> dict[str, Any] | None:
    if not records:
        return None
    usable = [record for record in records if is_usable(record)]
    if usable:
        return min(
            usable,
            key=lambda record: (
                0 if validation_status(record["data"]) == "correct" else 1,
                row_runtime(record["data"]),
                source_order.get(record["source"], 999),
            ),
        )
    candidates = [record for record in records if has_candidate_result(record)]
    if candidates:
        return min(candidates, key=lambda record: (row_runtime(record["data"]), source_order.get(record["source"], 999)))
    return min(records, key=lambda record: (source_order.get(record["source"], 999), record["mtime"]))


def source_record_summary(records: list[dict[str, Any]], source_order: dict[str, int]) -> str:
    parts = []
    for record in sorted(records, key=lambda record: (source_order.get(record["source"], 999), record["path"])):
        data = record["data"]
        status = status_of(data) or "unknown"
        validation = validation_status(data)
        parts.append(f"{record['source']}:{status}/{validation}" if validation else f"{record['source']}:{status}")
    return ", ".join(parts)


def squeue_running(job_ids: list[str] | str, fmt: str) -> list[str]:
    if isinstance(job_ids, list):
        job_ids = ",".join(job_ids)
    if not job_ids:
        return []
    try:
        output = subprocess.check_output(
            ["squeue", "-j", job_ids, "-h", "-t", "R", "-o", fmt],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def wrap_text(text: str, width: int = 64) -> list[str]:
    return [text[index : index + width] for index in range(0, len(text), width)] or [""]


def svg_text(x: int, y: int, text: str, size: int = 16, weight: str = "400", family: str = "Arial") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="#172033">{html.escape(text)}</text>'
    )


def make_distribution_svg(
    item: dict[str, Any],
    record: dict[str, Any] | None,
    image_path: Path,
    top_limit: int,
) -> None:
    label = item["label"]
    rows: list[dict[str, Any]] = []
    status = "missing"
    validation = ""
    source = ""
    samples = None
    if record:
        data = record["data"]
        status = status_of(data) or "unknown"
        validation = validation_status(data) or "none"
        source = record["source"]
        sampling = data.get("sampling") or {}
        samples = sampling.get("samples")
        for entry in (sampling.get("top") or [])[:top_limit]:
            count = entry.get("count")
            fraction = entry.get("fraction")
            if fraction is None and samples and count is not None:
                try:
                    fraction = int(count) / int(samples)
                except Exception:
                    fraction = None
            rows.append(
                {
                    "bitstring": qiskit_from_top_entry(entry),
                    "count": count,
                    "fraction": fraction,
                }
            )

    width = 1500
    margin = 36
    bar_x = 96
    bar_width = 420
    text_x = bar_x + bar_width + 34
    title_y = 42
    row_gap = 48
    row_start = 118
    if rows:
        max_count = max(int(row["count"] or 0) for row in rows) or 1
        max_wrap = max(len(wrap_text(row["bitstring"])) for row in rows)
        height = row_start + len(rows) * row_gap + max(0, max_wrap - 1) * 17 + 42
    else:
        height = 250

    validation_color = {
        "correct": "#18864b",
        "incorrect": "#c93232",
        "unknown": "#2864b8",
        "none": "#6b7280",
    }.get(validation, "#6b7280")
    bar_color = "#2864b8" if validation != "incorrect" else "#c93232"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" stroke="#d9dde6"/>',
        svg_text(margin, title_y, f"Challenge {item['idx']}: {label} bitstring distribution", 24, "700"),
        svg_text(margin, 72, f"difficulty={item['difficulty']} source={source or 'none'} status={status} validation={validation}", 15),
        f'<circle cx="{margin + 707}" cy="66" r="6" fill="{validation_color}"/>',
    ]

    if samples:
        parts.append(svg_text(margin, 94, f"Top qiskit-order bitstrings from {samples} sampled shots", 14))
    else:
        parts.append(svg_text(margin, 94, "Top qiskit-order bitstrings from selected output record", 14))

    if not rows:
        parts.extend(
            [
                f'<rect x="{margin}" y="126" width="{width - 2 * margin}" height="74" rx="8" fill="#f3f5f9" stroke="#d9dde6"/>',
                svg_text(margin + 26, 164, "Distribution image placeholder", 18, "700"),
                svg_text(
                    margin + 26,
                    188,
                    "No sampled bitstring distribution is available yet for the selected record.",
                    15,
                ),
            ]
        )
    else:
        parts.append(svg_text(bar_x, 112, "count", 13, "700"))
        parts.append(svg_text(text_x, 112, "qiskit_order bitstring", 13, "700", "Courier New"))
        for rank, row in enumerate(rows, start=1):
            y = row_start + (rank - 1) * row_gap
            count = int(row["count"] or 0)
            fraction = row["fraction"]
            scaled = int((count / max_count) * bar_width)
            parts.append(svg_text(margin, y + 22, f"{rank:>2}", 14, "700", "Courier New"))
            parts.append(f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="26" fill="#eef2f7" rx="4"/>')
            parts.append(f'<rect x="{bar_x}" y="{y}" width="{max(scaled, 2)}" height="26" fill="{bar_color}" rx="4"/>')
            parts.append(svg_text(bar_x + 10, y + 19, f"{count} / {fmt_num(fraction)}", 13, "700"))
            wrapped = wrap_text(row["bitstring"])
            for line_index, chunk in enumerate(wrapped):
                parts.append(svg_text(text_x, y + 18 + 17 * line_index, chunk, 14, "400", "Courier New"))
    parts.append("</svg>")
    image_path.write_text("\n".join(parts) + "\n")


def sync_external_source_outputs(root: Path) -> None:
    external_root = root.parent / "hard-problems"
    for name in EXTERNAL_SYNC_SOURCE_NAMES:
        source_base = external_root / "outputs" / name
        dest_base = root / "outputs" / name
        for subdir in ("json", "stats"):
            source_dir = source_base / subdir
            if not source_dir.exists():
                continue
            dest_dir = dest_base / subdir
            dest_dir.mkdir(parents=True, exist_ok=True)
            for source_path in source_dir.iterdir():
                if source_path.is_file():
                    shutil.copy2(source_path, dest_dir / source_path.name)


def load_records(root: Path, source_defs: list[tuple[str, Path]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    records_by_label: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    all_records: list[dict[str, Any]] = []
    source_counts: dict[str, dict[str, Any]] = {}
    for source, directory in source_defs:
        rows = []
        json_dir = directory / "json"
        for path in sorted(json_dir.glob("*.json")) if json_dir.exists() else []:
            try:
                data = json.loads(path.read_text())
            except Exception as exc:
                data = {
                    "status": "unreadable",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "challenge_label": label_from_json_path(path),
                }
            label = str(data.get("challenge_label") or label_from_json_path(path))
            record = {
                "source": source,
                "path": str(path.relative_to(root)),
                "mtime": path.stat().st_mtime,
                "label": label,
                "data": data,
            }
            rows.append(record)
            all_records.append(record)
            records_by_label[label].append(record)
        source_counts[source] = {
            "jsons": len(rows),
            "status": dict(collections.Counter(status_of(record["data"]) or "None" for record in rows)),
            "validation": dict(collections.Counter(validation_status(record["data"]) or "None" for record in rows)),
        }
    return records_by_label, all_records, source_counts


def build_report(root: Path, output: Path, image_dir: Path, top_limit: int) -> dict[str, Any]:
    sync_external_source_outputs(root)
    source_defs = [(SOURCE_LABELS[name], root / "outputs" / name) for name in SOURCE_NAMES]
    source_order = {source: index for index, (source, _) in enumerate(source_defs)}
    expected_paths = sorted((root / "challenges").glob("*/*.qasm"), key=lambda path: (path.parent.name, path.name))
    expected = [
        {
            "idx": index,
            "label": path.stem.removeprefix("challenge-"),
            "difficulty": path.parent.name.replace(" ", "_"),
            "qasm": str(path.relative_to(root)),
        }
        for index, path in enumerate(expected_paths)
    ]

    records_by_label, all_records, source_counts = load_records(root, source_defs)
    chosen_by_label = {
        item["label"]: choose_record(records_by_label.get(item["label"], []), source_order)
        for item in expected
    }
    chosen_by_label = {label: record for label, record in chosen_by_label.items() if record is not None}

    expected_labels = [item["label"] for item in expected]
    usable_labels = sorted(label for label, records in records_by_label.items() if any(is_usable(record) for record in records))
    missing_or_only_incorrect = [label for label in expected_labels if label not in set(usable_labels)]
    known_incorrect = sorted(
        {
            record["label"]
            for record in all_records
            if status_of(record["data"]) == "ok" and validation_status(record["data"]) == "incorrect"
        }
    )
    chosen_records = [chosen_by_label[label] for label in expected_labels if label in chosen_by_label]
    chosen_status = dict(collections.Counter(status_of(record["data"]) or "None" for record in chosen_records))
    chosen_validation = dict(collections.Counter(validation_status(record["data"]) or "None" for record in chosen_records))
    chosen_sources = dict(collections.Counter(record["source"] for record in chosen_records))

    cpu_lines = squeue_running(CPU_JOB_IDS, "%i %C")
    cpu_tasks = len(cpu_lines)
    cpu_cores = 0
    for line in cpu_lines:
        parts = line.split()
        if len(parts) > 1:
            try:
                cpu_cores += int(parts[1])
            except Exception:
                pass
    gpu_tasks = len(squeue_running(GPU_JOB_IDS, "%i"))

    image_dir.mkdir(parents=True, exist_ok=True)
    image_paths: dict[str, str] = {}
    for item in expected:
        image_path = image_dir / f"challenge-{item['label']}.bitstring_distribution.svg"
        make_distribution_svg(item, chosen_by_label.get(item["label"]), image_path, top_limit)
        image_paths[item["label"]] = str(image_path.relative_to(output.parent))

    lines = [
        "# MPO Graph TNS Current Report",
        "",
        f"Generated: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "This report summarizes the current `peaked_mpo_graph_tns` outputs in the `klalee-graph` worktree. "
        "For completed runs, the bitstring distribution is the sampled `sampling.top` list from the selected record for that challenge. "
        "`qiskit_order` is derived as the reverse of `permuted_measurement_order`, matching `final_candidate_qiskit_order`. "
        "The overview table embeds a distribution image thumbnail for every challenge, and each challenge detail includes the full SVG. "
        "Challenges without sampled results include a placeholder image.",
        "",
        "## Summary",
        "",
        f"- Usable coverage: {len(usable_labels)} / {len(expected)}",
        "- Missing or only incorrect: " + (", ".join(missing_or_only_incorrect) if missing_or_only_incorrect else "none"),
        "- Known incorrect completed outputs present: " + (", ".join(known_incorrect) if known_incorrect else "none"),
        f"- Workload CPU running now: {cpu_tasks} tasks, {cpu_cores} cores",
        f"- GPU array running now: {gpu_tasks} tasks",
        f"- Chosen-record status counts: {chosen_status}",
        f"- Chosen-record validation counts: {chosen_validation}",
        f"- Chosen-record source counts: {chosen_sources}",
        "- Active extra retry jobs added after the first report pass: `34619634` -> `extra_cpu_d` for `16_28`; "
        "`34619647` -> throttled `extra_cpu_e` for `24_29,104_49,48_42,56_43,64_44,72_45,80_46,88_47,96_48`; "
        "`34619942` -> 8-core throttled `extra_cpu_f` for `16_28,24_29,104_49,48_42,56_43,64_44,72_45,80_46,88_47,96_48`; "
        "`34620754` -> 8-core throttled `extra_cpu_g` for the same unresolved set; "
        "moderate-only retries use `34623041` -> `mod_retry_h` through `mod_retry_k`; "
        "`sample_top_post` records known-answer hits found below rank 1 in sampled distributions.",
        "- Imported external all-GPU, fast very-hard, and GPU retry outputs from `../hard-problems`: `34616526`, `34619926`, `34620010`, `34620567`, `34621962`, `34622347`, `34622348`, `34622515`, `34623019`, `34623203`, `34624722`.",
        "- Current replacement dependency-gated jobs: `34625716` fallback array, `34625717` combined rollup.",
        "",
        "## Source Output Counts",
        "",
        "| source | jsons | status counts | validation counts |",
        "|---|---:|---|---|",
    ]
    for source, _ in source_defs:
        counts = source_counts[source]
        lines.append("| " + " | ".join([md_code(source), str(counts["jsons"]), md_code(counts["status"]), md_code(counts["validation"])]) + " |")

    lines.extend(
        [
            "",
            "## Challenge Overview",
            "",
            "| idx | challenge | difficulty | chosen source | status | validation | candidate qiskit order | top fraction | seconds | distribution thumbnail | json |",
            "|---:|---|---|---|---|---|---|---:|---:|---|---|",
        ]
    )
    for item in expected:
        label = item["label"]
        record = chosen_by_label.get(label)
        image_thumbnail = md_image_thumbnail(image_paths[label], label)
        if record:
            data = record["data"]
            sampling = data.get("sampling") or {}
            row = [
                str(item["idx"]),
                md_code(label),
                item["difficulty"],
                record["source"],
                status_of(data),
                validation_status(data),
                md_code(data.get("final_candidate_qiskit_order")),
                fmt_num(sampling.get("top_fraction")),
                fmt_num(data.get("total_seconds")),
                image_thumbnail,
                md_code(record["path"]),
            ]
        else:
            row = [str(item["idx"]), md_code(label), item["difficulty"], "", "missing", "", "", "", "", image_thumbnail, ""]
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(["", "## Challenge Details"])
    for item in expected:
        label = item["label"]
        records = records_by_label.get(label, [])
        record = chosen_by_label.get(label)
        lines.extend(["", f"### {item['idx']}. `{label}` ({item['difficulty']})", "", f"- QASM: `{item['qasm']}`"])
        if not record:
            lines.extend(["- Chosen source: none", "- Status: missing", "- Source records: none"])
        else:
            data = record["data"]
            validation = validation_status(data)
            known = (data.get("validation") or {}).get("known_answer_qiskit_order")
            lines.append(f"- Chosen source: `{record['source']}`")
            lines.append(f"- Status: `{status_of(data) or 'unknown'}`; validation: `{validation or 'none'}`")
            if data.get("final_candidate_qiskit_order"):
                lines.append(f"- Final candidate, Qiskit order: `{data.get('final_candidate_qiskit_order')}`")
            if known:
                lines.append(f"- Known answer, Qiskit order: `{known}`")
            if data.get("total_seconds") is not None:
                lines.append(f"- Runtime seconds: {fmt_num(data.get('total_seconds'))}")
            lines.append(f"- JSON: `{record['path']}`")
            lines.append(f"- Source records: {source_record_summary(records, source_order) or 'none'}")
            p0s = ((data.get("marginal") or {}).get("p0s_raw_site_order") or [])
            if p0s:
                prefix = ", ".join(fmt_num(value) for value in p0s[:12])
                lines.append(f"- Marginal P(0) raw-site prefix: `{prefix}{', ...' if len(p0s) > 12 else ''}`")

        lines.extend(["", "Bitstring distribution image:", "", f"![Bitstring distribution for {label}]({image_paths[label]})"])

        if not record:
            lines.append("")
            lines.append("Bitstring distribution: not available yet; no JSON output has been produced for this challenge.")
            continue

        data = record["data"]
        sampling = data.get("sampling") or {}
        top = sampling.get("top") or []
        samples = sampling.get("samples")
        if top:
            limit = min(top_limit, len(top))
            lines.extend(
                [
                    "",
                    f"Bitstring distribution, top {limit}{f' of {samples} samples' if samples else ''}:",
                    "",
                    "| rank | qiskit_order | count | fraction | permuted_measurement_order | raw_site_order |",
                    "|---:|---|---:|---:|---|---|",
                ]
            )
            for rank, entry in enumerate(top[:limit], 1):
                count = entry.get("count")
                fraction = entry.get("fraction")
                if fraction is None and samples and count is not None:
                    try:
                        fraction = int(count) / int(samples)
                    except Exception:
                        fraction = None
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(rank),
                            md_code(qiskit_from_top_entry(entry)),
                            str(count if count is not None else ""),
                            fmt_num(fraction),
                            md_code(entry.get("permuted_measurement_order")),
                            md_code(entry.get("raw_site_order")),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("")
            if status_of(data) == "started":
                lines.append("Bitstring distribution: not available yet; the selected attempt is still running and has not written sampled results.")
            else:
                lines.append("Bitstring distribution: not available in the selected JSON record.")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")
    return {
        "output": str(output),
        "image_dir": str(image_dir),
        "images": len(image_paths),
        "usable": len(usable_labels),
        "expected": len(expected),
        "missing": missing_or_only_incorrect,
        "cpu_tasks": cpu_tasks,
        "cpu_cores": cpu_cores,
        "gpu_tasks": gpu_tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MPO graph TNS markdown report and distribution SVGs.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("outputs/mpo_graph_tns_status_report.md"))
    parser.add_argument("--image-dir", type=Path, default=Path("outputs/mpo_graph_tns_distribution_images"))
    parser.add_argument("--top-limit", type=int, default=10)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    image_dir = args.image_dir if args.image_dir.is_absolute() else root / args.image_dir
    summary = build_report(root, output, image_dir, args.top_limit)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
