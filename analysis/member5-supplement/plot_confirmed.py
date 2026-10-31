"""Replot current fixed-task TCR with the recorded mapping confirmation."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


def plot(root):
    root=Path(root)
    rows=list(csv.DictReader((root/'matched-k-scan.csv').open(encoding='utf-8',newline='')))
    styles=[('full-approve','Full-approve','#b55234','-','o'),
            ('full-escalate','Full-escalate','#8860a9','--','s'),
            ('basic_risk','BasicRiskPolicy','#1e7791','-.','^'),
            ('budget_aware','BudgetAwarePolicy','#3b8a53',':','x')]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.titleweight':'bold','savefig.dpi':180})
    fig,axes=plt.subplots(1,2,figsize=(10,4.2),sharey=True)
    for ax,condition,title in zip(axes,['none','file'],['No attack','Fixed injection']):
        for policy,label,color,line,marker in styles:
            selected=sorted([r for r in rows if r['policy']==policy and r['condition']==condition],key=lambda r:int(r['k']))
            assert len(selected)==5 and all(r['n_runs']=='2' for r in selected)
            ax.plot(range(5),[float(r['strict_all_action_TCR']) for r in selected],label=label,
                    color=color,linestyle=line,marker=marker,markersize=7,linewidth=1.9,alpha=.9)
        ax.set(title=title,xlabel='Review budget k',xticks=range(5),xticklabels=[0,1,2,4,8],ylim=(-.05,1.07))
        ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='y',alpha=.18)
    axes[0].set_ylabel('Strict task completion rate')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',ncol=4,frameon=False,bbox_to_anchor=(.5,.045))
    fig.suptitle('Fixed-task comparison across five review budgets',x=.08,ha='left',fontsize=14,fontweight='bold')
    fig.text(.08,.89,'Same tasks 0 and 1, repetition 0; two tasks per point. Mapping confirmation recorded.',fontsize=9,color='#444444')
    fig.text(.08,.015,'First-launched outcomes retained. Small descriptive panel; no population inference.',fontsize=8,color='#555555')
    fig.subplots_adjust(top=.79,bottom=.27,left=.08,right=.98,wspace=.18)
    out=root/'figures';out.mkdir(exist_ok=True)
    fig.savefig(out/'matched-tcr.png');fig.savefig(out/'matched-tcr.pdf');plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('results_directory',type=Path)
    plot(p.parse_args().results_directory)
