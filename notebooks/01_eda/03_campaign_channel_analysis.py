# %% [markdown]
# # Notebook 3 — Campaign & Channel Analysis
# **Customer Campaign Analytics Platform | CCAP**
#
# **Purpose:** Deep-dive into campaign and channel performance.
# Every analysis here maps directly to a KPI defined in `KPI_definitions.md`.
#
# Key questions answered:
# - Which campaigns have the highest CVR and ROI?
# - Which channel is most cost-effective?
# - How do campaign types differ in performance?
# - What is the A/B test win rate?
# - How has performance trended month over month?

# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path().resolve()
while ROOT.name != "Customer-Campaign-Analytics-Platform" and ROOT != ROOT.parent:
    ROOT = ROOT.parent
RAW = ROOT / "data" / "raw"

C = {"navy":"#1A3C5E","teal":"#2E86AB","red":"#E84855",
     "amber":"#F4A261","green":"#52B788","grey":"#6C757D","light":"#E9ECEF"}
PALETTE = [C["navy"],C["teal"],C["green"],C["amber"],C["red"],C["grey"]]

plt.rcParams.update({
    "figure.dpi":120,"figure.facecolor":"white","axes.facecolor":"white",
    "axes.spines.top":False,"axes.spines.right":False,
    "axes.titlesize":12,"axes.titleweight":"bold","font.family":"sans-serif",
})

campaigns    = pd.read_csv(RAW/"campaigns.csv", parse_dates=["start_date","end_date"])
channels     = pd.read_csv(RAW/"campaign_channels.csv")
products     = pd.read_csv(RAW/"products.csv")
interactions = pd.read_csv(RAW/"campaign_interactions.csv",
                           parse_dates=["interaction_date","response_date"])
conversions  = pd.read_csv(RAW/"campaign_conversions.csv",
                           parse_dates=["conversion_date"])
customers    = pd.read_csv(RAW/"customers.csv",
                           parse_dates=["date_of_birth","acquisition_date"])

ch_map   = dict(zip(channels["channel_id"], channels["channel_name"]))
prod_map = dict(zip(products["product_id"], products["product_category"]))
bench_cpa = dict(zip(channels["channel_name"], channels["benchmark_cpa"]))
bench_cvr = dict(zip(channels["channel_name"], channels["benchmark_cvr"]))

interactions["channel_name"]     = interactions["channel_id"].map(ch_map)
conversions["channel_name"]      = conversions["channel_id"].map(ch_map)
conversions["product_category"]  = conversions["product_id"].map(prod_map)
campaigns["channel_name"]        = campaigns["channel_id"].map(ch_map)
campaigns["product_category"]    = campaigns["product_id"].map(prod_map)

# Campaign KPIs aggregated
camp_stats = (
    interactions
    .groupby("campaign_id")
    .agg(
        total_contacts      =("interaction_id","count"),
        total_conversions   =("interaction_outcome", lambda x:(x=="Converted").sum()),
        total_responses     =("interaction_outcome",
                              lambda x:(~x.isin(["No Response","Pending"])).sum()),
        total_optouts       =("interaction_outcome", lambda x:(x=="Opted Out").sum()),
    )
    .assign(
        cvr=lambda d: d["total_conversions"]/d["total_contacts"]*100,
        rr =lambda d: d["total_responses"]  /d["total_contacts"]*100,
    )
    .reset_index()
)

camp_rev = (
    conversions.groupby("campaign_id")["revenue_attributed"]
    .sum().rename("revenue").reset_index()
)

camp_kpi = (
    campaigns.merge(camp_stats, on="campaign_id", how="left")
             .merge(camp_rev,   on="campaign_id", how="left")
)
camp_kpi["revenue"]  = camp_kpi["revenue"].fillna(0)
camp_kpi["cpa"]      = camp_kpi["total_budget"] / camp_kpi["total_conversions"].replace(0, np.nan)
camp_kpi["roi_pct"]  = (camp_kpi["revenue"] - camp_kpi["total_budget"]) / camp_kpi["total_budget"] * 100
camp_kpi["duration"] = (camp_kpi["end_date"] - camp_kpi["start_date"]).dt.days

print("Campaign KPIs computed.")
print(f"  Campaigns analysed : {len(camp_kpi)}")
print(f"  Mean CVR           : {camp_kpi['cvr'].mean():.1f}%")
print(f"  Mean ROI           : {camp_kpi['roi_pct'].mean():.0f}%")
print(f"  Total Revenue      : £{camp_kpi['revenue'].sum():,.0f}")

