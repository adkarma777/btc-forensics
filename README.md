# TangleForensix — Reference Implementation

Faithful Python implementation of the paper:

> **TangleForensix: A tool for forensic analysis of IOTA funds**
> Department of Information Technology, IIIT Allahabad

The project mirrors the paper's three-module architecture:

| Paper Section | Module file | Output |
|---|---|---|
| §IV  Dataset | `tangle_dataset_generator.py` | `output/transactions.csv` |
| §II  Heuristics + Clustering | `tangle_heuristic_mapper.py` | `output/results.json` |
| §III Renderer | `tangle_renderer.py` | `output/tangleforensix.html` (GUI) |

---

## Algorithm Comparison: Original vs Improved

This section documents every change made to the heuristic mapper and renderer, with the exact bug, the fix, and the measured impact on real Bitcoin data (200 transactions).

### Fix 1 — `IsWashTrading`: single-output self-send is not wash trading

| | Original | Improved |
|---|---|---|
| **Condition** | `all outputs resolve to sender's cluster` | same + `len(outputs) >= 2` |
| **False positives on BTC** | 46 of 58 hits were 1-output txs | eliminated |
| **Why it was wrong** | A single self-send (consolidation, self-transfer) trivially satisfies the predicate after Union-Find merges change addresses into the sender cluster. The paper was written for IOTA multi-output norms; 1-output BTC txs are a common and legitimate pattern. |
| **Fix location** | `is_wash_trading()` in `tangle_heuristic_mapper.py` |

```
# before
if not tx.input_addresses or not tx.output_addresses:
    return False

# after
if not tx.input_addresses or len(tx.output_addresses) < 2:
    return False
```

**Result:** wash_trading hits dropped from **58 → 19** on the BTC dataset.

---

### Fix 2 — `detect_wash_trading_pass`: sweep + wash_trading double-flag

| | Original | Improved |
|---|---|---|
| **Behaviour** | Every tx checked for wash trading, including sweeps | Sweeps are skipped |
| **Double-flags on BTC** | 13 transactions carried both `sweep` and `wash_trading` | 0 |
| **Why it was wrong** | A sweep (multiple inputs → 1 self-owned output) satisfies `IsWashTrading` by construction. Tagging it with both flags is redundant and inflates wash-trading counts. `sweep` is the more specific and informative label. |
| **Fix location** | `detect_wash_trading_pass()` in `tangle_heuristic_mapper.py` |

```python
# after
for tx in transactions:
    if "sweep" in results[tx.id].flags:
        continue          # sweep is already the precise label
    if is_wash_trading(tx, ds):
        ...
```

---

### Fix 3 — `large_value_examiner`: address-reuse is not new change-address evidence

| | Original | Improved |
|---|---|---|
| **Behaviour** | Returns Omax address as change regardless | Returns `(0, "")` if Omax ∈ input addresses |
| **False detections on BTC** | 41 of 97 LVE hits had change_address = an input address | filtered out |
| **Why it was wrong** | Bitcoin wallets often reuse the sender's own address as the change output (address reuse). In that case Omax is already a known member of the sender's cluster — flagging it as a "detected change address" adds no new clustering information and pollutes the `change_address` field in the output. |
| **Fix location** | `large_value_examiner()` in `tangle_heuristic_mapper.py` |

```python
# after
if discrepancy_ratio > t:
    if A_max in set(tx.input_addresses):
        return (0, "")   # address reuse — no new evidence
    return (1, A_max)
```

**Result:** LVE hits dropped from **97 → 56** on the BTC dataset.

---

### Fix 4 — `_strip_placeholders`: zero-value outputs stripped

| | Original | Improved |
|---|---|---|
| **Stripped entries** | `unknown` / empty addresses, `fee_*` addresses | + outputs with `value == 0` |
| **Why** | Zero-value outputs (OP_RETURN data outputs, unspendable slots) carry no economic information. Leaving them in can inflate input/output counts for Algorithm 1 and 2 checks. |
| **Fix location** | `_strip_placeholders()` in `tangle_heuristic_mapper.py` |

```python
# after
if v == 0:
    continue
```

---

### Overall flag counts: original vs improved (200 BTC transactions)

| Flag | Original | Improved | Change |
|---|---|---|---|
| `normal` | 45 | 78 | +33 correctly un-flagged |
| `sweep` | 17 | 17 | — unchanged |
| `wash_trading` | 58 | 19 | −39 false positives removed |
| `excess_input_filter` | 12 | 12 | — unchanged |
| `large_value_examiner` | 97 | 56 | −41 address-reuse false positives removed |
| `first_time_recipient` | 61 | 61 | — unchanged |

---

## BTC dataset support

The mapper auto-detects Bitcoin CSV format (column header `transaction_id` instead of `id`):

- No `type` column — all transactions tagged `unknown`
- No `parents` column — DAG edges are derived from UTXO flow (input address ↔ most recent earlier tx that produced it), capped at 2 parents
- `unknown` addresses and zero-value outputs are stripped before heuristics run

Run on a BTC CSV:

```bash
python tangle_heuristic_mapper.py \
  --input  /path/to/btc_transactions.csv \
  --output output/btc_results.json

python tangle_renderer.py \
  --input  output/btc_results.json \
  --output output/btc_tangleforensix.html

xdg-open output/btc_tangleforensix.html
```

