import connect_tycoon as ct
from connect_tycoon.career import ACHIEVEMENTS, UPGRADES, Career, config_for, level_of


def test_default_career_is_lecture_company():
    assert config_for({}) == ct.DEFAULT_CONFIG


def test_every_upgrade_level_builds_a_valid_company(brain):
    for u in UPGRADES:
        for lv in range(1, 4):
            cfg = config_for({u["key"]: lv})
            co = ct.Company(brain.intuition, ct.load_pool(), config=cfg)
            days = co.run_month(7000, ct.OwnerPolicy({}, demand_scale=cfg["base_demand"] / 40))[1]
            assert len(days) == 20


def test_buy_opens_next_month_and_costs_cash(tmp_path):
    c = Career()
    ok, cost = c.can_buy("logistics")
    assert ok and cost == 600
    assert c.buy("logistics") and c.cash == 1000 - 600
    assert c.config["warehouse"] == 250            # 아직 공사 중
    assert c.open_new_month() == ["logistics"]
    assert c.config["warehouse"] == 350
    path = c.save(str(tmp_path / "save.json"))
    again = Career.load(path)
    assert again.upgrades == {"logistics": 1} and again.cash == c.cash


def test_levels_and_achievements_are_consistent():
    assert level_of(0)[0] == 0 and level_of(10000)[0] == 2
    assert len({a[0] for a in ACHIEVEMENTS}) == len(ACHIEVEMENTS)


def test_owner_normal_equals_rule_ceo(company):
    a = ct.evaluate(company, ct.RulePolicy(), range(7000, 7004))
    b = ct.evaluate(company, ct.OwnerPolicy({}), range(7000, 7004))
    assert a == b