# %% [markdown]
# ## 1 — Campaign Performance Overview

# %%
fig, axes = plt.subplots(2, 3, figsize=(20, 12))
fig.suptitle("Campaign Performance Analysis", fontsize=15,
             fontweight="bold", y=1.01)

completed = camp_kpi[camp_kpi["status"] == "Completed"].copy()

# ── 1a. CVR distribution by campaign type ────────────────────────────────────
ax = axes[0][0]
type_order = completed.groupby("campaign_type")["cvr"].median().sort_values(ascending=False).index
sns.boxplot(data=completed, x="campaign_type", y="cvr",
            order=type_order,
            palette=PALETTE[:len(type_order)], ax=ax,
            flierprops=dict(marker="o", markersize=3, alpha=0.5))
ax.set_title("CVR Distribution by Campaign Type")
ax.set_xlabel("Campaign Type")
ax.set_ylabel("Conversion Rate (%)")
ax.tick_params(axis="x", rotation=20)
ax.axhline(completed["cvr"].mean(), color=C["red"], linestyle="--",
           linewidth=1.5, label=f"Overall mean: {completed['cvr'].mean():.1f}%")
ax.legend(fontsize=9)

# ── 1b. ROI distribution by product category ────────────────────────────────
ax = axes[0][1]
prod_roi = completed.groupby("product_category")["roi_pct"].median().sort_values(ascending=False)
colors   = [C["green"] if v >= 200 else C["amber"] if v >= 100 else C["red"]
            for v in prod_roi.values]
bars = ax.bar(prod_roi.index, prod_roi.values, color=colors, edgecolor="white")
ax.axhline(200, color=C["red"], linestyle="--", linewidth=1.5,
           label="200% ROI benchmark")
ax.set_title("Median ROI by Product Category (%)")
ax.set_xlabel("Product Category")
ax.set_ylabel("ROI (%)")
ax.tick_params(axis="x", rotation=20)
ax.legend(fontsize=9)
for bar, v in zip(bars, prod_roi.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
            f"{v:.0f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

# ── 1c. Top 10 campaigns by CVR ──────────────────────────────────────────────
ax = axes[0][2]
top10_cvr = completed.nlargest(10, "cvr")[
    ["campaign_code","channel_name","product_category","cvr"]
]
colors_ch = [PALETTE[list(ch_map.values()).index(c) % len(PALETTE)]
             if c in ch_map.values() else C["grey"]
             for c in top10_cvr["channel_name"]]
bars = ax.barh(top10_cvr["campaign_code"], top10_cvr["cvr"],
               color=colors_ch, edgecolor="white")
ax.set_title("Top 10 Campaigns by CVR")
ax.set_xlabel("CVR (%)")
for bar, v in zip(bars, top10_cvr["cvr"]):
    ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
            f"{v:.1f}%", va="center", fontsize=8)

# ── 1d. Budget vs Revenue scatter ────────────────────────────────────────────
ax = axes[1][0]
sc = ax.scatter(
    completed["total_budget"],
    completed["revenue"],
    c=completed["cvr"], cmap="YlOrRd",
    s=completed["total_contacts"]/50,
    alpha=0.75, edgecolors="white", linewidth=0.5
)
plt.colorbar(sc, ax=ax, label="CVR (%)")
max_val = max(completed["total_budget"].max(), completed["revenue"].max())
ax.plot([0, max_val], [0, max_val], color=C["grey"], linestyle="--",
        linewidth=1, label="Break-even line")
ax.plot([0, max_val], [0, max_val*3], color=C["green"], linestyle=":",
        linewidth=1, label="3× return (200% ROI)")
ax.set_title("Campaign Budget vs Revenue\n(bubble size = contacts)")
ax.set_xlabel("Campaign Budget (£)")
ax.set_ylabel("Revenue Attributed (£)")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"£{x:,.0f}"))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"£{x:,.0f}"))
ax.legend(fontsize=8)

# ── 1e. CPA by channel ───────────────────────────────────────────────────────
ax = axes[1][1]
ch_cpa = completed.groupby("channel_name").apply(
    lambda d: d["total_budget"].sum() / d["total_conversions"].sum()
).round(2).sort_values()

bench_values = [bench_cpa.get(ch, np.nan) for ch in ch_cpa.index]
x = np.arange(len(ch_cpa))
width = 0.35
bars1 = ax.bar(x - width/2, ch_cpa.values, width,
               color=[C["green"] if v <= b else C["red"]
                      for v, b in zip(ch_cpa.values, bench_values)],
               label="Actual CPA", edgecolor="white")
