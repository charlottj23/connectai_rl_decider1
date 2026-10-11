"""공개 데이터로 '일반 회사' 프로필을 만듭니다 → connect_tycoon/data/profiles/general.json

여러 업종(소매 · 호텔 · 자전거 대여 · 카드 결제 · 배송 마켓 · 고객센터)의 공개 데이터에서
업종과 상관없이 나타나는 '모양'만 가져옵니다: 요일 패턴, 하루 수요 흔들림, 취소 요일 · 금액 분포,
사기 비율과 사기 점수 분포, 서비스 실패 뒤 만족 하락. 숫자의 크기(손님 수 · 가격)는 회사마다 다르므로
엔진의 기본 규모에 맞춥니다. 나중에 한 회사의 기록을 넣으면 같은 방법으로 그 회사 프로필이 됩니다.

    python scripts/calibrate.py --data ~/connect-data        # 원본 데이터는 저장소에 넣지 않습니다

내려받기 (모두 공개):
    online_retail_II.xlsx      UCI Online Retail II · CC BY 4.0 · https://archive.ics.uci.edu/dataset/502
    hotels.csv                 Hotel Booking Demand (Antonio et al. 2019) · CC BY 4.0 · tidytuesday 2020-02-11
    bike/day.csv               UCI Bike Sharing · CC BY 4.0 · https://archive.ics.uci.edu/dataset/275
    creditcard.pq              ULB Credit Card Fraud · OpenML 1597 · DbCL (Public)
    olist_orders_dataset.csv, olist_order_reviews_dataset.csv   Olist Brazilian E-Commerce · CC BY-NC-SA 4.0
    bitext.csv                 Bitext Customer Support · CDLA-Sharing-1.0 · huggingface.co/datasets/bitext
"""
import argparse
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "connect_tycoon", "data", "profiles", "general.json")
REAL = os.path.join(ROOT, "connect_tycoon", "data", "real")          # 실제 데이터 시험(backtest)에 쓰는 작은 기록
QN = 21                                     # 분위수 표 크기 (0%, 5%, ..., 100%)
PROBS = np.linspace(0, 1, QN)
# 엔진 기본 규모: 금액은 중앙값을 맞추고(꼬리가 길어 평균은 쓰지 않습니다) 상한을 엔진 최대의 3배로 둡니다
BASE = {"week_demand_mean": 1.03, "refund_extra_week": 8, "refund_amount_median": 6.0, "refund_amount_cap": 36.0,
        "sec_amount_median": 22.0, "sec_amount_cap": 120.0, "customers_per_day": 50.0}


def scaled(q, median, target, cap):
    return [round(min(cap, max(1.0, v * target / median)), 2) for v in q]


def qtable(x, lo=0.01, hi=0.99):
    """양 끝 1%를 자른 분위수 표. 엔진은 같은 난수 하나(r)를 이 표에 넣어 값을 뽑습니다 (역누적분포)."""
    x = np.asarray(x, dtype=float)
    q = np.quantile(x, lo + (hi - lo) * PROBS)
    return [round(float(v), 4) for v in q]


