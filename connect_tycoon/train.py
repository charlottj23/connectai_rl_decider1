# -*- coding: utf-8 -*-
"""두뇌 키우기 · 지도학습(모방) → 강화학습(PPO) · numpy만 씁니다.

1. imitate   규칙 사장의 판단을 그대로 따라 하도록 부서 머리를 학습합니다 (C1을 만든 SFT와 같은 단계).
2. train_ppo 회사의 가치로 받은 보상으로 판단을 고칩니다 (PPO-clip).
             아침 결정(인력 · 발주 · 광고)은 그날부터 며칠의 보상으로, 낮의 일(문의 · 환불 · 보안)은 그날 남은 보상으로 배웁니다.
             검증 달에서 보상이 가장 높았던 정책을 마지막에 되돌려 놓습니다.
"""
import math

import numpy as np

from .company import DEPT_ORDER, DEPTS, MORNING

TEST_SEEDS = range(7000, 7040)     # 처음 보는 40개월 (강의 Colab과 같은 시험)
VAL_SEEDS = range(9000, 9012)


def evaluate(company, policy, seeds=TEST_SEEDS):
    """한 달 평균 · profit(만원) · sat(월말 고객 만족) · incidents(위험 사고) · human_over(사람 확인 초과) · stockout_days(품절일)."""
    months = [company.run_month(s, policy) for s in seeds]
    D = [d for _, days in months for d in days]
    n = len(months)
    return {"month_reward": float(np.mean([sum(x["reward"] for x in log) for log, _ in months])),
            "profit": float(np.mean([sum(d["profit"] for d in days) for _, days in months])),
            "sat": float(np.mean([days[-1]["sat"] for _, days in months])),
            "incidents": sum(d["incidents"] for d in D) / n, "human_over": sum(d["human_over"] for d in D) / n,
            "stockout_days": sum(1 for d in D if d["unmet"] > 0) / n, "fraud_loss": sum(d["fraud_loss"] for d in D) / n,
            "abuse_loss": sum(d["abuse_loss"] for d in D) / n, "months": n}


def imitate(company, policy, teacher, months=40, steps=400, lr=0.5, l2=1e-3, seed=500, soften=0.3):
    """지도학습: 선생님 정책의 판단을 따라 합니다. 부서별 정확도를 돌려줍니다."""
    data = {d: ([], []) for d in DEPT_ORDER}

    class Rec:
        def act(self, dept, obs, ev):
            a = teacher.act(dept, obs, ev)
            data[dept][0].append(np.asarray(obs, dtype=float)); data[dept][1].append(DEPTS[dept]["actions"].index(a))
            return a
    for m in range(months):
        company.run_month(seed + m, Rec())
    acc = {}
    for d, (O, A) in data.items():
        if not O: continue
        O, A = np.array(O), np.array(A); h = policy.heads[d]; Y = np.eye(len(DEPTS[d]["actions"]))[A]
        for _ in range(steps):
            Z = O @ h["W"].T + h["b"]; Z -= Z.max(1, keepdims=True); P = np.exp(Z); P /= P.sum(1, keepdims=True)
            G = Y - P
            h["W"] += lr * (G.T @ O / len(A) - l2 * h["W"]); h["b"] += lr * G.mean(0)
        acc[d] = float(np.mean((O @ h["W"].T + h["b"]).argmax(1) == A))
        if d in MORNING:                   # 아침 결정은 확신을 낮춰, 강화학습이 다른 선택도 시도해 보게 합니다
            h["W"] *= soften; h["b"] *= soften
    return acc


class _Sampler:
    def __init__(self, policy, rng):
        self.p, self.rng, self.traj = policy, rng, []

    def act(self, dept, obs, ev):
        pr = self.p.probs(dept, obs); a = int(self.rng.choice(len(pr), p=pr))
        self.traj.append((dept, np.asarray(obs, dtype=float), a, math.log(pr[a] + 1e-12)))
        return DEPTS[dept]["actions"][a]