bars2 = ax.bar(x + width/2, bench_values, width,
               color=C["grey"], alpha=0.5, label="Benchmark CPA", edgecolor="white")
ax.set_xticks(x)
ax.set_xticklabels(ch_cpa.index, rotation=15)
ax.set_title("Actual vs Benchmark CPA by Channel (£)")
ax.set_ylabel("Cost Per Acquisition (£)")
ax.legend(fontsize=9)
ax.axhline(45, color=C["navy"], linestyle="--", linewidth=1.5,
           label="Overall CPA benchmark £45")
for bar, v in zip(bars1, ch_cpa.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
            f"£{v:.0f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

# ── 1f. Monthly campaigns active and CVR trend ───────────────────────────────
ax = axes[1][2]
interactions["month"] = interactions["interaction_date"].dt.to_period("M")
monthly = (
    interactions
    .groupby("month")
    .agg(
        contacts     =("interaction_id","count"),
        conversions  =("interaction_outcome", lambda x:(x=="Converted").sum()),
    )
    .assign(cvr=lambda d: d["conversions"]/d["contacts"]*100)
    .reset_index()
)
monthly["month_dt"] = monthly["month"].dt.to_timestamp()

ax.fill_between(monthly["month_dt"], monthly["cvr"],
                alpha=0.3, color=C["teal"])
ax.plot(monthly["month_dt"], monthly["cvr"],
        color=C["navy"], linewidth=2, marker="o", markersize=3)
ax.set_title("Monthly Conversion Rate Trend")
ax.set_xlabel("Month")
ax.set_ylabel("CVR (%)")
ax.axhline(monthly["cvr"].mean(), color=C["red"], linestyle="--",
           linewidth=1.5, label=f"Mean: {monthly['cvr'].mean():.1f}%")
ax.legend(fontsize=9)
ax.tick_params(axis="x", rotation=30)

plt.tight_layout()
plt.savefig(ROOT/"reports"/"exports"/"campaign_performance_analysis.png",
            bbox_inches="tight", dpi=150)
plt.show()

# %% [markdown]
# ## 2 — Channel Effectiveness Deep-Dive

# %%
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle("Channel Effectiveness Analysis", fontsize=14, fontweight="bold")

ch_stats = (
    interactions
    .groupby("channel_name")
    .agg(
        contacts     =("interaction_id","count"),
        conversions  =("interaction_outcome", lambda x:(x=="Converted").sum()),
        optouts      =("interaction_outcome", lambda x:(x=="Opted Out").sum()),
        interested   =("interaction_outcome", lambda x:(x=="Interested").sum()),
        no_response  =("interaction_outcome", lambda x:(x=="No Response").sum()),
    )
    .assign(
        cvr     =lambda d: d["conversions"]/d["contacts"]*100,
        opt_rate=lambda d: d["optouts"]    /d["contacts"]*100,
        int_rate=lambda d: d["interested"] /d["contacts"]*100,
        nr_rate =lambda d: d["no_response"]/d["contacts"]*100,
    )
)
ch_rev = conversions.groupby("channel_name")["revenue_attributed"].sum()
ch_budget = camp_kpi.groupby("channel_name")["total_budget"].sum()
ch_stats["revenue"] = ch_rev
ch_stats["budget"]  = ch_budget
ch_stats["cpa"]     = ch_stats["budget"] / ch_stats["conversions"]
ch_stats["roi_pct"] = (ch_stats["revenue"] - ch_stats["budget"]) / ch_stats["budget"] * 100
ch_stats = ch_stats.sort_values("cvr", ascending=False)

# ── 2a. CVR vs benchmark ─────────────────────────────────────────────────────
ax = axes[0][0]
x = np.arange(len(ch_stats))
width = 0.35
cvr_actual = ch_stats["cvr"].values
cvr_bench  = [bench_cvr.get(ch, np.nan) for ch in ch_stats.index]
bars1 = ax.bar(x - width/2, cvr_actual, width, color=C["navy"],
               label="Actual CVR", edgecolor="white")
bars2 = ax.bar(x + width/2, cvr_bench, width, color=C["grey"],
               alpha=0.6, label="Benchmark CVR", edgecolor="white")
ax.set_xticks(x)
ax.set_xticklabels(ch_stats.index)
ax.set_title("CVR: Actual vs Benchmark by Channel (%)")
ax.set_ylabel("Conversion Rate (%)")
ax.legend(fontsize=9)
for bar, v in zip(bars1, cvr_actual):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
            f"{v:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold",
            color=C["navy"])

