"""실제 데이터 시험 · 시뮬레이터에서 배운 모델을 실제 기록 위에서 다시 채점합니다.

시뮬레이터는 분포를 데이터로 맞춰도 결국 만든 세상입니다. 그래서 학습에 쓰지 않은 실제 기록으로 한 번 더 봅니다.

  card(policy)    실제 카드 거래 검토 대기열 (ULB · 학습에 쓰지 않은 뒤쪽 절반) · 정답은 실제 사기 여부
                  모델의 '보안' 판단을 거래마다 묻고, 사기를 통과시키면 금액만큼, 정상을 막으면 금액의 30%를 잃습니다.
  demand(policy)  실제 하루 수요 기록 (소매 · 호텔 · 자전거 대여) · 엔진의 하루 수요 흔들림 자리에 실제 기록을 그대로 넣어
                  한 달씩 다시 돌립니다 (재고 · 광고 · 인력 판단이 실제 수요의 오르내림을 만납니다).

    from connect_tycoon import backtest
    backtest.card(brain)          # {"cases": 713, "fraud": 177, "loss": ..., "caught": ..., ...}
    backtest.demand(brain, company)
"""
import json
import os

from .company import DEFAULT_RULES, HUMAN, HUMAN_COST, Decision  # noqa: F401

_DIR = os.path.join(os.path.dirname(__file__), "data", "real")
_cache = {}


def _load(name):
    if name not in _cache:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def available():
    return os.path.exists(os.path.join(_DIR, "card_queue.json"))


def card(policy, company=None, rules=None):
    """실제 거래 하나하나에 '허용 · 차단 · 사람 확인'을 묻습니다.
    실제 데이터에는 새 기기 · 해외 · 결제 속도가 없어 평균값으로 채웁니다 (사기 점수와 금액으로 판단하게 됩니다).
    사람 확인은 자리가 있다고 보고, 건당 0.8만원에 사람이 정답대로 처리합니다."""
    from . import make_company
    co = company or make_company(profile="general")
    rows = _load("card_queue")["rows"]
    fb = sum(r[2] for r in rows) / len(rows)
    nd, ov, vel = 0.2 + 0.5 * fb, 0.1 + 0.4 * fb, 0.25 + 0.45 * fb
    s = {"sat": co.sat_base, "stock": 150.0, "incoming": 0.0, "ad": 0.0, "cap": {HUMAN: 4}, "left": {HUMAN: 4}, "mk": "유지",
         "cash": 0.0, "pipeline": [0.0, 0.0]}
    rules = co.rules if rules is None else [tuple(r) for r in rules]
    out = {"cases": len(rows), "fraud": 0, "caught": 0, "missed": 0, "false_block": 0, "human": 0, "loss": 0.0, "fraud_loss": 0.0,
           "block_loss": 0.0, "human_cost": 0.0}
    for k, (fs, amount, fraud) in enumerate(rows):
        day, t = k % co.days, 0.5
        obs = co._common(s, day, t) + [amount / 40.0, fs, nd, ov, vel]
        ev = {"ctx": co._ctx(s, day, t), "amount": amount, "fraud_score": fs, "new_device": nd, "overseas": ov, "velocity": vel}
        ruled = next((a for d, c, v, a in rules if d == "security" and c == "사기 점수 ≥" and fs >= v), None)
        a = ruled or policy.act("security", obs, ev)
        out["fraud"] += fraud
        if a == HUMAN:
            out["human"] += 1; out["human_cost"] += HUMAN_COST; out["caught"] += fraud
        elif a == "차단":
            if fraud: out["caught"] += 1
            else: out["false_block"] += 1; out["block_loss"] += 0.3 * amount
        elif fraud:
            out["missed"] += 1; out["fraud_loss"] += amount
    out["loss"] = out["fraud_loss"] + out["block_loss"] + out["human_cost"]
    out["allow_all_loss"] = sum(r[1] for r in rows if r[2])
    out["saved"] = 1.0 - out["loss"] / max(1e-9, out["allow_all_loss"])          # 모두 통과시켰을 때보다 줄인 손실
    return out


def demand(policy, company=None, sources=("retail", "hotel", "bike"), months=None):
    """실제 하루 수요 기록으로 한 달씩 다시 돌립니다 → 기록마다 평균 한 달 이익 · 품절일 · 만족."""
    from . import make_company
    from .train import evaluate
    co = company or make_company(profile="general")
    series = _load("demand_days")["series"]
    out = {}
    for name in sources:
        seq = series[name]
        n = len(seq) // co.days if months is None else min(months, len(seq) // co.days)
        c = co.with_config(co.cfg)
        c.replay = seq
        r = evaluate(c, policy, seeds=range(n))
        out[name] = {"months": n, "profit": r["profit"], "stockout_days": r["stockout_days"], "sat": r["sat"]}
    ps = [v["profit"] for v in out.values()]
    out["profit"] = sum(ps) / len(ps)
    return out


def report(policies, company=None):
    """여러 모델을 나란히 · {이름: {"card": ..., "demand": ...}}."""
    return {name: {"card": card(p, company), "demand": demand(p, company)} for name, p in policies.items()}
