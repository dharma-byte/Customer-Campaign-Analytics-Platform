# %% [markdown]
# # Notebook 1 — RFM Analysis & Customer Segmentation
# **Customer Campaign Analytics Platform | CCAP**
#
# **Business context:**
# HSBC's retail banking division runs campaigns across 50,000+ customers.
# Without segmentation, every customer receives the same message — leading to
# wasted budget, high opt-out rates, and missed cross-sell revenue.
#
# **RFM (Recency · Frequency · Monetary)** is the industry-standard method
# for scoring customer engagement value. It answers three questions:
#   - **R** — How recently did this customer interact with a campaign?
#   - **F** — How often do they engage with our campaigns?
#   - **M** — How much revenue have their conversions generated?
#
# Each dimension is scored 1–5 using quintile ranking (NTILE).
# Combining the three scores produces a segment label used by the
# marketing, relationship management, and retention teams.

# %%
import sys
from pathlib import Path

ROOT = Path().resolve()
while ROOT.name != "Customer-Campaign-Analytics-Platform" and ROOT != ROOT.parent:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import seaborn as sns
import warnings
warnings.filterwarnings("ignore")

from scripts.segmentation.feature_engineering import build_feature_matrix

EXPORTS = ROOT / "reports" / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)

C = {"navy":"#1A3C5E","teal":"#2E86AB","red":"#E84855",
     "amber":"#F4A261","green":"#52B788","grey":"#6C757D","light":"#E9ECEF"}

plt.rcParams.update({
    "figure.dpi":120,"figure.facecolor":"white","axes.facecolor":"white",
    "axes.spines.top":False,"axes.spines.right":False,
    "axes.titlesize":12,"axes.titleweight":"bold","font.family":"sans-serif",
})

print("Building feature matrix ...")
feat = build_feature_matrix(verbose=False)
print(f"Feature matrix: {feat.shape[0]:,} customers x {feat.shape[1]} features")

# %% [markdown]
# ## 1 — RFM Score Computation

# %%
rfm = feat[["recency_days", "freq_12m", "total_revenue",
            "customer_segment", "annual_income",
            "credit_score", "n_active_products"]].copy()

# Quintile scoring --------------------------------------------------------
# Recency: LOWER days = better customer → invert scoring (5 = most recent)
rfm["R"] = pd.qcut(rfm["recency_days"], q=5, labels=False, duplicates="drop")
rfm["R"] = 4 - rfm["R"]   # flip: 0→4, 4→0  → then +1 below

# Frequency: HIGHER = better
rfm["F"] = pd.qcut(
    rfm["freq_12m"].rank(method="first"), q=5, labels=False, duplicates="drop"
)
# Monetary: HIGHER = better; customers with zero revenue get score 1
rfm["M_raw"] = rfm["total_revenue"].copy()
non_zero_mask = rfm["M_raw"] > 0
rfm["M"] = 0
rfm.loc[non_zero_mask, "M"] = pd.qcut(
    rfm.loc[non_zero_mask, "M_raw"].rank(method="first"),
    q=4, labels=False, duplicates="drop"
) + 1                        # scores 1–4 for converters
# Non-converters stay at score 0; add 1 to all so range is 1–5
rfm["R"] = rfm["R"] + 1
rfm["F"] = rfm["F"] + 1

# Composite RFM score (equal weights, 3–15 scale)
rfm["rfm_score"] = rfm["R"] + rfm["F"] + rfm["M"]

print("Score distribution:")
print(rfm[["R","F","M","rfm_score"]].describe().round(2).to_string())

# %% [markdown]
# ## 2 — Segment Label Assignment
#
# Mapping rules follow the widely-used RFM matrix from Blattberg, Kim & Neslin (2008),
# adapted for retail banking where recency and frequency carry higher weight.

