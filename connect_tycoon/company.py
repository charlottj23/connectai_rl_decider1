# -*- coding: utf-8 -*-
"""CONNECT TYCOON 회사 엔진 (env id: connect-company/1)

한 달(영업일 20일) 동안 회사 하나를 운영합니다.

    아침  인력 배치 · 재고 발주 · 마케팅            (하루에 한 번씩)
    낮    고객 문의 · 환불 요청 · 보안 경보        (섞여서 들어옵니다)
    저녁  판매 · 매출 · 재고 비용 · 고객 만족 정산

판단의 결과는 늦게 돌아옵니다. 발주는 이틀 뒤에 도착하고, 광고 효과는 며칠 이어지고, 고객 만족은 다음 날의 수요를 바꿉니다.
'사람 확인' 자리는 고객센터 · 환불 · 보안이 함께 씁니다.

엔진은 제너레이터(episode)로 짜여 있습니다. 판단이 필요할 때마다 Decision(dept, obs, ev)을 내보내고, 행동 이름을 돌려받습니다.
같은 엔진 하나를 게임 화면 · Gymnasium 환경 · JEV 에이전트가 함께 씁니다. 난수는 mulberry32라서 같은 시드면 같은 한 달입니다.
기본 설정(DEFAULT_CONFIG)이면 CONNECT AI LAB 강의 Colab의 connect_company.py와 숫자까지 같은 회사입니다.
"""
from collections import namedtuple

from .rng import mulberry32

DAYS = 20
WEEK = ["월", "화", "수", "목", "금"]
HUMAN, URGENT, BILLING = "사람 확인", "즉시 처리", "결제 담당 배정"

# ── 부서와 선택지 (JEV criteria의 key) ──────────────────────────────────────
DEPTS = {
    "staffing":  {"name": "인력 배치", "actions": ["균형", "고객센터 집중", "결제팀 집중", "사람 확인 집중"], "keys": ["balanced", "cs_focus", "billing_focus", "review_focus"]},
    "inventory": {"name": "재고 발주", "actions": ["발주 안 함", "소량 발주", "대량 발주"], "keys": ["none", "small", "large"]},
    "marketing": {"name": "마케팅", "actions": ["중단", "유지", "증액"], "keys": ["stop", "keep", "boost"]},
    "cs":        {"name": "고객센터", "actions": [URGENT, "일반 처리", BILLING, HUMAN], "keys": ["urgent", "normal", "billing", "human"]},
    "refund":    {"name": "환불", "actions": ["전액 환불", "부분 환불", "거절", HUMAN], "keys": ["full", "partial", "deny", "human"]},
    "security":  {"name": "보안", "actions": ["허용", "차단", HUMAN], "keys": ["allow", "block", "human"]},
}
DEPT_ORDER = ["staffing", "inventory", "marketing", "cs", "refund", "security"]
MORNING = ("staffing", "inventory", "marketing")
DAYTIME = ("cs", "refund", "security")

STAFFING = {"균형": (4, 4, 4), "고객센터 집중": (8, 2, 3), "결제팀 집중": (2, 8, 3), "사람 확인 집중": (2, 2, 8)}   # 긴급팀 · 결제팀 · 사람 확인
ORDER_UNITS = {"발주 안 함": 0, "소량 발주": 50, "대량 발주": 120}
MARKETING = {"중단": (0.0, 0.0), "유지": (0.25, 8.0), "증액": (0.5, 20.0)}       # (광고 효과, 하루 비용 만원)
PRICE, ORDER_FEE, HOLD_COST, HUMAN_COST, SPOIL = 3.0, 5.0, 0.05, 0.8, 0.02     # 만원 · 원가는 팔릴 때 잡습니다(발생주의)
WEEK_DEMAND = [1.0, 0.9, 0.95, 1.05, 1.25]
CS_WEEK, REFUND_WEEK = [6, 2, 0, 0, 0], [0, 0, 1, 2, 5]                          # 요일별 추가 건수
REASONS, TIERS = ["불량", "미배송", "단순 변심", "의심"], ["신규", "단골", "VIP"]
ABUSE_BASE = {"불량": 0.05, "미배송": 0.1, "단순 변심": 0.25, "의심": 0.6}
ABUSE_TIER = {"신규": 0.15, "단골": 0.0, "VIP": -0.05}
KIND_WEIGHTS = [("info", .45), ("urgent", .2), ("billing", .2), ("risk", .15)]

