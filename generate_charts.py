#!/usr/bin/env python3
"""
Generate blog-ready charts from benchmark results.

Output:
  docs/accuracy_bar_chart.png   — Top-1 accuracy across tiers
  docs/cost_per_case_chart.png  — Cost per case on log scale
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ── Data (from final benchmark numbers, post-fix, post-cap) ─────────────────

conditions = [
    # (label, tier, top1%, cost_per_case)
    ("Sonnet\nBaseline",           1, 36.72, 0.0013),
    ("Opus\nBaseline",             1, 41.46, 0.0065),
    ("Opus\nStructured Prompt",    3, 47.80, 0.036),
    ("Opus\nThinking",             2, 48.60, 0.13),
    ("Opus Agent\nHPO + PubMed",   5, 51.80, 0.15),
    ("Opus Debate\nTeam v2 (Delphi)", 6, 58.34, 0.90),
]

labels = [c[0] for c in conditions]
tiers  = [c[1] for c in conditions]
top1s  = [c[2] for c in conditions]
costs  = [c[3] for c in conditions]

# Sequential color ramp: light to dark by tier number
tier_min, tier_max = min(tiers), max(tiers)
cmap = plt.cm.Blues
norm_tiers = [(t - tier_min) / (tier_max - tier_min) for t in tiers]
# Map to 0.3–0.85 range of the colormap (avoid extremes)
colors = [cmap(0.3 + 0.55 * nt) for nt in norm_tiers]

# Reference lines
references = [
    (26.0,  "Physician baseline (26%)",     "#888888", "--"),
    (33.05, "GPT-4o baseline (33%)",         "#999999", "-."),
    (54.67, "DeepRare-GPT-4o (54.67%)",      "#666666", ":"),
]


# ── Chart 1: Accuracy bar chart ────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 6))

bars = ax.bar(range(len(labels)), top1s, color=colors, edgecolor="white", width=0.7)

# Reference lines — place labels at right edge, offset vertically to avoid overlap
ref_label_offsets = [1.5, 1.5, 1.5]
for (yval, label, color, ls), offset in zip(references, ref_label_offsets):
    ax.axhline(y=yval, color=color, linestyle=ls, linewidth=1.2, alpha=0.7)
    ax.text(len(labels) - 0.3, yval + offset, label, fontsize=7.5, color=color,
            ha="right", va="bottom",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1))

# Value labels on bars
for bar, val in zip(bars, top1s):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
            f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

ax.set_xticks(range(len(labels)))
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylim(0, 100)
ax.set_ylabel("Top-1 Accuracy (%)", fontsize=11)
ax.set_title("Rare Disease Diagnostic Accuracy by Approach", fontsize=13, fontweight="bold")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.yaxis.set_major_locator(ticker.MultipleLocator(10))
ax.yaxis.set_minor_locator(ticker.MultipleLocator(5))

fig.tight_layout()
fig.savefig("docs/accuracy_bar_chart.png", dpi=200, bbox_inches="tight",
            facecolor="white", edgecolor="none")
print("Saved docs/accuracy_bar_chart.png")
plt.close(fig)


# ── Chart 2: Cost per case (log scale, horizontal bars) ────────────────────

fig, ax = plt.subplots(figsize=(10, 5))

y_pos = range(len(labels))
bars = ax.barh(y_pos, costs, color=colors, edgecolor="white", height=0.6)

# Reference line: $200 specialist consultation
ax.axvline(x=200, color="#cc4444", linestyle="--", linewidth=1.5, alpha=0.7)
ax.text(200, len(labels) - 0.5, "In-person rare disease\nspecialist ($200)",
        fontsize=8, color="#cc4444", ha="left", va="top", style="italic")

ax.set_xscale("log")
ax.set_yticks(y_pos)
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel("Cost per Case (USD, log scale)", fontsize=11)
ax.set_title("Cost per Diagnostic Case by Approach", fontsize=13, fontweight="bold")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Value labels on bars
for bar, cost in zip(bars, costs):
    if cost >= 0.01:
        label = f"${cost:.2f}"
    else:
        label = f"${cost:.4f}"
    ax.text(bar.get_width() * 1.3, bar.get_y() + bar.get_height() / 2,
            label, ha="left", va="center", fontsize=9, fontweight="bold")

# Set x limits to show the full range including $200 reference
ax.set_xlim(0.0005, 500)

fig.tight_layout()
fig.savefig("docs/cost_per_case_chart.png", dpi=200, bbox_inches="tight",
            facecolor="white", edgecolor="none")
print("Saved docs/cost_per_case_chart.png")
plt.close(fig)