# %%
def assign_rfm_segment(row: pd.Series) -> str:
    R, F, M = int(row["R"]), int(row["F"]), int(row["M"])

    if R >= 4 and F >= 4 and M >= 4:
        return "Champions"
    elif R >= 3 and F >= 4:
        return "Loyal Customers"
    elif R >= 4 and F <= 2:
        return "New Customers"
    elif R >= 3 and F >= 3:
        return "Potential Loyalists"
    elif R <= 2 and F >= 4 and M >= 4:
        return "Can't Lose Them"
    elif R <= 2 and F >= 3:
        return "At Risk"
    elif R >= 3 and M >= 4:
        return "High-Value Infrequent"
    elif R >= 4 and M == 0:
        return "New Customers"
    elif R <= 2 and F <= 2 and M <= 2:
        return "Hibernating"
    else:
        return "Needs Attention"

rfm["rfm_segment"] = rfm.apply(assign_rfm_segment, axis=1)

seg_counts = rfm["rfm_segment"].value_counts()
print("\nRFM Segment Counts:")
print(seg_counts.to_string())

# %% [markdown]
# ## 3 — Segment Distribution Dashboard

# %%
SEG_PALETTE = {
    "Champions":           "#1A3C5E",
    "Loyal Customers":     "#2E86AB",
    "Potential Loyalists": "#52B788",
    "New Customers":       "#91C7B1",
    "High-Value Infrequent": "#F4A261",
    "Can't Lose Them":     "#E84855",
    "At Risk":             "#C94040",
    "Needs Attention":     "#6C757D",
    "Hibernating":         "#ADB5BD",
}

fig, axes = plt.subplots(2, 3, figsize=(20, 12))
fig.suptitle("RFM Segmentation — Segment Distribution & Profile",
             fontsize=15, fontweight="bold", y=1.01)

seg_order = seg_counts.index.tolist()
colors     = [SEG_PALETTE.get(s, C["grey"]) for s in seg_order]

# ── 3a. Customer count by segment ───────────────────────────────────────────
ax = axes[0][0]
bars = ax.bar(seg_order, seg_counts.values,
              color=colors, edgecolor="white", linewidth=0.5)
ax.set_title("Customer Count by RFM Segment")
ax.set_ylabel("Customers")
ax.set_xticklabels(seg_order, rotation=30, ha="right", fontsize=9)
for bar, v in zip(bars, seg_counts.values):
    pct = v / len(rfm) * 100
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
            f"{v:,}\n({pct:.0f}%)", ha="center", va="bottom",
            fontsize=8, fontweight="bold")

# ── 3b. Revenue share by segment ─────────────────────────────────────────────
ax = axes[0][1]
seg_rev = (rfm.groupby("rfm_segment")["total_revenue"].sum()
           .reindex(seg_order) / 1_000)
bar_colors = [SEG_PALETTE.get(s, C["grey"]) for s in seg_order]
bars = ax.bar(seg_order, seg_rev.values,
              color=bar_colors, edgecolor="white", linewidth=0.5)
ax.set_title("Total Revenue by Segment (£K)")
ax.set_ylabel("Revenue (£K)")
ax.set_xticklabels(seg_order, rotation=30, ha="right", fontsize=9)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"£{x:,.0f}K"))
for bar, v in zip(bars, seg_rev.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
            f"£{v:,.0f}K", ha="center", va="bottom", fontsize=8, fontweight="bold")

# ── 3c. RFM score distribution by segment (box) ──────────────────────────────
ax = axes[0][2]
seg_score_data = [rfm[rfm["rfm_segment"]==s]["rfm_score"].values for s in seg_order]
bp = ax.boxplot(seg_score_data, patch_artist=True, widths=0.6,
                medianprops=dict(color="white", linewidth=2))
for patch, color in zip(bp["boxes"], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.8)
ax.set_title("RFM Score Distribution by Segment")
ax.set_ylabel("RFM Score (3–15)")
ax.set_xticklabels(seg_order, rotation=30, ha="right", fontsize=9)
ax.set_ylim(2, 16)

# ── 3d. R score heatmap (F vs M grid, mean R) ────────────────────────────────
ax = axes[1][0]
fm_grid = (rfm.groupby(["F","M"])["R"].mean().unstack(fill_value=0))
sns.heatmap(fm_grid, ax=ax, cmap="YlOrRd", annot=True, fmt=".1f",
            linewidths=0.5, linecolor="white",
            cbar_kws={"label":"Mean Recency Score"})
