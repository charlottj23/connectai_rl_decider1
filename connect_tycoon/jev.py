# -*- coding: utf-8 -*-
"""JEV 형식 · 회사의 모든 판단을 JEV(typesafe/jev-1.13, OpenRouter Decisions API)와 같은 모양으로 묻고 답합니다.

요청 (회사 → 두뇌)
    {"model": "typesafe/jev-1.13",
     "state": {"department": "refund", "company": {...오늘의 회사 상황...}, "reason": "단순 변심", "amount": 9, ...},
     "questions": {"decision": {"type": "choice", "instructions": "...", "criteria": {"full": "...", "deny": "...", ...}}}}

응답 (두뇌 → 회사)
    {"model": "...", "answers": {"decision": {"type": "choice", "choice": "deny",
                                               "probabilities": {"full": 0.1, ...}, "confidence": 0.62}}}

JEV 형식으로 답하는 것이면 무엇이든(이 패키지의 두뇌 · OpenRouter의 typesafe/jev-1.13 · 직접 만든 모델) 사장 자리에 앉힐 수 있습니다.
한 달을 돌리면 (요청, 응답, 보상)이 줄줄이 남습니다. 이것이 JEV를 강화학습시키는 데이터입니다.
"""
import json

from .company import DEFAULT_CONFIG, DEFAULT_VALUES, DEPTS, MARKETING, ORDER_UNITS, STAFFING

DEFAULT_MODEL = "typesafe/jev-1.13"
ENV_ID = "connect-company/1"
QUESTION = "decision"

INSTRUCTIONS = {
    "staffing":  "오늘 아침 직원 12명을 어느 팀에 둘지 고르세요. 자리를 넘긴 일은 야근 비용과 고객 불만이 됩니다.",
    "inventory": "오늘 물건을 발주할지 고르세요. 발주한 물건은 이틀 뒤에 도착합니다. 모자라면 품절, 넘치면 창고 폐기입니다.",
    "marketing": "오늘 광고를 어떻게 할지 고르세요. 광고 효과는 며칠 이어지지만, 손님이 늘면 사기 결제 시도도 늘어납니다.",
    "cs":        "고객 문의(message)를 어느 팀에 보낼지 고르세요. 위험한 문의를 사람이 보지 않으면 사고가 됩니다.",
    "refund":    "환불 요청을 어떻게 처리할지 고르세요. 악용이면 돈을 잃고, 정상 고객을 거절하면 만족이 떨어집니다.",
    "security":  "온라인 결제를 통과시킬지 고르세요. 사기를 통과시키면 결제 금액만큼 잃고, 정상 결제를 막으면 손님을 잃습니다.",
}


def criteria(dept, config=None):
    """부서별 선택지 (key → 설명). 회사 규모(config)에 맞춰 숫자를 적습니다."""
    c = dict(DEFAULT_CONFIG, **(config or {}))
    sb = int(c["staff_bonus"])
    if dept == "staffing":
        return {k: f"{a} · 긴급팀 {u + sb} · 결제팀 {b + sb} · 사람 확인 {h + sb}" for k, a, (u, b, h) in
                zip(DEPTS[dept]["keys"], DEPTS[dept]["actions"], [STAFFING[a] for a in DEPTS[dept]["actions"]])}
    if dept == "inventory":
        out = {}
        for k, a in zip(DEPTS[dept]["keys"], DEPTS[dept]["actions"]):
            n = int(ORDER_UNITS[a] * c["order_scale"] + 0.5)
            out[k] = "발주 안 함" if n == 0 else f"{a} · {n}개 · 수수료 5만원 · 이틀 뒤 도착 · 창고 한도 {c['warehouse']:.0f}개"
        return out
    if dept == "marketing":
        return {k: f"광고 {a} · 하루 {MARKETING[a][1]:.0f}만원" + (" · 손님 ↑ 사기 시도 ↑" if a == "증액" else "") for k, a in zip(DEPTS[dept]["keys"], DEPTS[dept]["actions"])}
    if dept == "cs":
        return {"urgent": "즉시 처리 · 긴급팀 자리를 씁니다", "normal": "일반 처리 · 대기열 (자리를 쓰지 않음)",
                "billing": "결제 담당 배정 · 결제팀 자리를 씁니다", "human": "사람 확인 · 사람 확인 자리 · 건당 0.8만원"}
    if dept == "refund":
        return {"full": "전액 환불", "partial": "부분 환불 (절반)", "deny": "거절", "human": "사람 확인 · 악용이면 사람이 거절합니다 · 건당 0.8만원"}
    if dept == "security":
        return {"allow": "허용", "block": "차단 · 정상 결제를 막으면 금액의 30% 손해", "human": "사람 확인 · 자리가 없으면 그냥 통과됩니다 · 건당 0.8만원"}
    raise ValueError(dept)


_STATE_FIELDS = {
    "staffing": ["yesterday_cs_overflow", "yesterday_refunds", "yesterday_security", "yesterday_human_overflow"],
    "inventory": ["recent_sales", "stockout_yesterday"],
    "marketing": ["recent_sales", "profit_yesterday"],
    "cs": ["message", "industry", "urgent_left", "billing_left"],
    "refund": ["reason", "tier", "amount", "fraud_score", "billing_left"],
    "security": ["amount", "fraud_score", "new_device", "overseas", "velocity"],
}