def _advantages(months, gamma_day=0.9, gamma_event=0.9):
    rows = []
    for log_, traj in months:
        day_total = {}
        for x in log_: day_total[x["day"]] = day_total.get(x["day"], 0.0) + x["reward"]
        ndays = max(day_total) + 1
        G_day = np.zeros(ndays); run = 0.0
        for d in range(ndays - 1, -1, -1):
            run = day_total[d] + gamma_day * run; G_day[d] = run
        k = 0; events = {}
        for x in log_:
            if x["dept"] is None or x["ruled"]:
                if x["dept"] is not None and x["day"] in events and events[x["day"]]: events[x["day"]][-1][1] += x["reward"]
                continue
            dept, o, a, lp = traj[k]; k += 1
            if dept in MORNING:
                rows.append([dept, o, a, lp, G_day[x["day"]]])
            else:
                events.setdefault(x["day"], []).append([len(rows), x["reward"]])
                rows.append([dept, o, a, lp, 0.0])
        for evs in events.values():
            run = 0.0
            for idx, rew in reversed(evs):
                run = rew + gamma_event * run; rows[idx][4] = run
    return rows


def train_ppo(company, policy, iterations=60, months_per_iter=24, epochs=4, lr=0.2, clip=0.2, entropy=0.005,
              seed=0, eval_every=5, val_seeds=VAL_SEEDS, log=print, callback=None, stop=None, depts=None):
    """PPO-clip. callback(row)는 반복마다 불립니다. stop()이 True를 돌려주면 멈춥니다. 반환: 기록(list).
    depts를 주면 그 질문(부서)만 배우고, 나머지는 출발점 그대로 둡니다 (사람마다 다른 학습 레시피)."""
    rng = np.random.default_rng(seed)
    hist, best = [], (-1e18, None, 0)
    for it in range(1, iterations + 1):
        if stop and stop():
            break
        months, month_rewards = [], []
        for m in range(months_per_iter):
            smp = _Sampler(policy, rng)
            log_, _ = company.run_month(100000 * (seed + 1) + it * months_per_iter + m, smp)
            month_rewards.append(sum(x["reward"] for x in log_)); months.append((log_, smp.traj))
        rows = _advantages(months)
        for d in DEPT_ORDER:
            if depts and d not in depts: continue
            sel = [r_ for r_ in rows if r_[0] == d]
            if len(sel) < 4: continue
            O = np.array([r_[1] for r_ in sel]); A = np.array([r_[2] for r_ in sel]); LP = np.array([r_[3] for r_ in sel]); G = np.array([r_[4] for r_ in sel])
            Xv = np.c_[O, np.ones(len(O))]
            V = Xv @ np.linalg.lstsq(Xv.T @ Xv + 1e-3 * np.eye(Xv.shape[1]), Xv.T @ G, rcond=None)[0]   # 부서별 기준선
            AD = G - V; AD = (AD - AD.mean()) / (AD.std() + 1e-8)
            h = policy.heads[d]
            for _ in range(epochs):
                Z = O @ h["W"].T + h["b"]; Z -= Z.max(1, keepdims=True); P = np.exp(Z); P /= P.sum(1, keepdims=True)
                ratio = np.exp(np.log(P[np.arange(len(A)), A] + 1e-12) - LP)
                use = ((AD >= 0) & (ratio < 1 + clip)) | ((AD < 0) & (ratio > 1 - clip))
                Gz = -P; Gz[np.arange(len(A)), A] += 1
                gz = (AD * ratio * use)[:, None] * Gz
                H = -(P * np.log(P + 1e-12)).sum(1, keepdims=True)
                gz += entropy * (-P * (np.log(P + 1e-12) + H))
                h["W"] += lr * gz.T @ O / len(A); h["b"] += lr * gz.mean(0)
        row = {"iteration": it, "iterations": iterations, "train_month_reward": float(np.mean(month_rewards))}
        if it % eval_every == 0 or it == iterations:
            ev = evaluate(company, policy, seeds=val_seeds)
            row.update({"eval_" + k: v for k, v in ev.items() if k != "months"})
            if ev["month_reward"] > best[0]:
                best = (ev["month_reward"], {d: {"W": h["W"].copy(), "b": h["b"].copy()} for d, h in policy.heads.items()}, it)
            if log: log(f"반복 {it:>3} · 한 달 보상 {ev['month_reward']:7.1f} · 이익 {ev['profit']:7.0f}만원 · 고객 만족 {ev['sat']:.2f} · "
                        f"위험 {ev['incidents']:.1f}건 · 사람 확인 초과 {ev['human_over']:.1f}건 · 품절 {ev['stockout_days']:.1f}일")
        hist.append(row)
        if callback: callback(row)
    if best[1] is not None:
        policy.heads = best[1]
        if log: log(f"검증 보상이 가장 높았던 반복 {best[2]}의 정책을 저장합니다")
    return hist