ax.set_title("Mean Recency Score (F vs M Matrix)")
ax.set_xlabel("Monetary Score")
ax.set_ylabel("Frequency Score")

# ── 3e. Avg revenue per customer per segment ─────────────────────────────────
ax = axes[1][1]
avg_rev = rfm.groupby("rfm_segment")["total_revenue"].mean().reindex(seg_order)
bars = ax.barh(seg_order, avg_rev.values,
               color=[SEG_PALETTE.get(s, C["grey"]) for s in seg_order],
               edgecolor="white")
ax.set_title("Avg Revenue per Customer by Segment (£)")
ax.set_xlabel("£")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"£{x:,.0f}"))
for bar, v in zip(bars, avg_rev.values):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
            f"£{v:,.0f}", va="center", fontsize=8, fontweight="bold")

# ── 3f. Segment distribution by bank customer segment ────────────────────────
ax = axes[1][2]
seg_cross = (
    rfm.groupby(["customer_segment","rfm_segment"])
    .size()
    .reset_index(name="count")
    .pivot(index="customer_segment", columns="rfm_segment", values="count")
    .fillna(0)
)
# Normalise to % within each bank segment
seg_cross_pct = seg_cross.div(seg_cross.sum(axis=1), axis=0) * 100
seg_cross_pct = seg_cross_pct.reindex(["Mass Market","Affluent","Premier","Private Banking"])

bottom = np.zeros(len(seg_cross_pct))
for col, color in zip(seg_cross_pct.columns,
                      [SEG_PALETTE.get(c, C["grey"]) for c in seg_cross_pct.columns]):
    ax.bar(seg_cross_pct.index, seg_cross_pct[col],
           bottom=bottom, color=color,
           label=col, edgecolor="white", linewidth=0.3)
    bottom += seg_cross_pct[col].values
ax.set_title("RFM Segment Mix within Bank Segment (%)")
ax.set_ylabel("% of Customers")
ax.set_xticklabels(seg_cross_pct.index, rotation=15, ha="right")
ax.legend(fontsize=7, loc="lower right", ncol=2)

plt.tight_layout()
plt.savefig(EXPORTS / "rfm_segment_overview.png", bbox_inches="tight", dpi=150)
plt.show()

# %% [markdown]
# ## 4 — Segment Profile Deep-Dive

# %%
profile_cols = [
    "recency_days", "freq_12m", "total_revenue",
    "annual_income", "credit_score", "n_active_products",
]
profile = (
    rfm.join(feat[["annual_income", "n_active_products"]])
    .groupby("rfm_segment")[profile_cols]
    .agg(["mean","median","count"])
)

# Flatten MultiIndex columns
profile.columns = ["_".join(c) for c in profile.columns]
profile = profile.sort_values("total_revenue_mean", ascending=False)

print("\nRFM SEGMENT PROFILE (mean values):")
print("=" * 90)
for seg in profile.index:
    row = profile.loc[seg]
    print(f"\n  {seg:<25}")
    print(f"    Customers     : {int(row['recency_days_count']):>6,}")
    print(f"    Recency       : {row['recency_days_mean']:>6.0f} days (median {row['recency_days_median']:.0f})")
    print(f"    Freq (12M)    : {row['freq_12m_mean']:>6.1f} interactions")
    print(f"    Revenue       : £{row['total_revenue_mean']:>8,.0f} (median £{row['total_revenue_median']:,.0f})")
    print(f"    Income        : £{row['annual_income_mean']:>8,.0f}")
    print(f"    Credit Score  : {row['credit_score_mean']:>6.0f}")
    print(f"    Products Held : {row['n_active_products_mean']:>6.1f}")

# %% [markdown]
# ## 5 — RFM Segment Radar Chart (Comparative Profiles)

# %%
from matplotlib.patches import FancyArrowPatch

