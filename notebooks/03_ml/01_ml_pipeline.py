# %% [markdown]
# # Notebook — Predictive Analytics: Conversion Propensity Model
# **Customer Campaign Analytics Platform | CCAP**
#
# **Business objective:**
# HSBC runs 50 campaigns across 100,000 interactions per cycle.
# Contacting every customer costs £8–£25 per contact. By scoring each
# customer's probability of converting *before* running the campaign,
# the marketing team can:
#   - Suppress low-propensity contacts (cut wasted spend by ~40%)
#   - Focus Relationship Manager time on high-propensity Premier customers
#   - Set channel and product by predicted segment behaviour
#
# **Models built:**
#   1. Logistic Regression  — interpretable baseline
#   2. Random Forest        — non-linear ensemble, robust to outliers
#   3. XGBoost              — gradient boosted trees, typically best performer
#
# **Evaluation metrics:**
#   Accuracy, Precision, Recall, F1, ROC-AUC
#   (ROC-AUC is the primary metric for imbalanced binary classification)

# %%
import sys
from pathlib import Path

ROOT = Path().resolve()
while ROOT.name != "Customer-Campaign-Analytics-Platform" and ROOT != ROOT.parent:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import warnings
warnings.filterwarnings("ignore")

from sklearn.pipeline         import Pipeline
from sklearn.compose          import ColumnTransformer
from sklearn.preprocessing    import StandardScaler, OneHotEncoder, label_binarize
from sklearn.linear_model     import LogisticRegression
from sklearn.ensemble         import RandomForestClassifier
from sklearn.model_selection  import (RandomizedSearchCV, GridSearchCV,
                                      StratifiedKFold, cross_val_score)
from sklearn.metrics          import (accuracy_score, precision_score, recall_score,
                                      f1_score, roc_auc_score, roc_curve,
                                      precision_recall_curve, confusion_matrix,
                                      average_precision_score, classification_report)
from xgboost import XGBClassifier
import joblib

from scripts.ml.preprocess import (build_ml_dataset,
                                    NUMERIC_FEATURES, CATEGORICAL_FEATURES,
                                    BINARY_FEATURES, ALL_FEATURES)

PROCESSED = ROOT / "data" / "processed"
EXPORTS   = ROOT / "reports" / "exports"
MODELS    = ROOT / "ml_models"
MODELS.mkdir(parents=True, exist_ok=True)
EXPORTS.mkdir(parents=True, exist_ok=True)

C = {"navy":"#1A3C5E","teal":"#2E86AB","red":"#E84855",
     "amber":"#F4A261","green":"#52B788","grey":"#6C757D","light":"#E9ECEF"}
MODEL_COLORS = {"Logistic Regression": C["teal"],
                "Random Forest":       C["green"],
                "XGBoost":             C["amber"]}

plt.rcParams.update({
    "figure.dpi":120,"figure.facecolor":"white","axes.facecolor":"white",
    "axes.spines.top":False,"axes.spines.right":False,
    "axes.titlesize":12,"axes.titleweight":"bold","font.family":"sans-serif",
})

RANDOM_STATE = 42
CV_FOLDS     = 5

# %% [markdown]
# ## 1 — Dataset Construction

# %%
print("Building ML dataset ...")
ml_df = build_ml_dataset(verbose=True)

train_df = pd.read_csv(PROCESSED / "ml_train.csv")
test_df  = pd.read_csv(PROCESSED / "ml_test.csv")

X_train = train_df[ALL_FEATURES]
y_train = train_df["converted"]
X_test  = test_df[ALL_FEATURES]
y_test  = test_df["converted"]

n_pos  = y_train.sum()
n_neg  = len(y_train) - n_pos
scale_pos_weight = round(n_neg / n_pos, 2)

print(f"\nTrain : {len(X_train):,} rows  |  Positive: {n_pos:,} ({n_pos/len(y_train)*100:.1f}%)")
print(f"Test  : {len(X_test):,} rows  |  Positive: {y_test.sum():,} ({y_test.mean()*100:.1f}%)")
print(f"XGBoost scale_pos_weight: {scale_pos_weight}")

