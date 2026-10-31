"""Render English research figures from the saved aggregate CSVs."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


def read(path):
    return list(csv.DictReader(Path(path).open(encoding="utf-8", newline="")))


def plot(result_directory):
    root = Path(result_directory)
    out = root / "figures"
    out.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "savefig.dpi": 180})
    policies = [("full-approve", "Full-approve", "#b55234", "-", "o"),
                ("full-escalate", "Full-escalate", "#8860a9", "--", "s"),
                ("basic_risk", "BasicRiskPolicy", "#1e7791", "-.", "^"),
                ("budget_aware", "BudgetAwarePolicy", "#3b8a53", ":", "x")]
    rows = read(root / "matched-k-scan.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for axis, condition, title in zip(axes, ["none", "file"], ["No attack", "Fixed injection"]):
        for policy, label, color, style, marker in policies:
            selected = sorted([r for r in rows if r["policy"] == policy and r["condition"] == condition], key=lambda r:int(r["k"]))
            axis.plot(range(5), [float(r["strict_all_action_TCR"]) for r in selected],
                      label=label, color=color, linestyle=style, marker=marker,
                      markersize=7, linewidth=1.9, alpha=.9)
        axis.set(title=title, xlabel="Review budget k", xticks=range(5), xticklabels=[0,1,2,4,8], ylim=(-.05,1.07))
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.grid(axis="y", alpha=.18)
    axes[0].set_ylabel("Strict task completion rate")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(.5,.045))
    fig.suptitle("Fixed-task comparison across five review budgets", x=.08, ha="left", fontsize=14, fontweight="bold")
    fig.text(.08,.89,"Same tasks 0 and 1, repetition 0; two tasks per point. M6 mapping acknowledgement pending.",fontsize=9,color="#444444")
    fig.text(.08,.015,"Failures retain their first-launched outcome. Small descriptive panel; no population inference.",fontsize=8,color="#555555")
    fig.subplots_adjust(top=.79,bottom=.27,left=.08,right=.98,wspace=.18)
    fig.savefig(out/"matched-tcr.png");fig.savefig(out/"matched-tcr.pdf");plt.close(fig)
    descriptive = read(root / "descriptive-metrics.csv")
    fig, axes = plt.subplots(1,2,figsize=(10,4.1),sharey=True)
    for axis,condition,title in zip(axes,["none","file"],["No attack","Fixed injection, approved configuration"]):
        selected=sorted([r for r in descriptive if r["policy"]=="budget_aware" and r["condition"]==condition],key=lambda r:int(r["k"]))
        x=list(range(len(selected)));values=[float(r["utility_completion_rate"]) for r in selected]
        axis.bar(x,values,color="#3b8a53",width=.6)
        for i,r in enumerate(selected):axis.text(i,values[i]+.02,f"{r['utility_completed']}/{r['n_runs']}",ha="center",fontsize=9)
        axis.set(title=title,xlabel="Review budget k",xticks=x,xticklabels=[r['k'] for r in selected],ylim=(0,1.12))
        axis.yaxis.set_major_formatter(PercentFormatter(1));axis.grid(axis='y',alpha=.16);axis.set_axisbelow(True)
    axes[0].set_ylabel("Utility completion (not strict TCR)")
    fig.suptitle("BudgetAwarePolicy: received coverage",x=.08,ha="left",fontsize=14,fontweight="bold")
    fig.text(.08,.89,"20 clean tasks per k. Attack denominators exclude seven endpoint-mismatched runs.",fontsize=9,color="#444444")
    fig.text(.08,.02,"Different conditions and repetition coverage; these bars do not establish a causal budget effect.",fontsize=8,color="#555555")
    fig.subplots_adjust(top=.77,bottom=.18,left=.08,right=.98,wspace=.18)
    fig.savefig(out/"budget-coverage.png");fig.savefig(out/"budget-coverage.pdf");plt.close(fig)
    print(str(out))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("result_directory",type=Path)
    plot(p.parse_args().result_directory)
