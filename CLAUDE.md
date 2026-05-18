# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

TangleForensix is a forensic analysis tool for Bitcoin transactions. It applies graph heuristics to detect suspicious patterns — sweep transactions, wash trading, change-address clusters — and renders an interactive D3.js GUI for exploration.

The project is a reference implementation of the paper:
> **TangleForensix: A tool for forensic analysis of IOTA funds**, IIIT Allahabad

## Running the project

No external dependencies — pure Python standard library.

```bash
# Full BTC pipeline (load → analyse → render → open GUI)
python main.py

# Custom BTC CSV
python main.py --input /path/to/btc_transactions.csv \
               --json  output/btc_results.json \
               --html  output/btc_tangleforensix.html

# Open the GUI
xdg-open output/btc_tangleforensix.html   # Linux
```

Default BTC input path hardcoded in `main.py`: `/home/anshul/btc_project/data/btc_transactions.csv`

## Running modules individually

```bash
# Analyse only
python tangle_heuristic_mapper.py \
  --input  /path/to/btc_transactions.csv \
  --output output/btc_results.json

# Render only (needs results JSON)
python tangle_renderer.py \
  --input  output/btc_results.json \
  --output output/btc_tangleforensix.html
```

## Architecture

### Pipeline flow

```
btc_transactions.csv
  └─▶ load_transactions_csv()      — auto-detects BTC vs IOTA format, strips
  │                                   unknown addrs + zero-value outputs,
  │                                   derives DAG parents from UTXO flow
  └─▶ cluster_and_analyze()        — applies Algorithms 1–4, builds Union-Find
  └─▶ detect_wash_trading_pass()   — post-clustering second pass
  └─▶ write_results_json()         — writes btc_results.json
  └─▶ build_html()                 — embeds JSON into self-contained HTML
```

### Module responsibilities

**`tangle_heuristic_mapper.py`** — all analysis logic
- `Transaction` dataclass — internal representation
- `DisjointSet` — Union-Find with path compression and union by rank
- `excess_input_filter()` — Algorithm 1: change addr when output < min(inputs)
- `large_value_examiner()` — Algorithm 2: change addr when Omax dominates by >85%
- `first_time_recipient()` — Algorithm 3: change addr when exactly one output is brand-new
- `is_sweep()` — multi-input → single-output consolidation
- `is_wash_trading()` — funds never leave sender's cluster (requires ≥2 outputs)
- `cluster_and_analyze()` — drives Algorithms 1–3, feeds results into DSU
- `detect_wash_trading_pass()` — second pass after clustering is complete
- `load_transactions_csv()` — auto-detects BTC (`transaction_id` column) vs IOTA (`id` column) format

**`tangle_renderer.py`** — single `build_html()` function that produces a self-contained HTML/JS file. All D3 simulation logic is inlined. No server needed.

**`main.py`** — thin orchestrator that calls mapper then renderer, prints a flag-count summary table.

### CSV format auto-detection

`load_transactions_csv()` branches on the presence of `transaction_id` vs `id` in the header:
- **BTC mode**: no `type`, no `parents` (derived from UTXO flow), strips `unknown`/zero-value entries
- **IOTA mode**: has `type` and explicit `parents`, sorts by timestamp for Algorithm 4

### Key algorithmic constraints (do not break these)

- Algorithm 3 (`first_time_recipient`) must receive H *before* the current tx is added to it — the `H.update()` call in `cluster_and_analyze` happens *after* the heuristic runs.
- `detect_wash_trading_pass` must run *after* `cluster_and_analyze` — it needs the fully-built DSU.
- `is_wash_trading` skips txs already flagged `sweep` to avoid double-counting.
- `large_value_examiner` returns `(0, "")` when Omax address is already an input address (address-reuse case adds no new clustering evidence).

### Algorithm improvements made (vs original paper)

| Function | Change | Reason |
|---|---|---|
| `is_wash_trading` | requires `len(outputs) >= 2` | 1-output self-sends are transfers, not wash trading |
| `detect_wash_trading_pass` | skips `sweep`-flagged txs | sweep is the more specific label |
| `large_value_examiner` | skips when Omax ∈ input_addresses | address reuse is not new change-address evidence |
| `_strip_placeholders` | also strips `value == 0` outputs | OP_RETURN / unspendable outputs skew heuristics |

## Output files

| File | Description |
|---|---|
| `output/btc_results.json` | Per-tx flags + change addresses + cluster list |
| `output/btc_tangleforensix.html` | Self-contained interactive GUI (open in browser) |

## GUI features (rendered HTML)

Transaction View: DAG graph, hover tooltips, flag-type filter checkboxes, address search, neighbour highlight on click, ID range filter, zoom controls, live filter count.

Cluster View: cluster nodes (size ∝ addresses), fund-flow edges toggle, hover tooltips, neighbour highlight, ID range filter, zoom controls.

Both views: `Esc` clears all selections and search.