# ── 2b. Stacked outcome distribution ────────────────────────────────────────
ax = axes[0][1]
outcomes = ["conversions","interested","optouts","no_response"]
labels   = ["Converted","Interested","Opted Out","No Response"]
out_colors = [C["green"],C["teal"],C["red"],C["grey"]]
bottom = np.zeros(len(ch_stats))
for col, label, color in zip(outcomes, labels, out_colors):
    vals = ch_stats[col].values / ch_stats["contacts"].values * 100
    ax.bar(ch_stats.index, vals, bottom=bottom, label=label,
           color=color, edgecolor="white", linewidth=0.5)
    bottom += vals
ax.set_title("Interaction Outcome Mix by Channel (%)")
ax.set_ylabel("% of Contacts")
ax.legend(fontsize=9, loc="upper right")
ax.set_ylim(0, 105)

# ── 2c. Revenue and ROI by channel ───────────────────────────────────────────
ax = axes[1][0]
ax2 = ax.twinx()
x = np.arange(len(ch_stats))
bars = ax.bar(x, ch_stats["revenue"].values/1_000_000,
              color=PALETTE[:len(ch_stats)], alpha=0.85,
              edgecolor="white", label="Revenue (£M)")
ax2.plot(x, ch_stats["roi_pct"].values, "o-",
         color=C["red"], linewidth=2, markersize=8, label="ROI %")
ax2.axhline(200, color=C["grey"], linestyle="--", linewidth=1,
            label="200% ROI benchmark")
ax.set_xticks(x)
ax.set_xticklabels(ch_stats.index)
ax.set_title("Revenue (£M) and ROI % by Channel")
ax.set_ylabel("Revenue (£M)")
ax2.set_ylabel("ROI (%)")
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)

# ── 2d. Channel efficiency matrix (CVR vs CPA) ───────────────────────────────
ax = axes[1][1]
sc = ax.scatter(
    ch_stats["cpa"],
    ch_stats["cvr"],
    s=ch_stats["revenue"]/50_000,
    c=PALETTE[:len(ch_stats)],
    alpha=0.85, edgecolors="white", linewidth=1.5, zorder=3
)
for ch in ch_stats.index:
    ax.annotate(
        ch,
        xy=(ch_stats.loc[ch,"cpa"], ch_stats.loc[ch,"cvr"]),
        xytext=(8, 4), textcoords="offset points",
        fontsize=10, fontweight="bold",
        color=PALETTE[list(ch_stats.index).index(ch) % len(PALETTE)]
    )
ax.axhline(15, color=C["grey"], linestyle="--", linewidth=1, alpha=0.7,
           label="CVR 15% target")
ax.axvline(45, color=C["grey"], linestyle=":",  linewidth=1, alpha=0.7,
           label="CPA £45 benchmark")
ax.set_title("Channel Efficiency Matrix\n(bubble = revenue; ideal: top-left)")
ax.set_xlabel("Cost Per Acquisition (£)  ← lower is better")
ax.set_ylabel("Conversion Rate (%)  ↑ higher is better")
ax.legend(fontsize=8)

# Shade "ideal" quadrant
ax.axvspan(0, 45, ymin=15/ax.get_ylim()[1] if ax.get_ylim()[1]>0 else 0,
           alpha=0.04, color=C["green"])

plt.tight_layout()
plt.savefig(ROOT/"reports"/"exports"/"channel_effectiveness.png",
            bbox_inches="tight", dpi=150)
plt.show()

print("CHANNEL ANALYSIS INSIGHTS:")
best_cvr = ch_stats["cvr"].idxmax()
best_roi = ch_stats["roi_pct"].idxmax()
lowest_cpa = ch_stats["cpa"].idxmin()
print(f"  • Highest CVR     : {best_cvr} ({ch_stats.loc[best_cvr,'cvr']:.1f}%)"
      f" — face-to-face interactions convert best")
print(f"  • Highest ROI     : {best_roi} ({ch_stats.loc[best_roi,'roi_pct']:.0f}%)")
print(f"  • Lowest CPA      : {lowest_cpa} (£{ch_stats.loc[lowest_cpa,'cpa']:.0f})")
print(f"  • Branch has highest CVR but likely highest CPA — check efficiency matrix")
print(f"  → Recommendation: Shift 15-20% of Branch budget to Digital/Email to"
      f" maintain revenue volume while reducing CPA below £45 benchmark\n")

