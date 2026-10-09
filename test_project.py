"""
test_project.py
---------------
End-to-end verification test suite for the BTxC Forensix & Hybrid Graph ML project.
"""

import os
import sys
import json
import numpy as np

def test_imports():
    print("[1/5] Testing Module Imports...")
    import dust_attack
    import tangle_heuristic_mapper
    import tangle_renderer
    import hybrid_feature_extractor
    import train_hybrid_gnn
    import elliptic_integration
    import generate_master_pdf
    print("      All modules imported successfully.")

def test_heuristic_mapper():
    print("[2/5] Testing Heuristic Mapper & DSU Clustering...")
    from tangle_heuristic_mapper import load_transactions_csv, cluster_and_analyze, detect_wash_trading_pass
    txs = load_transactions_csv("btc_transactions.csv")
    assert len(txs) > 0, "No transactions loaded"
    ds, results, clusters, H = cluster_and_analyze(txs)
    detect_wash_trading_pass(txs, ds, results)
    assert len(clusters) > 0, "No clusters created"
    assert len(H) > 0, "No addresses in history"
    print(f"      Loaded {len(txs)} txs, generated {len(clusters)} clusters across {len(H)} addresses.")

def test_hybrid_feature_extractor():
    print("[3/5] Testing Hybrid Feature Tensor Extractor...")
    from tangle_heuristic_mapper import load_transactions_csv, cluster_and_analyze, detect_wash_trading_pass
    from hybrid_feature_extractor import extract_hybrid_dataset
    txs = load_transactions_csv("btc_transactions.csv")
    ds, results, clusters, H = cluster_and_analyze(txs)
    detect_wash_trading_pass(txs, ds, results)
    hybrid_data = extract_hybrid_dataset(txs, results, ds, clusters)
    assert hybrid_data["num_nodes"] == len(txs), "Node count mismatch"
    assert len(hybrid_data["all_features"]) == 29, f"Feature dimension mismatch: {len(hybrid_data['all_features'])}"
    print(f"      Extracted 29-dimensional hybrid feature vectors for {hybrid_data['num_nodes']} nodes.")

def test_graph_npz_and_gnn_artifacts():
    print("[4/5] Testing GNN Tensors and Model Output Artifacts...")
    data = np.load("output/hybrid_graph.npz")
    assert "x_hybrid" in data and data["x_hybrid"].shape[1] == 29, "x_hybrid dimension invalid"
    assert "edge_index" in data, "edge_index missing"
    assert "risk_scores" in data, "risk_scores missing"

    with open("output/ablation_results.json", "r", encoding="utf-8") as f:
        ablation = json.load(f)
    assert "4. Proposed Hybrid GCN (X_hybrid)" in ablation, "Hybrid GCN missing in ablation"
    print("      GNN graph tensors and ablation metrics validated.")

def test_output_artifacts():
    print("[5/5] Testing All Output Artifacts...")
    required_files = [
        "output/btc_results.json",
        "output/btc_btxc_forensix.html",
        "output/hybrid_features.csv",
        "output/hybrid_graph.npz",
        "output/thesis_results_table.tex",
        "output/ablation_results.json",
        "output/gnn_predictions.json",
        "output/elliptic_thesis_table.tex",
        "output/elliptic_ablation_results.json",
        "output/elliptic_gnn_predictions.json",
        "Hybrid_Graph_ML_Bitcoin_Forensics_Master_Guide.pdf"
    ]
    for rf in required_files:
        assert os.path.exists(rf), f"Missing output file: {rf}"
        assert os.path.getsize(rf) > 0, f"Empty output file: {rf}"
        print(f"      [OK] {rf} ({os.path.getsize(rf):,} bytes)")

if __name__ == "__main__":
    try:
        test_imports()
        test_heuristic_mapper()
        test_hybrid_feature_extractor()
        test_graph_npz_and_gnn_artifacts()
        test_output_artifacts()
        print("\n========================================================")
        print(" SUCCESS: ALL SYSTEM MODULES AND PIPELINES ARE WORKING!")
        print("========================================================")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        sys.exit(1)
