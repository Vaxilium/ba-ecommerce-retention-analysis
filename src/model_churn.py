"""Repeat-purchase (90d) driver model: logistic regression on cleaned customer data.

Target: is_repeat_90d (second order within 90 days of the first).
Population: customers with a fully observed 90-day window (no censoring).
Outputs: outputs/analysis/churn_model.json + churn_model_odds_ratios.csv
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from build_warehouse import open_engine

CAT_FEATURES = ["acquisition_channel", "country", "first_order_discount_band", "age_band", "preferred_device"]
NUM_FEATURES = ["log_first_order_value", "first_order_delay_days", "first_order_delayed",
                "first_order_long_ticket", "first_order_returned", "marketing_consent_int", "month_sin", "month_cos"]


def load_data() -> pd.DataFrame:
    engine = open_engine(Path("outputs/warehouse.duckdb"))
    df = engine.query_df("""
        SELECT acquisition_channel, country, first_order_discount_band, age_band, preferred_device,
               first_order_value, first_order_delay_days, first_order_delayed,
               first_order_long_ticket, first_order_returned, marketing_consent,
               cohort_month, is_repeat_90d
        FROM dim_customer
        WHERE has_full_90d_window = 1 AND first_order_date IS NOT NULL
        ORDER BY customer_id
    """)
    engine.close()
    df["log_first_order_value"] = np.log1p(df["first_order_value"].clip(lower=0))
    df["first_order_delay_days"] = df["first_order_delay_days"].clip(-1, 30).fillna(0)
    df["first_order_long_ticket"] = df["first_order_long_ticket"].fillna(0).astype(int)
    df["first_order_returned"] = df["first_order_returned"].astype(int)
    df["marketing_consent_int"] = df["marketing_consent"].astype(int)
    month = df["cohort_month"].str.slice(5, 7).astype(int)
    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)
    return df


def fit_model(df: pd.DataFrame):
    X = df[CAT_FEATURES + NUM_FEATURES]
    y = df["is_repeat_90d"].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), CAT_FEATURES),
        ("num", "passthrough", NUM_FEATURES),
    ])
    pipe = Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=2000, random_state=42))])
    pipe.fit(X_train, y_train)

    auc_train = roc_auc_score(y_train, pipe.predict_proba(X_train)[:, 1])
    auc_test = roc_auc_score(y_test, pipe.predict_proba(X_test)[:, 1])

    # Wald 95% CIs via the Fisher information on the training design matrix.
    Xt = pre.transform(X_train)
    Xt = np.asarray(Xt.todense()) if hasattr(Xt, "todense") else np.asarray(Xt)
    coef = pipe.named_steps["clf"].coef_[0]
    p = 1 / (1 + np.exp(-(Xt @ coef + pipe.named_steps["clf"].intercept_[0])))
    W = p * (1 - p)
    hessian = Xt.T @ (W[:, None] * Xt)
    cov = np.linalg.pinv(hessian)
    se = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    names = list(pipe.named_steps["pre"].get_feature_names_out())
    odds = pd.DataFrame({
        "feature": names, "coef": coef, "odds_ratio": np.exp(coef),
        "ci_low": np.exp(coef - 1.96 * se), "ci_high": np.exp(coef + 1.96 * se),
        "z": coef / se,
    })
    odds["p_value"] = [math.erfc(abs(z) / math.sqrt(2)) for z in odds["z"]]
    odds["feature"] = odds["feature"].str.replace("cat__", "", regex=False).str.replace("num__", "", regex=False)

    # Decile lift on the test set (targeting value of the model).
    scores = pd.DataFrame({"y": y_test.values, "p": pipe.predict_proba(X_test)[:, 1]})
    scores["decile"] = pd.qcut(scores["p"], 10, labels=False, duplicates="drop") + 1
    lift = scores.groupby("decile").agg(customers=("y", "size"), actual_repeat_rate=("y", "mean")).reset_index()
    lift["lift_vs_base"] = lift["actual_repeat_rate"] / float(y_test.mean())
    return pipe, odds, auc_train, auc_test, lift, float(y_train.mean()), int(len(y_train)), int(len(y_test))


def main() -> None:
    df = load_data()
    pipe, odds, auc_train, auc_test, lift, base_rate, n_train, n_test = fit_model(df)
    Path("outputs/analysis").mkdir(parents=True, exist_ok=True)
    odds.sort_values("odds_ratio").to_csv("outputs/analysis/churn_model_odds_ratios.csv", index=False)

    neg = odds[odds["odds_ratio"] < 1].head(8)
    pos = odds[odds["odds_ratio"] > 1].sort_values("odds_ratio", ascending=False).head(8)
    result = {
        "population": int(len(df)),
        "base_rate": round(base_rate, 4),
        "auc_train": round(auc_train, 4),
        "auc_test": round(auc_test, 4),
        "n_train": n_train, "n_test": n_test,
        "decile_lift": lift.to_dict("records"),
        "strongest_negative": neg.to_dict("records"),
        "strongest_positive": pos.to_dict("records"),
    }
    Path("outputs/analysis/churn_model.json").write_text(json.dumps(result, indent=2))
    print(f"AUC train={auc_train:.3f} test={auc_test:.3f} (n={len(df)})")
    print("top negative ORs:\n", neg[["feature", "odds_ratio", "ci_low", "ci_high"]].to_string(index=False))
    print("top positive ORs:\n", pos[["feature", "odds_ratio", "ci_low", "ci_high"]].to_string(index=False))
    print("decile lift:\n", lift.to_string(index=False))


if __name__ == "__main__":
    main()
