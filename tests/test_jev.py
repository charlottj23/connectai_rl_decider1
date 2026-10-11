"""JEV로 물어도 숫자로 물어도 같은 판단이 나오는지, 그리고 요청 · 응답이 JEV 모양인지 확인합니다."""
import json

import numpy as np
import pytest

import connect_tycoon as ct
from connect_tycoon import jev


def test_request_round_trip_reproduces_engine_obs(company, brain):
    rows = []

    class Spy:
        def act(self, dept, obs, ev):
            rows.append((dept, obs, ev))
            return brain.act(dept, obs, ev)
    company.run_month(7003, Spy())
    assert {d for d, _, _ in rows} == set(ct.DEPT_ORDER)
    for dept, obs, ev in rows:
        req = jev.request(dept, ev, company.values, company.cfg)
        json.dumps(req, ensure_ascii=False)                      # JSON으로 보낼 수 있어야 합니다
        jev.validate_request(req)
        d2, obs2, _ = brain.observe(req)
        assert d2 == dept
        assert np.allclose(obs2, obs, atol=1e-12, rtol=0)


def test_jev_policy_matches_raw_policy(company, brain):
    raw = company.run_month(7004, brain)
    pol = jev.JevPolicy(brain, values=company.values, config=company.cfg)
    via = company.run_month(7004, pol)
    assert [x["action"] for x in raw[0]] == [x["action"] for x in via[0]]
    resp = pol.log[0]["response"]
    a = resp["answers"]["decision"]
    assert a["type"] == "choice" and a["choice"] in pol.log[0]["request"]["questions"]["decision"]["criteria"]
    assert abs(sum(a["probabilities"].values()) - 1) < 1e-3 and a["confidence"] == a["probabilities"][a["choice"]]
    rows = jev.dataset(pol.log, via[0], seed=7004)
    assert len(rows) == len(pol.log) and all("reward" in r for r in rows)


def test_rule_answers_with_certainty(brain):
    req = {"state": {"department": "security", "amount": 30, "fraud_score": 0.97}, "questions": {"decision": {"type": "choice", "criteria": {"allow": "허용", "block": "차단"}}}}
    a = brain(req)["answers"]["decision"]
    assert a["choice"] == "block" and a["confidence"] == 1.0 and a["reason"].startswith("규칙")


def test_bad_response_rejected():
    req = {"state": {}, "questions": {"decision": {"type": "choice", "criteria": {"a": "", "b": ""}}}}
    with pytest.raises(ValueError):
        jev.validate_response({"answers": {"decision": {"type": "choice", "choice": "c"}}}, req)