# %% [markdown]
# ## 2 — Class Balance and Feature Distribution

# %%
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
fig.suptitle("Dataset Overview", fontsize=13, fontweight="bold")

# ── Class balance ─────────────────────────────────────────────────────────────
ax = axes[0]
counts = y_train.value_counts().sort_index()
labels = ["Not Converted\n(0)", "Converted\n(1)"]
colors = [C["grey"], C["teal"]]
wedges, texts, autotexts = ax.pie(
    counts, labels=labels, colors=colors,
    autopct="%1.1f%%", startangle=90,
    wedgeprops=dict(edgecolor="white", linewidth=2),
)
for at in autotexts:
    at.set_fontsize(11)
    at.set_fontweight("bold")
ax.set_title("Class Balance (Training Set)")

# ── CVR by customer segment ───────────────────────────────────────────────────
ax = axes[1]
seg_cvr = (
    train_df.groupby("customer_segment")["converted"]
    .mean() * 100
).sort_values(ascending=False)
colors_seg = [C["navy"], C["teal"], C["green"], C["amber"]]
bars = ax.bar(seg_cvr.index, seg_cvr.values,
              color=colors_seg[:len(seg_cvr)], edgecolor="white")
ax.set_title("CVR by Customer Segment (Train)")
ax.set_ylabel("CVR (%)")
ax.tick_params(axis="x", rotation=20)
for bar, v in zip(bars, seg_cvr.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
            f"{v:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

# ── CVR by channel ────────────────────────────────────────────────────────────
ax = axes[2]
ch_cvr = (
    train_df.groupby("channel_name")["converted"]
    .mean() * 100
).sort_values(ascending=False)
bars = ax.bar(ch_cvr.index, ch_cvr.values,
              color=[C["navy"],C["teal"],C["green"],C["amber"],C["red"]],
              edgecolor="white")
ax.set_title("CVR by Channel (Train)")
ax.set_ylabel("CVR (%)")
ax.tick_params(axis="x", rotation=20)
for bar, v in zip(bars, ch_cvr.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
            f"{v:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

plt.tight_layout()
plt.savefig(EXPORTS / "ml_dataset_overview.png", bbox_inches="tight", dpi=150)
plt.show()

# %% [markdown]
# ## 3 — Preprocessing Pipeline

# %%
# ColumnTransformer applies different transformations to different feature types
preprocessor = ColumnTransformer(
    transformers=[
        ("num",  StandardScaler(),                           NUMERIC_FEATURES),
        ("cat",  OneHotEncoder(handle_unknown="ignore",
                               sparse_output=False,
                               drop="first"),               CATEGORICAL_FEATURES),
        ("bin",  "passthrough",                              BINARY_FEATURES),
    ],
    remainder="drop",
    verbose_feature_names_out=False,
)

# Fit on training data only to prevent data leakage
preprocessor.fit(X_train)

# Extract OHE feature names for later interpretation
ohe_names = (
    preprocessor
    .named_transformers_["cat"]
    .get_feature_names_out(CATEGORICAL_FEATURES)
    .tolist()
)
FEATURE_NAMES_OUT = NUMERIC_FEATURES + ohe_names + BINARY_FEATURES

print(f"Preprocessing pipeline built.")
print(f"  Numeric features    : {len(NUMERIC_FEATURES)}")
print(f"  OHE output features : {len(ohe_names)}")
print(f"  Binary (passthrough): {len(BINARY_FEATURES)}")
print(f"  Total features in X : {len(FEATURE_NAMES_OUT)}")

# %% [markdown]
# ## 4 — Model 1: Logistic Regression
#
# **Why LR first?**
# Logistic Regression is the banking industry's preferred explainability baseline.
# It produces probability scores directly, supports regulatory audit trails
# (model coefficients are interpretable), and runs instantly on 100K rows.

# %%
print("=" * 55)
print("  MODEL 1 — LOGISTIC REGRESSION")
print("=" * 55)

lr_pipe = Pipeline([
    ("prep", preprocessor),
    ("clf",  LogisticRegression(
        max_iter=1000,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        solver="liblinear",
    )),
])

lr_param_grid = {
    "clf__C":       [0.001, 0.01, 0.1, 1, 10, 100],
    "clf__penalty": ["l1", "l2"],
}

lr_cv = GridSearchCV(
    lr_pipe,
    param_grid  = lr_param_grid,
    cv          = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True,
                                  random_state=RANDOM_STATE),
    scoring     = "roc_auc",
    n_jobs      = -1,
    verbose     = 1,
)
lr_cv.fit(X_train, y_train)

print(f"\nBest params  : {lr_cv.best_params_}")
print(f"Best CV AUC  : {lr_cv.best_score_:.4f}")

lr_best = lr_cv.best_estimator_

# %% [markdown]
# ## 5 — Model 2: Random Forest
#
# **Why Random Forest?**
# Non-linear ensembles capture interaction effects between customer segment,
# product, and channel that LR misses. They provide feature importance via
# Mean Decrease in Impurity (MDI), and are robust to outliers and missing values.

# %%
print("=" * 55)
print("  MODEL 2 — RANDOM FOREST")
print("=" * 55)

rf_pipe = Pipeline([
    ("prep", preprocessor),
    ("clf",  RandomForestClassifier(
        random_state  = RANDOM_STATE,
        class_weight  = "balanced",
        n_jobs        = -1,
    )),
])

rf_param_dist = {
    "clf__n_estimators":    [100, 200, 300],
    "clf__max_depth":       [5, 10, 15, None],
    "clf__min_samples_leaf":[1, 5, 10, 20],
    "clf__max_features":    ["sqrt", "log2", 0.3],
}

rf_cv = RandomizedSearchCV(
    rf_pipe,
    param_distributions = rf_param_dist,
    n_iter              = 20,
    cv                  = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True,
                                          random_state=RANDOM_STATE),
    scoring             = "roc_auc",
    n_jobs              = -1,
    random_state        = RANDOM_STATE,
    verbose             = 1,
)
rf_cv.fit(X_train, y_train)