# 회사의 가치: 보상 = 이익 × (만원/10) + 고객 만족 × (변화 ×100) − 위험 × (사고 ×5)
DEFAULT_VALUES = {"이익": 1.0, "고객 만족": 1.0, "위험": 1.0}
# 회사 규정 (하향식 통제): (부서, 조건 이름, 기준값, 행동). 규정이 걸리면 두뇌에게 묻지 않습니다.
DEFAULT_RULES = [("cs", "위험 신호", 1, HUMAN), ("security", "사기 점수 ≥", 0.95, "차단")]
# 회사 규모 · 게임의 업그레이드가 바꾸는 값. 기본값이면 강의 Colab과 똑같은 회사입니다.
DEFAULT_CONFIG = {
    "warehouse": 250.0,     # 창고 한도 (넘치면 버림)
    "base_demand": 40.0,    # 기본 손님 수
    "unit_cost": 1.5,       # 원가 (판매가 3.0만원)
    "order_scale": 1.0,     # 발주 한 번의 양 배율
    "staff_bonus": 0,       # 팀마다 늘어난 직원 수
    "wage": 0.0,            # 늘린 직원의 하루 인건비 (만원)
    "ad_power": 1.0,        # 광고 효과 배율
    "fraud_tool": 0,        # 사기 탐지 AI 단계 (사기 점수가 또렷해짐)
    "extra_cs": 0,          # 하루 추가 문의
    "extra_refund": 0,      # 하루 추가 환불 요청
}

COMMON = ["하루 진행", "월", "화", "수", "목", "금", "고객 만족", "재고", "입고 예정", "광고 효과", "남은 사람 확인", "낮 시간"]
OBS_NAMES = {
    "staffing":  COMMON + ["어제 문의 초과", "어제 환불 건수", "어제 보안 건수", "어제 사람 확인 초과"],
    "inventory": COMMON + ["최근 판매", "어제 품절"],
    "marketing": COMMON + ["최근 판매", "어제 이익"],
    "cs":        COMMON + ["점수:즉시", "점수:일반", "점수:결제", "점수:사람", "신호:긴급", "신호:결제", "신호:위험", "확신", "남은 긴급팀", "남은 결제팀", "낯선 업종"],
    "refund":    COMMON + ["환불 금액", "불량", "미배송", "단순 변심", "의심", "신규", "단골", "VIP", "사기 점수", "남은 결제팀"],
    "security":  COMMON + ["결제 금액", "사기 점수", "새 기기", "해외", "결제 속도"],
}
OBS_DIM = {d: len(v) for d, v in OBS_NAMES.items()}

Decision = namedtuple("Decision", "dept obs ev")

# ── 프로필 · 공개 데이터나 한 회사의 기록으로 맞춘 분포 ──────────────────────
# 프로필이 없으면 강의 엔진과 숫자까지 같은 회사입니다. 프로필은 난수를 뽑는 횟수와 순서를 바꾸지 않고,
# 같은 난수 r 하나를 분위수 표에 넣어(역누적분포) 데이터의 분포대로 값을 뽑습니다.
PROFILE_KEYS = {"week_demand", "demand_q", "refund_week", "refund_amount_q", "tier_p", "fraud_base", "fraud_score_q",
                "sec_amount_q", "sat_base", "stockout_dsat", "kind_weights"}


