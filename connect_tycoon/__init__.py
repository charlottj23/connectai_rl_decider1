# -*- coding: utf-8 -*-
"""CONNECT TYCOON · JEV 의사결정 두뇌를 강화학습으로 키우는 기업 경영 시뮬레이터

    import connect_tycoon as ct
    company = ct.make_company()                        # 회사 하나 (강의 Colab과 같은 회사)
    brain = ct.CompanyBrain.default()                  # 예시 AI 사장
    log, days = company.run_month(7000, brain)         # 한 달 운영
    brain(ct.jev.request(...))                         # JEV로 묻고 답하기

게임:  python -m connect_tycoon play      학습:  python -m connect_tycoon train
"""
from . import jev
from .brain import CompanyBrain
from .company import (DAYS, DEFAULT_CONFIG, DEFAULT_RULES, DEFAULT_VALUES, DEPT_ORDER, DEPTS, MORNING, OBS_NAMES, Company,
                      Decision, load_pool)
from .env import CompanyEnv, JevEnv, default_company
from .policies import LinearPolicy, OwnerPolicy, RandomPolicy, RulePolicy
from .team import TeamPolicy, best_team
from .train import TEST_SEEDS, evaluate, grow_brain, imitate, train_ppo

__version__ = "0.1.0"


def make_company(config=None, values=None, rules=None, profile=None):
    """예시 두뇌의 고객 문의 직관으로 회사를 만듭니다. profile="general"이면 공개 데이터로 맞춘 일반 회사입니다."""
    return default_company(config=config, values=values, rules=rules, profile=profile)


__all__ = ["Company", "CompanyBrain", "CompanyEnv", "JevEnv", "LinearPolicy", "OwnerPolicy", "RandomPolicy", "RulePolicy",
           "DEFAULT_CONFIG", "DEFAULT_RULES", "DEFAULT_VALUES", "DEPTS", "DEPT_ORDER", "MORNING", "OBS_NAMES", "DAYS", "Decision",
           "evaluate", "imitate", "train_ppo", "grow_brain", "TEST_SEEDS", "jev", "load_pool", "make_company", "TeamPolicy", "best_team", "__version__"]