print(f"\nBest params  : {rf_cv.best_params_}")
print(f"Best CV AUC  : {rf_cv.best_score_:.4f}")

rf_best = rf_cv.best_estimator_

# %% [markdown]
# ## 6 — Model 3: XGBoost
#
# **Why XGBoost?**
# Gradient boosted trees consistently outperform random forests on tabular
# banking data. scale_pos_weight explicitly handles the 80:20 class imbalance.
# SHAP values (available from the XGBoost API) make it interpretable
# enough to satisfy internal model governance requirements at most UK banks.

# %%
print("=" * 55)
print("  MODEL 3 — XGBOOST")
print("=" * 55)

xgb_pipe = Pipeline([
    ("prep", preprocessor),
    ("clf",  XGBClassifier(
        objective        = "binary:logistic",
        eval_metric      = "auc",
        scale_pos_weight = scale_pos_weight,
        random_state     = RANDOM_STATE,
        n_jobs           = -1,
        verbosity        = 0,
        use_label_encoder= False,
    )),
])

xgb_param_dist = {
    "clf__n_estimators":     [100, 200, 300, 500],
    "clf__learning_rate":    [0.01, 0.05, 0.1, 0.2],
    "clf__max_depth":        [3, 5, 7],
    "clf__subsample":        [0.7, 0.8, 1.0],
    "clf__colsample_bytree": [0.6, 0.8, 1.0],
    "clf__min_child_weight": [1, 5, 10],
    "clf__gamma":            [0, 0.1, 0.3],
}

xgb_cv = RandomizedSearchCV(
    xgb_pipe,
    param_distributions = xgb_param_dist,
    n_iter              = 25,
    cv                  = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True,
                                          random_state=RANDOM_STATE),
    scoring             = "roc_auc",
    n_jobs              = -1,
    random_state        = RANDOM_STATE,
    verbose             = 1,
)
xgb_cv.fit(X_train, y_train)