def load_profile(name_or_path=None):
    """프로필 이름(data/profiles/<이름>.json) · 파일 경로 · dict → dict. None이나 "lecture"이면 None (강의 엔진 그대로)."""
    import json
    import os
    if name_or_path is None or name_or_path == "lecture":
        return None
    if isinstance(name_or_path, dict):
        return name_or_path
    if name_or_path not in _PROFILE_CACHE:
        path = name_or_path if os.path.exists(name_or_path) else os.path.join(os.path.dirname(__file__), "data", "profiles", name_or_path + ".json")
        with open(path, encoding="utf-8") as f:
            _PROFILE_CACHE[name_or_path] = json.load(f)
    return _PROFILE_CACHE[name_or_path]


_PROFILE_CACHE = {}


def profiles():
    """패키지에 들어 있는 프로필 이름들."""
    import os
    d = os.path.join(os.path.dirname(__file__), "data", "profiles")
    return ["lecture"] + sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else ["lecture"]


def _q(table, u):
    """분위수 표(0..1 사이를 고르게 나눈 점의 값) → 난수 u에 해당하는 값 (선형 보간)."""
    x = u * (len(table) - 1); i = min(int(x), len(table) - 2)
    return table[i] + (table[i + 1] - table[i]) * (x - i)


def _pick(p, u):
    acc = 0.0
    for i, w in enumerate(p):
        acc += w
        if u < acc: return i
    return len(p) - 1


