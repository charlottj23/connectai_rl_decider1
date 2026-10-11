# -*- coding: utf-8 -*-
"""강화학습 환경 · Gymnasium API (gymnasium이 없어도 같은 모양으로 씁니다)

CompanyEnv   한 달 = 에피소드 하나, 판단 하나 = 스텝 하나.
             관측 {"dept": 부서 번호, "obs": 숫자 23칸(남는 칸은 0), "action_mask": 고를 수 있는 행동 4칸}
             행동 Discrete(4) · 부서마다 선택지 수가 달라서 action_mask를 봅니다.
             보상 그 판단 뒤로 쌓인 회사의 보상(회사의 가치로 계산) · 한 달 보상의 합 = 에피소드 보상

JevEnv       같은 환경을 JEV로: reset() → JEV 요청, step(JEV 응답) → 다음 JEV 요청.
             JEV를 말하는 모델이면 무엇이든 이 환경에서 강화학습시킬 수 있습니다.
"""
import numpy as np

from . import jev as J
from .company import DEPT_ORDER, DEPTS, OBS_DIM, Company, load_pool

MAX_OBS = max(OBS_DIM.values())
MAX_ACTIONS = max(len(d["actions"]) for d in DEPTS.values())

try:
    import gymnasium as gym
    from gymnasium import spaces
    _Base = gym.Env
except ImportError:          # gymnasium 없이도 reset/step은 똑같이 동작합니다
    gym, spaces, _Base = None, None, object


def default_company(config=None, values=None, rules=None, profile=None):
    from .brain import CompanyBrain
    b = CompanyBrain.default()
    return Company(b.intuition, load_pool(), values=values, rules=rules, config=config, profile=profile)


class CompanyEnv(_Base):
    metadata = {"render_modes": ["ansi", "rgb_array"], "render_fps": 4}

    def __init__(self, company=None, config=None, values=None, render_mode=None):
        self.company = company or default_company(config=config, values=values)
        self.render_mode = render_mode
        if spaces is not None:
            self.observation_space = spaces.Dict({"dept": spaces.Discrete(len(DEPT_ORDER)),
                                                  "obs": spaces.Box(-np.inf, np.inf, (MAX_OBS,), np.float32),
                                                  "action_mask": spaces.MultiBinary(MAX_ACTIONS)})
            self.action_space = spaces.Discrete(MAX_ACTIONS)
        self._rng = np.random.default_rng()
        self._gen = None

    # ── Gymnasium API ────────────────────────────────────────────────────
    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        month = (options or {}).get("month_seed")
        self.month_seed = int(month if month is not None else self._rng.integers(0, 2**31 - 1))
        self.log, self.days = [], []
        self._gen = self.company.episode(self.month_seed, self.log, self.days)
        self._dec = next(self._gen)
        return self._obs(), self._info()

    def step(self, action):
        if self._gen is None or self._dec is None:
            raise RuntimeError("reset()을 먼저 부르세요")
        dept = self._dec.dept
        acts = DEPTS[dept]["actions"]
        a = int(action)
        if not 0 <= a < len(acts):
            raise ValueError(f"{DEPTS[dept]['name']} 부서의 행동은 0..{len(acts) - 1} 입니다 (action_mask를 보세요)")
        start = len(self.log)
        terminated = False
        try:
            self._dec = self._gen.send(acts[a])
        except StopIteration:
            self._dec, terminated = None, True
        reward = float(sum(x["reward"] for x in self.log[start:]))
        obs = self._obs() if not terminated else self._blank()
        return obs, reward, terminated, False, self._info()

    def render(self):
        if self.render_mode == "rgb_array":
            from .game.snapshot import render_rgb
            return render_rgb(self)
        d = self.days[-1] if self.days else None
        cur = self._dec
        line = f"{len(self.days)}일 마감 · 오늘 이익 {d['profit']:.1f}만 · 만족 {d['sat']:.0%} · 재고 {d['stock']:.0f}" if d else "개점 전"
        return line + (f"\n지금 묻는 부서: {DEPTS[cur.dept]['name']}" if cur else "\n한 달 끝")

    # ── 도우미 ────────────────────────────────────────────────────────────
    @property
    def decision(self):
        """지금 묻는 판단 (dept, obs, ev). 끝났으면 None."""
        return self._dec

    def jev_request(self, model=J.DEFAULT_MODEL):
        d = self._dec
        return J.request(d.dept, d.ev, self.company.values, self.company.cfg, model) if d else None

    def _blank(self):
        return {"dept": 0, "obs": np.zeros(MAX_OBS, np.float32), "action_mask": np.zeros(MAX_ACTIONS, np.int8)}

    def _obs(self):
        d = self._dec
        o = np.zeros(MAX_OBS, np.float32); o[:len(d.obs)] = d.obs
        m = np.zeros(MAX_ACTIONS, np.int8); m[:len(DEPTS[d.dept]["actions"])] = 1
        return {"dept": DEPT_ORDER.index(d.dept), "obs": o, "action_mask": m}

    def _info(self):
        d = self._dec
        info = {"month_seed": self.month_seed, "day": len(self.days)}
        if d is not None:
            info.update({"dept": d.dept, "actions": DEPTS[d.dept]["actions"], "ev": d.ev, "raw_obs": d.obs})
        else:
            info.update({"month_profit": sum(x["profit"] for x in self.days), "sat": self.days[-1]["sat"] if self.days else None})
        return info


class JevEnv(CompanyEnv):
    """JEV 요청을 관측으로, JEV 응답을 행동으로 받는 환경."""

    def __init__(self, company=None, config=None, values=None, model=J.DEFAULT_MODEL):
        super().__init__(company, config, values)
        self.model = model

    def reset(self, seed=None, options=None):
        _, info = super().reset(seed, options)
        return self.jev_request(self.model), info

    def step(self, response):
        dept = self._dec.dept
        req = self.jev_request(self.model)
        J.validate_response(response, req)
        a = DEPTS[dept]["keys"].index(response["answers"][J.QUESTION]["choice"])
        _, reward, terminated, truncated, info = super().step(a)
        return (None if terminated else self.jev_request(self.model)), reward, terminated, truncated, info


if gym is not None:
    try:
        gym.register(id="ConnectTycoon-v0", entry_point="connect_tycoon.env:CompanyEnv")
        gym.register(id="ConnectTycoonJev-v0", entry_point="connect_tycoon.env:JevEnv")
    except Exception:       # 이미 등록됨
        pass
