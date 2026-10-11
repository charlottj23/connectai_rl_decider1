# -*- coding: utf-8 -*-
"""Hugging Face 모델 카드 · 회사 두뇌(brain.json)를 올릴 때 README.md를 만듭니다."""
import json

from . import jev as J
from .policies import RulePolicy
from .train import TEST_SEEDS, evaluate


def model_card(brain, company, repo):
    pol = J.JevPolicy(brain, values=company.values, config=company.cfg, keep=False, check=False)
    me, rule = evaluate(company, pol, TEST_SEEDS), evaluate(company, RulePolicy(), TEST_SEEDS)
    env = __import__("connect_tycoon").CompanyEnv(company=company)
    env.reset(options={"month_seed": 7000})
    while env.decision.dept != "refund":
        d = env.decision
        env.step(__import__("connect_tycoon").DEPTS[d.dept]["actions"].index(brain.act(d.dept, d.obs, d.ev)))
    req = env.jev_request()
    resp = brain(req)
    short = {"model": req["model"], "state": {k: req["state"][k] for k in ("department", "reason", "tier", "amount", "fraud_score")},
             "questions": req["questions"]}
    return f"""---
license: apache-2.0
language: [ko]
library_name: numpy
tags: [connect-ai-lab, connect-company, connect-tycoon, jev, jev-style, reinforcement-learning, ppo, decision-making, prefrontal-cortex, korean]
---
# {brain.name} · AI 사장 (CONNECT TYCOON)

개발자 **{brain.researcher or '익명'}** · 회사의 가치 `{json.dumps(brain.values, ensure_ascii=False)}`

[CONNECT TYCOON](https://github.com/wonseokjung/connect-tycoon)의 회사를 한 달(영업일 20일) 동안 운영하는 전전두엽입니다.
인력 배치 · 재고 발주 · 마케팅 · 고객센터 · 환불 · 보안을 판단하고, 모든 판단을 JEV(`typesafe/jev-1.13`)와 같은 형식으로 답합니다.
규칙 사장을 먼저 따라 배우고(지도학습), 회사의 가치로 받은 보상으로 판단을 고쳤습니다(PPO).

| 처음 보는 40개월 평균 | 한 달 이익 | 고객 만족 | 위험 사고 | 사람 확인 초과 | 품절일 |
|---|---|---|---|---|---|
| 규칙 사장 | {rule['profit']:.0f}만원 | {rule['sat']:.0%} | {rule['incidents']:.1f}건 | {rule['human_over']:.1f}건 | {rule['stockout_days']:.1f}일 |
| **{brain.name}** | **{me['profit']:.0f}만원** | {me['sat']:.0%} | {me['incidents']:.1f}건 | {me['human_over']:.1f}건 | {me['stockout_days']:.1f}일 |

회사 규모(config): `{json.dumps(company.cfg, ensure_ascii=False)}`

## JEV로 묻고 답하기

```python
import connect_tycoon as ct
brain = ct.CompanyBrain.from_hub("{repo}")
brain({json.dumps(short, ensure_ascii=False)})
```

```json
{json.dumps(resp, ensure_ascii=False, indent=1)}
```

## 게임에서 사장으로 앉히기

```bash
pip install "connect-tycoon[game]"
connect-tycoon play --brain hf:{repo}
```

## Jay와 함께 AI 만들기

- [Connect AI LAB 유튜브](https://www.youtube.com/channel/UCdLZ0MsYS4hmqFgOYCB6C9w) · 도구와 모델을 만드는 과정
- [Connect AI LAB](https://www.aicitybuilders.com/lab) · 연결되는 모델 연구 (멤버 공개)
- [AI City Builders](https://www.aicitybuilders.com) · AI로 혼자서도 사업을 만드는 교육과 커뮤니티

합성 회사 시뮬레이터 위의 교육용 모형입니다. 실제 경영 성과를 보장하거나 예측하지 않습니다.
"""