RADAR_SEGMENTS = ["Champions","Loyal Customers","At Risk",
                  "Can't Lose Them","Hibernating","New Customers"]

# Normalise profile metrics to 0–1 range for radar
radar_metrics = ["recency_days","freq_12m","total_revenue",
                 "annual_income","n_active_products","credit_score"]
radar_labels  = ["Recency\n(inverted)","Frequency","Revenue",
                 "Income","Products","Credit Score"]

# For recency, invert so "better" = higher on chart
radar_df = (
    rfm.join(feat[["annual_income","n_active_products"]])
    .groupby("rfm_segment")[radar_metrics]
    .mean()
    .reindex(RADAR_SEGMENTS)
)
radar_df["recency_days"] = radar_df["recency_days"].max() - radar_df["recency_days"]  # invert

# Scale 0–1
radar_norm = (radar_df - radar_df.min()) / (radar_df.max() - radar_df.min() + 1e-9)

n_vars  = len(radar_metrics)
angles  = np.linspace(0, 2 * np.pi, n_vars, endpoint=False).tolist()
angles += angles[:1]

fig, axes = plt.subplots(2, 3, figsize=(18, 10),
                         subplot_kw=dict(polar=True))
fig.suptitle("RFM Segment Radar Profiles", fontsize=14, fontweight="bold")

colors_radar = [C["navy"],C["teal"],C["red"],C["amber"],C["grey"],C["green"]]

for ax, seg, color in zip(axes.flat, RADAR_SEGMENTS, colors_radar):
    values  = radar_norm.loc[seg].tolist()
    values += values[:1]

    ax.plot(angles, values, color=color, linewidth=2)
    ax.fill(angles, values, color=color, alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(radar_labels, fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75])
    ax.set_yticklabels(["25%", "50%", "75%"], fontsize=7)
    ax.set_title(seg, size=10, fontweight="bold", pad=15, color=color)
    ax.tick_params(pad=5)

plt.tight_layout()
plt.savefig(EXPORTS / "rfm_radar_profiles.png", bbox_inches="tight", dpi=150)
plt.show()

# %% [markdown]
# ## 6 — Business Action Playbook
#
# For each segment: who they are, their value, and the recommended action.

