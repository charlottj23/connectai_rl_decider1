"""JEV로 답하는 아무 모델이나 사장 자리에 앉히고, 한 달의 (요청, 응답, 보상)을 학습 데이터로 저장합니다.

OPENROUTER_API_KEY가 있으면 진짜 typesafe/jev-1.13에게 묻습니다 (몇 건만).
"""
import os

import connect_tycoon as ct
from connect_tycoon import jev


def cautious_model(request):
    """아주 단순한 JEV 모델 (규칙 몇 줄). 여러분의 LLM · 분류기 · 무엇이든 이 자리에 들어갑니다."""
    st = request["state"]
    dept, c = st["department"], st["company"]
    if dept == "staffing": choice = "review_focus"
    elif dept == "inventory": choice = "large" if c["stock"] + c["incoming"] < 200 else "small" if c["stock"] + c["incoming"] < 260 else "none"
    elif dept == "marketing": choice = "keep"
    elif dept == "cs": choice = "human" if any(w in st["message"] for w in ("고소", "신고", "변호사", "위반")) else "normal"
    elif dept == "refund": choice = "human" if st["fraud_score"] >= 0.5 or st["amount"] >= 8 else "full"
    else: choice = "block" if st["fraud_score"] >= 0.7 else "human" if st["fraud_score"] >= 0.4 else "allow"
    return {"model": "my/cautious", "answers": {"decision": {"type": "choice", "choice": choice}}}


company = ct.make_company()
policy = jev.JevPolicy(cautious_model)
log, days = company.run_month(7000, policy)
rows = jev.dataset(policy.log, log, seed=7000)
jev.write_jsonl(rows, "cautious_month.jsonl")
print(f"판단 {len(rows)}개 · 한 달 이익 {sum(d['profit'] for d in days):.0f}만원 → cautious_month.jsonl")

key = os.environ.get("OPENROUTER_API_KEY")
if key:
    agent = jev.OpenRouterJev(api_key=key)
    env = ct.JevEnv(company=company)
    req, _ = env.reset(options={"month_seed": 7000})
    for _ in range(3):
        resp = agent(req)
        print(req["state"]["department"], "→", resp["answers"]["decision"]["choice"])
        req, r, done, _, _ = env.step(resp)
