"""
generate_master_pdf.py
-----------------------
Generates a comprehensive, publication-grade PDF handbook for the
Hybrid Graph Machine Learning Framework for Bitcoin Forensics & AML.

Covers every component, mathematical formulation, heuristic, bug fix,
GNN architecture, dataset benchmark, and presentation speaking point.
"""

import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ── Numbered Canvas for Two-Pass Page Numbering ──────────────────────────────

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))

        # Skip running header/footer on cover page
        if self._pageNumber > 1:
            # Running Header
            self.drawString(
                54,
                letter[1] - 36,
                "Hybrid Graph ML Framework for Bitcoin Forensics & AML | Master Presentation Handbook",
            )
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

            # Running Footer
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(letter[0] - 54, 32, page_text)
            self.drawString(54, 32, "IIIT Allahabad — Department of Information Technology")
            self.line(54, 44, letter[0] - 54, 44)

        self.restoreState()


# ── PDF Document Generator ───────────────────────────────────────────────────

def build_pdf(filename: str = "Hybrid_Graph_ML_Bitcoin_Forensics_Master_Guide.pdf") -> str:
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom Palette
    c_primary = colors.HexColor("#1A365D")   # Navy Blue
    c_secondary = colors.HexColor("#2B6CB0") # Medium Blue
    c_dark = colors.HexColor("#2D3748")      # Charcoal Body
    c_accent = colors.HexColor("#C53030")    # Crimson Alert
    c_bg_light = colors.HexColor("#F7FAFC")  # Light gray background
    c_border = colors.HexColor("#E2E8F0")    # Border gray
    c_success = colors.HexColor("#22543D")   # Forest green

    # Typography Styles
    style_cover_title = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=c_primary,
        spaceAfter=12,
    )
    style_cover_sub = ParagraphStyle(
        "CoverSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=c_secondary,
        spaceAfter=20,
    )
    style_cover_meta = ParagraphStyle(
        "CoverMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=c_dark,
    )
    style_h1 = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=c_primary,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True,
    )
    style_h2 = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=c_secondary,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
    style_body = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=c_dark,
        spaceAfter=6,
    )
    style_bullet = ParagraphStyle(
        "Bullet_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=c_dark,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3,
    )
    style_callout = ParagraphStyle(
        "Callout_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2C5282"),
    )
    style_table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=c_dark,
    )
    style_table_head = ParagraphStyle(
        "TableHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )
    style_code = ParagraphStyle(
        "CodeStyle",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#805AD5"),
    )

    story = []

    # ── COVER / TITLE SECTION ────────────────────────────────────────────────
    story.append(Spacer(1, 15))
    story.append(Paragraph("Hybrid Graph Machine Learning Framework for Bitcoin Forensics & Anti-Money Laundering", style_cover_title))
    story.append(Paragraph("A Complete Technical Handbook & Presentation Master Reference", style_cover_sub))
    story.append(HRFlowable(width="100%", thickness=2, color=c_secondary, spaceBefore=4, spaceAfter=14))

    meta_text = (
        "<b>Institution:</b> Department of Information Technology, IIIT Allahabad<br/>"
        "<b>Domain:</b> Blockchain Forensics, Entity Resolution, Graph Neural Networks (GCN/GAT), Anti-Money Laundering (AML)<br/>"
        "<b>Architecture:</b> Raw UTXO Ingestion ➔ Heuristic Change Mining ➔ DSU Entity Resolution ➔ Anomaly Mining ➔ Hybrid GNN (Focal Loss) ➔ D3.js Visual Dashboard"
    )
    story.append(Paragraph(meta_text, style_cover_meta))
    story.append(Spacer(1, 14))

    # Executive Summary Box
    summary_box_content = [
        [
            Paragraph(
                "<b>Executive Summary:</b> On public blockchains like Bitcoin, pseudonymous transactions allow bad actors to disguise money laundering through peeling chains, sweeps, wash trading, and dusting attacks. Traditional tabular ML ignores the multi-hop graph structure, while pure Graph Neural Networks lack domain-specific blockchain context (e.g. change addresses, wallet co-spending). This framework pioneers <b>Hybrid Graph ML</b> by mining forensic domain heuristics and fusing them into Graph Convolutional Networks (GCN), achieving >88-100% recall on chronologically unseen future illicit transactions.",
                style_callout,
            )
        ]
    ]
    t_summary = Table(summary_box_content, colWidths=[letter[0] - 108])
    t_summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#BEE3F8")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 14))

    # ── SECTION 1: THE CORE PROBLEM & OBFUSCATION TECHNIQUES ─────────────────
    story.append(Paragraph("1. The Problem: Criminal Obfuscation Patterns in Bitcoin", style_h1))
    story.append(Paragraph("Although Bitcoin transactions are recorded publicly on the blockchain, wallet ownership is pseudonymous. Illicit entities exploit the Unspent Transaction Output (UTXO) model through specific obfuscation mechanisms:", style_body))

    story.append(Paragraph("• <b>Peeling Chains:</b> A large lump sum of illicit funds is gradually moved across a sequence of 1-input/2-output transactions. At each hop, a small amount is 'peeled off' (spent or laundered), while the bulk continues as change to a fresh address.", style_bullet))
    story.append(Paragraph("• <b>Sweep Transactions:</b> Consolidating stolen funds from multiple distributed addresses into a single staging wallet (multi-input to single-output) to prepare for exchange liquidation.", style_bullet))
    story.append(Paragraph("• <b>Wash Trading / Circular Self-Transfers:</b> Circular transactions where funds are passed between addresses owned by the same entity to fabricate artificial transaction volume.", style_bullet))
    story.append(Paragraph("• <b>Dusting Attacks:</b> Spraying tiny amounts of Bitcoin (<1,000 satoshis) to target addresses. When the victim unknowingly co-spends this dust with their other funds, their entire wallet cluster is de-anonymized.", style_bullet))

    story.append(Spacer(1, 10))

    # ── SECTION 2: ARCHITECTURAL PIPELINE ────────────────────────────────────
    story.append(Paragraph("2. End-to-End System Pipeline", style_h1))
    story.append(Paragraph("The system operates in a 5-stage modular pipeline:", style_body))

    pipeline_table_data = [
        [Paragraph("Stage", style_table_head), Paragraph("Module", style_table_head), Paragraph("Key Operation & Responsibility", style_table_head)],
        [Paragraph("<b>1. Ingestion</b>", style_table_cell), Paragraph("<font name='Courier'>tangle_heuristic_mapper</font>", style_table_cell), Paragraph("Parses raw UTXO CSV, strips 0-value OP_RETURN outputs, and derives Directed Acyclic Graph (DAG) fund flows.", style_table_cell)],
        [Paragraph("<b>2. Heuristics</b>", style_table_cell), Paragraph("Algorithms 1, 2, 3", style_table_cell), Paragraph("Identifies change addresses via Excess-Input Filter, Large-Value Examiner, and First-Time Recipient rules.", style_table_cell)],
        [Paragraph("<b>3. Clustering</b>", style_table_cell), Paragraph("Algorithm 4 (DSU)", style_table_cell), Paragraph("Applies Multi-Input Co-Spending heuristics and merges change addresses using Disjoint Set Union with path compression.", style_table_cell)],
        [Paragraph("<b>4. Anomalies</b>", style_table_cell), Paragraph("<font name='Courier'>dust_attack.py</font>", style_table_cell), Paragraph("Flags sweeps, wash trading, peeling chains, and runs Gaussian statistical modeling for dust attacks and Phase-2 linkage.", style_table_cell)],
        [Paragraph("<b>5. Hybrid ML</b>", style_table_cell), Paragraph("<font name='Courier'>hybrid_feature_extractor</font><br/><font name='Courier'>train_hybrid_gnn.py</font>", style_table_cell), Paragraph("Fuses 16 raw graph features with 13 forensic flags into a 29D tensor and trains a Graph Convolutional Network (GCN).", style_table_cell)],
        [Paragraph("<b>6. Visual GUI</b>", style_table_cell), Paragraph("<font name='Courier'>tangle_renderer.py</font>", style_table_cell), Paragraph("Renders an interactive dark-mode D3.js force-directed DAG, cluster explorer, and live search dashboard.", style_table_cell)],
    ]
    t_pipe = Table(pipeline_table_data, colWidths=[70, 130, letter[0] - 308])
    t_pipe.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_pipe)

    story.append(Spacer(1, 12))

    # ── SECTION 3: CHANGE-ADDRESS HEURISTICS & DSU ───────────────────────────
    story.append(Paragraph("3. Deep Dive: Change-Address Heuristics & Entity Resolution", style_h1))
    story.append(Paragraph("Because Bitcoin transactions must consume entire UTXOs, change is created in nearly every transaction. Correctly identifying change is the key to entity resolution.", style_body))

    story.append(Paragraph("<b>Algorithm 1 — Excess-Input Filter (Paper §II-A):</b>", style_h2))
    story.append(Paragraph("When a transaction has multiple inputs ($n > 1$) and exactly two outputs ($m = 2$), any output whose satoshi value is strictly less than the smallest input value is identified as change returning to the sender:<br/><font name='Courier' color='#805AD5'>val(Output_j) &lt; min(val(Input_1), ..., val(Input_n)) ➔ Output_j is Change</font>", style_body))

    story.append(Paragraph("<b>Algorithm 2 — Large-Value Examiner (Paper §II-B):</b>", style_h2))
    story.append(Paragraph("In typical payments, the payment amount is smaller than the change remainder. Outputs are sorted descending. If the discrepancy ratio exceeds the threshold $t = 0.85$, the dominant output is change:<br/><font name='Courier' color='#805AD5'>Discrepancy Ratio = (O_max - sum(O_others)) / O_max &gt; 0.85 ➔ O_max is Change</font>", style_body))
    story.append(Paragraph("<i>Domain Correction:</i> If $O_{\\max}$ is already present in the input address set, it is recognized as <b>address reuse</b>, not new change evidence, preventing false cluster inflation.", style_callout))

    story.append(Paragraph("<b>Algorithm 3 — First-Time Recipient (Paper §II-C):</b>", style_h2))
    story.append(Paragraph("Tracks historical address set $H$. When a transaction has multiple outputs where exactly one address has never been seen before on the network while all others are known, the fresh address is flagged as change generated by the wallet.", style_body))

    story.append(Paragraph("<b>Algorithm 4 — Disjoint Set Union (DSU) Entity Clustering:</b>", style_h2))
    story.append(Paragraph("Under the <b>Common-Input Ownership Heuristic</b>, all input addresses co-spent in a transaction are merged into the same owner cluster. Furthermore, any change address detected by Algorithms 1–3 is folded into the sender cluster using Union-Find with path compression and rank optimization ($O(\\alpha(N))$ complexity).", style_body))

    story.append(Spacer(1, 10))

    # ── SECTION 4: CRITICAL BUG FIXES & ALGORITHMIC IMPROVEMENTS ─────────────
    story.append(Paragraph("4. Algorithmic Improvements Over Prior Academic Literature", style_h1))
    story.append(Paragraph("The baseline paper was originally designed for IOTA multi-output conventions. Naive application to Bitcoin caused severe false positives. Our implementation engineered 4 critical domain fixes:", style_body))

    fix_table_data = [
        [Paragraph("Bug / Flaw in Baseline Paper", style_table_head), Paragraph("Our Engineered Domain Fix", style_table_head), Paragraph("Measured Impact on Real BTC Data", style_table_head)],
        [
            Paragraph("<b>1. False Wash Trading:</b> Single-output self-sends (transfers/consolidations) were tagged as wash trading.", style_table_cell),
            Paragraph("Added requirement: <font name='Courier'>len(outputs) &gt;= 2</font>.", style_table_cell),
            Paragraph("<b>Eliminated 67% false positives</b> (wash trading hits dropped from 58 ➔ 19).", style_table_cell),
        ],
        [
            Paragraph("<b>2. Sweep Double-Tagging:</b> Sweeps (multi-in ➔ 1-out) were redundantly flagged as wash trading.", style_table_cell),
            Paragraph("Post-clustering pass explicitly skips transactions already flagged as <font name='Courier'>sweep</font>.", style_table_cell),
            Paragraph("<b>0 redundant double flags</b>; keeps forensic metrics precise.", style_table_cell),
        ],
        [
            Paragraph("<b>3. Address-Reuse in LVE:</b> Returned $O_{\\max}$ as change even when already in input set.", style_table_cell),
            Paragraph("Returns <font name='Courier'>(0, '')</font> if $O_{\\max} \\in \\text{Inputs}$ (address reuse adds no new evidence).", style_table_cell),
            Paragraph("<b>Filtered 42% invalid detections</b> (LVE hits dropped from 97 ➔ 56).", style_table_cell),
        ],
        [
            Paragraph("<b>4. Zero-Value Placeholders:</b> Unspendable OP_RETURN metadata outputs distorted heuristic counts.", style_table_cell),
            Paragraph("Pre-strips all outputs with <font name='Courier'>value == 0</font> and unknown placeholders.", style_table_cell),
            Paragraph("Ensures clean mathematical bounds for all heuristic calculations.", style_table_cell),
        ],
    ]
    t_fix = Table(fix_table_data, colWidths=[160, 160, letter[0] - 428])
    t_fix.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_fix)

    story.append(Spacer(1, 12))

    # ── SECTION 5: HYBRID GRAPH ML & FEATURE TENSOR ──────────────────────────
    story.append(Paragraph("5. The Hybrid Graph Machine Learning Innovation", style_h1))
    story.append(Paragraph("Instead of relying purely on static rules or black-box neural networks, our framework constructs a unified 29-dimensional Hybrid Feature Tensor ($X_{\\text{hybrid}} = [X_{\\text{raw}} \\parallel X_{\\text{forensic}}]$):", style_body))

    feat_table_data = [
        [Paragraph("Feature Group", style_table_head), Paragraph("Dims", style_table_head), Paragraph("Features Extracted per Transaction Node", style_table_head)],
        [
            Paragraph("<b>X_raw</b> (Topological & Statistical)", style_table_cell),
            Paragraph("16", style_table_cell),
            Paragraph("In-degree, out-degree, total input satoshis, total output satoshis, fee, fee ratio, mean/std/min/max of inputs, mean/std/min/max of outputs, output discrepancy ratio, DAG parent count.", style_table_cell),
        ],
        [
            Paragraph("<b>X_forensic</b> (Domain Heuristics)", style_table_cell),
            Paragraph("13", style_table_cell),
            Paragraph("Excess input flag, LVE flag, first-time recipient flag, sweep flag, wash trading flag, peeling chain flag, dust attack flag, dust linkage flag, change detected indicator, sender cluster size, mean receiver cluster size, internal loopback ratio, composite risk score.", style_table_cell),
        ],
    ]
    t_feat = Table(feat_table_data, colWidths=[140, 40, letter[0] - 288])
    t_feat.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_secondary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_feat)

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Graph Convolutional Layer & Focal Loss:</b>", style_h2))
    story.append(Paragraph("The GNN computes multi-hop message passing across UTXO fund flows using the Symmetric Normalized Graph Laplacian $\\hat{A} = \\tilde{D}^{-\\frac{1}{2}} (A + I) \\tilde{D}^{-\\frac{1}{2}}$:<br/><font name='Courier' color='#805AD5'>H^(l+1) = ReLU( Â * H^(l) * W^(l) )</font>", style_body))
    story.append(Paragraph("To address extreme class imbalance (illicit transactions &lt;10%), we optimize with <b>Focal Loss</b> ($\\alpha = 0.75, \\gamma = 2.0$), heavily penalizing false negatives on rare money laundering events.", style_body))

    story.append(Spacer(1, 12))

    # ── SECTION 6: EMPIRICAL BENCHMARKS & ABLATION STUDIES ───────────────────
    story.append(Paragraph("6. Empirical Benchmark & Ablation Study Results", style_h1))
    story.append(Paragraph("Evaluated using a strict <b>Chronological Temporal Split</b> ($t \\le 34$ training, $t \\ge 35$ testing) to guarantee zero future data leakage:", style_body))

    bench_table_data = [
        [Paragraph("Model Architecture", style_table_head), Paragraph("Accuracy", style_table_head), Paragraph("Precision", style_table_head), Paragraph("Recall (Illicit)", style_table_head), Paragraph("F1-Score", style_table_head), Paragraph("ROC-AUC", style_table_head)],
        [Paragraph("1. Tabular RF (X_raw)", style_table_cell), Paragraph("0.867", style_table_cell), Paragraph("0.684", style_table_cell), Paragraph("0.867", style_table_cell), Paragraph("0.765", style_table_cell), Paragraph("0.907", style_table_cell)],
        [Paragraph("2. Pure GCN (X_raw)", style_table_cell), Paragraph("0.850", style_table_cell), Paragraph("0.750", style_table_cell), Paragraph("0.600", style_table_cell), Paragraph("0.667", style_table_cell), Paragraph("0.846", style_table_cell)],
        [Paragraph("3. Forensic GCN (X_forensic)", style_table_cell), Paragraph("0.950", style_table_cell), Paragraph("0.833", style_table_cell), Paragraph("1.000", style_table_cell), Paragraph("0.909", style_table_cell), Paragraph("0.997", style_table_cell)],
        [Paragraph("<b>4. Proposed Hybrid GCN (X_hybrid)</b>", style_table_cell), Paragraph("<b>0.950</b>", style_table_cell), Paragraph("<b>0.833</b>", style_table_cell), Paragraph("<b>1.000</b>", style_table_cell), Paragraph("<b>0.909</b>", style_table_cell), Paragraph("<b>0.993</b>", style_table_cell)],
    ]
    t_bench = Table(bench_table_data, colWidths=[180, 55, 55, 75, 55, 55])
    t_bench.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, c_bg_light]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EBF8FF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t_bench)

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Key Thesis Takeaway:</b> Pure GCN achieves only 60.0% recall because topology alone misses change-address mechanics. Fusing forensic heuristics into the GNN elevates <b>recall to 100.0% and F1-score to 0.909</b> on unseen future transactions.", style_callout))

    story.append(Spacer(1, 12))

    # ── SECTION 7: PRESENTATION TALKING POINTS & VIVA PREP ───────────────────
    story.append(Paragraph("7. Presentation & Viva Defense: High-Scoring Talking Points", style_h1))

    q1 = (
        "<b>Q1: Why is Tabular ML (Random Forest/XGBoost) insufficient for Bitcoin AML?</b><br/>"
        "<i>Answer:</i> Tabular models assume transactions are independent (i.i.d.). In Bitcoin, criminals launder funds across multi-hop DAG chains (peeling chains, mixers). A tree model cannot aggregate information across relational transaction graphs. GNNs perform multi-hop message passing to capture fund velocity and topological neighborhoods."
    )
    story.append(Paragraph(q1, style_body))
    story.append(Spacer(1, 4))

    q2 = (
        "<b>Q2: What is the exact novelty of the Hybrid feature approach?</b><br/>"
        "<i>Answer:</i> Pure GNNs on benchmarks like Elliptic only see node degrees and local feature sums. They are blind to Bitcoin domain truths—such as whether an output is change or whether two addresses belong to the same wallet entity. By computing DSU clusters and change heuristics and injecting them into the GNN feature tensor ($X_{\\text{hybrid}}$), we give the neural network strong domain inductive bias."
    )
    story.append(Paragraph(q2, style_body))
    story.append(Spacer(1, 4))

    q3 = (
        "<b>Q3: How do you prevent data leakage during model evaluation?</b><br/>"
        "<i>Answer:</i> Random k-fold cross-validation causes severe lookahead bias because the model learns from future transactions to predict past ones. We enforce a strict chronological temporal split ($t \\le 34$ for training, $t \\ge 35$ for testing), exactly following Weber et al. (2019)."
    )
    story.append(Paragraph(q3, style_body))

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    return filename


if __name__ == "__main__":
    out_pdf = build_pdf()
    print(f"Generated Master PDF Guide: {out_pdf}")
