import json

from connect_tycoon.cli import main


def test_demo_prints_jev(capsys):
    main(["demo", "--dept", "security"])
    out = capsys.readouterr().out
    assert '"choice"' in out and '"criteria"' in out


def test_jev_export(tmp_path):
    out = tmp_path / "m.jsonl"
    main(["jev", "--seed", "7000", "--out", str(out)])
    rows = [json.loads(l) for l in open(out, encoding="utf-8")]
    assert rows and {"request", "response", "reward"} <= set(rows[0])


def test_ask(tmp_path, capsys):
    req = {"state": {"department": "refund", "amount": 11, "reason": "의심", "tier": "신규", "fraud_score": 0.9},
           "questions": {"decision": {"type": "choice", "criteria": {"full": "전액 환불", "deny": "거절", "human": "사람 확인"}}}}
    p = tmp_path / "r.json"; p.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    main(["ask", "--request", str(p)])
    ans = json.loads(capsys.readouterr().out)["answers"]["decision"]
    assert ans["choice"] in ("full", "deny", "human")