def weekday_shape(daily):
    """daily: (date, count) 시리즈 → 월~금 상대 수요 (평균 1)과 하루 흔들림(같은 요일 · 4주 평균 대비 비율)."""
    s = daily.asfreq("D").fillna(0) if daily.index.inferred_type == "datetime64" else daily
    df = pd.DataFrame({"n": s}); df["wd"] = df.index.dayofweek
    df = df[df.wd < 5]
    df = df[df.n > 0]
    shape = df.groupby("wd").n.mean(); shape = shape / shape.mean()
    ref = df.groupby("wd").n.transform(lambda v: v.rolling(4, center=True, min_periods=2).mean())
    ratio = (df.n / ref).dropna()
    return shape.reindex(range(5)).fillna(1.0).values, ratio.sort_index().values


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--out", default=OUT)
    a = ap.parse_args(); D = os.path.expanduser(a.data)
    src, note = {}, {}

    # ── 소매 (UCI Online Retail II) ─────────────────────────────────────
    pq = os.path.join(D, "retail.pq")
    if os.path.exists(pq):
        rt = pd.read_parquet(pq)
    else:
        rt = pd.concat(pd.read_excel(os.path.join(D, "online_retail_II.xlsx"), sheet_name=None).values())
        rt = rt[["Invoice", "Quantity", "InvoiceDate", "Price", "Customer ID"]]; rt["Invoice"] = rt["Invoice"].astype(str)
        rt.to_parquet(pq)
    rt["date"] = pd.to_datetime(rt["InvoiceDate"]); rt["value"] = rt["Quantity"] * rt["Price"]
    inv = rt.groupby("Invoice").agg(date=("date", "first"), value=("value", "sum"), cust=("Customer ID", "first")).reset_index()
    inv["cancel"] = inv["Invoice"].str.startswith("C")
    sales, canc = inv[~inv.cancel], inv[inv.cancel]
    r_shape, r_noise = weekday_shape(sales.groupby(sales.date.dt.normalize()).size())
    c_shape, _ = weekday_shape(canc.groupby(canc.date.dt.normalize()).size())
    cv = (-canc.value[canc.value < 0]) / sales.value[sales.value > 0].median()           # 취소 금액 / 보통 주문 금액
    orders = sales.groupby("cust").size()
    f = canc.dropna(subset=["cust"]).cust.map(orders).fillna(0)
    vip_cut = orders.quantile(0.9)
    tier_r = [float((f <= 1).mean()), float(((f > 1) & (f < vip_cut)).mean()), float((f >= vip_cut).mean())]
    src["retail"] = {"name": "UCI Online Retail II", "license": "CC BY 4.0", "url": "https://archive.ics.uci.edu/dataset/502",
                     "rows": len(rt), "invoices": len(inv)}
    note["retail_cancel_rate"] = round(float(inv.cancel.mean()), 4)

    # ── 호텔 (Hotel Booking Demand) ─────────────────────────────────────
    h = pd.read_csv(os.path.join(D, "hotels.csv"))
    mon = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                        "October", "November", "December"], 1)}
    h["arr"] = pd.to_datetime({"year": h.arrival_date_year, "month": h.arrival_date_month.map(mon), "day": h.arrival_date_day_of_month})
    h_shape, h_noise = weekday_shape(h[h.is_canceled == 0].groupby("arr").size())
    hc = h[h.is_canceled == 1]
    hc_shape, _ = weekday_shape(hc.groupby(pd.to_datetime(hc.reservation_status_date)).size())
    prev = h.previous_bookings_not_canceled
    tier_h = [float((h.is_repeated_guest == 0).mean()), float(((h.is_repeated_guest == 1) & (prev < 3)).mean()),
              float(((h.is_repeated_guest == 1) & (prev >= 3)).mean())]
    src["hotel"] = {"name": "Hotel Booking Demand (Antonio, Almeida & Nunes 2019)", "license": "CC BY 4.0",
                    "url": "https://github.com/rfordatascience/tidytuesday/tree/master/data/2020/2020-02-11", "rows": len(h)}
    note["hotel_cancel_rate"] = round(float(h.is_canceled.mean()), 4)
    note["hotel_repeat_guest"] = round(1 - tier_h[0], 4)
    note["tier_retail"] = [round(v, 4) for v in tier_r]
    note["tier_hotel"] = [round(v, 4) for v in tier_h]

    # ── 자전거 대여 (UCI Bike Sharing) ──────────────────────────────────
    b = pd.read_csv(os.path.join(D, "bike", "day.csv"), parse_dates=["dteday"]).set_index("dteday")
    b = b[b.holiday == 0]
    b_shape, b_noise = weekday_shape(b.cnt.astype(float))
    src["bike"] = {"name": "UCI Bike Sharing", "license": "CC BY 4.0", "url": "https://archive.ics.uci.edu/dataset/275", "rows": len(b)}

    shapes = np.array([r_shape, h_shape, b_shape])
    week = shapes.mean(0) * BASE["week_demand_mean"]
    noise = np.concatenate([r_noise, h_noise, b_noise]); noise = noise / noise.mean()
    cshape = (c_shape + hc_shape) / 2
    extra = np.round(cshape / cshape.sum() * BASE["refund_extra_week"]).astype(int)

    # ── 카드 결제 (ULB) · 사기 점수 = 처음 보는 거래에 대한 모델의 확률 ────────
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    c = pd.read_parquet(os.path.join(D, "creditcard.pq"))
    y = c["Class"].astype(int).values
    X = c.drop(columns=["Class"]).copy(); X["Amount"] = np.log1p(X["Amount"])
    n = len(c) // 2                                                                         # 시간 순서로 반: 앞으로 학습, 뒤로 채점
    sc = StandardScaler().fit(X.iloc[:n]); m = LogisticRegression(max_iter=2000, C=0.1).fit(sc.transform(X.iloc[:n]), y[:n])
    p = m.predict_proba(sc.transform(X.iloc[n:]))[:, 1]; yt = y[n:]; amt = c["Amount"].values[n:]
    thr = np.quantile(p, 0.995)                                                             # 검토 대기열 = 점수 상위 0.5%
    qmask = p >= thr
    fraud_base = float(yt[qmask].mean())
    recall = float(yt[qmask].sum() / max(1, yt.sum()))
    fs_f, fs_n = p[qmask & (yt == 1)], p[qmask & (yt == 0)]
    am_f, am_n = amt[qmask & (yt == 1)], amt[qmask & (yt == 0)]
    am_med = float(np.median(np.r_[am_f, am_n]))
    src["card"] = {"name": "Credit Card Fraud Detection (ULB, Dal Pozzolo et al.)", "license": "DbCL v1.0 (OpenML: Public)",
                   "url": "https://www.openml.org/d/1597", "rows": len(c)}
    note.update({"card_fraud_rate_all": round(float(y.mean()), 5), "card_queue_share": 0.005, "card_queue_fraud_share": round(fraud_base, 4),
                 "card_queue_recall": round(recall, 4), "card_queue_size": int(qmask.sum())})

    # ── 배송 마켓 (Olist) · 서비스 실패 뒤 만족 ─────────────────────────────
    o = pd.read_csv(os.path.join(D, "olist_orders_dataset.csv"), parse_dates=["order_delivered_customer_date", "order_estimated_delivery_date"])
    rv = pd.read_csv(os.path.join(D, "olist_order_reviews_dataset.csv"))[["order_id", "review_score"]].groupby("order_id").review_score.mean()
    o = o.join(rv, on="order_id").dropna(subset=["review_score"])
    o["good"] = o.review_score >= 4
    ok = o[(o.order_status == "delivered") & (o.order_delivered_customer_date <= o.order_estimated_delivery_date)]
    late = o[(o.order_status == "delivered") & (o.order_delivered_customer_date > o.order_estimated_delivery_date)]
    fail = o[o.order_status.isin(["canceled", "unavailable"])]
    g_ok, g_late, g_fail = ok.good.mean(), late.good.mean(), fail.good.mean()
    sat_base = float(o.good.mean())
    # 만족(0~1) = 기억 속 손님 중 만족한 비율. 하루 0.1씩 기본값으로 돌아가므로 기억 속 손님 ≈ 하루 손님 / 0.1
    per_fail = float((g_ok - g_fail) / (BASE["customers_per_day"] / 0.1))
    src["olist"] = {"name": "Olist Brazilian E-Commerce", "license": "CC BY-NC-SA 4.0 (비영리 · 숫자 요약만 사용)",
                    "url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce", "rows": len(o)}
    note.update({"olist_good_on_time": round(float(g_ok), 4), "olist_good_late": round(float(g_late), 4), "olist_good_failed": round(float(g_fail), 4)})

    # ── 고객센터 (Bitext) · 문의 의도 → 팀 ─────────────────────────────────
    t = pd.read_csv(os.path.join(D, "bitext.csv"))
    TEAM = {"billing": ["check_invoice", "get_invoice", "check_payment_methods", "payment_issue", "get_refund", "track_refund",
                        "check_refund_policy", "check_cancellation_fee"],
            "urgent": ["cancel_order", "change_order", "change_shipping_address", "recover_password", "registration_problems", "contact_human_agent"],
            "risk": ["complaint", "delete_account"]}
    team = t.intent.map({i: k for k, v in TEAM.items() for i in v}).fillna("info")
    kw = team.value_counts(normalize=True)
    kind = [[k, round(float(kw.get(k, 0)), 4)] for k in ("info", "urgent", "billing", "risk")]
    src["support"] = {"name": "Bitext Customer Support LLM Chatbot Training Dataset", "license": "CDLA-Sharing-1.0",
                      "url": "https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset", "rows": len(t)}
    note["support_intent_map"] = TEAM
    note["support_caveat"] = "Bitext는 의도마다 문장 수가 비슷하게 만든 데이터라, 비율은 실제 빈도가 아니라 의도 분류의 범위입니다."

    prof = {
        "name": "general", "title": "일반 회사 · 공개 데이터",
        "about": "여러 업종의 공개 데이터에서 업종과 상관없는 모양(요일 · 흔들림 · 분포 · 비율)을 가져오고, 크기는 엔진 기본 규모에 맞췄습니다.",
        "week_demand": [round(float(v), 4) for v in week],
        "demand_q": qtable(noise),
        "refund_week": [int(v) for v in extra],
        "refund_amount_q": scaled(qtable(cv), float(np.median(cv)), BASE["refund_amount_median"], BASE["refund_amount_cap"]),
        "tier_p": [round((x + y_) / 2, 4) for x, y_ in zip(tier_r, tier_h)],
        "fraud_base": round(fraud_base, 4),
        "fraud_score_q": {"fraud": qtable(fs_f, 0, 1), "normal": qtable(fs_n, 0, 1)},
        "sec_amount_q": {"fraud": scaled(qtable(am_f), am_med, BASE["sec_amount_median"], BASE["sec_amount_cap"]),
                         "normal": scaled(qtable(am_n), am_med, BASE["sec_amount_median"], BASE["sec_amount_cap"])},
        "sat_base": round(sat_base, 4),
        "stockout_dsat": round(per_fail, 6),
        "kind_weights": kind,
        "assumed": ["악용 비율 (환불 사유 · 등급별)", "새 기기 · 해외 · 결제 속도 신호", "인력 · 재고 · 광고 비용", "문의 처리 결과의 만족 변화"],
        "sources": src, "stats": note,
        "per_dataset": {"week_demand": {"retail": r_shape.round(3).tolist(), "hotel": h_shape.round(3).tolist(), "bike": b_shape.round(3).tolist()},
                        "refund_week": {"retail": c_shape.round(3).tolist(), "hotel": hc_shape.round(3).tolist()}},
    }
    # ── 실제 데이터 시험용 기록 ────────────────────────────────────────────
    os.makedirs(REAL, exist_ok=True)
    wq = qmask.nonzero()[0]
    card = {"about": "ULB 카드 거래 뒤쪽 절반(학습에 쓰지 않은 거래) 중 점수 상위 0.5% 검토 대기열. 점수는 앞쪽 절반으로 학습한 로지스틱 회귀의 확률, "
                     "금액은 엔진 규모로 맞춘 값(중앙값 22만원 · 상한 120만원), 정답은 실제 사기 여부입니다.",
            "source": src["card"], "columns": ["fraud_score", "amount", "fraud"],
            "rows": [[round(float(p[i]), 4), round(min(BASE["sec_amount_cap"], max(1.0, amt[i] * BASE["sec_amount_median"] / am_med)), 1), int(yt[i])] for i in wq]}
    with open(os.path.join(REAL, "card_queue.json"), "w", encoding="utf-8") as fp:
        json.dump(card, fp, ensure_ascii=False)
    days = {"about": "평일 하루 수요 / 같은 요일 4주 평균. 날짜 순서 그대로입니다. 엔진의 하루 수요 흔들림 자리에 그대로 넣어 다시 돌립니다.",
            "sources": {k: src[k] for k in ("retail", "hotel", "bike")},
            "series": {"retail": [round(float(v), 3) for v in r_noise], "hotel": [round(float(v), 3) for v in h_noise],
                       "bike": [round(float(v), 3) for v in b_noise]}}
    with open(os.path.join(REAL, "demand_days.json"), "w", encoding="utf-8") as fp:
        json.dump(days, fp, ensure_ascii=False)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fp:
        json.dump(prof, fp, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in prof.items() if k not in ("sources", "per_dataset")}, ensure_ascii=False, indent=1))
    print("✓", a.out)


if __name__ == "__main__":
    main()
