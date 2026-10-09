"""
hybrid_feature_extractor.py
----------------------------
Hybrid Feature Tensor Extractor for Bitcoin Forensics & Graph Neural Networks.

Extracts two complementary feature sets per transaction:
  1. X_raw      — Topological & statistical attributes (degrees, values, fees, variance, ratios)
  2. X_forensic — Domain-specific heuristic indicators (change detection, DSU entity cluster sizes,
                  sweeps, wash trading, peeling chains, dust attacks, composite risk scores)

Combines them into the unified Hybrid Feature Tensor (X_hybrid = [X_raw || X_forensic]) and builds
the PyTorch Geometric / NumPy compatible graph edge index (E) for Graph Convolutional Networks (GCN/GAT).

Usage:
  python hybrid_feature_extractor.py --input btc_transactions_1000.csv \
                                     --csv   output/hybrid_features.csv \
                                     --npz   output/hybrid_graph.npz
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

import numpy as np

from tangle_heuristic_mapper import (
    DisjointSet, HeuristicResult, Transaction,
    cluster_and_analyze, detect_wash_trading_pass,
    load_transactions_csv,
)

# ── Feature Definitions ───────────────────────────────────────────────────────

RAW_FEATURE_NAMES = [
    "in_degree",
    "out_degree",
    "total_input_sat",
    "total_output_sat",
    "fee_sat",
    "fee_ratio",
    "mean_input_sat",
    "std_input_sat",
    "min_input_sat",
    "max_input_sat",
    "mean_output_sat",
    "std_output_sat",
    "min_output_sat",
    "max_output_sat",
    "output_discrepancy_ratio",
    "dag_parent_count",
]

FORENSIC_FEATURE_NAMES = [
    "flag_excess_input",
    "flag_large_value_examiner",
    "flag_first_time_recipient",
    "flag_sweep",
    "flag_wash_trading",
    "flag_peeling_chain",
    "flag_dust_attack",
    "flag_dust_linkage",
    "has_change_detected",
    "sender_cluster_size",
    "receiver_cluster_size_mean",
    "cluster_internal_ratio",
    "heuristic_risk_score",
]

ALL_FEATURE_NAMES = RAW_FEATURE_NAMES + FORENSIC_FEATURE_NAMES


# ── Feature Extraction Functions ─────────────────────────────────────────────

def compute_raw_features(tx: Transaction) -> List[float]:
    """Computes pure statistical and topological attributes for a transaction."""
    in_deg = len(tx.input_addresses)
    out_deg = len(tx.output_addresses)

    in_vals = tx.input_values if tx.input_values else [0]
    out_vals = tx.output_values if tx.output_values else [0]

    tot_in = sum(in_vals)
    tot_out = sum(out_vals)
    fee = max(0, tot_in - tot_out)
    fee_ratio = (fee / tot_in) if tot_in > 0 else 0.0

    mean_in = statistics.mean(in_vals)
    std_in = statistics.stdev(in_vals) if len(in_vals) > 1 else 0.0
    min_in = min(in_vals)
    max_in = max(in_vals)

    mean_out = statistics.mean(out_vals)
    std_out = statistics.stdev(out_vals) if len(out_vals) > 1 else 0.0
    min_out = min(out_vals)
    max_out = max(out_vals)

    # Discrepancy ratio between top output and other outputs
    if len(out_vals) >= 2 and max_out > 0:
        sorted_outs = sorted(out_vals, reverse=True)
        disc_ratio = (sorted_outs[0] - sum(sorted_outs[1:])) / sorted_outs[0]
    else:
        disc_ratio = 0.0

    parent_cnt = len(tx.parents)

    return [
        float(in_deg),
        float(out_deg),
        float(tot_in),
        float(tot_out),
        float(fee),
        float(fee_ratio),
        float(mean_in),
        float(std_in),
        float(min_in),
        float(max_in),
        float(mean_out),
        float(std_out),
        float(min_out),
        float(max_out),
        float(disc_ratio),
        float(parent_cnt),
    ]


def compute_forensic_features(
    tx: Transaction,
    res: HeuristicResult,
    ds: DisjointSet,
    cluster_sizes: Dict[str, int],
) -> List[float]:
    """Computes domain-specific heuristic signals and entity cluster metrics."""
    flags_set = set(res.flags)

    f_excess = 1.0 if "excess_input_filter" in flags_set else 0.0
    f_lve = 1.0 if "large_value_examiner" in flags_set else 0.0
    f_ftr = 1.0 if "first_time_recipient" in flags_set else 0.0
    f_sweep = 1.0 if "sweep" in flags_set else 0.0
    f_wash = 1.0 if "wash_trading" in flags_set else 0.0
    f_peel = 1.0 if "peeling_chain" in flags_set else 0.0
    f_dust_att = 1.0 if "dust_attack" in flags_set else 0.0
    f_dust_link = 1.0 if "dust_linkage" in flags_set else 0.0
    has_change = 1.0 if res.change_address is not None else 0.0

    # Sender cluster size
    sender_root = ds.find_root(tx.input_addresses[0]) if tx.input_addresses else ""
    sender_size = float(cluster_sizes.get(sender_root, 1))

    # Receiver cluster sizes & internal loopback ratio
    receiver_sizes: List[int] = []
    internal_count = 0
    for out_addr in tx.output_addresses:
        out_root = ds.find_root(out_addr)
        receiver_sizes.append(cluster_sizes.get(out_root, 1))
        if sender_root and out_root == sender_root:
            internal_count += 1

    mean_rec_size = float(statistics.mean(receiver_sizes)) if receiver_sizes else 1.0
    internal_ratio = float(internal_count / len(tx.output_addresses)) if tx.output_addresses else 0.0

    # Composite Forensic Risk Score (0.0 to 1.0)
    # Weighted by severity: Wash trading (0.35), Peeling (0.25), Dust link (0.20), Sweep (0.10), Dust attack (0.10)
    risk_score = min(
        1.0,
        (f_wash * 0.35)
        + (f_peel * 0.25)
        + (f_dust_link * 0.20)
        + (f_sweep * 0.10)
        + (f_dust_att * 0.10)
        + (internal_ratio * 0.10 if internal_ratio > 0.5 and len(tx.output_addresses) >= 2 else 0.0),
    )

    return [
        f_excess,
        f_lve,
        f_ftr,
        f_sweep,
        f_wash,
        f_peel,
        f_dust_att,
        f_dust_link,
        has_change,
        sender_size,
        mean_rec_size,
        internal_ratio,
        risk_score,
    ]


# ── Edge Index Construction ──────────────────────────────────────────────────

def build_graph_edge_index(
    transactions: List[Transaction],
) -> Tuple[np.ndarray, int]:
    """
    Constructs PyTorch Geometric edge_index [2, num_edges] from DAG parent links.
    Returns (edge_index_array, total_edge_count).
    """
    id_to_idx = {tx.id: idx for idx, tx in enumerate(transactions)}
    src_nodes: List[int] = []
    dst_nodes: List[int] = []

    for tx in transactions:
        dst_idx = id_to_idx[tx.id]
        for parent_id in tx.parents:
            if parent_id in id_to_idx:
                src_idx = id_to_idx[parent_id]
                src_nodes.append(src_idx)
                dst_nodes.append(dst_idx)

    if not src_nodes:
        edge_index = np.zeros((2, 0), dtype=np.int64)
    else:
        edge_index = np.array([src_nodes, dst_nodes], dtype=np.int64)

    return edge_index, edge_index.shape[1]


# ── Master Extraction Pipeline ───────────────────────────────────────────────

def extract_hybrid_dataset(
    transactions: List[Transaction],
    results: Dict[int, HeuristicResult],
    ds: DisjointSet,
    clusters: Dict[int, Set[str]],
) -> Dict[str, Any]:
    """
    Builds the full hybrid dataset: X_raw, X_forensic, X_hybrid, edge_index, labels, and metadata.
    """
    # Precompute cluster size by root
    cluster_sizes: Dict[str, int] = {}
    for cl_id, addrs in clusters.items():
        if addrs:
            first_addr = next(iter(addrs))
            root = ds.find_root(first_addr)
            cluster_sizes[root] = len(addrs)

    x_raw_list: List[List[float]] = []
    x_forensic_list: List[List[float]] = []
    x_hybrid_list: List[List[float]] = []
    risk_scores: List[float] = []

    for tx in transactions:
        res = results[tx.id]
        raw_feat = compute_raw_features(tx)
        forensic_feat = compute_forensic_features(tx, res, ds, cluster_sizes)
        hybrid_feat = raw_feat + forensic_feat

        x_raw_list.append(raw_feat)
        x_forensic_list.append(forensic_feat)
        x_hybrid_list.append(hybrid_feat)
        risk_scores.append(forensic_feat[-1])  # last element is risk_score

    x_raw = np.array(x_raw_list, dtype=np.float32)
    x_forensic = np.array(x_forensic_list, dtype=np.float32)
    x_hybrid = np.array(x_hybrid_list, dtype=np.float32)
    risk_scores_arr = np.array(risk_scores, dtype=np.float32)

    edge_index, edge_count = build_graph_edge_index(transactions)

    return {
        "x_raw": x_raw,
        "x_forensic": x_forensic,
        "x_hybrid": x_hybrid,
        "edge_index": edge_index,
        "risk_scores": risk_scores_arr,
        "raw_features": RAW_FEATURE_NAMES,
        "forensic_features": FORENSIC_FEATURE_NAMES,
        "all_features": ALL_FEATURE_NAMES,
        "num_nodes": len(transactions),
        "num_edges": edge_count,
    }


def export_features_csv(
    out_csv: str,
    transactions: List[Transaction],
    hybrid_data: Dict[str, Any],
) -> None:
    """Exports the tabular hybrid feature matrix to a CSV file."""
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    header = ["tx_id"] + ALL_FEATURE_NAMES

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for i, tx in enumerate(transactions):
            row = [tx.id] + [f"{val:.6f}" if isinstance(val, float) else str(val)
                             for val in hybrid_data["x_hybrid"][i]]
            writer.writerow(row)


def export_graph_npz(
    out_npz: str,
    transactions: List[Transaction],
    hybrid_data: Dict[str, Any],
) -> None:
    """Exports numpy arrays for PyTorch Geometric / DGL GNN training."""
    os.makedirs(os.path.dirname(out_npz) or ".", exist_ok=True)
    tx_ids = np.array([tx.id for tx in transactions])
    np.savez_compressed(
        out_npz,
        x_hybrid=hybrid_data["x_hybrid"],
        x_raw=hybrid_data["x_raw"],
        x_forensic=hybrid_data["x_forensic"],
        edge_index=hybrid_data["edge_index"],
        risk_scores=hybrid_data["risk_scores"],
        tx_ids=tx_ids,
        feature_names=np.array(ALL_FEATURE_NAMES),
    )


# ── CLI Interface ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Hybrid Graph Features (X_raw + X_forensic) for Bitcoin Forensics & GNNs."
    )
    parser.add_argument("--input", default="btc_transactions_1000.csv", help="Input Bitcoin transactions CSV")
    parser.add_argument("--csv",   default="output/hybrid_features_1000.csv", help="Output feature CSV path")
    parser.add_argument("--npz",   default="output/hybrid_graph_1000.npz", help="Output graph tensor NPZ path")
    args = parser.parse_args()

    print(f"[load]     Reading transactions from {args.input}")
    transactions = load_transactions_csv(args.input)
    print(f"           Loaded {len(transactions)} valid transactions")

    print("[mine]     Running forensic heuristics & DSU entity clustering...")
    ds, results, clusters, H = cluster_and_analyze(transactions)
    detect_wash_trading_pass(transactions, ds, results)

    print("[extract]  Building Hybrid Feature Tensor (X_raw + X_forensic)...")
    hybrid_data = extract_hybrid_dataset(transactions, results, ds, clusters)

    export_features_csv(args.csv, transactions, hybrid_data)
    export_graph_npz(args.npz, transactions, hybrid_data)

    print("\n" + "=" * 60)
    print(" [SUMMARY] HYBRID GRAPH FEATURE EXTRACTION")
    print("=" * 60)
    print(f"  * Total Graph Nodes (Transactions):  {hybrid_data['num_nodes']}")
    print(f"  * Total Graph Edges (UTXO Flows):    {hybrid_data['num_edges']}")
    print(f"  * Raw Feature Dimension (X_raw):     {len(RAW_FEATURE_NAMES)}")
    print(f"  * Forensic Feature Dimension:        {len(FORENSIC_FEATURE_NAMES)}")
    print(f"  * Unified Hybrid Dimension (X_hyb):  {len(ALL_FEATURE_NAMES)}")
    print(f"  * Feature CSV Exported:              {args.csv}")
    print(f"  * GNN Tensor NPZ Exported:           {args.npz}")
    print("=" * 60)


if __name__ == "__main__":
    main()