Expected BTC CSV schema:

| column | description |
|---|---|
| `transaction_id` | transaction hash |
| `input_addresses` | `;`-separated addresses |
| `input_values` | `;`-separated satoshi values |
| `output_addresses` | `;`-separated addresses |
| `output_values` | `;`-separated satoshi values |

---

## Understanding cluster counts

The Union-Find algorithm starts with every unique address as its own cluster and merges them only when:
- Two addresses are co-inputs in the same transaction (common-input-ownership)
- A heuristic detects a change address and unions it with the sender's input address

On real Bitcoin data (200 txs, 778 addresses), 411 of 520 clusters are singletons — addresses that appear only as a one-time recipient and never get linked to another address. Bitcoin's single-use address convention is the main reason; most receiving addresses have no co-spend evidence in a 200-transaction window.

---

## Interactive GUI features

The renderer (`tangle_renderer.py`) produces a self-contained D3.js HTML file with two views:

**Transaction View**
- Hover tooltip — shows tx#, type, and flags on hover
- Flag filter checkboxes — toggle any combination of the six flag types; All / None shortcuts
- Address search — paste a partial address to dim all non-matching transactions
- Neighbour highlight — click a node to dim everything not directly connected; output panel lists neighbour IDs
- ID range filter — show a subset of transactions by ID range
- Live count — "Showing X / Y transactions" updates with every filter change

**Cluster View**
- Hover tooltip — shows cluster id and address count
- Neighbour highlight — click a cluster to dim non-connected clusters
- Fund-flow edges — "Show fund flow" button draws edges between clusters that exchanged funds
- ID range filter — show a subset of clusters

**Both views**
- `+` / `−` zoom buttons
- `⊡` zoom-to-fit button — auto-fits all visible nodes
- `Esc` key — clears selection, search, and all highlights

---

## What's implemented (paper-by-section)

**Section II — Tangle Heuristic Mapper**
- Algorithm 1 — Excess-input filter heuristic (`n>1, m=2, V_O < I_min`)
- Algorithm 2 — Large-value examiner heuristic (`(O_max − O_others)/O_max > t`)
- Algorithm 3 — First-time recipient heuristic (`o' ∉ H ∧ o' ∉ I ∧ unique`)
- Algorithm 4 — Address Clustering (Disjoint Set Union with path compression)
- §II-E — `IsSweep(T)`
- §II-F — `IsWashTrading(T)` (post-clustering, uses `FindRoot`)

**Section III — Tangle Renderer (GUI)**
- Transaction View and Cluster View with full interactivity (see above)
- Built with D3.js v7, single self-contained HTML file (no server required)

**Section IV — Tangle Dataset Generator**
- 81-tryte IOTA-style addresses (`A–Z + 9`)
- Timestamps in the paper's `%Y-%m-%d %H:%M:%S:%f` format
- Tangle parent-selection (each tx validates two earlier tips)
- Six transaction types with probability-based selection: `normal`, `sweep`, `wash_trading`, `excess_input_filter`, `large_value_examiner`, `first_time_recipient`
- Deterministic given a seed (default `42`)

---

## Project structure

```
iota_project/
├── README.md
├── main.py                        ← runs all three stages
├── tangle_dataset_generator.py
├── tangle_heuristic_mapper.py
├── tangle_renderer.py
└── output/
    ├── transactions.csv
    ├── results.json
    └── tangleforensix.html        ← open this
```

---

## Run it

No external Python dependencies — pure standard library.

```bash
python main.py
```

This runs all three stages and writes everything to `output/`. Then open the GUI:

```bash
xdg-open output/tangleforensix.html   # Linux
open     output/tangleforensix.html   # macOS
start    output/tangleforensix.html   # Windows
```

### Options

```bash
# Bigger dataset, different seed
python main.py --num-transactions 100 --num-entities 20 --seed 7

# Run modules individually
python tangle_dataset_generator.py --output output/transactions.csv
python tangle_heuristic_mapper.py  --input  output/transactions.csv \
                                   --output output/results.json
python tangle_renderer.py          --input  output/results.json \
                                   --output output/tangleforensix.html
```

---

## CSV / JSON schemas

`output/transactions.csv` (produced by §IV generator)

| column | description |
|---|---|
| `id` | sequential transaction id (1, 2, …) |
| `type` | planted type (one of six) |
| `timestamp` | `%Y-%m-%d %H:%M:%S:%f` |
| `parents` | `;`-separated ids of validated transactions (DAG edges) |
| `input_addresses` / `input_values` | `;`-separated lists |
| `output_addresses` / `output_values` | `;`-separated lists |

`output/results.json` (produced by §II mapper)

```jsonc
{
  "transactions": [
    {
      "id": 17,
      "type": "excess_input_filter",
      "timestamp": "2024-01-01 12:08:31:451200",
      "parents": [16, 14],
      "inputs":  [{"addr": "...", "val": 4321}, ...],
      "outputs": [{"addr": "...", "val": 87},   ...],
      "flags": ["excess_input_filter"],
      "change_address": "...",
      "detected_by": "excess_input_filter"
    }
  ],
  "clusters": [
    { "id": 0, "addresses": ["...", "...", "..."] }
  ]
}
```
