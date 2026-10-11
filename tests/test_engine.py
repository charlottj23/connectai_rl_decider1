"""엔진이 강의 Colab의 connect_company.py와 숫자까지 같은지, 그리고 결정적인지 확인합니다."""
import json
import os

import pytest

import connect_tycoon as ct

GOLDEN = json.load(open(os.path.join(os.path.dirname(__file__), "golden_connect_company.json"), encoding="utf-8"))


@pytest.mark.parametrize("name", ["rule", "ai"])
@pytest.mark.parametrize("seed", [7000, 7001, 7002])
def test_same_month_as_lecture_engine(company, brain, name, seed):
    pol = ct.RulePolicy() if name == "rule" else brain.policy
    log, days = company.run_month(seed, pol)
    g = GOLDEN[f"{name}-{seed}"]
    assert [x["action"] for x in log] == g["actions"]
    assert [d["profit"] for d in days] == pytest.approx(g["profit"], abs=1e-9)
    assert [d["sat"] for d in days] == pytest.approx(g["sat"], abs=1e-12)
    assert [d["stock"] for d in days] == g["stock"]
    assert sum(x["reward"] for x in log) == pytest.approx(g["month_reward"], abs=1e-9)


@pytest.mark.parametrize("name", ["rule", "ai"])
def test_same_40_month_exam(company, brain, name):
    pol = ct.RulePolicy() if name == "rule" else brain.policy
    ev = ct.evaluate(company, pol)
    for k, v in GOLDEN[f"{name}-eval"].items():
        assert ev[k] == pytest.approx(v, abs=1e-9), k


def test_deterministic_and_config_changes_month(company):
    a = company.run_month(123, ct.RulePolicy())[1]
    b = company.run_month(123, ct.RulePolicy())[1]
    assert [d["profit"] for d in a] == [d["profit"] for d in b]
    big = company.with_config({"base_demand": 60, "warehouse": 400, "order_scale": 1.5})
    c = big.run_month(123, ct.OwnerPolicy({}, demand_scale=1.5))[1]
    assert sum(d["sales"] for d in c) > sum(d["sales"] for d in a)


def test_unknown_config_rejected(brain):
    with pytest.raises(ValueError):
        ct.Company(brain.intuition, ct.load_pool(), config={"warehous": 300})


def test_hidden_truth_not_visible_to_policy(company):
    seen = []

    class Spy:
        def act(self, dept, obs, ev):
            seen.append(set(ev))
            return ct.RulePolicy().act(dept, obs, ev)
    company.run_month(5, Spy())
    assert all("abuse" not in keys and "truth" not in keys and "fraud" not in keys for keys in seen)