print(f"\nBest params  : {xgb_cv.best_params_}")
print(f"Best CV AUC  : {xgb_cv.best_score_:.4f}")

xgb_best = xgb_cv.best_estimator_

# %% [markdown]
# ## 7 — Evaluation: Metrics Table

# %%
def evaluate_model(name: str, pipe, X_test, y_test, threshold: float = 0.5) -> dict:
    y_prob = pipe.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= threshold).astype(int)
    return {
        "Model":     name,
        "Accuracy":  round(accuracy_score(y_test, y_pred),       4),
        "Precision": round(precision_score(y_test, y_pred,
                                           zero_division=0),     4),
        "Recall":    round(recall_score(y_test, y_pred),         4),
        "F1":        round(f1_score(y_test, y_pred),             4),
        "ROC-AUC":   round(roc_auc_score(y_test, y_prob),        4),
        "Avg Prec":  round(average_precision_score(y_test,y_prob),4),
        "_proba":    y_prob,
        "_pred":     y_pred,
    }

results = [
    evaluate_model("Logistic Regression", lr_best,  X_test, y_test),
    evaluate_model("Random Forest",        rf_best,  X_test, y_test),
    evaluate_model("XGBoost",              xgb_best, X_test, y_test),
]

metrics_df = pd.DataFrame(results).drop(columns=["_proba","_pred"])
metrics_df = metrics_df.set_index("Model")

print("\n" + "=" * 65)
print("  MODEL COMPARISON — TEST SET METRICS")
print("=" * 65)
print(metrics_df.to_string())
print("=" * 65)

# Highlight best per column
best_model = metrics_df["ROC-AUC"].idxmax()
print(f"\n  Best model by ROC-AUC: {best_model}")
print(f"  ROC-AUC:   {metrics_df.loc[best_model,'ROC-AUC']:.4f}")
print(f"  Precision: {metrics_df.loc[best_model,'Precision']:.4f}")
print(f"  Recall:    {metrics_df.loc[best_model,'Recall']:.4f}")
print(f"  F1:        {metrics_df.loc[best_model,'F1']:.4f}")

# %% [markdown]
# ## 8 — Metrics Visualisation Dashboard

# %%
fig, axes = plt.subplots(2, 3, figsize=(20, 12))
fig.suptitle("Model Evaluation Dashboard — Test Set Performance",
             fontsize=14, fontweight="bold", y=1.01)

metric_list = ["Accuracy","Precision","Recall","F1","ROC-AUC","Avg Prec"]
model_names = metrics_df.index.tolist()
x           = np.arange(len(model_names))
width       = 0.55

for ax, metric in zip(axes.flat, metric_list):
    vals   = metrics_df[metric].values
    colors = [MODEL_COLORS[m] for m in model_names]
    bars   = ax.bar(model_names, vals, color=colors,
                    edgecolor="white", linewidth=0.5, width=width)

    # Threshold line for context
    if metric in ("Accuracy","Precision","Recall","F1"):
        ax.axhline(0.5, color=C["grey"], linestyle="--",
                   linewidth=1, alpha=0.6, label="0.5 baseline")
    if metric in ("ROC-AUC","Avg Prec"):
        ax.axhline(0.5, color=C["red"], linestyle="--",
                   linewidth=1, alpha=0.6, label="Random (0.5)")

    ax.set_title(metric)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Score")
    ax.set_xticklabels(model_names, rotation=15, ha="right", fontsize=9)
    ax.legend(fontsize=8)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.012,
                f"{v:.4f}", ha="center", va="bottom",
                fontsize=10, fontweight="bold",
                color=MODEL_COLORS[model_names[list(vals).index(v)]])

plt.tight_layout()
plt.savefig(EXPORTS / "ml_metrics_dashboard.png", bbox_inches="tight", dpi=150)
plt.show()

# %% [markdown]
# ## 9 — ROC Curves and Precision-Recall Curves

# %%
fig, axes = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle("ROC & Precision-Recall Curves — All Models",
             fontsize=13, fontweight="bold")