# %%
playbook = {
    "Champions": {
        "size_pct":    f"{(rfm['rfm_segment']=='Champions').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']=='Champions']['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "High-income customers who interact often and have converted multiple times.",
        "action":      "Reward programme. Invite to Private Banking upgrade. Use as A/B test control group.",
        "channel":     "Relationship Manager call + Priority email",
        "product":     "Home Loan upgrade, Fixed Deposit premium tier",
        "risk":        "Risk of competitor poaching if not personally managed.",
    },
    "Loyal Customers": {
        "size_pct":    f"{(rfm['rfm_segment']=='Loyal Customers').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']=='Loyal Customers']['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "Consistent engagers. Not highest revenue but reliable relationship.",
        "action":      "Cross-sell adjacent products (e.g., Savings → Fixed Deposit).",
        "channel":     "Email + in-app notification",
        "product":     "Fixed Deposit, Personal Loan",
        "risk":        "Complacency — they may drift to 'At Risk' without regular contact.",
    },
    "Potential Loyalists": {
        "size_pct":    f"{(rfm['rfm_segment']=='Potential Loyalists').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']=='Potential Loyalists']['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "Recently engaged, moderate frequency. Could become Loyal with nurturing.",
        "action":      "Onboarding email series. Offer introductory rate on second product.",
        "channel":     "Email sequence (3-touch over 30 days)",
        "product":     "Savings Account, Credit Card",
        "risk":        "High sensitivity to first bad experience — service quality critical.",
    },
    "New Customers": {
        "size_pct":    f"{(rfm['rfm_segment']=='New Customers').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']=='New Customers']['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "Recently acquired, few interactions, no or low revenue yet.",
        "action":      "Welcome journey. Educate on product range. Set up direct debit incentive.",
        "channel":     "SMS + Email (high open-rate first 30 days)",
        "product":     "Current Account, Savings Account",
        "risk":        "First 90 days are critical — churn risk highest here.",
    },
    "High-Value Infrequent": {
        "size_pct":    f"{(rfm['rfm_segment']=='High-Value Infrequent').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']=='High-Value Infrequent']['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "Large single conversions (e.g., Home Loan) but low campaign engagement.",
        "action":      "Relationship-led outreach. Do NOT spam — low tolerance for mass campaigns.",
        "channel":     "Phone call + personalised letter",
        "product":     "Home Loan review, Buy-to-Let, Private Banking",
        "risk":        "Mass campaign opt-out destroys relationship. Frequency cap essential.",
    },
    "Can't Lose Them": {
        "size_pct":    f"{(rfm['rfm_segment']=='Can\\'t Lose Them').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']==\"Can't Lose Them\"]['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "Previously high-frequency, high-revenue. Recency has dropped sharply.",
        "action":      "Urgent win-back. Personalised offer. Escalate to RM if Premier+.",
        "channel":     "Phone call (Relationship Manager) + Premium email",
        "product":     "Retention offer on existing product. Rate review.",
        "risk":        "Already showing churn signals. Act within 30 days.",
    },
    "At Risk": {
        "size_pct":    f"{(rfm['rfm_segment']=='At Risk').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']=='At Risk']['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "Previously engaged. Activity declining. Middle of the churn curve.",
        "action":      "Re-engagement campaign. Survey to understand unmet needs.",
        "channel":     "Email + Telemarketing",
        "product":     "Rate refresh, fee waiver offer",
        "risk":        "Large segment — prioritise by product value to focus effort.",
    },
    "Hibernating": {
        "size_pct":    f"{(rfm['rfm_segment']=='Hibernating').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']=='Hibernating']['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "Low recency, low frequency, low revenue. Effectively dormant.",
        "action":      "Low-cost reactivation (email only). If no response after 2 touches, suppress.",
        "channel":     "Email only (lowest cost channel)",
        "product":     "Easy-access Savings, free product tier",
        "risk":        "High suppression rate. Don't invest premium channels here.",
    },
    "Needs Attention": {
        "size_pct":    f"{(rfm['rfm_segment']=='Needs Attention').mean()*100:.1f}%",
        "revenue_pct": f"{rfm[rfm['rfm_segment']=='Needs Attention']['total_revenue'].sum()/rfm['total_revenue'].sum()*100:.1f}%",
        "who":         "Mixed signals — moderate across all three dimensions.",
        "action":      "Test different product messages. A/B test messaging tone.",
        "channel":     "Email (test Digital vs Direct Mail)",
        "product":     "Personal Loan, Credit Card upgrade",
        "risk":        "Undefined segment — profile more before heavy spend.",
    },
}

print("\n" + "=" * 70)
print("  RFM SEGMENT BUSINESS PLAYBOOK")
print("=" * 70)
for seg, info in playbook.items():
    print(f"\n  [{info['size_pct']} of customers | {info['revenue_pct']} of revenue]")
    print(f"  SEGMENT : {seg}")
    print(f"  WHO     : {info['who']}")
    print(f"  ACTION  : {info['action']}")
    print(f"  CHANNEL : {info['channel']}")
    print(f"  PRODUCT : {info['product']}")
    print(f"  RISK    : {info['risk']}")
    print("  " + "-" * 68)

# %% [markdown]
# ## 7 — Save RFM Output for Downstream Use

# %%
rfm_output = rfm[["R","F","M","rfm_score","rfm_segment"]].reset_index()
rfm_output.columns = ["customer_id","R","F","M","rfm_score","rfm_segment"]
rfm_output.to_csv(ROOT / "data" / "processed" / "rfm_scores.csv", index=False)

print(f"Saved rfm_scores.csv — {len(rfm_output):,} rows")
print("\nExports saved:")
print("  reports/exports/rfm_segment_overview.png")
print("  reports/exports/rfm_radar_profiles.png")
print("  data/processed/rfm_scores.csv")
print("  data/processed/customer_features.csv")
print("  data/processed/customer_features_scaled.csv")
