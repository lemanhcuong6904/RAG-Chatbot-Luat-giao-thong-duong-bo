#!/usr/bin/env python3
import argparse, sqlite3, json
from pathlib import Path

DB = Path(__file__).with_name("sanctions.sqlite")

def main():
    ap=argparse.ArgumentParser(description="Query the Structured Sanction Layer")
    ap.add_argument('--date', required=True, help='Event date YYYY-MM-DD')
    ap.add_argument('--contains', help='Substring in legal behavior wording')
    ap.add_argument('--vehicle', help='Canonical vehicle code, e.g. MOTORCYCLE')
    ap.add_argument('--article', help='Article number')
    ap.add_argument('--include-review', action='store_true')
    ap.add_argument('--limit', type=int, default=20)
    args=ap.parse_args()
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
    where=["(valid_from IS NULL OR valid_from <= ?)","(valid_to IS NULL OR ? < valid_to)"]
    vals=[args.date,args.date]
    if args.contains:
        where.append("LOWER(behavior_text) LIKE LOWER(?)"); vals.append('%'+args.contains+'%')
    if args.vehicle:
        where.append("vehicle_codes_json LIKE ?"); vals.append('%"'+args.vehicle+'"%')
    if args.article:
        where.append("article = ?"); vals.append(args.article)
    if not args.include_review:
        where.append("validation_status = 'PASS'")
    sql="SELECT * FROM sanction_rules WHERE "+' AND '.join(where)+" ORDER BY CAST(article AS INTEGER), clause, point LIMIT ?"
    vals.append(args.limit)
    rows=[]
    for rr in con.execute(sql, vals):
        r=dict(rr)
        for k in ['vehicle_codes_json','conditions_json','additional_sanctions_json','remedial_measures_json','notes_json']:
            if k in r and r[k]:
                try: r[k]=json.loads(r[k])
                except Exception: pass
        if r.get('deferred_effective_from') and args.date < r['deferred_effective_from']:
            r['temporal_warning']='Rule contains a specially deferred scope; inspect deferred_scope_text before applying it to the user facts.'
        rows.append(r)
    print(json.dumps(rows,ensure_ascii=False,indent=2))
    con.close()

if __name__=='__main__': main()