def request(dept, ev, values=None, config=None, model=DEFAULT_MODEL, company="Connect AI Company"):
    """엔진이 내보낸 판단(dept, ev)을 JEV 요청으로 바꿉니다. 숫자는 반올림하지 않습니다 (두뇌가 똑같은 관측을 다시 만들 수 있도록)."""
    v = dict(DEFAULT_VALUES, **(values or {}))
    state = {"department": dept, "department_name": DEPTS[dept]["name"], "company_name": company, "company": dict(ev["ctx"])}
    for k in _STATE_FIELDS[dept]:
        state[k] = ev[k]
    instr = f"{INSTRUCTIONS[dept]} 회사의 가치 — 이익 {v['이익']:g} · 고객 만족 {v['고객 만족']:g} · 위험 회피 {v['위험']:g}."
    return {"model": model, "state": state,
            "questions": {QUESTION: {"type": "choice", "instructions": instr, "criteria": criteria(dept, config)}}}


def validate_request(req):
    if not isinstance(req, dict) or not isinstance(req.get("state"), dict) or not isinstance(req.get("questions"), dict):
        raise ValueError("JEV 요청은 state(객체)와 questions(객체)가 있어야 합니다")
    for name, q in req["questions"].items():
        if q.get("type") != "choice" or not isinstance(q.get("criteria"), dict) or len(q["criteria"]) < 2:
            raise ValueError(f"질문 {name!r}: type='choice'와 선택지 2개 이상(criteria)이 필요합니다")
    return req


def validate_response(resp, req=None):
    if not isinstance(resp, dict) or not isinstance(resp.get("answers"), dict):
        raise ValueError("JEV 응답에는 answers(객체)가 있어야 합니다")
    for name, a in resp["answers"].items():
        if a.get("type") != "choice" or "choice" not in a:
            raise ValueError(f"답 {name!r}: type='choice'와 choice가 필요합니다")
        if req is not None:
            keys = req["questions"][name]["criteria"]
            if a["choice"] not in keys:
                raise ValueError(f"답 {name!r}: choice {a['choice']!r}는 criteria {list(keys)}에 없습니다")
            probs = a.get("probabilities")
            if probs is not None and set(probs) - set(keys):
                raise ValueError(f"답 {name!r}: probabilities에 모르는 key가 있습니다")
    return resp


def parse(resp, dept, question=QUESTION):
    """JEV 응답 → 엔진의 행동 이름."""
    choice = resp["answers"][question]["choice"]
    keys = DEPTS[dept]["keys"]
    if choice not in keys:
        raise ValueError(f"{DEPTS[dept]['name']}: choice {choice!r}는 {keys} 중 하나여야 합니다")
    return DEPTS[dept]["actions"][keys.index(choice)]


def answer(dept, probs, model, reason=None, choice=None):
    """확률(부서 행동 순서) → JEV 응답."""
    keys = DEPTS[dept]["keys"]
    p = {k: round(float(x), 4) for k, x in zip(keys, probs)}
    choice = choice or max(p, key=p.get)
    out = {"type": "choice", "choice": choice, "probabilities": p, "confidence": p[choice]}
    if reason: out["reason"] = reason
    return {"model": model, "answers": {QUESTION: out}}


class JevPolicy:
    """JEV로 답하는 아무 에이전트(agent(request) → response)를 회사에 앉힙니다. 모든 요청과 응답을 log에 남깁니다."""

    def __init__(self, agent, values=None, config=None, model=DEFAULT_MODEL, keep=True, check=True):
        self.agent, self.values, self.config, self.model = agent, values, config, model
        self.keep, self.check, self.log = keep, check, []
        self.name = getattr(agent, "name", "JEV 사장")

    def act(self, dept, obs, ev):
        req = request(dept, ev, self.values, self.config, self.model)
        resp = self.agent(req)
        if self.check:
            validate_response(resp, req)
        if self.keep:
            self.log.append({"request": req, "response": resp})
        return parse(resp, dept)


def dataset(jev_log, month_log, seed=None, env=ENV_ID):
    """JevPolicy.log + 엔진 log → (요청, 응답, 보상) 줄. 규정으로 정해진 판단은 두뇌에게 묻지 않았으므로 빠집니다.
    reward는 그 판단의 즉시 보상, return_day는 그날 남은 보상의 합(낮의 일) 또는 그날 하루 보상(아침 판단)입니다."""
    asked = [x for x in month_log if x["dept"] is not None and not x["ruled"]]
    if len(asked) != len(jev_log):
        raise ValueError("JEV 기록과 엔진 기록의 판단 수가 다릅니다")
    day_total = {}
    for x in month_log:
        day_total[x["day"]] = day_total.get(x["day"], 0.0) + x["reward"]
    rows = []
    for rec, x in zip(jev_log, asked):
        rows.append({"env": env, "seed": seed, "day": x["day"], "department": x["dept"], "request": rec["request"], "response": rec["response"],
                     "reward": round(x["reward"], 6), "day_reward": round(day_total[x["day"]], 6),
                     "outcome": {k: x[k] for k in ("truth", "effective", "overflow", "money", "dsat", "incidents") if k in x}})
    return rows


def write_jsonl(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


class OpenRouterJev:
    """OpenRouter Decisions API로 진짜 typesafe/jev-1.13에게 묻습니다 (네트워크 · API 키 필요).

        agent = OpenRouterJev(api_key=os.environ["OPENROUTER_API_KEY"])
        log, days = company.run_month(7000, JevPolicy(agent))
    """
    URL = "https://openrouter.ai/api/alpha/decisions"

    def __init__(self, api_key, model=DEFAULT_MODEL, url=None, timeout=60):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY가 필요합니다")
        self.api_key, self.model, self.url, self.timeout = api_key, model, url or self.URL, timeout
        self.name = model

    def __call__(self, req):
        import urllib.request
        body = json.dumps(dict(req, model=self.model), ensure_ascii=False).encode("utf-8")
        http = urllib.request.Request(self.url, data=body, method="POST",
                                      headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(http, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))
