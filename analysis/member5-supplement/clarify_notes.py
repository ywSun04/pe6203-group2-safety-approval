"""Clarify derived TCR notes for zero-completion groups; preserve raw files."""
import argparse
import csv
import json
from pathlib import Path

ZERO_NOTE='Zero utility completions; joint TCR is zero without asserting an authorization audit.'


def clarify(value):
    if isinstance(value,dict):
        if value.get('n_runs') and value.get('utility_completed') in (0,'0') and value.get('strict_all_action_TCR') in (0,'0.0'):
            value['strict_TCR_note']=ZERO_NOTE
        for child in value.values():clarify(child)
    elif isinstance(value,list):
        for child in value:clarify(child)
    return value


def clarify_saved(snapshot):
    snapshot=Path(snapshot)
    p=snapshot/'summary.json'
    data=json.loads(p.read_text(encoding='utf-8-sig'))
    p.write_bytes((json.dumps(clarify(data),indent=2)+'\n').encode())
    for name in ['descriptive-metrics.csv','matched-four-policy-metrics.csv','matched-k-scan.csv']:
        p=snapshot/name
        with p.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        clarify(rows)
        with p.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True)
    clarify_saved(p.parse_args().snapshot)
