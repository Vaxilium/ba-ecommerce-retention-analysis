"""Synthetic data generator for the 'Altiplano Goods' portfolio case study.

FICTITIOUS DATA. Generates a realistic D2C e-commerce dataset with deliberately
injected data-quality issues (~2-3% of rows) so the cleaning layer has real work.

Tables: products, customers, orders, order_items, marketing_touches,
support_tickets, returns  ->  CSV files in data/raw (+ small samples in data/sample).

Mechanisms encoded in the simulation (to be *rediscovered* by the analysis):
  H1  acquisition mix shifts toward paid social (worse repeat behaviour)
  H2  first-order discounts deepen over time (deal-seekers churn more)
  H3  delivery-delay problem in Colombia during H2 2025
  H4  long support-ticket resolutions increase churn
  +   Nov/Dec seasonality, 90-day-repeat probability anchored per customer.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HORIZON_START = date(2024, 1, 1)
HORIZON_END = date(2025, 12, 31)

COUNTRIES = ["Mexico", "Brazil", "Colombia", "Chile", "Peru", "Argentina"]
COUNTRY_W = [0.25, 0.22, 0.16, 0.15, 0.13, 0.09]
CITIES = {
    "Mexico": ["CDMX", "Guadalajara", "Monterrey", "Puebla", "Merida"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Curitiba", "Belo Horizonte", "Porto Alegre"],
    "Colombia": ["Bogota", "Medellin", "Cali", "Barranquilla", "Bucaramanga"],
    "Chile": ["Santiago", "Valparaiso", "Concepcion", "La Serena", "Temuco"],
    "Peru": ["Lima", "Arequipa", "Trujillo", "Cusco", "Piura"],
    "Argentina": ["Buenos Aires", "Cordoba", "Rosario", "Mendoza", "La Plata"],
}
CHANNELS = ["organic_search", "paid_search", "paid_social", "email", "referral", "influencer"]
CH_MIX_START = dict(zip(CHANNELS, [0.30, 0.25, 0.22, 0.08, 0.08, 0.07]))
CH_MIX_END = dict(zip(CHANNELS, [0.16, 0.14, 0.60, 0.05, 0.03, 0.02]))
CHAN_MULT = {"organic_search": 1.15, "paid_search": 0.95, "paid_social": 0.66,
             "email": 1.05, "referral": 1.25, "influencer": 0.85}
MIX_CONVERGENCE = 0.85  # acquisition/discount mix reaches its end state by this fraction of the period
DISCOUNT_BANDS = {"none": (0.00, 0.00), "light": (0.05, 0.15),
                  "medium": (0.16, 0.30), "heavy": (0.31, 0.50)}
DISC_MIX_START = {"none": 0.35, "light": 0.27, "medium": 0.20, "heavy": 0.18}
DISC_MIX_END = {"none": 0.15, "light": 0.19, "medium": 0.16, "heavy": 0.50}
DISC_MULT = {"none": 1.05, "light": 1.00, "medium": 0.90, "heavy": 0.66}
REGION_MULT = {"Chile": 1.08, "Peru": 0.98, "Colombia": 0.98,
               "Mexico": 1.05, "Argentina": 0.92, "Brazil": 0.97}
COLOMBIA_DELAY_START = date(2025, 7, 1)
COLOMBIA_H2_MULT = 0.75
PROMISED_DAYS = {"Chile": 3, "Peru": 5, "Colombia": 6, "Mexico": 5, "Argentina": 7, "Brazil": 8}
SEASONAL = {1: 0.90, 2: 0.95, 3: 0.95, 4: 1.00, 5: 1.05, 6: 0.95,
            7: 0.95, 8: 0.95, 9: 1.00, 10: 1.10, 11: 1.35, 12: 1.25}
SEGMENTS = [
    {"name": "loyal", "share": 0.34, "p90": 0.78, "gap_days": 27},
    {"name": "occasional", "share": 0.29, "p90": 0.34, "gap_days": 66},
    {"name": "one_time", "share": 0.37, "p90": 0.08, "gap_days": 185},
]
CATEGORY_W = {"Home Decor": 0.25, "Kitchen & Dining": 0.20, "Textiles": 0.18,
              "Lighting": 0.12, "Storage": 0.13, "Outdoor": 0.12}
PRICE_RANGE = {"Home Decor": (15, 120), "Kitchen & Dining": (12, 90), "Textiles": (20, 150),
               "Lighting": (25, 180), "Storage": (18, 110), "Outdoor": (30, 160)}
TOPICS = ["delivery_delay", "product_quality", "refund_status", "account", "other"]
TOPIC_W = [0.35, 0.25, 0.15, 0.15, 0.10]
RETURN_REASONS = ["changed_mind", "damaged", "not_as_described", "late_delivery", "wrong_item"]
REASON_W = [0.30, 0.25, 0.20, 0.15, 0.10]
N_ADJ = ["Andes", "Pampa", "Cordillera", "Solar", "Bosque", "Rio", "Cumbre", "Barro", "Lino", "Cobre"]
N_NOUN = {"Home Decor": ["Vase", "Frame", "Candleholder", "Mural", "Sculpture", "Mirror"],
          "Kitchen & Dining": ["Mug Set", "Board", "Bowl", "Kettle", "Cutlery Set", "Tray"],
          "Textiles": ["Throw", "Cushion", "Rug", "Table Runner", "Quilt", "Towel Set"],
          "Lighting": ["Lamp", "Sconce", "Pendant", "Lantern", "String Lights"],
          "Storage": ["Basket", "Box Set", "Shelf", "Organizer", "Hamper"],
          "Outdoor": ["Planter", "Hammock", "Chair", "Mat", "Fire Pit"]}
MAX_SEASONAL = max(SEASONAL.values())
PRODUCTS_N = 300
dirty_log: dict[str, int] = {}


def month_idx(d: date) -> int:
    return (d.year - 2024) * 12 + d.month - 1


def month_start(i: int) -> date:
    return date(2024 + i // 12, i % 12 + 1, 1)


def lerp_mix(start: dict, end: dict, t: float) -> dict:
    w = {k: start[k] + (end[k] - start[k]) * t for k in start}
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def sample(pool, probs, rng, size=None):
    p = np.asarray(probs, dtype=float)
    return rng.choice(pool, p=p / p.sum(), size=size)


def gen_products(rng, n):
    cats = list(CATEGORY_W)
    rows = []
    for i in range(n):
        cat = sample(cats, list(CATEGORY_W.values()), rng)
        lo, hi = PRICE_RANGE[cat]
        price = round(float(rng.uniform(lo, hi)), 2)
        cost = round(price * float(rng.uniform(0.42, 0.62)), 2)
        launch = HORIZON_START + timedelta(days=int(rng.integers(-400, 500)))
        rows.append({"product_id": f"P{100 + i}",
                     "product_name": f"{sample(N_ADJ, [1] * len(N_ADJ), rng)} {sample(N_NOUN[cat], [1] * len(N_NOUN[cat]), rng)}",
                     "category": cat, "list_price": price, "cost": cost,
                     "launched_date": launch.isoformat(), "active": True})
    return pd.DataFrame(rows)


def gen_customers(rng, n):
    growth = np.linspace(1.0, 2.0, 24)
    signup_w = np.array([growth[m] * SEASONAL[m % 12 + 1] for m in range(24)])
    signup_w = signup_w / signup_w.sum()
    months = rng.choice(24, size=n, p=signup_w)
    dom = rng.integers(0, 28, n)
    rows = []
    for i, (m, d) in enumerate(zip(months, dom)):
        signup = month_start(int(m)) + timedelta(days=int(d))
        t = min(1.0, month_idx(signup) / 23.0 / MIX_CONVERGENCE)
        ch = sample(CHANNELS, list(lerp_mix(CH_MIX_START, CH_MIX_END, t).values()), rng)
        country = sample(COUNTRIES, COUNTRY_W, rng)
        rows.append({"customer_id": f"C{1000 + i}", "signup_date": signup.isoformat(),
                     "acquisition_channel": ch, "country": country,
                     "city": sample(CITIES[country], [1] * len(CITIES[country]), rng),
                     "email": f"user{1000 + i}@{sample(['mail.com', 'correo.net', 'inbox.io'], [0.5, 0.3, 0.2], rng)}",
                     "age_band": sample(["18-24", "25-34", "35-44", "45-54", "55+"], [0.15, 0.35, 0.27, 0.15, 0.08], rng),
                     "marketing_consent": bool(rng.random() < 0.62),
                     "preferred_device": sample(["mobile", "desktop", "tablet"], [0.62, 0.30, 0.08], rng)})
    return pd.DataFrame(rows)


def next_order_date(prev: date, gap_mean: float, rng) -> date:
    for _ in range(60):
        cand = prev + timedelta(days=max(3, int(rng.exponential(gap_mean))))
        if cand > HORIZON_END:
            return cand
        if rng.random() < SEASONAL[cand.month] / MAX_SEASONAL:
            return cand
    return prev + timedelta(days=max(3, int(rng.exponential(gap_mean))))


def gen_order(cust, order_date, rng, buckets) -> dict:
    t = min(1.0, month_idx(order_date) / 23.0 / MIX_CONVERGENCE)
    band = sample(list(DISCOUNT_BANDS), list(lerp_mix(DISC_MIX_START, DISC_MIX_END, t).values()), rng)
    lo, hi = DISCOUNT_BANDS[band]
    disc = round(float(rng.uniform(lo, hi)), 3)
    status = "cancelled" if rng.random() < 0.04 else "delivered"
    promised = PROMISED_DAYS[cust["country"]] + int(rng.integers(0, 2))
    extra = float(rng.exponential(1.5))
    if cust["country"] == "Colombia" and order_date >= COLOMBIA_DELAY_START:
        extra += 6.0 if rng.random() < 0.60 else 2.0
    if order_date.month in (11, 12):
        extra += 1.5
    actual = max(1, int(round(promised + extra)))
    oid = f"O{100000 + len(buckets['orders'])}"
    buckets["orders"].append({"order_id": oid, "customer_id": cust["customer_id"],
                              "order_date": order_date.isoformat(), "order_status": status,
                              "ship_country": cust["country"], "discount_rate": disc,
                              "promised_delivery_days": promised, "actual_delivery_days": actual,
                              "shipping_cost": round(float(rng.uniform(2.5, 8.0) + PROMISED_DAYS[cust["country"]] * 0.5), 2),
                              "payment_method": sample(["credit_card", "debit_card", "transfer", "wallet"],
                                                       [0.45, 0.25, 0.12, 0.18], rng),
                              "device": sample(["mobile", "desktop", "tablet"], [0.62, 0.30, 0.08], rng)})
    for _ in range(int(sample([1, 2, 3, 4], [0.45, 0.33, 0.16, 0.06], rng))):
        pid = f"P{cust['affinity'] if rng.random() < 0.70 else int(rng.integers(100, 100 + PRODUCTS_N))}"
        buckets["items"].append({"order_item_id": f"OI{500000 + len(buckets['items'])}", "order_id": oid,
                                 "product_id": pid, "quantity": int(sample([1, 2, 3], [0.82, 0.14, 0.04], rng)),
                                 "discount_rate": disc})
    return {"oid": oid, "date": order_date, "band": band, "ok": status != "cancelled",
            "delayed": (actual - promised) > 5 and status != "cancelled"}


def maybe_ticket(cust, ev, rng, buckets) -> bool:
    """Return True when a long (>72h) ticket follows this order."""
    if not ev["ok"] and rng.random() > 0.06:
        return False
    if rng.random() > (0.18 if ev["delayed"] else 0.04):
        return False
    opened = pd.Timestamp(ev["date"]) + pd.Timedelta(days=PROMISED_DAYS[cust["country"]] + 4 + float(rng.exponential(3)))
    med = 42.0 if (cust["country"] == "Colombia" and opened >= pd.Timestamp(COLOMBIA_DELAY_START)) else 20.0
    hours = float(np.exp(rng.normal(np.log(med), 0.9)))
    buckets["tickets"].append({"customer_id": cust["customer_id"], "order_id": ev["oid"],
                               "opened_at": opened, "resolution_hours": round(hours, 1),
                               "topic": sample(TOPICS, TOPIC_W, rng),
                               "contact_channel": sample(["chat", "email", "phone"], [0.5, 0.3, 0.2], rng),
                               "satisfaction_score": int(np.clip(round(rng.normal(4.1 if hours <= 72 else 2.6, 0.8)), 1, 5))})
    return hours > 72


def simulate(customers, affinity_cat, prod_by_cat, rng):
    buckets = {"orders": [], "items": [], "touches": [], "tickets": [], "returns": []}
    for _, cust_row in customers.iterrows():
        cust = dict(cust_row)
        pool = prod_by_cat[affinity_cat[cust["customer_id"]]]
        cust["affinity"] = int(sample(pool, [1] * len(pool), rng, size=1)[0])
        signup = date.fromisoformat(cust["signup_date"])
        first_date = signup + timedelta(days=int(rng.integers(0, 4)))
        if first_date > HORIZON_END:
            continue
        buckets["touches"].append({"touch_id": f"T{200000 + len(buckets['touches'])}", "customer_id": cust["customer_id"],
                                   "touch_date": signup.isoformat(), "channel": cust["acquisition_channel"],
                                   "campaign": f"acq_{cust['acquisition_channel']}_{signup.year}_{signup.month:02d}"})
        seg = sample([s["name"] for s in SEGMENTS], [s["share"] for s in SEGMENTS], rng)
        spec = next(s for s in SEGMENTS if s["name"] == seg)
        p90 = spec["p90"] * CHAN_MULT[cust["acquisition_channel"]] * REGION_MULT[cust["country"]]
        if cust["country"] == "Colombia" and first_date >= COLOMBIA_DELAY_START:
            p90 *= COLOMBIA_H2_MULT

        ev = gen_order(cust, first_date, rng, buckets)
        p90 *= DISC_MULT[ev["band"]]
        ticket_long = maybe_ticket(cust, ev, rng, buckets)
        ret_flag = False
        if ev["ok"] and ev["delayed"]:
            p90 *= 0.90
        if ev["ok"] and rng.random() < (0.12 if affinity_cat[cust["customer_id"]] == "Textiles" else 0.07):
            ret_flag = True
            buckets["returns"].append({"order_id": ev["oid"]})
            p90 *= 0.85
        if ticket_long:
            p90 *= 0.78
        gap = spec["gap_days"] * (1.35 if (ticket_long or ret_flag) else 1.0)

        u = rng.random()
        if u < p90:
            second = first_date + timedelta(days=5 + min(84, int(rng.exponential(28))))
        elif u < p90 + 0.06:
            second = first_date + timedelta(days=int(rng.integers(92, 380)))
        else:
            second = None
        prev_date = first_date
        n_orders = 1
        while True:
            if n_orders == 1:
                if second is None or second > HORIZON_END:
                    break
                when = second
            else:
                when = next_order_date(prev_date, gap, rng)
                if when > HORIZON_END:
                    break
            ev = gen_order(cust, when, rng, buckets)
            ticket_long = ticket_long or maybe_ticket(cust, ev, rng, buckets)
            if ev["ok"] and rng.random() < (0.12 if affinity_cat[cust["customer_id"]] == "Textiles" else 0.07):
                buckets["returns"].append({"order_id": ev["oid"]})
            prev_date = when
            n_orders += 1
    return buckets


def gen_touches(customers, rng, buckets):
    consent = customers[customers["marketing_consent"]]
    for cid, signup_s in zip(consent["customer_id"], consent["signup_date"]):
        signup = date.fromisoformat(signup_s)
        m = month_idx(signup) + 1
        while m <= 23:
            ms = month_start(m)
            if rng.random() < 0.6:
                buckets["touches"].append({"touch_id": f"T{200000 + len(buckets['touches'])}", "customer_id": cid,
                                           "touch_date": (ms + timedelta(days=int(rng.integers(0, 20)))).isoformat(),
                                           "channel": "email", "campaign": f"newsletter_{ms.year}_{ms.month:02d}"})
            if ms.month in (11, 12) or rng.random() < 0.06:
                buckets["touches"].append({"touch_id": f"T{200000 + len(buckets['touches'])}", "customer_id": cid,
                                           "touch_date": (ms + timedelta(days=int(rng.integers(0, 25)))).isoformat(),
                                           "channel": "paid_social", "campaign": f"promo_{ms.year}_{ms.month:02d}"})
            m += 1


def build_frames(customers, products, buckets, rng):
    orders_df = pd.DataFrame(buckets["orders"]).sort_values("order_date").reset_index(drop=True)
    oid_map = {old: f"O{100000 + i}" for i, old in enumerate(orders_df["order_id"])}
    orders_df["order_id"] = [f"O{100000 + i}" for i in range(len(orders_df))]
    items_df = pd.DataFrame(buckets["items"])
    items_df["order_id"] = items_df["order_id"].map(oid_map)
    price_map = products.set_index("product_id")["list_price"]
    items_df["unit_price"] = [round(float(price_map[p]) * (1 - d), 2) for p, d in zip(items_df["product_id"], items_df["discount_rate"])]
    items_df = items_df[["order_item_id", "order_id", "product_id", "quantity", "unit_price"]]

    order_date_map = orders_df.set_index("order_id")["order_date"]
    line_total = items_df.assign(t=items_df["quantity"] * items_df["unit_price"]).groupby("order_id")["t"].sum()

    tickets_df = pd.DataFrame(buckets["tickets"])
    if len(tickets_df):
        tickets_df["order_id"] = tickets_df["order_id"].map(oid_map)
        tickets_df["ticket_id"] = [f"TICK-{5000 + i}" for i in range(len(tickets_df))]
        tickets_df["resolved_at"] = tickets_df["opened_at"] + pd.to_timedelta(tickets_df["resolution_hours"], unit="h")
        tickets_df["status"] = "resolved"
        tickets_df = tickets_df[["ticket_id", "customer_id", "order_id", "opened_at", "resolved_at",
                                 "topic", "contact_channel", "status", "resolution_hours", "satisfaction_score"]]

    returns_df = pd.DataFrame(buckets["returns"])
    if len(returns_df):
        returns_df["order_id"] = returns_df["order_id"].map(oid_map)
        returns_df["return_id"] = [f"R{8000 + i}" for i in range(len(returns_df))]
        returns_df["requested_date"] = [(pd.Timestamp(order_date_map[o]) + pd.Timedelta(days=int(rng.integers(3, 35)))).date().isoformat() for o in returns_df["order_id"]]
        returns_df["reason"] = [sample(RETURN_REASONS, REASON_W, rng) for _ in range(len(returns_df))]
        returns_df["status"] = [sample(["approved", "pending", "rejected"], [0.8, 0.12, 0.08], rng) for _ in range(len(returns_df))]
        returns_df["refund_amount"] = [round(float(line_total.get(o, 0.0)) * float(rng.uniform(0.55, 1.0)), 2) for o in returns_df["order_id"]]
        returns_df = returns_df[["return_id", "order_id", "requested_date", "reason", "status", "refund_amount"]]

    tables = {"products": products, "customers": customers, "orders": orders_df, "order_items": items_df,
              "marketing_touches": pd.DataFrame(buckets["touches"]),
              "support_tickets": tickets_df, "returns": returns_df}
    return tables


def inject_dirty(tables, rng):
    global dirty_log
    dirty_log = {}

    def pick(df, frac):
        return rng.choice(len(df), max(1, int(len(df) * frac)), replace=False)

    p = tables["products"]
    p.loc[pick(p, 0.007), "category"] = None
    idx = pick(p, 0.01)
    p.loc[idx, "cost"] = p.loc[idx, "list_price"] * 1.3
    dup = p.sample(max(1, int(len(p) * 0.007)), random_state=int(rng.integers(0, 1e9)))
    dirty_log["products_null_category"] = int(p["category"].isna().sum())
    dirty_log["products_cost_gt_price"] = int((p["cost"] > p["list_price"]).sum())
    dirty_log["products_duplicate_rows"] = len(dup)
    tables["products"] = pd.concat([p, dup], ignore_index=True)

    c = tables["customers"]
    c.loc[pick(c, 0.005), "country"] = None
    for i in pick(c, 0.02):
        v = c.at[i, "country"]
        if isinstance(v, str):
            c.at[i, "country"] = {"Peru": "Perú", "Brazil": "brasil", "Chile": "CHILE"}.get(v, (v.lower() if rng.random() < 0.5 else " " + v.upper() + " "))
    c.loc[pick(c, 0.002), "signup_date"] = None
    dup = c.sample(max(1, int(len(c) * 0.004)), random_state=int(rng.integers(0, 1e9)))
    c = pd.concat([c, dup], ignore_index=True)
    donors = rng.choice(len(c), max(1, int(len(c) * 0.004)), replace=True)
    victims = rng.choice(len(c), len(donors), replace=True)
    c.loc[c.index[victims], "email"] = c.loc[c.index[donors], "email"].values
    dirty_log["customers_null_country"] = int(c["country"].isna().sum())
    dirty_log["customers_null_signup"] = int(c["signup_date"].isna().sum())
    dirty_log["customers_duplicate_rows"] = len(dup)
    dirty_log["customers_duplicate_emails"] = int(c["email"].duplicated().sum())
    tables["customers"] = c

    o = tables["orders"]
    o.loc[pick(o, 0.006), "ship_country"] = None
    for i in pick(o, 0.015):
        v = o.at[i, "ship_country"]
        if isinstance(v, str):
            o.at[i, "ship_country"] = v.upper() if rng.random() < 0.5 else " " + v.lower() + " "
    for i in pick(o, 0.0015):
        o.at[i, "order_date"] = (pd.Timestamp(o.at[i, "order_date"]) + pd.Timedelta(days=int(rng.integers(30, 300)))).date().isoformat()
    idx = pick(o, 0.001)
    o.loc[idx, "customer_id"] = [f"CUST-GHOST-{i}" for i in range(len(idx))]
    idx = pick(o, 0.003)
    o.loc[idx, "shipping_cost"] = -o.loc[idx, "shipping_cost"].abs()
    o.loc[pick(o, 0.005), "discount_rate"] = None
    dup = o.sample(max(1, int(len(o) * 0.006)), random_state=int(rng.integers(0, 1e9)))
    dirty_log["orders_future_dates"] = int((pd.to_datetime(o["order_date"]) > pd.Timestamp(HORIZON_END)).sum())
    dirty_log["orders_orphan_customer"] = int(o["customer_id"].str.startswith("CUST-GHOST").sum())
    dirty_log["orders_null_country"] = int(o["ship_country"].isna().sum())
    dirty_log["orders_negative_shipping"] = int((o["shipping_cost"] < 0).sum())
    dirty_log["orders_null_discount"] = int(o["discount_rate"].isna().sum())
    dirty_log["orders_duplicate_rows"] = len(dup)
    tables["orders"] = pd.concat([o, dup], ignore_index=True)

    it = tables["order_items"]
    idx = pick(it, 0.006)
    it.loc[idx, "quantity"] = -it.loc[idx, "quantity"].abs()
    it.loc[pick(it, 0.004), "unit_price"] = 0.0
    idx = pick(it, 0.004)
    it.loc[idx, "product_id"] = "P999999"
    dirty_log["items_negative_qty"] = int((it["quantity"] <= 0).sum())
    dirty_log["items_bad_price"] = int((it["unit_price"] <= 0).sum())
    dirty_log["items_orphan_product"] = int((it["product_id"] == "P999999").sum())
    tables["order_items"] = it

    t = tables["marketing_touches"]
    t.loc[pick(t, 0.005), "channel"] = None
    idx = pick(t, 0.01)
    t.loc[idx, "channel"] = t.loc[idx, "channel"].str.upper()
    for i in pick(t, 0.003):
        t.at[i, "touch_date"] = (pd.Timestamp(t.at[i, "touch_date"]) + pd.Timedelta(days=int(rng.integers(30, 200)))).date().isoformat()
    dup = t.sample(max(1, int(len(t) * 0.003)), random_state=int(rng.integers(0, 1e9)))
    dirty_log["touches_null_channel"] = int(t["channel"].isna().sum())
    dirty_log["touches_duplicate_rows"] = len(dup)
    tables["marketing_touches"] = pd.concat([t, dup], ignore_index=True)

    tk = tables["support_tickets"]
    if len(tk):
        idx = pick(tk, 0.006)
        tk.loc[idx, "opened_at"] = (pd.to_datetime(tk.loc[idx, "resolved_at"]) + pd.Timedelta(hours=5)).to_numpy()
        tk.loc[pick(tk, 0.004), "topic"] = None
        dirty_log["tickets_resolved_before_opened"] = int((pd.to_datetime(tk["resolved_at"]) < pd.to_datetime(tk["opened_at"])).sum())
        dirty_log["tickets_null_topic"] = int(tk["topic"].isna().sum())
    tables["support_tickets"] = tk

    r = tables["returns"]
    if len(r):
        idx = pick(r, 0.005)
        r.loc[idx, "refund_amount"] = -r.loc[idx, "refund_amount"].abs()
        r.loc[pick(r, 0.005), "reason"] = None
        dirty_log["returns_negative_refund"] = int((r["refund_amount"] < 0).sum())
        dirty_log["returns_null_reason"] = int(r["reason"].isna().sum())
    tables["returns"] = r
    return tables


def cohort_check(orders_df):
    valid = orders_df[orders_df["order_status"] != "cancelled"]
    first = valid.groupby("customer_id")["order_date"].min().rename("first_date")
    pairs = valid.merge(first, left_on="customer_id", right_index=True)
    pairs = pairs[pairs["order_date"] > pairs["first_date"]].copy()
    pairs["gap"] = (pd.to_datetime(pairs["order_date"]) - pd.to_datetime(pairs["first_date"])).dt.days
    rep = pairs.groupby("customer_id")["gap"].min().le(90)
    fo = first.to_frame()
    fo["repeated_90d"] = fo.index.map(rep).fillna(False)
    fo["cohort"] = pd.to_datetime(fo["first_date"]).dt.to_period("M").astype(str)
    full = fo[fo["cohort"] <= "2025-09"]
    return full.groupby("cohort")["repeated_90d"].mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=20000)
    ap.add_argument("--products", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("data/raw"))
    ap.add_argument("--samples-dir", type=Path, default=Path("data/sample"))
    args = ap.parse_args()

    global PRODUCTS_N
    PRODUCTS_N = args.products
    rng = np.random.default_rng(args.seed)
    products = gen_products(rng, args.products)
    customers = gen_customers(rng, args.customers)
    prod_by_cat: dict[str, list[int]] = {cat: [int(p[1:]) for p in grp["product_id"]] for cat, grp in products.groupby("category")}
    affinity_cat = {cid: sample(list(CATEGORY_W), list(CATEGORY_W.values()), rng) for cid in customers["customer_id"]}

    buckets = simulate(customers, affinity_cat, prod_by_cat, rng)
    gen_touches(customers, rng, buckets)
    tables = build_frames(customers, products, buckets, rng)
    clean_counts = {k: int(len(v)) for k, v in tables.items()}
    tables = inject_dirty(tables, rng)

    args.out.mkdir(parents=True, exist_ok=True)
    args.samples_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(args.out / f"{name}.csv", index=False)
        df.head(200).to_csv(args.samples_dir / f"{name}_sample.csv", index=False)

    Path("outputs").mkdir(exist_ok=True)
    manifest = {"seed": args.seed, "customers_param": args.customers, "products_param": args.products,
                "clean_counts": clean_counts, "dirty_counts": dirty_log,
                "horizon": [HORIZON_START.isoformat(), HORIZON_END.isoformat()]}
    Path("outputs/generator_manifest.json").write_text(json.dumps(manifest, indent=2))

    trend = cohort_check(tables["orders"].drop_duplicates(subset=["order_id"]))
    print(f"clean rows: {clean_counts}")
    print("90d repeat by cohort:")
    for c, v in trend.items():
        print(f"  {c}: {v:.3f}")
    print("dirty injection:", json.dumps(dirty_log))


if __name__ == "__main__":
    main()
