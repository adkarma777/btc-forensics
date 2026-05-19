"""
main.py
-------
TangleForensix pipeline for real Bitcoin transaction data.

Stages:
  1. tangle_heuristic_mapper  — analyses btc_transactions.csv  → output/btc_results.json
  2. tangle_renderer          — renders the interactive GUI     → output/btc_tangleforensix.html
"""

import argparse
import json
import os

from tangle_heuristic_mapper import (
    load_transactions_csv, cluster_and_analyze,
    detect_wash_trading_pass, write_results_json,
)
from tangle_renderer import build_html

DEFAULT_INPUT  = "btc_transactions.csv"
DEFAULT_JSON   = "output/btc_results.json"
DEFAULT_HTML   = "output/btc_tangleforensix.html"


def main() -> None:
    p = argparse.ArgumentParser(description="Run TangleForensix on Bitcoin transaction data.")
    p.add_argument("--input",  default=DEFAULT_INPUT,  help="Path to BTC transactions CSV")
    p.add_argument("--json",   default=DEFAULT_JSON,   help="Output results JSON path")
    p.add_argument("--html",   default=DEFAULT_HTML,   help="Output GUI HTML path")
    args = p.parse_args()

    # ── Stage 1: load & analyse ──────────────────────────────────────
    print(f"[load]     reading {args.input}")
    txs = load_transactions_csv(args.input)
    print(f"           {len(txs)} transactions loaded")

    ds, results, clusters, H = cluster_and_analyze(txs)
    n_wash = detect_wash_trading_pass(txs, ds, results)
    write_results_json(args.json, txs, results, clusters)

    flag_counts: dict = {}
    for r in results.values():
        for fl in r.flags:
            flag_counts[fl] = flag_counts.get(fl, 0) + 1

    print(f"\n[analyse]  {len(clusters)} clusters  |  {len(H)} unique addresses")
    print(f"           {'flag':<26} {'count':>5}  {'% of txs':>8}")
    print(f"           {'-'*42}")
    for fl in ("normal", "sweep", "wash_trading", "peeling_chain",
               "dust_attack", "dust_linkage",
               "excess_input_filter", "large_value_examiner", "first_time_recipient"):
        cnt = flag_counts.get(fl, 0)
        pct = cnt / len(txs) * 100
        print(f"           {fl:<26} {cnt:>5}   {pct:>6.1f}%")
    print(f"\n           results  → {args.json}")

    # ── Stage 2: render GUI ──────────────────────────────────────────
    with open(args.json, encoding="utf-8") as f:
        payload = json.load(f)
    html = build_html(payload)
    os.makedirs(os.path.dirname(args.html) or ".", exist_ok=True)
    with open(args.html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[render]   {args.html}  ({len(html)//1024} KB)")
    print(f"\nDone.  Open the GUI:\n  xdg-open {args.html}")


if __name__ == "__main__":
    main()