def _clip(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


class Company:
    """회사 하나. episode(seed)는 판단을 하나씩 묻는 제너레이터, run_month(seed, policy)는 한 달을 끝까지 돌립니다.

    intuition : 고객 문의를 읽는 1주차 두뇌 (intuition.ConnectBrain)
    pool      : 고객 문의 모음 (data/pool.json)
    values    : 회사의 가치 (보상의 가중치)
    rules     : 회사 규정 (두뇌보다 먼저 적용)
    config    : 회사 규모 (DEFAULT_CONFIG의 일부만 바꿔도 됩니다)
    profile   : 데이터로 맞춘 분포 (이름 · 경로 · dict). 없으면 강의 엔진 그대로 · load_profile 참고
    """

    def __init__(self, intuition, pool, industry=None, values=None, rules=None, days=DAYS, home_share=0.5, config=None, profile=None):
        self.intuition, self.pool = intuition, pool
        self.items = pool["items"]
        self.industry = industry or intuition.spec.get("experience")
        self.values = dict(DEFAULT_VALUES, **(values or {}))
        self.rules = [tuple(r) for r in (rules if rules is not None else DEFAULT_RULES)]
        self.days, self.home_share = days, home_share
        unknown = set(config or {}) - set(DEFAULT_CONFIG)
        if unknown:
            raise ValueError(f"모르는 설정: {sorted(unknown)}")
        self.cfg = dict(DEFAULT_CONFIG, **(config or {}))
        self.set_profile(profile)
        self.cs_scores, self.cs_signals, self.cs_theta = [], [], []
        for it in self.items:                                   # 고객 문의 두뇌의 직관을 미리 계산
            self.cs_scores.append([float(v) for v in intuition.scores(it["text"])])
            self.cs_signals.append([float(v) for v in list(intuition.detect(it["text"]).values())[:3]])
            self.cs_theta.append(intuition.decide_theta(it["text"])["action"])
        self.by = {}
        for i, it in enumerate(self.items):
            self.by.setdefault((it["kind"], it["industry"] == self.industry), []).append(i)

    def set_profile(self, profile):
        P = load_profile(profile) or {}
        self.profile = P or None
        self.profile_name = P.get("name", "custom") if P else "lecture"
        self.week_demand = P.get("week_demand", WEEK_DEMAND)
        self.refund_week = P.get("refund_week", REFUND_WEEK)
        self.kind_weights = [tuple(x) for x in P.get("kind_weights", KIND_WEIGHTS)]
        self.sat_base = P.get("sat_base", 0.7)
        self.stockout_dsat = P.get("stockout_dsat", 0.001)
        self.replay = None                      # 실제 하루 수요 기록 (backtest.demand가 넣습니다)
        return self

    def with_config(self, config=None, values=None, rules=None, profile=False):
        """직관 계산을 다시 하지 않고 설정만 바꾼 회사를 만듭니다. profile을 주면 프로필도 바꿉니다."""
        other = object.__new__(Company)
        other.__dict__.update(self.__dict__)
        if profile is not False: other.set_profile(profile)
        other.cfg = dict(DEFAULT_CONFIG, **(config or {}))
        if values is not None: other.values = dict(DEFAULT_VALUES, **values)
        if rules is not None: other.rules = [tuple(r) for r in rules]
        return other

    # ── 보상 · 관측 ────────────────────────────────────────────────────────
    def reward(self, money=0.0, dsat=0.0, incidents=0):
        v = self.values
        return v["이익"] * money / 10.0 + v["고객 만족"] * dsat * 100.0 - v["위험"] * incidents * 5.0

    def _common(self, s, day, t):
        wk = [0.0] * 5; wk[day % 5] = 1.0
        return [day / self.days] + wk + [s["sat"], min(s["stock"], 300.0) / 200.0, s["incoming"] / 200.0, s["ad"] / 2.0,
                                        s["left"][HUMAN] / max(1.0, s["cap"][HUMAN]), t]

    def _ctx(self, s, day, t):
        """JEV state의 company 부분 (사람이 읽을 수 있는 값)."""
        return {"day": day, "weekday": WEEK[day % 5], "sat": s["sat"], "stock": s["stock"], "incoming": s["incoming"], "ad": s["ad"],
                "human_left": s["left"][HUMAN] / max(1.0, s["cap"][HUMAN]), "human_seats_left": max(s["left"][HUMAN], 0), "human_seats": s["cap"][HUMAN],
                "time": t, "days": self.days}

    def _rule(self, dept, ev):
        for d, cond, val, action in self.rules:
            if d != dept: continue
            if dept == "cs" and cond == "위험 신호" and ev["signals"][2] >= val: return action
            if dept == "security" and cond == "사기 점수 ≥" and ev["fraud_score"] >= val: return action
            if dept == "refund" and cond == "사기 점수 ≥" and ev["fraud_score"] >= val: return action
            if dept == "refund" and cond == "금액 ≥" and ev["amount"] >= val: return action
        return None

    def _decide(self, dept, obs, ev, rule):
        if rule is not None:
            return rule, True
        a = yield Decision(dept, obs, ev)
        if a not in DEPTS[dept]["actions"]:
            raise ValueError(f"{DEPTS[dept]['name']} 부서의 행동은 {DEPTS[dept]['actions']} 중 하나여야 합니다: {a!r}")
        return a, False

    @staticmethod
    def _take(s, team):
        if team not in s["left"]: return False
        over = s["left"][team] <= 0
        s["left"][team] -= 1
        return over

    # ── 한 달 ─────────────────────────────────────────────────────────────
    def run_month(self, seed, policy):
        """policy.act(dept, obs, ev) → 행동 이름. 반환: (log, days) — 판단 기록과 하루 정산."""
        gen = self.episode(seed)
        try:
            d = next(gen)
            while True:
                d = gen.send(policy.act(d.dept, d.obs, d.ev))
        except StopIteration as stop:
            return stop.value

    def episode(self, seed, log=None, days=None):
        """판단이 필요할 때마다 Decision을 내보내는 제너레이터. 끝나면 (log, days)를 돌려줍니다.
        log와 days 리스트를 넘기면 진행 중에도 바깥에서 읽을 수 있습니다 (Gymnasium 환경이 보상을 이렇게 읽습니다)."""
        r = mulberry32(seed); C = self.cfg; sb = C["staff_bonus"]
        P = self.profile or {}
        s = {"sat": self.sat_base, "stock": 150.0, "incoming": 0.0, "pipeline": [0.0, 0.0], "ad": 0.0, "cash": 0.0, "mk": "유지",
             "cap": {}, "left": {}, "hist_sales": [60.0, 60.0, 60.0], "y": {"cs_over": 0, "refunds": 4, "security": 4, "human_over": 0, "stockout": 0, "profit": 60.0}}
        log = [] if log is None else log
        days = [] if days is None else days
        for day in range(self.days):
            wd = day % 5
            delivered = s["pipeline"][0]                                         # 입고: 이틀 전 발주가 도착
            s["stock"] += s["pipeline"][0]; s["pipeline"] = [s["pipeline"][1], 0.0]; s["incoming"] = s["pipeline"][0]
            money_day, dsat_day, inc_day = 0.0, 0.0, 0
            waste = max(0.0, s["stock"] - C["warehouse"]); s["stock"] -= waste   # 창고에 못 들어간 물건은 버립니다
            overflow = waste
            stock_morning = s["stock"]
            cnt = {"cs_over": 0, "refunds": 0, "security": 0, "human_over": 0, "human": 0, "cs": 0, "fraud_loss": 0.0, "abuse_loss": 0.0}
            day_start = len(log)

            # ── 아침 ① 인력 배치
            s["cap"] = {URGENT: 4 + sb, BILLING: 4 + sb, HUMAN: 4 + sb}; s["left"] = dict(s["cap"])
            y = s["y"]
            obs = self._common(s, day, 0.0) + [min(y["cs_over"], 5) / 5.0, y["refunds"] / 6.0, y["security"] / 6.0, min(y["human_over"], 5) / 5.0]
            ev = {"ctx": self._ctx(s, day, 0.0), "yesterday_cs_overflow": y["cs_over"], "yesterday_refunds": y["refunds"],
                  "yesterday_security": y["security"], "yesterday_human_overflow": y["human_over"]}
            a, _ = yield from self._decide("staffing", obs, ev, None)
            u, b, h = STAFFING[a]; s["cap"] = {URGENT: u + sb, BILLING: b + sb, HUMAN: h + sb}; s["left"] = dict(s["cap"])
            money_day -= C["wage"]
            log.append({"day": day, "dept": "staffing", "obs": obs, "action": a, "reward": self.reward(money=-C["wage"]), "ruled": False,
                        "money": -C["wage"], "ev": ev, "cap": dict(s["cap"])})
            # ── 아침 ② 재고 발주
            recent = sum(s["hist_sales"][-3:]) / 3.0
            obs = self._common(s, day, 0.0) + [recent / 100.0, 1.0 if y["stockout"] else 0.0]
            ev = {"ctx": self._ctx(s, day, 0.0), "recent_sales": recent, "stockout_yesterday": bool(y["stockout"])}
            a, _ = yield from self._decide("inventory", obs, ev, None)
            units = int(ORDER_UNITS[a] * C["order_scale"] + 0.5); cost = ORDER_FEE if units else 0.0
            s["pipeline"][1] += units; money_day -= cost
            log.append({"day": day, "dept": "inventory", "obs": obs, "action": a, "reward": self.reward(money=-cost), "ruled": False,
                        "money": -cost, "units": units, "ev": ev})
            # ── 아침 ③ 마케팅
            obs = self._common(s, day, 0.0) + [recent / 100.0, y["profit"] / 100.0]
            ev = {"ctx": self._ctx(s, day, 0.0), "recent_sales": recent, "profit_yesterday": y["profit"]}
            a, _ = yield from self._decide("marketing", obs, ev, None)
            eff, spend = MARKETING[a]; s["ad"] = 0.6 * s["ad"] + eff * C["ad_power"]; s["mk"] = a; money_day -= spend
            log.append({"day": day, "dept": "marketing", "obs": obs, "action": a, "reward": self.reward(money=-spend), "ruled": False,
                        "money": -spend, "ev": ev})

            # ── 낮: 오늘 들어올 일
            n_cs = 7 + int(r() * 4) + CS_WEEK[wd] + C["extra_cs"]
            n_ref = 2 + int(r() * 3) + self.refund_week[wd] + C["extra_refund"]
            mk_level = ["중단", "유지", "증액"].index(s["mk"])
            n_sec = 2 + int(r() * 3) + mk_level
            events = ["cs"] * n_cs + ["refund"] * n_ref + ["security"] * n_sec
            for i in range(len(events) - 1, 0, -1):                              # Fisher-Yates
                j = int(r() * (i + 1)); events[i], events[j] = events[j], events[i]
            total = len(events)
            for k, kind in enumerate(events):
                t = (k + 1) / (total + 1)
                if kind == "cs":
                    rec = yield from self._cs_event(r, s, day, t); cnt["cs"] += 1
                elif kind == "refund":
                    rec = yield from self._refund_event(r, s, day, t); cnt["refunds"] += 1
                else:
                    rec = yield from self._security_event(r, s, day, t, mk_level); cnt["security"] += 1
                money_day += rec["money"]; dsat_day += rec["dsat"]; inc_day += rec["incidents"]
                if rec["overflow"]:
                    if rec["action"] == HUMAN: cnt["human_over"] += 1
                    elif kind == "cs": cnt["cs_over"] += 1
                if rec["action"] == HUMAN: cnt["human"] += 1
                cnt["fraud_loss"] += rec.get("fraud_loss", 0.0) if kind == "security" else 0.0
                cnt["abuse_loss"] += rec.get("fraud_loss", 0.0) if kind == "refund" else 0.0
                rec["reward"] = self.reward(rec["money"], rec["dsat"], rec["incidents"])
                rec["t"] = t; rec["left"] = dict(s["left"]); rec["sat_after"] = s["sat"]
                log.append(rec)

            # ── 저녁: 판매 정산
            u = r(); noise = _q(P["demand_q"], u) if "demand_q" in P else 0.85 + 0.3 * u
            if self.replay: noise = self.replay[(seed * self.days + day) % len(self.replay)]      # 실제 기록의 하루 수요를 그대로
            demand = C["base_demand"] * self.week_demand[wd] * (1.0 + 1.6 * s["ad"] / (1.0 + s["ad"])) * (0.6 + 0.8 * s["sat"]) * noise
            demand = float(int(demand))
            sales = min(demand, s["stock"]); unmet = demand - sales
            s["stock"] -= sales
            spoiled = float(int(s["stock"] * SPOIL)); s["stock"] -= spoiled; waste += spoiled
            hold = s["stock"] * HOLD_COST + waste * C["unit_cost"]
            dsat = -min(self.stockout_dsat * unmet, 0.04)
            revenue = sales * (PRICE - C["unit_cost"])                              # 판매 이익 = 판매가 − 원가
            s["sat"] = _clip(s["sat"] + dsat)
            s["sat"] = self.sat_base + (s["sat"] - self.sat_base) * 0.9
            money_eve = revenue - hold
            money_day += money_eve; dsat_day += dsat
            s["hist_sales"].append(sales); s["hist_sales"] = s["hist_sales"][-3:]
            profit = money_day
            s["cash"] += money_day
            log.append({"day": day, "dept": None, "action": None, "reward": self.reward(money_eve, dsat, 0), "ruled": True,
                        "money": money_eve, "dsat": dsat, "sales": sales, "demand": demand, "unmet": unmet, "waste": waste,
                        "revenue": revenue, "hold": hold, "spoiled": spoiled})
            s["y"] = {"cs_over": cnt["cs_over"], "refunds": cnt["refunds"], "security": cnt["security"], "human_over": cnt["human_over"],
                      "stockout": 1 if unmet > 0 else 0, "profit": profit}
            days.append({"day": day, "weekday": WEEK[wd], "profit": profit, "cash": s["cash"], "sat": s["sat"], "stock": s["stock"],
                         "stock_morning": stock_morning, "delivered": delivered, "overflow_waste": overflow,
                         "sales": sales, "demand": demand, "unmet": unmet, "incidents": inc_day, "human": cnt["human"], "human_over": cnt["human_over"],
                         "cs_over": cnt["cs_over"], "waste": waste, "cap": dict(s["cap"]), "staffing": log[day_start]["action"], "order": log[day_start + 1]["action"],
                         "units": log[day_start + 1]["units"], "marketing": s["mk"], "fraud_loss": cnt["fraud_loss"], "abuse_loss": cnt["abuse_loss"],
                         "revenue": revenue, "reward": sum(x["reward"] for x in log[day_start:]),
                         "events": {"cs": cnt["cs"], "refund": cnt["refunds"], "security": cnt["security"]}})
        return log, days

    # ── 낮의 일 세 가지 ─────────────────────────────────────────────────────
    def _cs_event(self, r, s, day, t):
        KW = self.kind_weights
        u = r() * sum(w for _, w in KW); acc = 0.0; kind = KW[-1][0]
        for kk, w in KW:
            acc += w
            if u < acc: kind = kk; break
        home = r() < self.home_share
        bucket = self.by.get((kind, home)) or self.by[(kind, not home)]
        i = bucket[int(r() * len(bucket))]
        it = self.items[i]; sc = self.cs_scores[i]; top = sorted(sc)
        urgent_left = max(s["left"][URGENT], 0) / max(1, s["cap"][URGENT])
        billing_left = max(s["left"][BILLING], 0) / max(1, s["cap"][BILLING])
        obs = self._common(s, day, t) + list(sc) + list(self.cs_signals[i]) + [top[-1] - top[-2], urgent_left, billing_left,
                                                                              1.0 if it["industry"] != self.industry else 0.0]
        ev = {"ctx": self._ctx(s, day, t), "message": it["text"], "industry": it["industry"], "item": i,
              "signals": list(self.cs_signals[i]), "theta": self.cs_theta[i], "urgent_left": urgent_left, "billing_left": billing_left}
        a, ruled = yield from self._decide("cs", obs, ev, self._rule("cs", ev))
        truth = it["label"]
        over = self._take(s, a) if a != "일반 처리" else False
        money, dsat, inc = 0.0, 0.0, 0
        if a == HUMAN: money -= HUMAN_COST
        if a == truth: dsat += 0.003
        elif truth == HUMAN: inc += 1; dsat -= 0.02                       # 사람이 봐야 할 위험 문의를 놓침
        elif truth == URGENT and a != HUMAN: dsat -= 0.015
        elif a == HUMAN: pass                                              # 필요 없는 사람 확인: 비용만
        else: dsat -= 0.008
        if over: dsat -= 0.01; money -= 1.0                                # 자리를 넘기면 야근 비용과 불만
        s["sat"] = _clip(s["sat"] + dsat)
        return {"day": day, "dept": "cs", "obs": obs, "action": a, "truth": truth, "ruled": ruled, "overflow": over,
                "money": money, "dsat": dsat, "incidents": inc, "item": i, "ev": ev}

    def _refund_event(self, r, s, day, t):
        P = self.profile or {}
        reason = REASONS[int(r() * 4)]
        u = r(); tier = TIERS[_pick(P["tier_p"], u) if "tier_p" in P else int(u * 3)]
        u = r(); amount = round(_q(P["refund_amount_q"], u), 1) if "refund_amount_q" in P else 1.0 + float(int(u * 12))
        abuse = r() < _clip(ABUSE_BASE[reason] + ABUSE_TIER[tier])          # 숨은 진실 (두뇌에게는 보이지 않습니다)
        sh = 0.1 * self.cfg["fraud_tool"]                                   # 사기 탐지 AI: 점수가 더 또렷해집니다
        fs = _clip(0.35 + 0.6 * r() + sh) if abuse else _clip(0.6 * r() - sh)
        billing_left = max(s["left"][BILLING], 0) / max(1, s["cap"][BILLING])
        obs = self._common(s, day, t) + [amount / 12.0] + [1.0 if reason == x else 0.0 for x in REASONS] + [1.0 if tier == x else 0.0 for x in TIERS] + \
            [fs, billing_left]
        ev = {"ctx": self._ctx(s, day, t), "reason": reason, "tier": tier, "amount": amount, "fraud_score": fs, "billing_left": billing_left}
        a, ruled = yield from self._decide("refund", obs, ev, self._rule("refund", ev))
        money, dsat, over, loss = 0.0, 0.0, False, 0.0
        vip = 2.0 if tier == "VIP" else 1.0
        effective = a
        if a == HUMAN:
            over = self._take(s, HUMAN); money -= HUMAN_COST
            effective = ("전액 환불" if over else "거절") if abuse else "전액 환불"   # 자리가 없으면 확인 못 하고 그냥 환불
            if over: dsat -= 0.01; money -= 1.0
        if effective in ("전액 환불", "부분 환불"):
            if self._take(s, BILLING): dsat -= 0.01; money -= 1.0; over = True
            pay = amount if effective == "전액 환불" else amount / 2.0
            money -= pay
            if abuse: loss = pay
            else: dsat += 0.01 * vip if effective == "전액 환불" else -0.004 * vip
        elif effective == "거절" and not abuse:
            dsat -= 0.03 * vip
        s["sat"] = _clip(s["sat"] + dsat)
        return {"day": day, "dept": "refund", "obs": obs, "action": a, "effective": effective, "truth": "악용" if abuse else "정상", "ruled": ruled,
                "overflow": over, "money": money, "dsat": dsat, "incidents": 0, "fraud_loss": loss, "ev": ev}

    def _security_event(self, r, s, day, t, mk_level):
        P = self.profile or {}
        ua = r()
        fraud = r() < P.get("fraud_base", 0.2) + 0.08 * mk_level
        if "sec_amount_q" in P: amount = round(_q(P["sec_amount_q"]["fraud" if fraud else "normal"], ua), 1)
        else: amount = 5.0 + float(int(ua * 36))
        sh = 0.1 * self.cfg["fraud_tool"]
        u = r()
        if "fraud_score_q" in P: fs = _clip(_q(P["fraud_score_q"]["fraud" if fraud else "normal"], u) + (sh if fraud else -sh))
        else: fs = _clip(0.3 + 0.7 * u + sh) if fraud else _clip(0.6 * u - sh)
        nd = 1.0 if r() < (0.7 if fraud else 0.2) else 0.0
        ov = 1.0 if r() < (0.5 if fraud else 0.1) else 0.0
        vel = (0.4 + 0.6 * r()) if fraud else 0.5 * r()
        obs = self._common(s, day, t) + [amount / 40.0, fs, nd, ov, vel]
        ev = {"ctx": self._ctx(s, day, t), "amount": amount, "fraud_score": fs, "new_device": nd, "overseas": ov, "velocity": vel}
        a, ruled = yield from self._decide("security", obs, ev, self._rule("security", ev))
        money, dsat, inc, over, loss = 0.0, 0.0, 0, False, 0.0
        effective = a
        if a == HUMAN:
            over = self._take(s, HUMAN); money -= HUMAN_COST
            effective = "허용" if over else ("차단" if fraud else "허용")          # 자리가 없으면 확인 못 하고 통과
        if effective == "허용" and fraud: money -= amount; inc += 1; loss = amount
        elif effective == "차단" and not fraud: money -= amount * 0.3; dsat -= 0.01
        if over: dsat -= 0.005; money -= 1.0
        s["sat"] = _clip(s["sat"] + dsat)
        return {"day": day, "dept": "security", "obs": obs, "action": a, "effective": effective, "truth": "사기" if fraud else "정상", "ruled": ruled,
                "overflow": over, "money": money, "dsat": dsat, "incidents": inc, "fraud_loss": loss, "ev": ev}


def load_pool(path=None):
    """고객 문의 모음 (패키지에 들어 있습니다)."""
    import json
    import os
    path = path or os.path.join(os.path.dirname(__file__), "data", "pool.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
