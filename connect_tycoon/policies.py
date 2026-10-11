# -*- coding: utf-8 -*-
"""사장 여러 명 · 모두 act(dept, obs, ev) → 행동 이름 하나로 판단합니다.

RulePolicy     사람이 정한 규칙 (강의의 '사람이 정한 전전두엽')
LinearPolicy   부서마다 선형 소프트맥스 머리 하나 · 강화학습으로 배우는 두뇌
OwnerPolicy    게임에서 플레이어가 내린 지시 (날짜별 계획표)
RandomPolicy   무작위 (기준선)
JevPolicy      JEV 형식으로 묻고 답하는 아무 에이전트를 회사에 앉힙니다 (jev.py)
"""
import numpy as np

from .company import DEPT_ORDER, DEPTS, HUMAN, MORNING, OBS_NAMES


class RulePolicy:
    """사람이 정한 전전두엽: 사람이 직접 정한 규칙과 멈춤 기준."""
    name = "규칙 사장"

    def act(self, dept, obs, ev):
        if dept == "staffing": return "균형"
        if dept == "inventory":
            stock, incoming = obs[7] * 200.0, obs[8] * 200.0
            return "대량 발주" if stock + incoming < 120 else "소량 발주" if stock + incoming < 180 else "발주 안 함"
        if dept == "marketing": return "유지"
        if dept == "cs": return ev["theta"]
        if dept == "refund":
            return HUMAN if (ev["amount"] >= 8 or ev["fraud_score"] >= 0.5) else "전액 환불"
        if dept == "security":
            fs = ev["fraud_score"]
            return "차단" if fs >= 0.8 else HUMAN if fs >= 0.4 else "허용"
        raise ValueError(dept)


HeuristicPolicy = RulePolicy   # 강의 Colab의 이름


class RandomPolicy:
    name = "무작위 사장"

    def __init__(self, seed=0):
        self.rng = np.random.default_rng(seed)

    def act(self, dept, obs, ev):
        acts = DEPTS[dept]["actions"]
        return acts[int(self.rng.integers(len(acts)))]


class LinearPolicy:
    """보상으로 배우는 전전두엽: 부서마다 선형 소프트맥스 머리(head) 하나씩."""
    name = "AI 사장"

    def __init__(self, heads=None):
        if heads is None:
            heads = {d: {"W": np.zeros((len(DEPTS[d]["actions"]), len(OBS_NAMES[d]))), "b": np.zeros(len(DEPTS[d]["actions"]))} for d in DEPT_ORDER}
        self.heads = {d: {"W": np.asarray(h["W"], dtype=float), "b": np.asarray(h["b"], dtype=float)} for d, h in heads.items()}
        for d in DEPT_ORDER:
            W = self.heads[d]["W"]
            if W.shape != (len(DEPTS[d]["actions"]), len(OBS_NAMES[d])):
                raise ValueError(f"{d} 머리의 크기가 맞지 않습니다: {W.shape}")

    def logits(self, dept, obs):
        h = self.heads[dept]
        return h["W"] @ np.asarray(obs, dtype=float) + h["b"]

    def probs(self, dept, obs):
        z = self.logits(dept, obs); z = z - z.max(); e = np.exp(z)
        return e / e.sum()

    def act(self, dept, obs, ev=None):
        return DEPTS[dept]["actions"][int(np.argmax(self.logits(dept, obs)))]

    def copy(self):
        return LinearPolicy({d: {"W": h["W"].copy(), "b": h["b"].copy()} for d, h in self.heads.items()})

    def to_json(self):
        return {"type": "linear-softmax-heads", "env": "connect-company/1",
                "heads": {d: {"actions": DEPTS[d]["actions"], "keys": DEPTS[d]["keys"], "obs": OBS_NAMES[d],
                              "W": np.round(h["W"], 6).tolist(), "b": np.round(h["b"], 6).tolist()} for d, h in self.heads.items()}}

    @classmethod
    def from_json(cls, d):
        if d.get("type") != "linear-softmax-heads":
            raise ValueError("linear-softmax-heads 형식이 아닙니다")
        return cls({k: {"W": v["W"], "b": v["b"]} for k, v in d["heads"].items()})


# ── 플레이어의 지시 ─────────────────────────────────────────────────────────
OWNER_OPTIONS = {
    "staffing": ["균형", "고객센터 집중", "결제팀 집중", "사람 확인 집중"],
    "order":    ["중단", "적게", "보통", "넉넉히", "가득"],          # 재고 목표 (창고+도착 예정)
    "ad":       ["중단", "유지", "증액"],
    "refund":   ["관대", "보통", "엄격"],
    "security": ["낮음", "보통", "높음"],
}
OWNER_DEFAULT = {"staffing": "균형", "order": "보통", "ad": "유지", "refund": "보통", "security": "보통"}
STOCK_TARGET = {"중단": 0, "적게": 120, "보통": 180, "넉넉히": 240, "가득": 300}


class OwnerPolicy:
    """게임의 사장 지시. schedule[day] = {"staffing", "order", "ad", "refund", "security"}.
    order는 재고 목표입니다: 창고+도착 예정이 목표보다 60개 넘게 모자라면 대량, 모자라면 소량 발주.
    모든 항목의 '보통'은 규칙 사장과 똑같습니다. 회사가 커지면(demand_scale) 재고 목표도 같이 커집니다."""
    name = "내 경영"

    def __init__(self, schedule, demand_scale=1.0):
        if isinstance(schedule, dict):
            schedule = [schedule]
        self.schedule = [dict(OWNER_DEFAULT, **s) for s in schedule]
        self.scale = demand_scale
        self.rule = RulePolicy()

    def settings(self, day):
        return self.schedule[min(day, len(self.schedule) - 1)]

    def act(self, dept, obs, ev):
        s = self.settings(ev["ctx"]["day"])
        if dept == "staffing": return s["staffing"]
        if dept == "inventory":
            target = STOCK_TARGET[s["order"]] * self.scale
            have = ev["ctx"]["stock"] + ev["ctx"]["incoming"]
            return "대량 발주" if have < target - 60 * self.scale else "소량 발주" if have < target else "발주 안 함"
        if dept == "marketing": return s["ad"]
        if dept == "cs": return ev["theta"]                     # 고객센터는 1주차 전전두엽(직관)이 응대합니다
        if dept == "refund":
            fs = ev["fraud_score"]
            if s["refund"] == "관대": return HUMAN if fs >= 0.75 else "전액 환불"
            if s["refund"] == "엄격": return "거절" if fs >= 0.45 else HUMAN if ev["amount"] >= 8 else "전액 환불"
            return self.rule.act(dept, obs, ev)
        if dept == "security":
            fs = ev["fraud_score"]
            if s["security"] == "낮음": return "차단" if fs >= 0.9 else "허용"
            if s["security"] == "높음": return "차단" if fs >= 0.6 else HUMAN if fs >= 0.3 else "허용"
            return self.rule.act(dept, obs, ev)
        raise ValueError(dept)


class Recorder:
    """다른 정책을 감싸서 (dept, obs, ev, action)을 모두 기록합니다."""

    def __init__(self, policy):
        self.policy, self.rows = policy, []

    def act(self, dept, obs, ev):
        a = self.policy.act(dept, obs, ev)
        self.rows.append((dept, obs, ev, a))
        return a


__all__ = ["RulePolicy", "HeuristicPolicy", "RandomPolicy", "LinearPolicy", "OwnerPolicy", "OWNER_OPTIONS", "OWNER_DEFAULT", "STOCK_TARGET", "Recorder", "MORNING"]
