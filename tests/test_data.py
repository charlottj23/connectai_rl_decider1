"""공개 데이터 프로필 · 실제 데이터 시험."""
import connect_tycoon as ct
from connect_tycoon import backtest
from connect_tycoon.company import PROFILE_KEYS, load_profile, profiles
from connect_tycoon.policies import RandomPolicy, RulePolicy


def test_profile_file_has_sources_and_keys():
    p = load_profile("general")
    assert PROFILE_KEYS <= set(p)
    assert {"retail", "hotel", "bike", "card", "olist", "support"} <= set(p["sources"])
    assert all(src["license"] for src in p["sources"].values())
    assert abs(sum(p["tier_p"]) - 1) < 1e-3 and len(p["week_demand"]) == 5
    assert "general" in profiles() and "lecture" in profiles()


def test_general_company_is_deterministic_and_differs_from_lecture():
    lec = ct.make_company()
    gen = lec.with_config(profile="general")
    assert lec.profile is None and gen.profile_name == "general"
    a = gen.run_month(7000, RulePolicy())[1]
    b = gen.run_month(7000, RulePolicy())[1]
    assert [d["profit"] for d in a] == [d["profit"] for d in b]
    c = lec.run_month(7000, RulePolicy())[1]
    assert [d["demand"] for d in a] != [d["demand"] for d in c]
    assert lec.with_config(profile="general").with_config({"staff_bonus": 1}).profile_name == "general"   # 설정만 바꾸면 프로필은 그대로


def test_backtest_card_scores_real_cases():
    gen = ct.make_company(profile="general")
    rule, rnd = backtest.card(RulePolicy(), gen), backtest.card(RandomPolicy(0), gen)
    assert rule["cases"] > 500 and 0 < rule["fraud"] < rule["cases"]
    assert rule["caught"] + rule["missed"] == rule["fraud"]
    assert rule["loss"] < rule["allow_all_loss"] and rule["saved"] > rnd["saved"]


def test_backtest_demand_replays_real_days():
    gen = ct.make_company(profile="general")
    out = backtest.demand(RulePolicy(), gen)
    assert {"retail", "hotel", "bike"} <= set(out) and all(v["months"] >= 20 for k, v in out.items() if k != "profit")
    assert gen.replay is None                                  # 원래 회사는 그대로


def test_trained_brain_records_profile():
    gen = ct.make_company(profile="general")
    b = ct.CompanyBrain.default()
    spec = ct.CompanyBrain.make_spec(b.spec, b.policy, name="t", profile=gen.profile_name)
    assert spec["company"]["profile"] == "general"