models_dict = {
    "Logistic Regression": (lr_best,  results[0]["_proba"]),
    "Random Forest":       (rf_best,  results[1]["_proba"]),
    "XGBoost":             (xgb_best, results[2]["_proba"]),
}

# ── ROC Curves ───────────────────────────────────────────────────────────────
ax = axes[0]
ax.plot([0, 1], [0, 1], linestyle="--", color=C["grey"],
        linewidth=1, label="Random (AUC=0.50)")
for name, (_, proba) in models_dict.items():
    fpr, tpr, _ = roc_curve(y_test, proba)
    auc         = metrics_df.loc[name, "ROC-AUC"]
    ax.plot(fpr, tpr, color=MODEL_COLORS[name], linewidth=2.5,
            label=f"{name} (AUC={auc:.4f})")

ax.set_title("ROC Curve")
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.legend(fontsize=9, loc="lower right")
ax.set_xlim(-0.01, 1.01)
ax.set_ylim(-0.01, 1.05)
ax.fill_between([0,1], [0,1], alpha=0.05, color=C["grey"])

# ── Precision-Recall Curves ──────────────────────────────────────────────────
ax = axes[1]
baseline_pr = y_test.mean()
ax.axhline(baseline_pr, linestyle="--", color=C["grey"],
           linewidth=1, label=f"Baseline P={baseline_pr:.2f}")
for name, (_, proba) in models_dict.items():
    prec, rec, _ = precision_recall_curve(y_test, proba)
    ap           = metrics_df.loc[name, "Avg Prec"]
    ax.plot(rec, prec, color=MODEL_COLORS[name], linewidth=2.5,
            label=f"{name} (AP={ap:.4f})")

ax.set_title("Precision-Recall Curve")
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.legend(fontsize=9, loc="upper right")
ax.set_xlim(-0.01, 1.01)
ax.set_ylim(0, 1.05)

plt.tight_layout()
plt.savefig(EXPORTS / "ml_roc_pr_curves.png", bbox_inches="tight", dpi=150)
plt.show()

# %% [markdown]
# ## 10 — Confusion Matrices

# %%
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
fig.suptitle("Confusion Matrices — Test Set (Threshold = 0.50)",
             fontsize=13, fontweight="bold")

for ax, (name, res) in zip(axes, zip(model_names, results)):
    cm = confusion_matrix(y_test, res["_pred"])
    cm_pct = cm.astype(float) / cm.sum() * 100

    annot = np.array([[f"{v:,}\n({p:.1f}%)"
                       for v, p in zip(row_v, row_p)]
                      for row_v, row_p in zip(cm, cm_pct)])

    sns.heatmap(cm, ax=ax, annot=annot, fmt="", cmap="Blues",
                linewidths=1, linecolor="white",
                xticklabels=["Pred: 0","Pred: 1"],
                yticklabels=["True: 0","True: 1"],
                cbar=False, annot_kws={"size": 10})

    tn, fp, fn, tp = cm.ravel()
    ax.set_title(f"{name}\nTP={tp:,}  FP={fp:,}  FN={fn:,}  TN={tn:,}",
                 fontsize=10)

plt.tight_layout()
plt.savefig(EXPORTS / "ml_confusion_matrices.png", bbox_inches="tight", dpi=150)
plt.show()

# %% [markdown]
# ## 11 — Feature Importance (All Three Models)

# %%
fig, axes = plt.subplots(1, 3, figsize=(24, 9))
fig.suptitle("Feature Importance — Top 20 Features per Model",
             fontsize=14, fontweight="bold")

TOP_N = 20

# ── LR: Absolute Coefficients ────────────────────────────────────────────────
ax = axes[0]
lr_clf    = lr_best.named_steps["clf"]
lr_coefs  = pd.Series(np.abs(lr_clf.coef_[0]),
                       index=FEATURE_NAMES_OUT).sort_values(ascending=False)
top_lr    = lr_coefs.head(TOP_N)
colors_lr = [C["teal"] if c > top_lr.median() else C["light"]
             for c in top_lr.values]
