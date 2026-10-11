import connect_tycoon as ct
from connect_tycoon import jev


def test_team_routes_departments_and_keeps_jev_in_order(company, brain):
    rule = ct.RulePolicy()
    team = ct.TeamPolicy({"refund": jev.JevPolicy(brain, values=company.values, config=company.cfg)}, default=rule)
    log, days = company.run_month(7002, team)
    asked = [x for x in log if x["dept"] and not x["ruled"]]
    assert len(team.trace) == len(asked)
    for x, rec in zip(asked, team.trace):
        assert (rec is not None) == (x["dept"] == "refund")
        if rec is not None:
            assert rec["request"]["state"]["department"] == "refund"
    rule_only = company.run_month(7002, rule)[0]
    assert [x["action"] for x in log if x["dept"] == "staffing"] == [x["action"] for x in rule_only if x["dept"] == "staffing"]


def test_best_team_is_never_worse_than_best_single(company, brain):
    cands = {"rule": ct.RulePolicy(), "brain": brain.policy}
    assign, best = ct.best_team(company, cands, seeds=range(9000, 9003), rounds=1, log=None)
    singles = [ct.evaluate(company, ct.TeamPolicy({d: cands[n] for d in ct.DEPT_ORDER}), range(9000, 9003))["profit"] for n in cands]
    assert set(assign) == set(ct.DEPT_ORDER)
    assert best >= max(singles) - 1e-9


def test_counterfactual_labels(company, brain, tmp_path):
    from connect_tycoon import labels
    rows = labels.counterfactual(company, brain.policy, 7005, stride=40)
    assert rows and all(set(r["q"]) == set(ct.DEPTS[r["dept"]]["actions"]) for r in rows)
    base = sum(x["reward"] for x in company.run_month(7005, brain.policy)[0])
    assert all(abs(r["q"][r["chosen"]] - base) < 1e-9 for r in rows)
    n = labels.export(rows, company, sft_path=str(tmp_path / "s.jsonl"), pairs_path=str(tmp_path / "p.jsonl"), raw_path=str(tmp_path / "r.jsonl"))
    assert n["sft"] == len(rows) == n["raw"]


def test_train_only_selected_questions(company):
    pol = ct.LinearPolicy()
    ct.imitate(company, pol, ct.RulePolicy(), months=4, steps=50)
    before = {d: pol.heads[d]["W"].copy() for d in ct.DEPT_ORDER}
    ct.train_ppo(company, pol, iterations=2, months_per_iter=4, eval_every=99, log=None, depts={"refund"})
    import numpy as np
    assert not np.allclose(before["refund"], pol.heads["refund"]["W"])
    assert all(np.allclose(before[d], pol.heads[d]["W"]) for d in ct.DEPT_ORDER if d != "refund")
