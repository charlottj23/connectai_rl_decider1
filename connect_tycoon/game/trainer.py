# -*- coding: utf-8 -*-
"""두뇌 훈련소 · 게임 화면이 멈추지 않도록 다른 프로세스에서 학습합니다.

출발점은 셋 중 하나입니다.
  · 지금 AI 사장 · 앉아 있는 두뇌를 이 회사에서 이어서 훈련합니다 (파인튜닝). 회사가 커졌을 때 가장 좋습니다.
  · 규칙 사장 / 내 지시 · 먼저 따라 배우고(지도학습) → 회사의 가치로 받은 보상으로 고칩니다(PPO).
지금 회사 규모(업그레이드)에서 학습합니다.
"""
import multiprocessing as mp
import queue as _queue

TEST_MONTHS = range(7000, 7010)


def _worker(q, config, values, teacher, iterations, months_per_iter, seed, start_spec=None, labels=None, profile=None):
    try:
        import connect_tycoon as ct
        b = ct.CompanyBrain(start_spec) if start_spec else ct.CompanyBrain.default()
        co = ct.Company(b.intuition, ct.load_pool(), values=values, config=config, profile=profile)
        scale = config.get("base_demand", 40.0) / 40.0
        if start_spec:                                   # 파인튜닝: 지금 AI 사장에서 출발
            teach = b.policy
            pol = b.policy.copy()
            q.put({"stage": "ppo", "accuracy": None})
            lr = 0.15
        else:
            teach = ct.RulePolicy() if teacher is None else ct.OwnerPolicy(teacher, demand_scale=scale)
            q.put({"stage": "imitate"})
            pol = ct.LinearPolicy()
            acc = ct.imitate(co, pol, teach, months=40 if not iterations else 16, steps=1500 if not iterations else 250,   # v0: 규칙을 충분히 따라 배움
                             soften=1.0 if not iterations else 0.3)
            q.put({"stage": "ppo", "accuracy": acc})
            lr = 0.2
        if iterations:
            ct.train_ppo(co, pol, iterations=iterations, months_per_iter=months_per_iter, lr=lr, seed=seed, eval_every=3, log=None,
                         callback=lambda row: q.put({"stage": "row", "row": row}))
        human = ct.train.supervise(pol, labels, company=co) if labels else None     # 사람이 고른 답을 지도학습으로 (닻과 함께)
        q.put({"stage": "test", "human": human})
        res = {"new": ct.evaluate(co, pol, TEST_MONTHS), "teacher": ct.evaluate(co, teach, TEST_MONTHS), "human": human}
        from connect_tycoon import backtest                 # 실제 데이터 시험: 학습에 쓰지 않은 실제 기록으로 다시 채점
        if backtest.available():
            c, d = backtest.card(pol, co), backtest.demand(pol, co)
            res["real"] = {"saved": c["saved"], "caught": c["caught"], "fraud": c["fraud"], "cases": c["cases"], "demand": d["profit"]}
        q.put({"stage": "done", "policy": pol.to_json(), "results": res})
    except Exception as e:  # 화면에 알립니다
        import traceback
        q.put({"stage": "error", "error": f"{e}", "trace": traceback.format_exc()})


def _team_worker(q, config, specs, seeds):
    """두뇌 연합 찾기 · specs = {roster id: brain spec 또는 None(규칙 사장)}."""
    try:
        import connect_tycoon as ct
        from connect_tycoon import jev as J
        co = ct.make_company(config=config)
        cands = {rid: (ct.RulePolicy() if spec is None else J.JevPolicy(ct.CompanyBrain(spec), values=co.values, config=co.cfg, keep=False, check=False))
                 for rid, spec in specs.items()}
        total = 1 + 2 * 6 * max(1, len(cands) - 1)
        done = [0]

        def progress(d, n, v):
            if d == "singles":
                q.put({"stage": "singles", "singles": n}); return
            done[0] += 1
            q.put({"stage": "try", "dept": d, "name": n, "value": v, "done": done[0], "total": total})
        assign, best = ct.best_team(co, cands, seeds=seeds, log=None, progress=progress)
        q.put({"stage": "done", "assign": assign, "best": best})
    except Exception as e:
        import traceback
        q.put({"stage": "error", "error": str(e), "trace": traceback.format_exc()})


class TeamSearch:
    def __init__(self):
        self.proc, self.q = None, None
        self.reset()

    def reset(self):
        self.stage, self.singles, self.result, self.error, self.last, self.done, self.total = None, None, None, None, None, 0, 1

    @property
    def running(self):
        return self.proc is not None and self.proc.is_alive()

    def start(self, config, specs, seeds):
        self.stop(); self.reset()
        ctx = mp.get_context("spawn")
        self.q = ctx.Queue()
        self.proc = ctx.Process(target=_team_worker, args=(self.q, dict(config), specs, list(seeds)), daemon=True)
        self.proc.start()
        self.stage = "start"

    def poll(self):
        if self.q is None: return None
        out = None
        while True:
            try:
                m = self.q.get_nowait()
            except (_queue.Empty, EOFError, OSError):
                break
            self.stage = m["stage"]
            if m["stage"] == "singles": self.singles = m["singles"]
            elif m["stage"] == "try": self.last, self.done, self.total = m, m["done"], m["total"]
            elif m["stage"] == "done": self.result, out = m, "done"
            elif m["stage"] == "error": self.error, out = m, "error"
        if out: self.q = None
        return out

    def stop(self):
        if self.proc is not None and self.proc.is_alive():
            self.proc.terminate()
        self.proc = None


class Trainer:
    def __init__(self):
        self.proc = None
        self.q = None
        self.reset()

    def reset(self):
        self.stage, self.rows, self.result, self.error, self.accuracy = None, [], None, None, None

    @property
    def running(self):
        return self.proc is not None and self.proc.is_alive()

    def start(self, config, values, teacher=None, iterations=40, months_per_iter=12, seed=0, start_spec=None, labels=None, profile=None):
        self.stop()
        self.reset()
        ctx = mp.get_context("spawn")
        self.q = ctx.Queue()
        self.iterations = iterations
        self.warm = start_spec is not None
        self.proc = ctx.Process(target=_worker, args=(self.q, dict(config), dict(values), teacher, iterations, months_per_iter, seed, start_spec, labels, profile),
                                daemon=True)
        self.proc.start()
        self.stage = "start"

    def poll(self):
        """새 소식을 읽습니다. 끝났으면 'done' 또는 'error'를 돌려줍니다."""
        if self.q is None:
            return None
        out = None
        while True:
            try:
                m = self.q.get_nowait()
            except _queue.Empty:
                break
            except (EOFError, OSError):
                break
            self.stage = m["stage"]
            if m["stage"] == "row": self.rows.append(m["row"])
            elif m["stage"] == "ppo": self.accuracy = m.get("accuracy")
            elif m["stage"] == "done": self.result = m; out = "done"
            elif m["stage"] == "error": self.error = m; out = "error"
        if out:
            self.q = None
        return out

    def stop(self):
        if self.proc is not None and self.proc.is_alive():
            self.proc.terminate()
        self.proc = None
