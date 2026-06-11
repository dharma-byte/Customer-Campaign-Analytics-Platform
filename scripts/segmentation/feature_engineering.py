"""
Feature Engineering — Customer Segmentation
============================================
Builds the master customer feature matrix used by both:
  - RFM Analysis      (notebooks/02_segmentation/01_rfm_analysis.py)
  - K-Means Clustering (notebooks/02_segmentation/02_kmeans_clustering.py)

Output files (data/processed/):
  customer_features.csv     — raw engineered features (one row per customer)
  customer_features_scaled.csv — StandardScaler normalised (clustering input)

Run standalone:
  python scripts/segmentation/feature_engineering.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve()
while ROOT.name != "Customer-Campaign-Analytics-Platform" and ROOT != ROOT.parent:
    ROOT = ROOT.parent

RAW       = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PRODUCT_CATEGORIES = ["Credit Card", "Savings Account",
                      "Fixed Deposit", "Personal Loan", "Home Loan"]
COL_FLAG = {c: "has_" + c.lower().replace(" ", "_") for c in PRODUCT_CATEGORIES}

TODAY = pd.Timestamp("today").normalize()


def _load_raw() -> dict:
    """Load all raw CSVs into a dict keyed by table name."""
    tables = {}
    tables["customers"] = pd.read_csv(
        RAW / "customers.csv",
        parse_dates=["date_of_birth", "acquisition_date"],
    )
    tables["campaigns"] = pd.read_csv(
        RAW / "campaigns.csv",
        parse_dates=["start_date", "end_date"],
    )
    tables["channels"] = pd.read_csv(RAW / "campaign_channels.csv")
    tables["products"] = pd.read_csv(RAW / "products.csv")
    tables["interactions"] = pd.read_csv(
        RAW / "campaign_interactions.csv",
        parse_dates=["interaction_date", "response_date"],
    )
    tables["conversions"] = pd.read_csv(
        RAW / "campaign_conversions.csv",
        parse_dates=["conversion_date"],
    )
    tables["cust_prods"] = pd.read_csv(
        RAW / "customer_products.csv",
        parse_dates=["acquisition_date", "closure_date"],
    )
    return tables


# ---------------------------------------------------------------------------
# Feature builders — each returns a Series or DataFrame indexed by customer_id
# ---------------------------------------------------------------------------

def _demographic_features(customers: pd.DataFrame) -> pd.DataFrame:
    """Age, income, credit score, tenure, segment flag."""
    df = customers[
        ["customer_id", "date_of_birth", "annual_income",
         "credit_score", "acquisition_date", "customer_segment",
         "number_of_products", "is_active", "is_dnc",
         "employment_status", "gender", "region"]
    ].copy()

    df["age"] = ((TODAY - df["date_of_birth"]).dt.days / 365.25).astype(int)
    df["tenure_days"] = (TODAY - df["acquisition_date"]).dt.days
    df["log_income"]  = np.log1p(df["annual_income"])

    # Income decile (1=bottom 10%, 10=top 10%) — useful for segment labelling
    df["income_decile"] = pd.qcut(
        df["annual_income"], q=10, labels=False, duplicates="drop"
    ) + 1

    # Ordinal segment encoding for correlation analysis
    seg_order = {"Mass Market": 1, "Affluent": 2,
                 "Premier": 3,    "Private Banking": 4}
    df["segment_rank"] = df["customer_segment"].map(seg_order)

    df = df.drop(columns=["date_of_birth", "acquisition_date"])
    return df.set_index("customer_id")


def _recency_features(interactions: pd.DataFrame) -> pd.Series:
    """Days since last campaign interaction (lower = more recent)."""
    last_touch = (
        interactions
        .groupby("customer_id")["interaction_date"]
        .max()
        .rename("last_interaction_date")
    )
    recency = (TODAY - last_touch).dt.days.rename("recency_days")
    return recency


def _frequency_features(interactions: pd.DataFrame) -> pd.DataFrame:
    """Total interactions and interactions in the last 12 months."""
    cutoff_12m = TODAY - pd.Timedelta(days=365)

    total_freq = (
        interactions
        .groupby("customer_id")
        .size()
        .rename("total_interactions")
    )

    freq_12m = (
        interactions[interactions["interaction_date"] >= cutoff_12m]
        .groupby("customer_id")
        .size()
        .rename("freq_12m")
    )

    responded = (
        interactions[
            ~interactions["interaction_outcome"].isin(["No Response", "Pending"])
        ]
        .groupby("customer_id")
        .size()
        .rename("responded_count")
    )

    opted_out = (
        interactions[interactions["interaction_outcome"] == "Opt-Out"]
        .groupby("customer_id")
        .size()
        .rename("optout_count")
    )

    freq_df = pd.concat([total_freq, freq_12m, responded, opted_out], axis=1).fillna(0)
    freq_df["response_rate"]  = freq_df["responded_count"]  / freq_df["total_interactions"]
    freq_df["optout_rate"]    = freq_df["optout_count"]      / freq_df["total_interactions"]
    freq_df["log_freq_total"] = np.log1p(freq_df["total_interactions"])
    freq_df["log_freq_12m"]   = np.log1p(freq_df["freq_12m"])

    return freq_df


def _monetary_features(conversions: pd.DataFrame) -> pd.DataFrame:
    """Revenue metrics per customer (monetary dimension of RFM)."""
    mon = (
        conversions
        .groupby("customer_id")
        .agg(
            total_revenue           = ("revenue_attributed", "sum"),
            n_conversions           = ("conversion_id",      "count"),
            avg_revenue_per_conv    = ("revenue_attributed", "mean"),
            max_single_conversion   = ("revenue_attributed", "max"),
            n_distinct_products_bought = ("product_id",       "nunique"),
        )
    )

    # Conversion types
    type_counts = (
        conversions
        .groupby(["customer_id", "conversion_type"])
        .size()
        .unstack(fill_value=0)
        .rename(columns={c: f"conv_{c.lower().replace('-', '_').replace(' ','_')}"
                         for c in conversions["conversion_type"].unique()})
    )

    mon = mon.join(type_counts, how="left").fillna(0)
    mon["log_revenue"] = np.log1p(mon["total_revenue"])
    return mon


def _product_features(cust_prods: pd.DataFrame,
                       products: pd.DataFrame) -> pd.DataFrame:
    """Product holdings, diversity, and value."""
    prod_map  = dict(zip(products["product_id"], products["product_category"]))
    cust_prods = cust_prods.copy()
    cust_prods["product_category"] = cust_prods["product_id"].map(prod_map)

    active = cust_prods[cust_prods["status"] == "Active"]

    n_active = (
        active.groupby("customer_id").size().rename("n_active_products")
    )
    n_categories = (
        active.groupby("customer_id")["product_category"]
        .nunique().rename("n_product_categories")
    )
    total_value = (
        active.groupby("customer_id")["product_value"]
        .sum().rename("total_product_value")
    )
    avg_value = (
        active.groupby("customer_id")["product_value"]
        .mean().rename("avg_product_value")
    )
    max_value = (
        active.groupby("customer_id")["product_value"]
        .max().rename("max_product_value")
    )

    # Binary flags per product category
    flags = (
        active
        .groupby(["customer_id", "product_category"])
        .size()
        .unstack(fill_value=0)
        .clip(upper=1)
        .rename(columns=COL_FLAG)
    )
    # Ensure all 5 flags exist
    for flag in COL_FLAG.values():
        if flag not in flags.columns:
            flags[flag] = 0

    prod_df = pd.concat(
        [n_active, n_categories, total_value, avg_value, max_value, flags],
        axis=1
    ).fillna(0)

    prod_df["log_product_value"] = np.log1p(prod_df["total_product_value"])
    prod_df["is_multi_product"]  = (prod_df["n_active_products"] >= 2).astype(int)
    prod_df["cross_sell_score"]  = (
        prod_df["n_product_categories"] / len(PRODUCT_CATEGORIES)
    )

    return prod_df


def _engagement_features(interactions: pd.DataFrame) -> pd.DataFrame:
    """Channel and campaign engagement signals."""
    ch_diversity = (
        interactions
        .groupby("customer_id")["channel_id"]
        .nunique()
        .rename("channels_used")
    )
    campaign_count = (
        interactions
        .groupby("customer_id")["campaign_id"]
        .nunique()
        .rename("campaigns_touched")
    )
    ab_participant = (
        interactions[interactions["ab_variant"].notna()]
        .groupby("customer_id")
        .size()
        .gt(0)
        .astype(int)
        .rename("ab_participant_flag")
    )
    days_since_first = (
        interactions
        .groupby("customer_id")["interaction_date"]
        .min()
    )
    days_active_span = (
        (
            interactions.groupby("customer_id")["interaction_date"].max()
            - days_since_first
        ).dt.days.rename("interaction_span_days")
    )

    return pd.concat(
        [ch_diversity, campaign_count, ab_participant, days_active_span],
        axis=1
    ).fillna(0)


# ---------------------------------------------------------------------------
# Master builder
# ---------------------------------------------------------------------------

def build_feature_matrix(verbose: bool = True) -> pd.DataFrame:
    """
    Build and return the complete customer feature matrix.
    Also saves two CSVs to data/processed/.

    Returns
    -------
    pd.DataFrame
        One row per customer_id, raw (unscaled) features + metadata columns.
    """
    if verbose:
        print("Loading raw data ...")
    t = _load_raw()

    if verbose:
        print("Engineering features ...")

    demo     = _demographic_features(t["customers"])
    recency  = _recency_features(t["interactions"])
    freq     = _frequency_features(t["interactions"])
    monetary = _monetary_features(t["conversions"])
    products = _product_features(t["cust_prods"], t["products"])
    engage   = _engagement_features(t["interactions"])

    # Merge all onto customer base
    feat = (
        demo
        .join(recency,  how="left")
        .join(freq,     how="left")
        .join(monetary, how="left")
        .join(products, how="left")
        .join(engage,   how="left")
    )

    # Customers with zero interactions get sensible defaults
    feat["recency_days"]   = feat["recency_days"].fillna(feat["tenure_days"])
    feat["total_revenue"]  = feat["total_revenue"].fillna(0)
    feat["n_conversions"]  = feat["n_conversions"].fillna(0)
    feat["log_revenue"]    = feat["log_revenue"].fillna(0)
    feat["total_interactions"] = feat["total_interactions"].fillna(0)
    feat["freq_12m"]       = feat["freq_12m"].fillna(0)
    feat["n_active_products"] = feat["n_active_products"].fillna(0)

    # Fill remaining NaN with 0 (products, flags, engagement)
    feat = feat.fillna(0)

    # Save raw features
    feat.reset_index().to_csv(PROCESSED / "customer_features.csv", index=False)
    if verbose:
        print(f"  Saved customer_features.csv  ({feat.shape[0]:,} rows x {feat.shape[1]} cols)")

    # Build scaled version for clustering (continuous features only)
    scale_cols = [
        "age", "log_income", "credit_score", "tenure_days",
        "recency_days", "log_freq_total", "log_freq_12m",
        "response_rate", "optout_rate",
        "log_revenue", "n_conversions", "avg_revenue_per_conv",
        "n_active_products", "n_product_categories",
        "log_product_value", "cross_sell_score",
        "channels_used", "campaigns_touched",
        "interaction_span_days",
    ]
    # Keep only columns that actually exist
    scale_cols = [c for c in scale_cols if c in feat.columns]

    scaler     = StandardScaler()
    scaled_arr = scaler.fit_transform(feat[scale_cols])
    scaled_df  = pd.DataFrame(scaled_arr, index=feat.index, columns=scale_cols)

    scaled_df.reset_index().to_csv(
        PROCESSED / "customer_features_scaled.csv", index=False
    )
    if verbose:
        print(f"  Saved customer_features_scaled.csv ({scaled_df.shape[0]:,} rows x {scaled_df.shape[1]} cols)")
        print(f"\nFeature groups:")
        print(f"  Demographic  : age, log_income, credit_score, tenure_days, segment_rank")
        print(f"  RFM          : recency_days, freq_12m, total_revenue (log)")
        print(f"  Product      : n_active_products, n_product_categories, total_product_value (log)")
        print(f"  Engagement   : response_rate, channels_used, campaigns_touched")
        print(f"  Binary flags : has_credit_card … has_home_loan, is_multi_product")

    return feat


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    df = build_feature_matrix(verbose=True)
    print(f"\nFeature matrix shape : {df.shape}")
    print(f"Missing values       : {df.isnull().sum().sum()}")
    print("\nSample statistics:")
    print(
        df[["age","annual_income","credit_score","recency_days",
            "total_revenue","n_active_products"]].describe().round(1).to_string()
    )