ax.barh(top_lr.index[::-1], top_lr.values[::-1],
        color=colors_lr[::-1], edgecolor="white")
ax.set_title("Logistic Regression\n|Coefficients| (Top 20)")
ax.set_xlabel("Absolute Coefficient")
ax.axvline(top_lr.median(), color=C["grey"], linestyle="--",
           linewidth=1, alpha=0.7)

# ── RF: Mean Decrease Impurity ──────────────────────────────────────────────
ax = axes[1]
rf_clf   = rf_best.named_steps["clf"]
rf_imp   = pd.Series(rf_clf.feature_importances_,
                      index=FEATURE_NAMES_OUT).sort_values(ascending=False)
top_rf   = rf_imp.head(TOP_N)
colors_rf = [C["green"] if v > top_rf.median() else C["light"]
              for v in top_rf.values]
ax.barh(top_rf.index[::-1], top_rf.values[::-1],
        color=colors_rf[::-1], edgecolor="white")
ax.set_title("Random Forest\nMDI Importance (Top 20)")
ax.set_xlabel("Mean Decrease in Impurity")
ax.axvline(top_rf.median(), color=C["grey"], linestyle="--",
           linewidth=1, alpha=0.7)

# ── XGBoost: Gain ────────────────────────────────────────────────────────────
ax = axes[2]
xgb_clf  = xgb_best.named_steps["clf"]
xgb_imp  = pd.Series(
    xgb_clf.get_booster().get_score(importance_type="gain"),
).rename(index=lambda k: FEATURE_NAMES_OUT[int(k[1:])]
         if k.startswith("f") and k[1:].isdigit()
         else k)
# Fill any missing features with 0
xgb_full = pd.Series(0.0, index=FEATURE_NAMES_OUT)
for k, v in xgb_imp.items():
    if k in xgb_full.index:
        xgb_full[k] = v
xgb_full = xgb_full.sort_values(ascending=False)
top_xgb  = xgb_full.head(TOP_N)

colors_xgb = [C["amber"] if v > top_xgb.median() else C["light"]
               for v in top_xgb.values]
ax.barh(top_xgb.index[::-1], top_xgb.values[::-1],
        color=colors_xgb[::-1], edgecolor="white")
ax.set_title("XGBoost\nGain Importance (Top 20)")
ax.set_xlabel("Total Gain")
ax.axvline(top_xgb.median(), color=C["grey"], linestyle="--",
           linewidth=1, alpha=0.7)

plt.tight_layout()
plt.savefig(EXPORTS / "ml_feature_importance.png", bbox_inches="tight", dpi=150)
plt.show()

# %% [markdown]
# ## 12 — Feature Importance Agreement (Top Features Across Models)

# %%
TOP_AGR = 15
lr_rank  = pd.Series(range(1, len(lr_coefs) +1), index=lr_coefs.index)
rf_rank  = pd.Series(range(1, len(rf_imp)   +1), index=rf_imp.index)
xgb_rank = pd.Series(range(1, len(xgb_full) +1), index=xgb_full.index)

agree = pd.DataFrame({
    "LR Rank":   lr_rank,
    "RF Rank":   rf_rank,
    "XGB Rank":  xgb_rank,
}).dropna()
agree["Mean Rank"] = agree.mean(axis=1)
agree = agree.sort_values("Mean Rank").head(TOP_AGR)

fig, ax = plt.subplots(figsize=(12, 6))
x   = np.arange(len(agree))
w   = 0.28
ax.bar(x - w, agree["LR Rank"],  width=w, label="LR Rank",  color=C["teal"],  edgecolor="white")
ax.bar(x,     agree["RF Rank"],  width=w, label="RF Rank",  color=C["green"], edgecolor="white")
ax.bar(x + w, agree["XGB Rank"], width=w, label="XGB Rank", color=C["amber"], edgecolor="white")
ax.set_xticks(x)
ax.set_xticklabels(agree.index, rotation=35, ha="right", fontsize=9)
ax.set_title(f"Top {TOP_AGR} Features by Mean Rank Across All 3 Models\n"
             "(lower bar = more important)")