def supervise(policy, labels, company=None, anchor_seeds=range(9000, 9004), weight=4.0, share=0.2, steps=200, lr=0.3, l2=1e-3):
    """사람 라벨로 지도학습: labels = [(부서, 관측, 행동 번호)].
    라벨 몇 개가 부서 전체를 덮어쓰지 않도록, 모델이 원래 하던 판단(닻)도 함께 배웁니다:
    사람이 답한 비슷한 상황만 바뀌고 나머지 판단은 그대로 남습니다. 부서별로 사람 답과 맞는 비율을 돌려줍니다."""
    by = {}
    for dept, obs, a in labels:
        by.setdefault(dept, [[], [], []])
        by[dept][0].append(np.asarray(obs, dtype=float)); by[dept][1].append(np.eye(len(DEPTS[dept]["actions"]))[int(a)]); by[dept][2].append(weight)
    if company is not None and by:                      # 닻: 지금 모델이 하던 판단 (부드러운 정답)
        frozen = policy.copy()

        class Rec:
            def act(self, dept, obs, ev):
                if dept in by:
                    by[dept][0].append(np.asarray(obs, dtype=float)); by[dept][1].append(frozen.probs(dept, obs)); by[dept][2].append(1.0)
                return frozen.act(dept, obs, ev)
        for s in anchor_seeds:
            company.run_month(s, Rec())
    acc = {}
    for d, (O, Y, Wt) in by.items():
        n_h = sum(1 for l in labels if l[0] == d)
        n_a = len(O) - n_h
        if n_a:                                          # 사람 라벨 전체가 학습 신호의 share만큼 되도록
            w_h = max(weight, share / (1 - share) * n_a / max(1, n_h))
            Wt = [w_h] * n_h + [1.0] * n_a
        O, Y, Wt = np.array(O), np.array(Y), np.array(Wt)[:, None]
        h = policy.heads[d]
        for _ in range(steps):
            Z = O @ h["W"].T + h["b"]; Z -= Z.max(1, keepdims=True); P = np.exp(Z); P /= P.sum(1, keepdims=True)
            G = (Y - P) * Wt
            h["W"] += lr * (G.T @ O / Wt.sum() - l2 * h["W"]); h["b"] += lr * G.sum(0) / Wt.sum()
        n = sum(1 for _, _, _ in [l for l in labels if l[0] == d])
        Oh = O[:n]
        acc[d] = float(np.mean((Oh @ h["W"].T + h["b"]).argmax(1) == Y[:n].argmax(1))) if n else 1.0
    return acc


def grow_brain(company, teacher, iterations=60, months_per_iter=24, imitate_months=40, imitate_steps=400, seed=0, log=print, callback=None, stop=None,
               depts=None):
    """두뇌 하나를 처음부터 키웁니다: 규칙 따라 하기 → 보상으로 배우기. (policy, 기록)을 돌려줍니다."""
    from .policies import LinearPolicy
    pol = LinearPolicy()
    acc = imitate(company, pol, teacher, months=imitate_months, steps=imitate_steps)
    if callback: callback({"stage": "imitate", "accuracy": acc})
    hist = train_ppo(company, pol, iterations=iterations, months_per_iter=months_per_iter, seed=seed, log=log, callback=callback, stop=stop, depts=depts)
    return pol, hist
