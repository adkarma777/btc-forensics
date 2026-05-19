"""
dust_attack.py
--------------
Dust-attack detection for TangleForensix.

WHAT THIS ADAPTS (and what it deliberately does NOT)
----------------------------------------------------
Detection criterion is adapted from:
    Wang, Yang, Li, Zhu, Zhou. "Anti-Dust: A Method for Identifying and
    Preventing Blockchain's Dust Attacks." ICISCAE 2018.

The Anti-Dust paper is a *network-level prevention* system (dust pool,
non-forwarding, mempool, confirmation-time). NONE of that transfers to a
forensic CSV analyser. What DOES transfer is the paper's core idea: stop
using a hard-coded dust threshold (546 sat) and instead characterise dust
*statistically* with a Gaussian over (a) micro-output values and
(b) the per-transaction count of micro outputs (Anti-Dust eqs. 1-4,
Table I lines 7-22).

PHASE-2 ('dust_linkage') IS OUR EXTENSION, NOT FROM THE PAPER.
The Anti-Dust paper prevents flooding; it never addresses the
de-anonymisation consequence (a victim later co-spending received dust,
which links the dust address to their real address). That linkage is the
part that matters for an address-CLUSTERING tool, so it is added here and
should be claimed as the thesis's own contribution.

Output: {tx_id: kind} where kind is
    'dusting'       - phase 1: a tx that sprays many micro outputs (bait)
    'dust_linkage'  - phase 2: a tx that spends earlier-received dust
                      together with >=1 other input (the de-anon moment)

Drop-in: import Transaction from your tangle_heuristic_mapper.
"""

from __future__ import annotations

import math
import statistics
from typing import TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:
    from tangle_heuristic_mapper import Transaction


# ── Tunable parameters ───────────────────────────────────────────────────────
DUST_VALUE_CEILING     = 1000     # satoshi (paper's <= 0.00001 BTC)
USE_PERCENTILE_CEILING = True     # True -> unit-agnostic (recommended for
                                  #          real BTC CSVs with non-satoshi units)
DUST_PERCENTILE        = 0.05     # bottom 5% of positive outputs = "micro"
DUST_FREQ_SIGMA_K      = 2.0      # tail bound: mean + k*sigma micro outputs


# ── Gaussian dust model (Anti-Dust eqs. 1-4) ─────────────────────────────────

def _gaussian_dust_model(
    transactions: List[Transaction],
    micro_ceiling: float,
) -> Tuple[float, float, float, float]:
    micro_vals: List[int] = []
    micro_counts: List[int] = []
    for tx in transactions:
        c = 0
        for v in tx.output_values:
            if 0 < v <= micro_ceiling:
                micro_vals.append(v)
                c += 1
        micro_counts.append(c)

    def _mu_sigma(xs: List[int]) -> Tuple[float, float]:
        if not xs:
            return 0.0, 0.0
        if len(xs) < 2:
            return float(xs[0]), 0.0
        return statistics.fmean(xs), statistics.stdev(xs)

    mu_amt,  sigma_amt  = _mu_sigma(micro_vals)
    mu_freq, sigma_freq = _mu_sigma([c for c in micro_counts if c > 0])
    return mu_amt, sigma_amt, mu_freq, sigma_freq


def _resolve_micro_ceiling(transactions: List[Transaction]) -> float:
    if not USE_PERCENTILE_CEILING:
        return float(DUST_VALUE_CEILING)
    pos = sorted(v for tx in transactions for v in tx.output_values if v > 0)
    if not pos:
        return float(DUST_VALUE_CEILING)
    idx = max(0, min(len(pos) - 1, int(DUST_PERCENTILE * len(pos))))
    return float(pos[idx])


# ── Main detector ────────────────────────────────────────────────────────────

def detect_dust_attacks(
    transactions: List[Transaction],
) -> Dict[int, str]:
    micro_ceiling = _resolve_micro_ceiling(transactions)
    mu_a, sig_a, mu_f, sig_f = _gaussian_dust_model(transactions, micro_ceiling)

    v_t = min(micro_ceiling, mu_a + sig_a) if sig_a > 0 else micro_ceiling
    freq_t = (mu_f + DUST_FREQ_SIGMA_K * sig_f) if sig_f > 0 else 2.0
    min_dust_outs = max(2, math.ceil(freq_t))

    def is_dust_value(v: int) -> bool:
        return 0 < v <= v_t

    flags: Dict[int, str] = {}
    dust_recipients: Dict[str, int] = {}

    for tx in transactions:
        # Phase 2: check against past dust only
        spent_dust = [a for a in tx.input_addresses if a in dust_recipients]
        if spent_dust and len(tx.input_addresses) > 1:
            flags[tx.id] = "dust_linkage"

        # Phase 1: is this tx a duster?
        dust_outs = [a for a, v in zip(tx.output_addresses, tx.output_values)
                     if is_dust_value(v)]
        if len(dust_outs) >= min_dust_outs:
            flags.setdefault(tx.id, "dusting")
            for a in dust_outs:
                dust_recipients.setdefault(a, tx.id)

    return flags
