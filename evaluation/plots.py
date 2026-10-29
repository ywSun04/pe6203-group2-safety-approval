"""Dependency-free static SVG figures; missing evidence is never interpolated."""
from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path


COLORS = ["#2563a6", "#b45309", "#18866d", "#9333a8", "#c2414c", "#596274"]


def _text(x, y, value, size=13, color="#17212c", **attributes):
    attrs = " ".join(f'{k.replace("_", "-")}="{escape(str(v), quote=True)}"' for k, v in attributes.items())
    return f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" fill="{color}" {attrs}>{escape(str(value))}</text>'


def _svg(width, height, title, description, parts):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
        f'<rect width="{width}" height="{height}" fill="white"/>' + "".join(parts) + '</svg>\n')


def _number(value):
    return f"{value:,}"


def write_tcr_svg(report, path):
    """Plot each evidence/configuration cohort in separate strict/proxy facets.

    Absent and unknown points create gaps. No formal data creates an explicit
    empty formal section rather than a synthetic formal curve.
    """
    cohorts = defaultdict(list)
    cohort_fields = ("evidence_kind", "experiment_id", "suite", "suite_version", "model_id", "reviewer_model", "configuration_signature", "condition", "attack_group_id", "attack_group_sha256")
    for group in report["groups"]:
        cohorts[tuple(group[field] for field in cohort_fields)].append(group)
    items = sorted(cohorts.items(), key=lambda item: str(item[0]))
    has_formal = any(key[0] == "formal" for key, _ in items)
    panel_height = 332
    height = 164 + panel_height * max(1, len(items)) + (84 if not has_formal else 0)
    parts = [_text(32, 34, "Safe task completion versus review budget", 23, font_weight="bold"),
        _text(32, 61, "Evidence kinds, model/settings hashes and attack conditions are separated. Points use all planned task runs.", 13),
        _text(32, 83, "Gaps mean absent or unresolved outcomes. Bounds are in summary_metrics.csv; they are not confidence intervals.", 13),
        _text(32, 105, "Smoke/demo points describe validation evidence only. A single point is not a budget sweep.", 13)]
    if not items:
        parts.append(_text(32, 168, "No evaluated task groups. No TCR curve is available.", 17))
    all_policies = sorted({g["policy_name"] for g in report["groups"]})
    colors = {policy: COLORS[i % len(COLORS)] for i, policy in enumerate(all_policies)}
    for index, (key, groups) in enumerate(items):
        top = 134 + panel_height * index
        meta = dict(zip(cohort_fields, key))
        parts.append(_text(32, top, f"{meta['evidence_kind'].upper()} | {meta['experiment_id']} | {meta['suite']} {meta['suite_version']}", 15, font_weight="bold"))
        parts.append(_text(32, top + 20, f"Settings {meta['configuration_signature']} | attack {meta['condition']} / {meta['attack_group_id']} | agent {meta['model_id']}", 11))
        policies = sorted({g["policy_name"] for g in groups})
        budgets = sorted({g["k"] for g in groups})
        for facet, (metric, label) in enumerate((("tcr_strict", "Strict safety from authorization audit"), ("tcr_benchmark_proxy", "Benchmark goal proxy from runner"))):
            left = 75 + facet * 530
            chart_top = top + 62
            chart_width, chart_height = 430, 164
            x_min, x_max = min(budgets), max(budgets)
            def xpos(k):
                return left + chart_width / 2 if x_min == x_max else left + chart_width * (k - x_min) / (x_max - x_min)
            def ypos(rate):
                return chart_top + chart_height * (1 - rate)
            parts.append(_text(left, chart_top - 14, label, 14, font_weight="bold"))
            for tick in (0, .25, .5, .75, 1):
                y = ypos(tick)
                parts.append(f'<line x1="{left}" y1="{y}" x2="{left+chart_width}" y2="{y}" stroke="#dce2e8"/>')
                parts.append(_text(left-12, y+4, f"{tick:.0%}", 11, text_anchor="end"))
            parts.append(f'<line x1="{left}" y1="{chart_top}" x2="{left}" y2="{chart_top+chart_height}" stroke="#556273"/>')
            parts.append(f'<line x1="{left}" y1="{chart_top+chart_height}" x2="{left+chart_width}" y2="{chart_top+chart_height}" stroke="#556273"/>')
            for budget in budgets:
                parts.append(_text(xpos(budget), chart_top+chart_height+18, str(budget), 11, text_anchor="middle"))
            parts.append(_text(left+chart_width/2, chart_top+chart_height+37, "Review budget k", 12, text_anchor="middle"))
            any_point = False
            for policy in policies:
                series = {g["k"]: g for g in groups if g["policy_name"] == policy}
                previous = None
                for budget in budgets:
                    group = series.get(budget)
                    value = group.get(metric) if group else None
                    if value is None:
                        previous = None
                        continue
                    any_point = True
                    x, y = xpos(budget), ypos(value)
                    if previous is not None:
                        parts.append(f'<line x1="{previous[0]}" y1="{previous[1]}" x2="{x}" y2="{y}" stroke="{colors[policy]}" stroke-width="2"/>')
                    parts.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{colors[policy]}" stroke="white" stroke-width="1"><title>{escape(policy)}; k={budget}; n={group["planned_tasks"]}; rate={value:.4f}</title></circle>')
                    previous = (x, y)
            if not any_point:
                parts.append(_text(left+chart_width/2, chart_top+chart_height/2, "No resolved point estimates", 13, color="#596274", text_anchor="middle"))
        unknown = sum(g["strict_unknown_outcomes"] for g in groups)
        n = sum(g["planned_tasks"] for g in groups)
        parts.append(_text(32, top+290, f"{n} planned task runs in this cohort; {unknown} unresolved strict safe-completion outcomes.", 12))
        legend_x = 32
        for policy in policies:
            parts.append(f'<circle cx="{legend_x+5}" cy="{top+311}" r="4" fill="{colors[policy]}"/>')
            parts.append(_text(legend_x+15, top+315, policy, 11))
            legend_x += max(150, len(policy)*7+30)
    if not has_formal:
        y = height - 48
        parts.append(_text(32, y, "FORMAL EXPERIMENT", 14, font_weight="bold"))
        parts.append(_text(32, y+23, "No registered formal evidence. Formal TCR@k curves remain unavailable.", 14, color="#596274"))
    Path(path).write_text(_svg(1120, height, "TCR versus k by evidence cohort", "Strict safety and benchmark goal proxy are separate panels; unknown points are gaps; no formal curve is fabricated.", parts), encoding="utf-8")


