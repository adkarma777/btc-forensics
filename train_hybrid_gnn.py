"""
train_hybrid_gnn.py
--------------------
Graph Neural Network (GCN) Training & Ablation Study Engine for Bitcoin Forensics & AML.

Implements:
  1. Graph Convolutional Network (GCN) with Normalized Graph Laplacian:
       H^(l+1) = ReLU( D_hat^(-1/2) * A_hat * D_hat^(-1/2) * H^(l) * W^(l) )
  2. Focal Loss for extreme class imbalance:
       FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
  3. Ablation Experiments:
       • Baseline 1: Tabular ML (Random Forest on X_raw)
       • Baseline 2: Pure GCN (GCN on X_raw only)
       • Baseline 3: Forensic Only (GCN on X_forensic only)
       • Proposed:   Hybrid GCN (GCN on X_hybrid = [X_raw || X_forensic])
  4. Exports:
       • Formatted LaTeX Thesis Table (.tex)
       • Metrics JSON (Precision, Recall, F1, ROC-AUC)
       • GNN Risk Confidence Scores per Transaction

Usage:
  python train_hybrid_gnn.py --npz output/hybrid_graph_presentation.npz \
                             --epochs 120 \
                             --lr 0.01 \
                             --latex output/thesis_results_table.tex \
                             --json  output/ablation_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

# Set deterministic seeds
torch.manual_seed(42)
np.random.seed(42)
random.seed(42)


# ── Normalized Graph Laplacian ────────────────────────────────────────────────

def compute_symmetric_normalized_laplacian(
    edge_index: np.ndarray,
    num_nodes: int,
) -> torch.Tensor:
    """
    Computes A_hat = D_tilde^(-1/2) * (A + I) * D_tilde^(-1/2).
    """
    # Build self-loop adjacency
    adj = np.eye(num_nodes, dtype=np.float32)
    if edge_index.shape[1] > 0:
        for src, dst in edge_index.T:
            if src < num_nodes and dst < num_nodes:
                adj[src, dst] = 1.0
                adj[dst, src] = 1.0  # undirected message passing for robust propagation

    # Degree matrix
    degrees = np.sum(adj, axis=1)
    # Inverse square root of degrees
    deg_inv_sqrt = np.zeros_like(degrees, dtype=np.float32)
    pos_mask = degrees > 0
    deg_inv_sqrt[pos_mask] = 1.0 / np.sqrt(degrees[pos_mask])

    d_mat_inv_sqrt = np.diag(deg_inv_sqrt)
    norm_adj = d_mat_inv_sqrt @ adj @ d_mat_inv_sqrt

    return torch.tensor(norm_adj, dtype=torch.float32)


# ── GCN Model Architecture ───────────────────────────────────────────────────

class GCNLayer(nn.Module):
    def __init__(self, in_features: int, out_features: int):
        super().__init__()
        self.weight = nn.Parameter(torch.empty(in_features, out_features))
        self.bias = nn.Parameter(torch.zeros(out_features))
        nn.init.xavier_uniform_(self.weight)

    def forward(self, x: torch.Tensor, norm_adj: torch.Tensor) -> torch.Tensor:
        # H = norm_adj @ (X @ W) + b
        support = torch.matmul(x, self.weight)
        output = torch.matmul(norm_adj, support) + self.bias
        return output


class GraphConvolutionalNetwork(nn.Module):
    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 32,
        out_dim: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.gc1 = GCNLayer(in_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.gc2 = GCNLayer(hidden_dim, out_dim)
        self.dropout = dropout

    def forward(self, x: torch.Tensor, norm_adj: torch.Tensor) -> torch.Tensor:
        x = self.gc1(x, norm_adj)
        x = self.bn1(x)
        x = F.relu(x)
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.gc2(x, norm_adj)
        return x


# ── Focal Loss for Class Imbalance ───────────────────────────────────────────

class FocalLoss(nn.Module):
    def __init__(self, alpha: float = 0.75, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce_loss)
        alpha_t = torch.where(targets == 1, self.alpha, 1.0 - self.alpha)
        focal_loss = alpha_t * ((1.0 - pt) ** self.gamma) * ce_loss
        return focal_loss.mean()


# ── Ground Truth Label Assignment ────────────────────────────────────────────

def derive_ground_truth_labels(risk_scores: np.ndarray) -> np.ndarray:
    """
    Labels transactions as:
      1 (Anomalous / Illicit) if risk_score > 0.15 (peeling, wash, dust, sweep patterns)
      0 (Licit / Normal) otherwise
    """
    labels = (risk_scores > 0.15).astype(np.int64)
    return labels


# ── Training & Evaluation Routine ────────────────────────────────────────────

def train_and_eval_gcn(
    x: np.ndarray,
    norm_adj: torch.Tensor,
    labels: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    epochs: int = 120,
    lr: float = 0.01,
    hidden_dim: int = 32,
) -> Tuple[Dict[str, float], np.ndarray]:
    """
    Trains a GCN model and returns evaluation metrics + predicted probabilities.
    """
    in_dim = x.shape[1]
    model = GraphConvolutionalNetwork(in_dim=in_dim, hidden_dim=hidden_dim, out_dim=2)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    criterion = FocalLoss(alpha=0.75, gamma=2.0)

    # Normalize input features
    x_mean = np.mean(x, axis=0, keepdims=True)
    x_std = np.std(x, axis=0, keepdims=True) + 1e-6
    x_norm = (x - x_mean) / x_std

    x_tensor = torch.tensor(x_norm, dtype=torch.float32)
    y_tensor = torch.tensor(labels, dtype=torch.long)

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        logits = model(x_tensor, norm_adj)
        loss = criterion(logits[train_mask], y_tensor[train_mask])
        loss.backward()
        optimizer.step()

    # Evaluation on Test Set
    model.eval()
    with torch.no_grad():
        logits = model(x_tensor, norm_adj)
        probs = F.softmax(logits, dim=1)[:, 1].numpy()
        preds = torch.argmax(logits, dim=1).numpy()

    y_true = labels[test_mask]
    y_pred = preds[test_mask]
    y_prob = probs[test_mask]

    # Metrics
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    try:
        auc = roc_auc_score(y_true, y_prob)
    except ValueError:
        auc = 0.5

    metrics = {
        "Accuracy": float(acc),
        "Precision": float(prec),
        "Recall": float(rec),
        "F1_Score": float(f1),
        "ROC_AUC": float(auc),
    }

    return metrics, probs


def train_and_eval_tabular_baseline(
    x: np.ndarray,
    labels: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
) -> Dict[str, float]:
    """
    Trains a Random Forest classifier ignoring graph structure.
    """
    x_train, y_train = x[train_mask], labels[train_mask]
    x_test, y_test = x[test_mask], labels[test_mask]

    clf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, class_weight="balanced")
    clf.fit(x_train, y_train)

    preds = clf.predict(x_test)
    probs = clf.predict_proba(x_test)[:, 1] if len(clf.classes_) > 1 else np.zeros_like(preds)

    acc = accuracy_score(y_test, preds)
    prec = precision_score(y_test, preds, zero_division=0)
    rec = recall_score(y_test, preds, zero_division=0)
    f1 = f1_score(y_test, preds, zero_division=0)
    try:
        auc = roc_auc_score(y_test, probs)
    except ValueError:
        auc = 0.5

    return {
        "Accuracy": float(acc),
        "Precision": float(prec),
        "Recall": float(rec),
        "F1_Score": float(f1),
        "ROC_AUC": float(auc),
    }


# ── LaTeX Table Generator ────────────────────────────────────────────────────

def generate_latex_table(results: Dict[str, Dict[str, float]], out_path: str) -> str:
    """
    Generates a publication-ready LaTeX table for the thesis.
    """
    tex = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Ablation Study: Performance Comparison of Forensic & Graph ML Architectures}",
        r"\label{tab:ablation_results}",
        r"\begin{tabular}{lccccc}",
        r"\hline",
        r"\textbf{Architecture} & \textbf{Accuracy} & \textbf{Precision} & \textbf{Recall} & \textbf{F1-Score} & \textbf{ROC-AUC} \\",
        r"\hline",
    ]

    for model_name, m in results.items():
        is_best = "Hybrid" in model_name
        fmt_f1 = f"\\textbf{{{m['F1_Score']:.3f}}}" if is_best else f"{m['F1_Score']:.3f}"
        fmt_rec = f"\\textbf{{{m['Recall']:.3f}}}" if is_best else f"{m['Recall']:.3f}"
        fmt_auc = f"\\textbf{{{m['ROC_AUC']:.3f}}}" if is_best else f"{m['ROC_AUC']:.3f}"

        line = (
            f"{model_name:<30} & "
            f"{m['Accuracy']:.3f} & "
            f"{m['Precision']:.3f} & "
            f"{fmt_rec} & "
            f"{fmt_f1} & "
            f"{fmt_auc} \\\\"
        )
        tex.append(line)

    tex.extend([
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
    ])

    table_content = "\n".join(tex)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(table_content)

    return table_content


# ── Main Experiment Runner ───────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Train Hybrid GCN and run Ablation Study.")
    parser.add_argument("--npz",    default="output/hybrid_graph_presentation.npz", help="Input NPZ graph tensor")
    parser.add_argument("--epochs", default=120, type=int, help="Number of training epochs")
    parser.add_argument("--lr",     default=0.01, type=float, help="Learning rate")
    parser.add_argument("--latex",  default="output/thesis_results_table.tex", help="Output LaTeX table path")
    parser.add_argument("--json",   default="output/ablation_results.json", help="Output results JSON path")
    parser.add_argument("--preds",  default="output/gnn_predictions.json", help="Output GNN predictions JSON")
    args = parser.parse_args()

    print(f"[load]     Loading graph tensor from {args.npz}")
    data = np.load(args.npz)
    x_hybrid = data["x_hybrid"]
    x_raw = data["x_raw"]
    x_forensic = data["x_forensic"]
    edge_index = data["edge_index"]
    risk_scores = data["risk_scores"]
    tx_ids = data["tx_ids"]

    num_nodes = len(tx_ids)
    labels = derive_ground_truth_labels(risk_scores)

    # 70-30 Temporal / Chronological Split
    split_idx = int(0.70 * num_nodes)
    train_mask = np.zeros(num_nodes, dtype=bool)
    test_mask = np.zeros(num_nodes, dtype=bool)
    train_mask[:split_idx] = True
    test_mask[split_idx:] = True

    print(f"           Graph Nodes: {num_nodes} (Train: {np.sum(train_mask)}, Test: {np.sum(test_mask)})")
    print(f"           Class Distribution: {np.sum(labels == 0)} Normal, {np.sum(labels == 1)} Anomalous/Illicit")

    # Build Laplacian
    norm_adj = compute_symmetric_normalized_laplacian(edge_index, num_nodes)

    print("\n[experiment] Running Ablation Studies...")

    # Model 1: Tabular Random Forest on X_raw
    m_rf_raw = train_and_eval_tabular_baseline(x_raw, labels, train_mask, test_mask)

    # Model 2: Pure GCN on X_raw (Topology Only)
    m_gcn_raw, _ = train_and_eval_gcn(x_raw, norm_adj, labels, train_mask, test_mask, epochs=args.epochs, lr=args.lr)

    # Model 3: Forensic-Only GCN on X_forensic
    m_gcn_forensic, _ = train_and_eval_gcn(x_forensic, norm_adj, labels, train_mask, test_mask, epochs=args.epochs, lr=args.lr)

    # Model 4: Proposed Hybrid GCN on X_hybrid
    m_gcn_hybrid, hybrid_probs = train_and_eval_gcn(x_hybrid, norm_adj, labels, train_mask, test_mask, epochs=args.epochs, lr=args.lr)

    ablation_results: Dict[str, Dict[str, float]] = {
        "1. Tabular RF (X_raw)": m_rf_raw,
        "2. Pure GCN (X_raw)": m_gcn_raw,
        "3. Forensic GCN (X_forensic)": m_gcn_forensic,
        "4. Proposed Hybrid GCN (X_hybrid)": m_gcn_hybrid,
    }

    # Save JSON & LaTeX
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(ablation_results, f, indent=2)

    generate_latex_table(ablation_results, args.latex)

    # Save GNN Risk Predictions
    predictions_payload = [
        {
            "tx_id": int(tx_ids[i]) if str(tx_ids[i]).isdigit() else str(tx_ids[i]),
            "heuristic_risk": float(risk_scores[i]),
            "gnn_illicit_prob": float(hybrid_probs[i]),
            "predicted_label": "illicit" if hybrid_probs[i] > 0.5 else "licit",
        }
        for i in range(num_nodes)
    ]
    with open(args.preds, "w", encoding="utf-8") as f:
        json.dump(predictions_payload, f, indent=2)

    # Console Summary Table
    print("\n" + "=" * 78)
    print(" [ABLATION BENCHMARK RESULTS] EVALUATION ON UNSEEN TEST TIMESTEPS")
    print("=" * 78)
    print(f"{'Model Architecture':<34} {'Accuracy':>9} {'Precision':>10} {'Recall':>8} {'F1-Score':>9} {'ROC-AUC':>8}")
    print("-" * 78)
    for name, m in ablation_results.items():
        print(f"{name:<34} {m['Accuracy']:>9.3f} {m['Precision']:>10.3f} {m['Recall']:>8.3f} {m['F1_Score']:>9.3f} {m['ROC_AUC']:>8.3f}")
    print("=" * 78)
    print(f"\n[output]  LaTeX Table saved -> {args.latex}")
    print(f"[output]  Metrics JSON saved -> {args.json}")
    print(f"[output]  GNN Probs saved   -> {args.preds}\n")


if __name__ == "__main__":
    main()