# %% [markdown]
# ## 3 — A/B Test Analysis

# %%
ab_interactions = interactions[interactions["ab_variant"].notna()].copy()
ab_conversions  = conversions[conversions["ab_variant"].notna()].copy()

if len(ab_interactions) > 0:
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("A/B Test Analysis — Variant Comparison",
                 fontsize=13, fontweight="bold")

    # Aggregate by variant
    ab_stats = (
        ab_interactions
        .groupby("ab_variant")
        .agg(
            contacts     =("interaction_id","count"),
            conversions  =("interaction_outcome", lambda x:(x=="Converted").sum()),
        )
        .assign(cvr=lambda d: d["conversions"]/d["contacts"]*100)
    )
    ab_rev = (ab_conversions.groupby("ab_variant")["revenue_attributed"]
              .sum().rename("revenue"))
    ab_stats = ab_stats.join(ab_rev).fillna(0)

    # ── CVR by variant
    ax = axes[0]
    bars = ax.bar(ab_stats.index, ab_stats["cvr"],
                  color=[C["navy"], C["teal"]], edgecolor="white", width=0.5)
    ax.set_title("CVR by A/B Variant")
    ax.set_ylabel("CVR (%)")
    ax.set_xlabel("Variant")
    for bar, v in zip(bars, ab_stats["cvr"]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f"{v:.1f}%", ha="center", va="bottom", fontsize=12,
                fontweight="bold")

    # ── Revenue by variant
    ax = axes[1]
    bars = ax.bar(ab_stats.index, ab_stats["revenue"]/1_000,
                  color=[C["navy"], C["teal"]], edgecolor="white", width=0.5)
    ax.set_title("Revenue by A/B Variant (£K)")
    ax.set_ylabel("Revenue (£K)")
    ax.set_xlabel("Variant")
    for bar, v in zip(bars, ab_stats["revenue"]/1_000):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"£{v:,.0f}K", ha="center", va="bottom", fontsize=11,
                fontweight="bold")

    # ── CVR uplift per campaign
    ax = axes[2]
    ab_camp = (
        ab_interactions
        .groupby(["campaign_id","ab_variant"])
        .agg(
            contacts    =("interaction_id","count"),
            conversions =("interaction_outcome", lambda x:(x=="Converted").sum()),
        )
        .assign(cvr=lambda d: d["conversions"]/d["contacts"]*100)
        .reset_index()
    )
    ab_pivot = ab_camp.pivot(index="campaign_id", columns="ab_variant", values="cvr").dropna()
    if "A" in ab_pivot.columns and "B" in ab_pivot.columns:
        ab_pivot["uplift"] = ab_pivot["B"] - ab_pivot["A"]
        ax.bar(range(len(ab_pivot)), ab_pivot["uplift"].sort_values(),
               color=[C["green"] if v > 0 else C["red"]
                      for v in ab_pivot["uplift"].sort_values()],
               edgecolor="white")
        ax.axhline(0, color=C["grey"], linewidth=1)
        ax.set_title("CVR Uplift (B − A) per Campaign")
        ax.set_xlabel("Campaign (sorted by uplift)")
        ax.set_ylabel("CVR Uplift (pp)")
        pos_pct = (ab_pivot["uplift"] > 0).mean() * 100
        ax.text(0.05, 0.95,
                f"B wins in {pos_pct:.0f}% of campaigns",
                transform=ax.transAxes, fontsize=10,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor=C["light"], alpha=0.8))

    plt.tight_layout()
    plt.savefig(ROOT/"reports"/"exports"/"ab_test_analysis.png",
                bbox_inches="tight", dpi=150)
    plt.show()

    # Calculate relative uplift
    if "A" in ab_stats.index and "B" in ab_stats.index:
        a_cvr = ab_stats.loc["A","cvr"]
        b_cvr = ab_stats.loc["B","cvr"]
        uplift = (b_cvr - a_cvr) / a_cvr * 100
        winner = "B" if b_cvr > a_cvr else "A"
        print(f"A/B TEST RESULT:")
        print(f"  Variant A CVR : {a_cvr:.2f}%")
        print(f"  Variant B CVR : {b_cvr:.2f}%")
        print(f"  Relative uplift: {uplift:+.1f}%")
        print(f"  Winner: Variant {winner}")
        print(f"  → Scale Variant {winner} in future campaigns of the same type\n")
else:
    print("No A/B test data available in this dataset.")
