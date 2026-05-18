"""
Generates a realistic-looking BTC transaction CSV for presentation.
All 5 flag types are guaranteed to appear:
  - sweep
  - wash_trading
  - excess_input_filter
  - large_value_examiner
  - first_time_recipient
Plus normal transactions to fill up to 200 rows.
"""

import random
import csv
import string
import hashlib

random.seed(42)

# ── Address factory ───────────────────────────────────────────────────────────
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def _b58(n=33):
    return "1" + "".join(random.choices(BASE58, k=n))

def make_addr():
    return _b58(random.randint(32, 33))

def make_txid():
    return hashlib.sha256(random.randbytes(32)).hexdigest()

# ── Pre-generate address pools ────────────────────────────────────────────────
# "entity" pools — same person owns these (enables wash trading + clustering)
ENTITIES = [[make_addr() for _ in range(random.randint(3, 8))] for _ in range(30)]
FRESH    = [make_addr() for _ in range(2000)]   # one-time addresses

def fresh():
    return FRESH.pop()

def entity_addr(ent_idx):
    return random.choice(ENTITIES[ent_idx])

# ── Row builder ───────────────────────────────────────────────────────────────
def row(in_addrs, in_vals, out_addrs, out_vals):
    return {
        "transaction_id": make_txid(),
        "input_addresses":  ";".join(in_addrs),
        "input_values":     ";".join(str(v) for v in in_vals),
        "output_addresses": ";".join(out_addrs),
        "output_values":    ";".join(str(v) for v in out_vals),
    }

# ── Pattern generators ────────────────────────────────────────────────────────

def gen_normal():
    """Single input → 2 outputs, values balanced."""
    sender = fresh()
    recv   = fresh()
    change = fresh()
    total  = random.randint(500_000, 5_000_000)
    send   = random.randint(total // 3, 2 * total // 3)
    fee    = random.randint(1_000, 10_000)
    chg    = total - send - fee
    if chg <= 0:
        chg = 10_000
    return row([sender], [total], [recv, change], [send, chg])


def gen_sweep(ent_idx):
    """Multi-input (same entity) → single output. Triggers sweep."""
    n_in   = random.randint(2, 5)
    inputs = [entity_addr(ent_idx) for _ in range(n_in)]
    vals   = [random.randint(100_000, 800_000) for _ in range(n_in)]
    dest   = fresh()
    total  = sum(vals) - random.randint(2_000, 15_000)  # minus fee
    return row(inputs, vals, [dest], [total])


def gen_wash_trading(ent_idx):
    """
    Multi-output tx where ALL outputs go to addresses of the same entity.
    After clustering (common-input unions), all outputs resolve to sender's cluster.
    To guarantee detection we first do a sweep (merges entity addrs),
    then send from entity → entity addresses only.
    """
    n_in  = random.randint(2, 3)
    n_out = random.randint(2, 3)
    ins   = [entity_addr(ent_idx) for _ in range(n_in)]
    outs  = [entity_addr(ent_idx) for _ in range(n_out)]
    i_vals = [random.randint(300_000, 900_000) for _ in range(n_in)]
    total  = sum(i_vals) - random.randint(2_000, 10_000)
    # split total across outputs
    o_vals = []
    rem = total
    for k in range(n_out - 1):
        v = random.randint(rem // (n_out - k + 1), rem // 2)
        o_vals.append(v); rem -= v
    o_vals.append(rem)
    return row(ins, i_vals, outs, o_vals)


def gen_excess_input_filter():
    """
    n>1 inputs, exactly 2 outputs, one output < min(input_values).
    Triggers excess_input_filter (Algorithm 1).
    """
    n_in  = random.randint(2, 4)
    i_vals = sorted([random.randint(200_000, 1_000_000) for _ in range(n_in)])
    i_addrs = [fresh() for _ in range(n_in)]
    # change output < min(i_vals)
    change_val = random.randint(10_000, i_vals[0] - 1)
    main_val   = sum(i_vals) - change_val - random.randint(1_000, 8_000)
    if main_val <= 0:
        main_val = 50_000
    recv   = fresh()
    change = fresh()
    return row(i_addrs, i_vals, [recv, change], [main_val, change_val])


def gen_large_value_examiner():
    """
    2+ outputs, largest output dominates by >85%.
    Triggers large_value_examiner (Algorithm 2).
    Omax address must NOT be an input address.
    """
    sender = fresh()
    total  = random.randint(2_000_000, 10_000_000)
    # Omax gets >85% of total
    omax_val   = int(total * random.uniform(0.87, 0.95))
    other_val  = total - omax_val - random.randint(1_000, 5_000)
    if other_val <= 0:
        other_val = 5_000
    omax_addr  = fresh()   # distinct from sender → not address-reuse
    other_addr = fresh()
    return row([sender], [total], [omax_addr, other_addr], [omax_val, other_val])


def gen_first_time_recipient(seen_addrs):
    """
    Exactly one brand-new output address; all other outputs already in seen_addrs.
    Triggers first_time_recipient (Algorithm 3).
    """
    if len(seen_addrs) < 2:
        # fallback to normal if not enough seen addresses yet
        return gen_normal(), None

    sender    = fresh()
    old_addr  = random.choice(list(seen_addrs))  # already seen → in H
    new_addr  = fresh()                           # brand new
    total     = random.randint(500_000, 4_000_000)
    new_val   = random.randint(50_000, total // 3)
    old_val   = total - new_val - random.randint(1_000, 8_000)
    if old_val <= 0:
        old_val = 20_000
    r = row([sender], [total], [new_addr, old_addr], [new_val, old_val])
    return r, new_addr


# ── Build dataset ─────────────────────────────────────────────────────────────
rows = []
seen_addrs = set()   # tracks H for first_time_recipient seeding

def add(r):
    rows.append(r)
    for addr in r["input_addresses"].split(";") + r["output_addresses"].split(";"):
        seen_addrs.add(addr)

# 1. Seed seen_addrs with some normal txs first (Algorithm 3 needs prior history)
for _ in range(20):
    add(gen_normal())

# 2. Guarantee wash-trading: first sweep entity addrs to merge them in DSU,
#    then do intra-entity sends.
wash_entities = [0, 1, 2, 3, 4]
for ent in wash_entities:
    add(gen_sweep(ent))          # sweep → merges entity addrs into one cluster
    add(gen_wash_trading(ent))   # now all outputs are in that cluster → wash trade
    add(gen_wash_trading(ent))   # second wash trade for the same entity

# 3. More sweeps (different entities)
for ent in range(5, 15):
    add(gen_sweep(ent))

# 4. Excess input filter
for _ in range(20):
    add(gen_excess_input_filter())

# 5. Large value examiner
for _ in range(25):
    add(gen_large_value_examiner())

# 6. First time recipient (needs seen_addrs to be populated)
ftr_count = 0
for _ in range(25):
    r, new_addr = gen_first_time_recipient(seen_addrs)
    add(r)
    if new_addr:
        ftr_count += 1

# 7. Fill remaining with normal txs
while len(rows) < 200:
    add(gen_normal())

# Shuffle so patterns aren't in blocks
random.shuffle(rows)

# ── Write CSV ─────────────────────────────────────────────────────────────────
out_path = "/home/anshul/iota_project/btc_presentation.csv"
fieldnames = ["transaction_id", "input_addresses", "input_values",
              "output_addresses", "output_values"]

with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f"Written {len(rows)} transactions → {out_path}")