ax.set_ylabel("Feature Rank (lower = more important)")
ax.invert_yaxis()
ax.legend(fontsize=10)
ax.axhline(5, color=C["grey"], linestyle="--", linewidth=1, alpha=0.6,
           label="Top-5 threshold")
plt.tight_layout()
plt.savefig(EXPORTS / "ml_feature_agreement.png", bbox_inches="tight", dpi=150)
plt.show()

print("\nTop 10 features agreed by all 3 models:")
print(agree["Mean Rank"].head(10).round(1).to_string())

# %% [markdown]
# ## 13 — Propensity Threshold Optimisation
#
# The default threshold of 0.50 isn't always optimal in banking.
# A lower threshold (e.g. 0.35) increases recall — catches more converters
# at the cost of more false positives (wasted contacts).
# The business team must decide based on:
#   - Cost per contact (£8–£25)
#   - Revenue per conversion (£120–£6,000 depending on product)

# %%
best_proba = results[2]["_proba"]   # XGBoost (best AUC)

thresholds   = np.arange(0.1, 0.9, 0.01)
prec_list, rec_list, f1_list, acc_list = [], [], [], []

for t in thresholds:
    y_pred_t = (best_proba >= t).astype(int)
    prec_list.append(precision_score(y_test, y_pred_t, zero_division=0))
    rec_list.append(recall_score(y_test, y_pred_t))
    f1_list.append(f1_score(y_test, y_pred_t, zero_division=0))
    acc_list.append(accuracy_score(y_test, y_pred_t))

fig, axes = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle("XGBoost — Propensity Threshold Analysis",
             fontsize=13, fontweight="bold")

# ── Precision / Recall / F1 vs threshold ─────────────────────────────────────
ax = axes[0]
ax.plot(thresholds, prec_list, color=C["teal"],  linewidth=2, label="Precision")
ax.plot(thresholds, rec_list,  color=C["red"],   linewidth=2, label="Recall")
ax.plot(thresholds, f1_list,   color=C["amber"], linewidth=2, label="F1")
ax.axvline(0.50, color=C["grey"], linestyle="--",
           linewidth=1.5, label="Default 0.50")

optimal_f1_idx = np.argmax(f1_list)
opt_threshold  = thresholds[optimal_f1_idx]
ax.axvline(opt_threshold, color=C["navy"], linestyle="-.",
           linewidth=2, label=f"Optimal F1 threshold: {opt_threshold:.2f}")
ax.set_title("Precision / Recall / F1 vs Threshold")
ax.set_xlabel("Threshold")
ax.set_ylabel("Score")
ax.legend(fontsize=9)
ax.set_ylim(0, 1.05)

# ── Contact volume vs conversion capture ─────────────────────────────────────
ax = axes[1]
contact_pct  = [(best_proba >= t).mean() * 100 for t in thresholds]
capture_pct  = [
    ((best_proba >= t) & (y_test == 1)).sum() / y_test.sum() * 100
    for t in thresholds
]
ax.plot(thresholds, contact_pct, color=C["grey"],  linewidth=2,
        label="% contacts sent")
ax.plot(thresholds, capture_pct, color=C["green"], linewidth=2,
        label="% converters captured")

ax.axvline(0.35, color=C["teal"], linestyle="--",
           linewidth=1.5, label="Threshold 0.35 (high recall)")
ax.axvline(0.50, color=C["grey"], linestyle="--",
           linewidth=1.5, label="Threshold 0.50 (balanced)")
ax.axvline(0.65, color=C["navy"], linestyle="--",
           linewidth=1.5, label="Threshold 0.65 (high precision)")
ax.set_title("Contact Volume vs Converter Capture Rate")
ax.set_xlabel("Threshold")
ax.set_ylabel("% of Total")
ax.legend(fontsize=9)
ax.set_ylim(0, 105)

