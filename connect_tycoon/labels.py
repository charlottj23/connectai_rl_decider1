# -*- coding: utf-8 -*-
"""시뮬레이터 → 언어 모델 학습 데이터 (반사실 정답 라벨)

강화학습으로 키운 작은 정책 모델은 이 게임 안에서 잘 판단합니다. 그 지식을 C1 · JEV 같은 언어 모델에 옮기려면 데이터가 필요합니다.
엔진이 결정적이라, 판단 하나마다 '다른 선택을 했다면 이번 달이 어떻게 끝났을까'를 선택지마다 끝까지 다시 돌려 볼 수 있습니다.

    q[행동] = 그 판단에서 그 행동을 고르고, 나머지는 원래 정책대로 한 달을 끝냈을 때의 한 달 보상

이 q로 세 가지를 만듭니다.
    sft   · JEV 요청 → 가장 좋았던 선택의 JEV 응답          (지도학습 · SFT)
    pairs · 같은 요청에 좋았던 응답(chosen) vs 나빴던 응답(rejected)   (선호 학습 · DPO)
    raw   · 요청 · 선택지별 q · 원래 고른 행동                 (보상 모형 · 오프라인 강화학습)
"""
import json
import math

from . import jev as J
from .company import DEPTS


class _Override:
    """정책을 그대로 따르다가 k번째로 묻는 판단만 다른 행동으로 바꿉니다."""

    def __init__(self, policy, k, action):
        self.policy, self.k, self.action, self.n = policy, k, action, 0

    def act(self, dept, obs, ev):
        i = self.n; self.n += 1
        return self.action if i == self.k else self.policy.act(dept, obs, ev)


class _Rec:
    def __init__(self, policy):
        self.policy, self.rows = policy, []

    def act(self, dept, obs, ev):
        a = self.policy.act(dept, obs, ev)
        self.rows.append((dept, obs, ev, a))
        return a


def counterfactual(company, policy, seed, stride=1, depts=None, progress=None):
    """한 달의 판단마다 선택지별 한 달 보상(q). stride=3이면 세 판단에 하나만 (빠르게)."""
    rec = _Rec(policy)
    log, _ = company.run_month(seed, rec)
    base = sum(x["reward"] for x in log)
    out = []
    todo = [k for k in range(len(rec.rows)) if k % stride == 0 and (not depts or rec.rows[k][0] in depts)]
    for n, k in enumerate(todo):
        dept, obs, ev, a = rec.rows[k]
        q = {}
        for act in DEPTS[dept]["actions"]:
            if act == a:
                q[act] = base
            else:
                lg, _ = company.run_month(seed, _Override(policy, k, act))
                q[act] = sum(x["reward"] for x in lg)
        out.append({"seed": seed, "index": k, "dept": dept, "ev": ev, "chosen": a, "q": q, "_obs": list(obs)})
        if progress: progress(n + 1, len(todo))
    return out


def _response(dept, q, model, temperature=2.0):
    acts = DEPTS[dept]["actions"]
    m = max(q.values())
    e = [math.exp((q[a] - m) / temperature) for a in acts]
    z = sum(e)
    return J.answer(dept, [v / z for v in e], model=model, reason="시뮬레이터 반사실 정답")


SYSTEM = ("너는 회사의 의사결정 모델이다. JEV 요청(state + questions)을 받으면 criteria 중 하나를 골라 "
          "JEV 응답(answers.decision: type, choice, probabilities, confidence)으로만 답한다.")


def export(rows, company, sft_path=None, pairs_path=None, raw_path=None, model="connect-tycoon/simulator", min_margin=0.3):
    """반사실 라벨 → SFT · 선호쌍 · 원본. 저장한 줄 수를 돌려줍니다."""
    n = {"sft": 0, "pairs": 0, "raw": 0}
    files = {k: open(p, "w", encoding="utf-8") for k, p in (("sft", sft_path), ("pairs", pairs_path), ("raw", raw_path)) if p}
    try:
        for r in rows:
            dept, q = r["dept"], r["q"]
            req = J.request(dept, r["ev"], company.values, company.cfg)
            keys, acts = DEPTS[dept]["keys"], DEPTS[dept]["actions"]
            best = max(acts, key=lambda a: q[a]); worst = min(acts, key=lambda a: q[a])
            good = _response(dept, q, model)
            if "sft" in files:
                files["sft"].write(json.dumps({"messages": [{"role": "system", "content": SYSTEM},
                                                            {"role": "user", "content": json.dumps(req, ensure_ascii=False)},
                                                            {"role": "assistant", "content": json.dumps(good, ensure_ascii=False)}]}, ensure_ascii=False) + "\n")
                n["sft"] += 1
            if "pairs" in files and q[best] - q[worst] >= min_margin:
                bad = J.answer(dept, [1.0 if a == worst else 0.0 for a in acts], model=model, choice=keys[acts.index(worst)])
                files["pairs"].write(json.dumps({"prompt": json.dumps(req, ensure_ascii=False), "chosen": json.dumps(good, ensure_ascii=False),
                                                 "rejected": json.dumps(bad, ensure_ascii=False), "margin": round(q[best] - q[worst], 4)},
                                                ensure_ascii=False) + "\n")
                n["pairs"] += 1
            if "raw" in files:
                files["raw"].write(json.dumps({"request": req, "q": {keys[acts.index(a)]: round(v, 4) for a, v in q.items()},
                                               "chosen_by_policy": keys[acts.index(r["chosen"])], "best": keys[acts.index(best)],
                                               "seed": r["seed"], "index": r["index"]}, ensure_ascii=False) + "\n")
                n["raw"] += 1
    finally:
        for f in files.values(): f.close()
    return n


def learn_from_labels(company, policy, seeds, stride=3, rounds=2, steps=300, lr=0.5, temperature=2.0, depts=None, l2=1e-3,
                      progress=None, log=print):
    """정답 비교 학습: 선택지를 모두 끝까지 돌려 본 결과(q)를 정답으로, 부서 머리를 지도학습합니다 (정책 반복).
    PPO가 '해 보고 보상으로 고치기'라면, 이것은 '모든 선택지를 다 해 보고 제일 좋은 것 배우기'입니다."""
    import numpy as np
    from .company import DEPT_ORDER
    for rnd in range(rounds):
        data = {d: ([], []) for d in DEPT_ORDER}
        for i, seed in enumerate(seeds):
            for r in counterfactual(company, policy, seed, stride=stride, depts=depts):
                acts = DEPTS[r["dept"]]["actions"]
                qs = np.array([r["q"][a] for a in acts])
                p = np.exp((qs - qs.max()) / temperature); p /= p.sum()
                data[r["dept"]][0].append(r["_obs"])
                data[r["dept"]][1].append(p)
            if progress: progress(rnd, i + 1, len(seeds))
        for d, (O, P) in data.items():
            if len(O) < 4: continue
            O, P = np.array(O, dtype=float), np.array(P)
            h = policy.heads[d]
            for _ in range(steps):
                Z = O @ h["W"].T + h["b"]; Z -= Z.max(1, keepdims=True); Q = np.exp(Z); Q /= Q.sum(1, keepdims=True)
                G = P - Q
                h["W"] += lr * (G.T @ O / len(O) - l2 * h["W"]); h["b"] += lr * G.mean(0)
        if log: log(f"정답 비교 학습 {rnd + 1}/{rounds} · 판단 {sum(len(v[0]) for v in data.values())}개")
    return policy