def write_smoke_tokens_svg(report, path):
    """Stack recorded token subtotals for real smoke runs only."""
    rows = [row for row in report["tasks"] if row["evidence_kind"] == "smoke"]
    width, height = 1120, 188 + max(1, len(rows))*84
    parts = [_text(32, 35, "Recorded API tokens in historical smoke runs", 23, font_weight="bold"),
        _text(32, 62, "One row per task run. These are connection checks, not a formal policy comparison.", 13),
        _text(32, 83, "Task totals count retries once; only late usage excluded from task totals is added. Unknown usage is marked.", 13)]
    components = [("agent", "#2563a6"), ("policy", "#18866d"), ("reviewer", "#b45309")]
    for index, (component, color) in enumerate(components):
        x = 32 + index*200
        parts.append(f'<rect x="{x}" y="101" width="14" height="14" fill="{color}"/>')
        total = sum(row[f"{component}_tokens_recorded"] or 0 for row in rows)
        parts.append(_text(x+22, 113, f"{component.title()} {_number(total)}", 12))
    maximum = max((sum(row[f"{c}_tokens_recorded"] or 0 for c, _ in components) for row in rows), default=1) or 1
    left, bar_width = 440, 560
    if not rows:
        parts.append(_text(32, 165, "No registered real smoke task runs are available.", 16))
    for index, row in enumerate(rows):
        y = 155 + index*84
        parts.append(_text(32, y, f"{row['policy_name']}   k={row['k']}", 14, font_weight="bold"))
        parts.append(_text(32, y+20, f"{row['run_id'][:24]}... | {row['task_id']}", 11, color="#596274"))
        parts.append(_text(32, y+37, f"Settings {row['configuration_signature']}", 10, color="#596274"))
        x = left
        for component, color in components:
            count = row[f"{component}_tokens_recorded"] or 0
            segment = bar_width*count/maximum
            if segment:
                opacity = "1" if row[f"{component}_usage_known"] else ".45"
                parts.append(f'<rect x="{x}" y="{y-12}" width="{segment}" height="24" fill="{color}" opacity="{opacity}"><title>{component}: {count}; usage complete: {str(row[f"{component}_usage_known"]).lower()}</title></rect>')
            x += segment
        total = sum(row[f"{c}_tokens_recorded"] or 0 for c, _ in components)
        parts.append(_text(x+9, y+5, _number(total), 12))
        details = " / ".join(f"{c[0].upper()}={_number(row[f'{c}_tokens_recorded']) if row[f'{c}_tokens_recorded'] is not None else '?'}" + (" [unknown]" if not row[f"{c}_usage_known"] else "") for c, _ in components)
        parts.append(_text(left, y+34, details, 11, color="#596274"))
    parts.append(_text(32, height-22, "Recorded token counts measure supplied usage. They are not final provider bills or a dollar estimate.", 12, color="#596274"))
    Path(path).write_text(_svg(width, height, "Smoke run API token components", "Historical smoke-run token subtotals, split by agent, policy and reviewer. Unknown usage is labelled and shown with lower opacity.", parts), encoding="utf-8")
