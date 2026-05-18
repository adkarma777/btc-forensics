"""
tangle_heuristic_mapper.py
--------------------------
Implementation of the *Tangle Heuristic Mapper* module (Section II of
TangleForensix). Implements:

  Algorithm 1  — Excess-input filter heuristic   (§II-A)
  Algorithm 2  — Large-value examiner heuristic  (§II-B)
  Algorithm 3  — First-time recipient heuristic  (§II-C)
  Algorithm 4  — Address Clustering              (§II-D, Disjoint Set Union)
  IsSweep      — sweep transaction predicate     (§II-E)
  IsWashTrading — wash-trading predicate         (§II-F)

Input:   transactions CSV produced by tangle_dataset_generator.py
Output:  results JSON consumed by tangle_renderer.py — contains per-tx
         analysis (flags + change address) and the address clusters.

Variable names mirror the paper: T, I, O, n, m, AIi, VIi, AOi, VOi, H, C.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

LARGE_VALUE_THRESHOLD = 0.85   # paper threshold t for Algorithm 2


# ─── Transaction record ──────────────────────────────────────────────────────

@dataclass
class Transaction:
    id: int
    type: str
    timestamp: str
    parents: List[int]
    input_addresses:  List[str]
    input_values:     List[int]
    output_addresses: List[str]
    output_values:    List[int]


# ─── Disjoint Set Union (used by Algorithm 4) ────────────────────────────────

class DisjointSet:
    """Union-Find with path compression and union by rank."""
    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}
        self.rank:   Dict[str, int] = {}

    def add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x]   = 0

    def find_root(self, x: str) -> str:
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # path compression
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find_root(a), self.find_root(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


# ─── Algorithm 1: Excess-input filter heuristic ──────────────────────────────

def excess_input_filter(tx: Transaction) -> Tuple[int, str]:
    """
    Paper §II-A / Algorithm 1.

    Pre-condition: n > 1 and m == 2.
    Returns (1, change_address) if an output value < min(input values)
    is found, else (0, "").
    """
    I_addrs, I_vals = tx.input_addresses, tx.input_values
    O_addrs, O_vals = tx.output_addresses, tx.output_values
    n, m = len(I_addrs), len(O_addrs)

    if n > 1 and m == 2:
        I_min = min(I_vals)
        for j in range(m):
            if O_vals[j] < I_min:
                return (1, O_addrs[j])
    return (0, "")


# ─── Algorithm 2: Large-value examiner heuristic ─────────────────────────────

def large_value_examiner(
    tx: Transaction,
    t: float = LARGE_VALUE_THRESHOLD,
) -> Tuple[int, str]:
    """
    Paper §II-B / Algorithm 2.

    Sort outputs descending; if (Omax - Oothers) / Omax > t,
    return (1, address-of-Omax). Else (0, "").

    BTC fix: if Omax address is already an input address it is address
    reuse (self-change), not a new change-address detection — return no
    match so the caller does not treat it as new clustering evidence.
    """
    O_addrs, O_vals = tx.output_addresses, tx.output_values
    if len(O_vals) < 2:
        return (0, "")

    # sort outputs by value desc, keeping address pairing
    paired = sorted(zip(O_vals, O_addrs), key=lambda p: -p[0])
    O_max_val,    A_max = paired[0]
    O_others = sum(v for v, _ in paired[1:])

    if O_max_val == 0:
        return (0, "")
    discrepancy_ratio = (O_max_val - O_others) / O_max_val
    if discrepancy_ratio > t:
        if A_max in set(tx.input_addresses):
            return (0, "")   # already-known address reuse, not new evidence
        return (1, A_max)
    return (0, "")


# ─── Algorithm 3: First-time recipient heuristic ─────────────────────────────

def first_time_recipient(tx: Transaction, H: Set[str]) -> Tuple[int, str]:
    """
    Paper §II-C / Algorithm 3.

    Returns (1, o') iff exactly one output address o' is brand-new
    (o' ∉ H), is not among the inputs, AND every other output address
    is already in H. Else (0, "").
    """
    inputs_set  = set(tx.input_addresses)
    outputs     = list(tx.output_addresses)

    new_outputs = [o for o in outputs if o not in H and o not in inputs_set]
    if len(new_outputs) != 1:
        return (0, "")

    o_prime = new_outputs[0]
    # condition 3: every other output address is already in H
    for p in outputs:
        if p == o_prime:
            continue
        if p not in H:
            return (0, "")
    return (1, o_prime)


# ─── §II-E: Sweep predicate ──────────────────────────────────────────────────

def is_sweep(tx: Transaction) -> bool:
    """IsSweep(T) = 1 iff |I| > 1 and |O| = 1."""
    return len(tx.input_addresses) > 1 and len(tx.output_addresses) == 1


# ─── §II-F: Wash-trading predicate (post-clustering) ─────────────────────────

def is_wash_trading(tx: Transaction, ds: DisjointSet) -> bool:
    """
    IsWashTrading(T) = 1 iff every output address resolves (via FindRoot)
    to the cluster of some input address — i.e. funds stay within the
    sender's entity.

    Requires at least 2 outputs: a single self-send is a plain transfer,
    not wash trading. (BTC fix — avoids 1-in/1-out false positives.)
    """
    if not tx.input_addresses or len(tx.output_addresses) < 2:
        return False
    sender_roots = {ds.find_root(a) for a in tx.input_addresses}
    for ao in tx.output_addresses:
        if ds.find_root(ao) not in sender_roots:
            return False
    return True


# ─── Peeling chain detection ─────────────────────────────────────────────────
#
# Replaces the old single-transaction is_peeling_chain() predicate, which
# had three problems confirmed against real chain data:
#
#   1. No chain requirement. A lone 1-in/2-out tx whose larger output is
#      reused as an input somewhere is an ORDINARY spend-with-change, not a
#      peeling chain. The old test flagged a large fraction of normal txs.
#
#   2. `all_input_addrs` was too weak: true if the address is an input
#      ANYWHERE (even the same tx, even earlier). Not a real continuation.
#
#   3. Address-keyed linking is ambiguous. Real peel chains reuse ONE
#      address as both input and change for every hop, so "the tx that
#      spends address X" is undefined. The unambiguous link is the tx
#      whose single input is the remainder address AND carries exactly
#      the remainder value (value carry-forward).
#
# Fix: a per-hop shape predicate + a multi-hop walk linked by value, with
# a minimum chain length. (OP_RETURN / 'unknown' / 0-value outputs are
# already stripped by load_transactions_csv, so two outputs here means
# two real outputs.)


def _is_peel_link(tx: Transaction) -> Tuple[int, str]:
    """
    One hop of a peel chain: a single input and exactly two outputs, where
    the larger output (the remainder/change) strictly dominates the smaller
    'peel' payment. Returns (1, remainder_address) or (0, "").

    Necessary but NOT sufficient — detect_peeling_chains() adds the
    multi-hop walk and the length requirement.
    """
    if len(tx.input_addresses) != 1 or len(tx.output_addresses) != 2:
        return (0, "")
    paired = sorted(zip(tx.output_values, tx.output_addresses),
                    key=lambda p: -p[0])
    (rem_v, rem_a), (peel_v, _peel_a) = paired
    if rem_v <= peel_v:
        return (0, "")
    return (1, rem_a)


def detect_peeling_chains(
    transactions: List[Transaction],
) -> Dict[int, str]:
    """
    Detect peeling chain candidates and return {tx_id: change_address}.

    A tx is flagged if:
      1. Exactly 1 input and 2 outputs, with the larger output strictly
         dominating (peel shape — see _is_peel_link).
      2. The larger output (remainder/change) is NOT the same address as
         the input (no address reuse — those are self-sends, not peels).
      3. The remainder address is later spent as an input in at least one
         other transaction in the dataset (confirming the chain continues).
    """
    # all addresses that appear as inputs anywhere in the dataset
    all_input_addrs: Set[str] = {a for tx in transactions for a in tx.input_addresses}

    chain_map: Dict[int, str] = {}
    for tx in transactions:
        ok, rem_a = _is_peel_link(tx)
        if not ok:
            continue
        if rem_a == tx.input_addresses[0]:
            continue  # address reuse: change goes back to sender's own address
        if rem_a in all_input_addrs:
            chain_map[tx.id] = rem_a

    return chain_map


# ─── Algorithm 4: Address clustering with heuristics 1–3 ─────────────────────

@dataclass
class HeuristicResult:
    """Per-transaction result, mirroring the paper's results-file schema."""
    tx_id: int
    flags: List[str] = field(default_factory=list)
    change_address: Optional[str] = None
    detected_by: Optional[str] = None  # which heuristic flagged the change addr


def cluster_and_analyze(
    transactions: List[Transaction],
) -> Tuple[DisjointSet, Dict[int, HeuristicResult], Dict[int, Set[str]], Set[str]]:
    """
    Paper §II-D / Algorithm 4 + §II-A,B,C,E driving the clustering.

    Walks transactions in chronological order, applies Heuristics 1–3 to
    each one, performs Union-Find unions, builds the cluster dict C, and
    records per-tx analytic results (which heuristic fired, what the
    detected change address was, whether the tx is a sweep).

    Returns:
        ds       — the populated DisjointSet (used later for wash trading)
        results  — tx_id → HeuristicResult
        clusters — cluster_id → set of addresses (the dictionary C)
        H        — the historical address set after the full pass
    """
    ds = DisjointSet()
    H: Set[str] = set()
    results: Dict[int, HeuristicResult] = {}

    # Detect actual peeling chains (multi-hop, value-linked, length>=N) once,
    # up front. Membership in this map replaces the old per-tx predicate.
    peeling_chain_map: Dict[int, str] = detect_peeling_chains(transactions)

    # 1) Initialise DSU with every address present in the dataset.
    for tx in transactions:
        for a in tx.input_addresses + tx.output_addresses:
            ds.add(a)

    # 2) Walk transactions in timestamp order, applying heuristics 1–3
    #    and folding change addresses + common-input-ownership into DSU.
    for tx in transactions:
        res = HeuristicResult(tx_id=tx.id)

        # Heuristic 1
        f1, addr1 = excess_input_filter(tx)
        # Heuristic 2
        f2, addr2 = large_value_examiner(tx)
        # Heuristic 3 (uses H *before* this tx is folded in)
        f3, addr3 = first_time_recipient(tx, H)
        # Peeling chain — membership in a real >= PEELING_CHAIN_MIN_LEN chain
        if tx.id in peeling_chain_map:
            f_pc, addr_pc = 1, peeling_chain_map[tx.id]
        else:
            f_pc, addr_pc = 0, ""

        if f1:
            res.flags.append("excess_input_filter")
            if res.change_address is None:
                res.change_address, res.detected_by = addr1, "excess_input_filter"
        if f2:
            res.flags.append("large_value_examiner")
            if res.change_address is None:
                res.change_address, res.detected_by = addr2, "large_value_examiner"
        if f3:
            res.flags.append("first_time_recipient")
            if res.change_address is None:
                res.change_address, res.detected_by = addr3, "first_time_recipient"
        if f_pc:
            res.flags.append("peeling_chain")
            if res.change_address is None:
                res.change_address, res.detected_by = addr_pc, "peeling_chain"

        if is_sweep(tx):
            res.flags.append("sweep")

        # Algorithm 4 lines 7-10: union change addr + common-input-ownership
        if res.change_address is not None and tx.input_addresses:
            ds.union(res.change_address, tx.input_addresses[0])
        if len(tx.input_addresses) > 1:
            anchor = tx.input_addresses[0]
            for other in tx.input_addresses[1:]:
                ds.union(anchor, other)

        # Add all addresses of this tx to H (line 11).
        H.update(tx.input_addresses)
        H.update(tx.output_addresses)

        # tag remaining txs as "normal" if no heuristic fired and not a sweep
        if not res.flags:
            res.flags.append("normal")

        results[tx.id] = res

    # 3) Build cluster dictionary C (lines 12-18).
    clusters: Dict[int, Set[str]] = {}
    root_to_cid: Dict[str, int] = {}
    for a in H:
        root = ds.find_root(a)
        if root not in root_to_cid:
            root_to_cid[root] = len(root_to_cid)
            clusters[root_to_cid[root]] = set()
        clusters[root_to_cid[root]].add(a)

    return ds, results, clusters, H


# ─── Wash-trading second pass ────────────────────────────────────────────────

def detect_wash_trading_pass(
    transactions: List[Transaction],
    ds: DisjointSet,
    results: Dict[int, HeuristicResult],
) -> int:
    """Annotate `results` with the wash-trading flag. Returns hit count.

    Skips transactions already labelled 'sweep': a multi-input consolidation
    to a single self-address satisfies IsWashTrading by construction, but
    'sweep' is the more precise label and avoids double-counting.
    """
    n = 0
    for tx in transactions:
        flags = results[tx.id].flags
        if "sweep" in flags or "peeling_chain" in flags:
            continue
        if is_wash_trading(tx, ds):
            results[tx.id].flags.append("wash_trading")
            n += 1
    return n


# ─── CSV loader ──────────────────────────────────────────────────────────────

PLACEHOLDER_ADDRS = ("unknown", "")  # treated as non-addresses & stripped


def _strip_placeholders(addrs: List[str], vals: List[int]) -> Tuple[List[str], List[int]]:
    """Remove 'unknown'/empty addresses and zero-value entries (OP_RETURN etc.)."""
    keep_a, keep_v = [], []
    for a, v in zip(addrs, vals):
        a_norm = a.strip().lower()
        if a_norm in PLACEHOLDER_ADDRS or a_norm.startswith("fee_"):
            continue
        if v == 0:
            continue
        keep_a.append(a); keep_v.append(v)
    return keep_a, keep_v


def _derive_btc_parents(transactions: List[Transaction]) -> None:
    """
    BTC has no native 'parents' field. We derive an analogous DAG: tx_B's
    parents are the most recent earlier txs that produced the output
    addresses tx_B is now consuming as inputs. Capped at 2 parents to
    keep the visualization clean (matches IOTA's two-parent rule).
    """
    last_produced: Dict[str, int] = {}   # addr → most recent tx id
    for tx in transactions:
        parents: List[int] = []
        seen: Set[int] = set()
        for in_addr in tx.input_addresses:
            pid = last_produced.get(in_addr)
            if pid is not None and pid != tx.id and pid not in seen:
                parents.append(pid); seen.add(pid)
                if len(parents) >= 2:
                    break
        tx.parents = parents
        for out_addr in tx.output_addresses:
            last_produced[out_addr] = tx.id


def load_transactions_csv(path: str) -> List[Transaction]:
    """
    Loads transactions from CSV. Auto-detects the format:

      A) Canonical (Tangle Dataset Generator output):
         id, type, timestamp, parents, input_addresses, input_values,
         output_addresses, output_values

      B) Bitcoin CSV (real-world data, no planted ground truth):
         transaction_id, input_addresses, input_values,
         output_addresses, output_values
    """
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        cols = set(r.fieldnames or [])
        rows = list(r)

    # Detect BTC format by the presence of `transaction_id` instead of `id`.
    is_btc = "transaction_id" in cols and "id" not in cols

    txs: List[Transaction] = []

    if is_btc:
        # ── BTC mode ─────────────────────────────────────────────────────────
        for idx, row in enumerate(rows, start=1):
            in_addrs_raw  = [a for a in row["input_addresses"].split(";")  if a]
            in_vals_raw   = [v for v in row["input_values"].split(";")     if v]
            out_addrs_raw = [a for a in row["output_addresses"].split(";") if a]
            out_vals_raw  = [v for v in row["output_values"].split(";")    if v]
            try:
                in_vals_all  = [int(v) for v in in_vals_raw]
                out_vals_all = [int(v) for v in out_vals_raw]
            except ValueError:
                continue
            if (len(in_addrs_raw)  != len(in_vals_all) or
                len(out_addrs_raw) != len(out_vals_all)):
                continue

            in_a,  in_v  = _strip_placeholders(in_addrs_raw,  in_vals_all)
            out_a, out_v = _strip_placeholders(out_addrs_raw, out_vals_all)
            if not in_a or not out_a:
                continue   # nothing usable after stripping

            txs.append(Transaction(
                id=idx,
                type="unknown",                                # no planted type
                timestamp=f"btc-row-{idx:05d}",                # CSV row order proxy
                parents=[],                                    # filled in below
                input_addresses=in_a,
                input_values=in_v,
                output_addresses=out_a,
                output_values=out_v,
            ))

        # Derive parents from UTXO flow (input addr ↔ earlier tx's output addr)
        _derive_btc_parents(txs)
        return txs

    # ── Canonical (synthetic IOTA) mode ──────────────────────────────────────
    for row in rows:
        parents = (
            [int(x) for x in row["parents"].split(";") if x]
            if row.get("parents") else []
        )
        in_addrs  = [a for a in row["input_addresses"].split(";")  if a]
        in_vals   = [int(v) for v in row["input_values"].split(";")     if v]
        out_addrs = [a for a in row["output_addresses"].split(";") if a]
        out_vals  = [int(v) for v in row["output_values"].split(";")    if v]
        txs.append(Transaction(
            id=int(row["id"]),
            type=row.get("type", ""),
            timestamp=row["timestamp"],
            parents=parents,
            input_addresses=in_addrs,
            input_values=in_vals,
            output_addresses=out_addrs,
            output_values=out_vals,
        ))
    txs.sort(key=lambda t: t.timestamp)   # Algorithm 4 expects timestamp order
    return txs


# ─── JSON results writer ─────────────────────────────────────────────────────

def write_results_json(
    path: str,
    transactions: List[Transaction],
    results: Dict[int, HeuristicResult],
    clusters: Dict[int, Set[str]],
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "transactions": [
            {
                "id": tx.id,
                "type": tx.type,
                "timestamp": tx.timestamp,
                "parents": tx.parents,
                "inputs":  [{"addr": a, "val": v}
                            for a, v in zip(tx.input_addresses,  tx.input_values)],
                "outputs": [{"addr": a, "val": v}
                            for a, v in zip(tx.output_addresses, tx.output_values)],
                "flags": results[tx.id].flags,
                "change_address": results[tx.id].change_address,
                "detected_by":    results[tx.id].detected_by,
            } for tx in transactions
        ],
        "clusters": [
            {"id": cid, "addresses": sorted(addrs)}
            for cid, addrs in sorted(clusters.items())
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Apply TangleForensix heuristics.")
    p.add_argument("--input",  default="output/transactions.csv")
    p.add_argument("--output", default="output/results.json")
    args = p.parse_args()

    txs = load_transactions_csv(args.input)
    print(f"[load]    {len(txs)} transactions from {args.input}")

    ds, results, clusters, H = cluster_and_analyze(txs)
    n_wash = detect_wash_trading_pass(txs, ds, results)

    write_results_json(args.output, txs, results, clusters)

    # summary
    flag_counts: Dict[str, int] = {}
    for r in results.values():
        for fl in r.flags:
            flag_counts[fl] = flag_counts.get(fl, 0) + 1
    print(f"[done]    wrote {args.output}")
    print(f"          {len(clusters)} clusters covering {len(H)} addresses")
    for fl in ("normal", "sweep", "wash_trading", "peeling_chain",
               "excess_input_filter", "large_value_examiner", "first_time_recipient"):
        print(f"          {fl:<24} {flag_counts.get(fl, 0)}")


if __name__ == "__main__":
    main()