plt.tight_layout()
plt.savefig(EXPORTS / "ml_threshold_analysis.png", bbox_inches="tight", dpi=150)
plt.show()

print(f"\nOptimal F1 threshold: {opt_threshold:.2f}")
print(f"  At threshold {opt_threshold:.2f}:")
y_opt = (best_proba >= opt_threshold).astype(int)
print(f"    Precision : {precision_score(y_test, y_opt):.4f}")
print(f"    Recall    : {recall_score(y_test, y_opt):.4f}")
print(f"    F1        : {f1_score(y_test, y_opt):.4f}")
print(f"    Contacts  : {y_opt.mean()*100:.1f}% of test set contacted")

# %% [markdown]
# ## 14 — ROI Impact: Propensity-Based Targeting

# %%
COST_PER_CONTACT  = 15    # £ average across channels
AVG_REVENUE       = 800   # £ average revenue per conversion (blended product mix)

total_test   = len(y_test)
total_conv   = y_test.sum()
total_cost_mass = total_test * COST_PER_CONTACT
total_rev_mass  = total_conv * AVG_REVENUE
roi_mass = (total_rev_mass - total_cost_mass) / total_cost_mass * 100

scenarios = []
for thresh in [0.30, 0.35, 0.40, 0.50, 0.60, 0.65]:
    y_t         = (best_proba >= thresh).astype(int)
    n_contact   = y_t.sum()
    n_captured  = ((y_t == 1) & (y_test == 1)).sum()
    cost        = n_contact * COST_PER_CONTACT
    revenue     = n_captured * AVG_REVENUE
    roi         = (revenue - cost) / cost * 100 if cost > 0 else 0
    prec        = precision_score(y_test, y_t, zero_division=0)
    rec         = recall_score(y_test, y_t)
    scenarios.append({
        "Threshold":          thresh,
        "Contacts":           n_contact,
        "Converters Caught":  n_captured,
        "Precision":          round(prec, 3),
        "Recall":             round(rec,  3),
        "Campaign Cost (£)":  cost,
        "Revenue (£)":        revenue,
        "ROI (%)":            round(roi, 1),
    })

roi_df = pd.DataFrame(scenarios)
print("\nROI IMPACT — PROPENSITY THRESHOLD COMPARISON")
print("(Assumptions: £15 cost per contact, £800 avg revenue per conversion)")
print("=" * 100)
print(roi_df.to_string(index=False))
print("=" * 100)
print(f"\n  Mass-market (no model) ROI : {roi_mass:.1f}%")
print(f"  Best propensity-model ROI  : {roi_df['ROI (%)'].max():.1f}%  "
      f"(threshold={roi_df.loc[roi_df['ROI (%)'].idxmax(),'Threshold']})")

# %% [markdown]
# ## 15 — Save Models and Final Report

# %%
joblib.dump(lr_best,  MODELS / "logistic_regression.pkl")
joblib.dump(rf_best,  MODELS / "random_forest.pkl")
joblib.dump(xgb_best, MODELS / "xgboost.pkl")

metrics_df.to_csv(PROCESSED / "model_metrics.csv")
roi_df.to_csv(PROCESSED    / "propensity_roi_scenarios.csv", index=False)

print("=" * 55)
print("  PHASE 8 COMPLETE — MODEL ARTEFACTS SAVED")
print("=" * 55)
print(f"  ml_models/logistic_regression.pkl")
print(f"  ml_models/random_forest.pkl")
print(f"  ml_models/xgboost.pkl")
print(f"  data/processed/model_metrics.csv")
print(f"  data/processed/propensity_roi_scenarios.csv")
print(f"\n  Exports (reports/exports/):")
print(f"  ml_dataset_overview.png")
print(f"  ml_metrics_dashboard.png")
print(f"  ml_roc_pr_curves.png")
print(f"  ml_confusion_matrices.png")
print(f"  ml_feature_importance.png")
print(f"  ml_feature_agreement.png")
print(f"  ml_threshold_analysis.png")
print()
print("  FINAL MODEL METRICS (Test Set):")
print(metrics_df.to_string())
