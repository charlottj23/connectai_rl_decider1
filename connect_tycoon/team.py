# -*- coding: utf-8 -*-
"""두뇌 연합 (Connect AI의 첫걸음) · 부서마다 다른 두뇌가 판단합니다.

개미 군집에서 개미마다 맡은 일이 다르듯, 인력 배치는 A의 두뇌가, 환불은 B의 두뇌가, 보안은 C의 두뇌가 맡습니다.
모두 JEV로 묻고 답하기 때문에 누가 만든 두뇌든 한 회사에서 함께 일할 수 있습니다.

    team = TeamPolicy({"refund": brain_a, "security": brain_b}, default=brain_c)
    assignment, score = best_team(company, {"a": brain_a, "b": brain_b, "c": brain_c})
"""
from .company import DEPT_ORDER
from .train import VAL_SEEDS, evaluate


class TeamPolicy:
    """부서 → 정책. JevPolicy를 섞어 쓰면 모든 JEV 요청/응답을 순서대로 self.log에 모읍니다."""
    name = "두뇌 연합"

    def __init__(self, members, default=None):
        self.members, self.default = dict(members), default
        self.log = []          # JEV 요청/응답만
        self.trace = []        # 판단마다 하나 (JEV가 아니면 None)

    def member(self, dept):
        p = self.members.get(dept, self.default)
        if p is None:
            raise ValueError(f"{dept} 부서를 맡은 두뇌가 없습니다")
        return p

    def act(self, dept, obs, ev):
        p = self.member(dept)
        n = len(getattr(p, "log", ()) or ())
        a = p.act(dept, obs, ev)
        plog = getattr(p, "log", None)
        rec = plog[-1] if plog is not None and len(plog) > n else None
        if rec is not None: self.log.append(rec)
        self.trace.append(rec)
        return a


def best_team(company, candidates, seeds=VAL_SEEDS, rounds=2, log=print, progress=None):
    """부서마다 가장 잘하는 두뇌를 고릅니다 (좌표 오르기: 한 부서씩 바꿔 보고 나아지면 유지).
    candidates = {이름: 정책}. 고르는 데는 검증 달을 쓰고, 시험 달은 남겨 둡니다. 반환 (부서 → 이름, 한 달 평균 이익)."""
    names = list(candidates)
    score = lambda assign: evaluate(company, TeamPolicy({d: candidates[n] for d, n in assign.items()}), seeds)["profit"]
    singles = {n: score({d: n for d in DEPT_ORDER}) for n in names}
    if progress: progress("singles", singles, None)
    best_name = max(singles, key=singles.get)
    assign, best = {d: best_name for d in DEPT_ORDER}, singles[best_name]
    if log: log("혼자 운영할 때: " + " · ".join(f"{n} {v:.0f}만원" for n, v in singles.items()))
    for _ in range(rounds):
        improved = False
        for d in DEPT_ORDER:
            for n in names:
                if n == assign[d]: continue
                trial = dict(assign, **{d: n})
                v = score(trial)
                if progress: progress(d, n, v)
                if v > best + 1e-9:
                    assign, best, improved = trial, v, True
                    if log: log(f"  {d} ← {n} · {v:.0f}만원")
        if not improved:
            break
    return assign, best
