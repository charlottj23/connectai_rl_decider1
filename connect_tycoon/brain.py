# -*- coding: utf-8 -*-
"""회사 두뇌 (format: connect-ai-brain/1 + company) · brain.json 한 장

    고객 문의 직관 (1주차 전전두엽)  +  부서 6곳의 강화학습 정책  +  규칙  +  회사의 가치

brain(request)는 JEV 요청을 받아 JEV 응답을 돌려줍니다. 엔진의 관측을 JEV 요청에서 그대로 다시 만들기 때문에,
JEV로 물어도 숫자로 물어도 같은 판단이 나옵니다. 강의 Colab이 Hugging Face에 올린 brain.json을 그대로 읽습니다.
"""
import json
import os
import re
import urllib.request

import numpy as np

from . import jev as J
from .company import DEFAULT_RULES, DEFAULT_VALUES, DEPTS, REASONS, TIERS, WEEK
from .intuition import ConnectBrain
from .policies import LinearPolicy

DATA = os.path.join(os.path.dirname(__file__), "data")
HF_REPO = re.compile(r"^[A-Za-z0-9][\w.-]*/[\w.-]+$")


class CompanyBrain:
    def __init__(self, spec):
        if "company" not in spec:
            raise ValueError("회사 두뇌가 아닙니다 (brain.json에 company가 없습니다). connect-company-로 시작하는 저장소의 brain.json을 쓰세요")
        self.spec = spec
        self.name = spec.get("name", "brain")
        self.researcher = spec.get("researcher", "")
        self.intuition = ConnectBrain(spec)
        comp = spec["company"]
        self.values = dict(DEFAULT_VALUES, **comp.get("values", {}))
        self.rules = [tuple(r) for r in comp.get("rules", DEFAULT_RULES)]
        self.policy = LinearPolicy.from_json(comp["policy"])
        self.model = f"connect-company/{self.name}"
        self._cache = {}

    # ── 불러오기 · 저장 ───────────────────────────────────────────────────
    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    @classmethod
    def default(cls):
        """패키지에 들어 있는 예시 두뇌 (CONNECT AI LAB · jay-company)."""
        return cls.from_file(os.path.join(DATA, "jay-company.json"))

    @classmethod
    def from_hub(cls, repo_id, filename="brain.json", revision="main", timeout=30):
        """Hugging Face 저장소(아이디/connect-company-이름)에서 brain.json을 받습니다. huggingface_hub가 없어도 됩니다."""
        repo_id = repo_id.strip().removeprefix("https://huggingface.co/").strip("/")
        if not HF_REPO.match(repo_id):
            raise ValueError("저장소 이름은 '아이디/저장소' 모양이어야 합니다")
        url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{filename}"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "connect-tycoon"}), timeout=timeout) as r:
            spec = json.loads(r.read().decode("utf-8"))
        brain = cls(spec)
        brain.source = f"hf:{repo_id}"
        return brain

    @classmethod
    def load(cls, ref):
        """'default' · 파일 경로 · 'hf:아이디/저장소' 중 하나."""
        if ref in (None, "", "default"): return cls.default()
        if ref.startswith("hf:"): return cls.from_hub(ref[3:])
        return cls.from_file(ref)

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.spec, f, ensure_ascii=False)
        return path

    @staticmethod
    def make_spec(intuition_spec, policy, name, values=None, rules=None, researcher="", config=None, results=None, profile=None):
        """직관(1주차 두뇌 spec) + 학습한 정책 → 새 brain.json."""
        spec = {k: v for k, v in intuition_spec.items() if k != "company"}
        spec["name"], spec["researcher"] = name, researcher or spec.get("researcher", "")
        spec["company"] = {"env": J.ENV_ID, "values": dict(DEFAULT_VALUES, **(values or {})),
                           "rules": [list(r) for r in (rules if rules is not None else DEFAULT_RULES)], "policy": policy.to_json()}
        if config: spec["company"]["config"] = dict(config)
        if results: spec["company"]["results"] = results
        if profile: spec["company"]["profile"] = profile          # 학습한 회사의 분포 (general · lecture · 내 회사)
        return spec

    # ── 판단 ──────────────────────────────────────────────────────────────
    def act(self, dept, obs, ev=None):
        """숫자 관측으로 바로 판단 (학습 · 평가용 빠른 길)."""
        return self.policy.act(dept, obs, ev)

    def probs(self, dept, obs):
        return self.policy.probs(dept, obs)

    def _scores(self, text):
        hit = self._cache.get(text)
        if hit is None:
            sc = [float(v) for v in self.intuition.scores(text)]
            sig = [float(v) for v in list(self.intuition.detect(text).values())[:3]]
            hit = self._cache[text] = (sc, sig)
        return hit

    def observe(self, req):
        """JEV 요청 → (부서, 관측, 규칙에 쓰는 값). 엔진이 만든 관측과 똑같은 숫자가 나옵니다."""
        st = req["state"]
        dept = st.get("department")
        if dept not in DEPTS:
            names = {v["name"]: k for k, v in DEPTS.items()}
            dept = names.get(dept)
        if dept is None:
            raise ValueError(f"state.department는 {list(DEPTS)} 중 하나여야 합니다")
        c = st.get("company", {})
        day, days = c.get("day", 0), c.get("days", 20)
        wk = [1.0 if c.get("weekday", "월") == w else 0.0 for w in WEEK]
        common = [day / days] + wk + [c.get("sat", 0.7), min(c.get("stock", 120.0), 300.0) / 200.0, c.get("incoming", 0.0) / 200.0,
                                      c.get("ad", 0.6) / 2.0, c.get("human_left", 1.0), c.get("time", 0.5)]
        ev = {}
        if dept == "staffing":
            obs = common + [min(st.get("yesterday_cs_overflow", 0), 5) / 5.0, st.get("yesterday_refunds", 4) / 6.0,
                            st.get("yesterday_security", 4) / 6.0, min(st.get("yesterday_human_overflow", 0), 5) / 5.0]
        elif dept == "inventory":
            obs = common + [st.get("recent_sales", 60.0) / 100.0, 1.0 if st.get("stockout_yesterday") else 0.0]
        elif dept == "marketing":
            obs = common + [st.get("recent_sales", 60.0) / 100.0, st.get("profit_yesterday", 60.0) / 100.0]
        elif dept == "cs":
            text = st.get("message") or ""
            sc, sig = self._scores(text); top = sorted(sc)
            foreign = 1.0 if st.get("industry", self.spec.get("experience")) != self.spec.get("experience") else 0.0
            obs = common + list(sc) + list(sig) + [top[-1] - top[-2], st.get("urgent_left", 1.0), st.get("billing_left", 1.0), foreign]
            ev = {"signals": sig}
        elif dept == "refund":
            reason, tier, fs, amount = st.get("reason", "단순 변심"), st.get("tier", "단골"), float(st.get("fraud_score", 0.2)), float(st.get("amount", 5))
            obs = common + [amount / 12.0] + [1.0 if reason == x else 0.0 for x in REASONS] + [1.0 if tier == x else 0.0 for x in TIERS] + \
                [fs, st.get("billing_left", 1.0)]
            ev = {"fraud_score": fs, "amount": amount}
        else:
            fs = float(st.get("fraud_score", 0.2))
            obs = common + [float(st.get("amount", 20)) / 40.0, fs, float(st.get("new_device", 0)), float(st.get("overseas", 0)), float(st.get("velocity", 0.2))]
            ev = {"fraud_score": fs, "amount": float(st.get("amount", 20))}
        return dept, obs, ev

    def _rule(self, dept, ev):
        for d, cond, val, action in self.rules:
            if d != dept: continue
            if cond == "위험 신호" and ev.get("signals", [0, 0, 0])[2] >= val: return action
            if cond == "사기 점수 ≥" and ev.get("fraud_score", 0) >= val: return action
            if cond == "금액 ≥" and ev.get("amount", 0) >= val: return action
        return None

    def jev(self, req):
        """JEV 요청 → JEV 응답. 규칙이 걸리면 확률 1로 확정합니다."""
        dept, obs, ev = self.observe(req)
        acts, keys = DEPTS[dept]["actions"], DEPTS[dept]["keys"]
        p = self.policy.probs(dept, obs)
        rule = self._rule(dept, ev)
        answers = {}
        for qname, q in req["questions"].items():
            if q.get("type", "choice") != "choice":
                raise ValueError("이 두뇌는 type='choice' 질문만 답합니다")
            crit = list(q.get("criteria") or keys)
            if any(k not in keys for k in crit):
                raise ValueError(f"{DEPTS[dept]['name']} 부서의 criteria key는 {keys} 중에서 고릅니다")
            idx = [keys.index(k) for k in crit]
            sub = p[idx] / p[idx].sum()
            probs = {k: round(float(v), 4) for k, v in zip(crit, sub)}
            choice, reason = crit[int(np.argmax(sub))], "강화학습 정책"
            if rule and keys[acts.index(rule)] in crit:
                choice, reason = keys[acts.index(rule)], f"규칙 · {rule}"
                probs = {k: (1.0 if k == choice else 0.0) for k in crit}
            answers[qname] = {"type": "choice", "choice": choice, "probabilities": probs, "confidence": probs[choice], "reason": reason}
        return {"model": self.model, "answers": answers}

    __call__ = jev

    def __repr__(self):
        return f"CompanyBrain(name={self.name!r}, values={self.values})"
