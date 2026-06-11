"""
ML Dataset Preprocessor — Conversion Propensity Model
======================================================
Builds an interaction-level feature matrix suitable for training
binary classifiers that predict whether a customer will convert
on a given campaign interaction.

Target variable
---------------
  converted = 1  (interaction_outcome == 'Converted')
  converted = 0  (all other outcomes)

Class ratio
-----------
  ~19% positive — mild imbalance handled via class_weight / scale_pos_weight.

Output (data/processed/)
------------------------
  ml_dataset.csv          — full labelled dataset (one row per interaction)
  ml_train.csv            — 80% stratified training split
  ml_test.csv             — 20% holdout test split
  ml_feature_names.txt    — ordered list of all model input features

Run standalone
--------------
  python scripts/ml/preprocess.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve()
while ROOT.name != "Customer-Campaign-Analytics-Platform" and ROOT != ROOT.parent:
    ROOT = ROOT.parent

RAW       = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
TEST_SIZE    = 0.20

# ── Load raw tables ──────────────────────────────────────────────────────────
def _load() -> dict:
    t = {}
    t["interactions"] = pd.read_csv(
        RAW / "campaign_interactions.csv",
        parse_dates=["interaction_date", "response_date"],
    )
    t["customers"] = pd.read_csv(
        RAW / "customers.csv",
        parse_dates=["date_of_birth", "acquisition_date"],
    )
    t["campaigns"] = pd.read_csv(
        RAW / "campaigns.csv",
        parse_dates=["start_date", "end_date"],
    )
    t["channels"]  = pd.read_csv(RAW / "campaign_channels.csv")
    t["products"]  = pd.read_csv(RAW / "products.csv")
    t["cust_prods"]= pd.read_csv(
        RAW / "customer_products.csv",
        parse_dates=["acquisition_date"],
    )
    return t


# ── Feature builders ─────────────────────────────────────────────────────────

def _customer_aggregate_stats(interactions: pd.DataFrame) -> pd.DataFrame:
    """
    Historical engagement statistics per customer.

    Note: computed over the entire dataset rather than as a true lookback
    window. In production these would be derived from a pre-interaction
    feature store. Here they serve as a stable proxy for customer behaviour.
    """
    grp = interactions.groupby("customer_id")
    total = grp["interaction_id"].count().rename("hist_interactions")
    cvr   = (
        grp["interaction_outcome"]
        .apply(lambda x: (x == "Converted").sum() / len(x))
        .rename("hist_cvr")
    )
    response_rate = (
        grp["interaction_outcome"]
        .apply(lambda x: (~x.isin(["No Response", "Pending"])).sum() / len(x))
        .rename("hist_response_rate")
    )
    return pd.concat([total, cvr, response_rate], axis=1).reset_index()


def _product_holding_flags(cust_prods: pd.DataFrame,
                            products: pd.DataFrame) -> pd.DataFrame:
    """
    Set of product categories each customer currently holds (Active only).
    Used to derive the is_existing_holder flag.
    """
    prod_cat = dict(zip(products["product_id"], products["product_category"]))
    active   = cust_prods[cust_prods["status"] == "Active"].copy()
    active["product_category"] = active["product_id"].map(prod_cat)
    held = (
        active
        .groupby("customer_id")["product_category"]
        .apply(set)
        .rename("held_categories")
        .reset_index()
    )
    return held


def build_ml_dataset(verbose: bool = True) -> pd.DataFrame:
    """
    Build and return the full interaction-level ML dataset.
    Saves ml_dataset.csv, ml_train.csv, ml_test.csv to data/processed/.

    Returns
    -------
    pd.DataFrame  (full dataset, before train/test split)
    """
    if verbose:
        print("Loading raw tables ...")
    t = _load()

    ch_map   = dict(zip(t["channels"]["channel_id"],   t["channels"]["channel_name"]))
    prod_cat = dict(zip(t["products"]["product_id"],   t["products"]["product_category"]))

    # ── Base: interactions ────────────────────────────────────────────────────
    df = t["interactions"].copy()
    df["channel_name"] = df["channel_id"].map(ch_map)

    # Target
    df["converted"] = (df["interaction_outcome"] == "Converted").astype(int)

    # ── Join: campaigns ───────────────────────────────────────────────────────
    camp = t["campaigns"][
        ["campaign_id","campaign_type","product_id","start_date","end_date",
         "total_budget","contacts_target","ab_test_enabled","target_segment"]
    ].copy()
    camp["product_category"]      = camp["product_id"].map(prod_cat)
    camp["campaign_duration_days"]= (camp["end_date"] - camp["start_date"]).dt.days
    camp["budget_per_contact"]    = camp["total_budget"] / camp["contacts_target"].clip(lower=1)
    df = df.merge(
        camp[["campaign_id","campaign_type","product_category",
               "campaign_duration_days","budget_per_contact",
               "ab_test_enabled","start_date","target_segment"]],
        on="campaign_id", how="left",
    )
    df["days_into_campaign"] = (
        df["interaction_date"] - df["start_date"]
    ).dt.days.clip(lower=0)

    # ── Join: customers ───────────────────────────────────────────────────────
    TODAY = pd.Timestamp("today").normalize()
    cust  = t["customers"][
        ["customer_id","date_of_birth","annual_income","credit_score",
         "customer_segment","employment_status","number_of_products",
         "acquisition_date","region"]
    ].copy()
    cust["age"]          = ((TODAY - cust["date_of_birth"]).dt.days / 365.25).astype(int)
    cust["log_income"]   = np.log1p(cust["annual_income"])
    cust["tenure_days"]  = (TODAY - cust["acquisition_date"]).dt.days

    df = df.merge(
        cust[["customer_id","age","log_income","credit_score","tenure_days",
               "customer_segment","employment_status","number_of_products"]],
        on="customer_id", how="left",
    )

    # Tenure at time of interaction (more accurate than overall tenure)
    df["tenure_at_interaction"] = (
        df["interaction_date"] - t["customers"].set_index("customer_id")
        .loc[df["customer_id"].values, "acquisition_date"].values
    ).dt.days.clip(lower=0)

    # ── Customer aggregate stats (historical behaviour) ───────────────────────
    if verbose:
        print("Computing customer aggregate features ...")
    cust_stats = _customer_aggregate_stats(df)
    df = df.merge(cust_stats, on="customer_id", how="left")

    # ── Product holding flag ──────────────────────────────────────────────────
    held = _product_holding_flags(t["cust_prods"], t["products"])
    df   = df.merge(held, on="customer_id", how="left")
    df["held_categories"] = df["held_categories"].fillna("").apply(
        lambda x: x if isinstance(x, set) else set()
    )
    df["is_existing_holder"] = df.apply(
        lambda r: int(r["product_category"] in r["held_categories"])
        if isinstance(r["held_categories"], set) else 0,
        axis=1,
    )

    # ── A/B variant feature ───────────────────────────────────────────────────
    df["ab_variant_B"]    = (df["ab_variant"] == "B").astype(int)
    df["ab_test_enabled"] = df["ab_test_enabled"].astype(int)

    # ── Segment is target segment flag ────────────────────────────────────────
    df["is_target_segment"] = (
        df["customer_segment"] == df["target_segment"]
    ).astype(int)

    # ── Final column selection ────────────────────────────────────────────────
    NUMERIC_FEATURES = [
        "age", "log_income", "credit_score", "tenure_at_interaction",
        "number_of_products", "campaign_duration_days", "budget_per_contact",
        "days_into_campaign", "hist_interactions", "hist_cvr",
        "hist_response_rate",
    ]
    CATEGORICAL_FEATURES = [
        "customer_segment", "employment_status", "channel_name",
        "campaign_type", "product_category", "interaction_type",
    ]
    BINARY_FEATURES = [
        "ab_variant_B", "ab_test_enabled",
        "is_existing_holder", "is_target_segment",
    ]
    ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES + BINARY_FEATURES

    out = df[["interaction_id", "customer_id", "campaign_id"] +
             ALL_FEATURES + ["converted"]].copy()

    # Sanity: no NaN in final dataset
    null_counts = out[ALL_FEATURES].isnull().sum()
    if null_counts.any():
        if verbose:
            print(f"  Filling NaN in: {null_counts[null_counts > 0].index.tolist()}")
        out[NUMERIC_FEATURES]     = out[NUMERIC_FEATURES].fillna(out[NUMERIC_FEATURES].median())
        out[CATEGORICAL_FEATURES] = out[CATEGORICAL_FEATURES].fillna("Unknown")
        out[BINARY_FEATURES]      = out[BINARY_FEATURES].fillna(0)

    # Save full dataset
    out.to_csv(PROCESSED / "ml_dataset.csv", index=False)
    if verbose:
        pos = out["converted"].mean() * 100
        print(f"  Saved ml_dataset.csv — {len(out):,} rows, {pos:.1f}% positive")

    # Train / test split (stratified on target)
    X  = out[ALL_FEATURES]
    y  = out["converted"]
    ids = out[["interaction_id","customer_id","campaign_id"]]

    X_train, X_test, y_train, y_test, id_train, id_test = train_test_split(
        X, y, ids,
        test_size=TEST_SIZE,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    train_df = pd.concat([id_train.reset_index(drop=True),
                          X_train.reset_index(drop=True),
                          y_train.reset_index(drop=True)], axis=1)
    test_df  = pd.concat([id_test.reset_index(drop=True),
                          X_test.reset_index(drop=True),
                          y_test.reset_index(drop=True)], axis=1)

    train_df.to_csv(PROCESSED / "ml_train.csv", index=False)
    test_df.to_csv( PROCESSED / "ml_test.csv",  index=False)

    with open(PROCESSED / "ml_feature_names.txt", "w") as f:
        f.write("\n".join(ALL_FEATURES))

    if verbose:
        print(f"  Saved ml_train.csv — {len(train_df):,} rows")
        print(f"  Saved ml_test.csv  — {len(test_df):,} rows")
        print(f"\nFeature breakdown:")
        print(f"  Numeric      ({len(NUMERIC_FEATURES)}): {NUMERIC_FEATURES}")
        print(f"  Categorical  ({len(CATEGORICAL_FEATURES)}): {CATEGORICAL_FEATURES}")
        print(f"  Binary       ({len(BINARY_FEATURES)}): {BINARY_FEATURES}")

    return out


# ── Metadata for consumers ────────────────────────────────────────────────────
NUMERIC_FEATURES = [
    "age", "log_income", "credit_score", "tenure_at_interaction",
    "number_of_products", "campaign_duration_days", "budget_per_contact",
    "days_into_campaign", "hist_interactions", "hist_cvr",
    "hist_response_rate",
]
CATEGORICAL_FEATURES = [
    "customer_segment", "employment_status", "channel_name",
    "campaign_type", "product_category", "interaction_type",
]
BINARY_FEATURES = [
    "ab_variant_B", "ab_test_enabled",
    "is_existing_holder", "is_target_segment",
]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES + BINARY_FEATURES


if __name__ == "__main__":
    df = build_ml_dataset(verbose=True)
    print(f"\nDataset shape : {df.shape}")
    print(f"Class balance : {df['converted'].value_counts().to_dict()}")
