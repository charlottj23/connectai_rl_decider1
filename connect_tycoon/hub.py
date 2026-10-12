# -*- coding: utf-8 -*-
"""Hugging Face 모델 카드 · 회사 두뇌(brain.json)를 올릴 때 README.md를 만듭니다."""
import json
import os

from . import jev as J
from .policies import RulePolicy
from .train import TEST_SEEDS, evaluate


def model_card(brain, company, repo, author=None):
    from .llm.hub import author_section, brand_header, simulator_gif
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
pipeline_tag: reinforcement-learning
tags: [connect-ai-lab, deep-reinforcement-learning, gymnasium, connect-company, connect-tycoon, jev, jev-style, reinforcement-learning, ppo, decision-making, prefrontal-cortex, korean]
---

{brand_header()}

{author_section(author)}

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

{simulator_gif()}

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

## 만든 곳 · CONNECT AI LAB × AI CITY BUILDERS

AI 교육 브랜드 · Transforming Lives Through AI Education

- [CONNECT AI LAB 유튜브](https://www.youtube.com/@CONNECT-AI-LAB) · AI 1인 기업 · 로컬 AI · 강화학습 · JEV 무료 강의
- [AI CITY BUILDERS](https://www.aicitybuilders.com) · AI 비즈니스의 정석 · [강화학습 AI 과정](https://www.aicitybuilders.com/robot)
- [Connect AI](https://www.ezerai.xyz) · 기업 의사결정 모델 C1 공동 연구 · 모델 연결은 테스트 중

합성 회사 시뮬레이터 위의 교육용 모형입니다. 실제 경영 성과를 보장하거나 예측하지 않습니다.
"""


def push_brain(path, repo=None, version="v1", name=None, author=None, token=None):
    """brain.json 하나를 Hugging Face에 올립니다 · 이름은 connectailab-rl-이름-버전-teacher (이름을 안 주면 HF 아이디).
    토큰은 `hf auth login`으로 저장된 것 또는 환경변수 HF_TOKEN (코드에 적지 않습니다)."""
    from huggingface_hub import HfApi

    import connect_tycoon as ct
    from .llm.hub import repo_name
    b = ct.CompanyBrain.from_file(path)
    api = HfApi(token=token or os.environ.get("HF_TOKEN"))
    if not repo:
        user = api.whoami()["name"]
        repo = f"{user}/{repo_name(name or user, version or 'v1', 'teacher')}"
    api.create_repo(repo, exist_ok=True)
    co = ct.make_company(config=b.spec["company"].get("config"), profile=b.spec["company"].get("profile"))   # 학습한 회사 그대로
    api.upload_file(path_or_fileobj=path, path_in_repo="brain.json", repo_id=repo)
    api.upload_file(path_or_fileobj=model_card(b, co, repo, author=author).encode("utf-8"), path_in_repo="README.md", repo_id=repo)
    return f"https://huggingface.co/{repo}"


def find_about():
    """자기소개 글 · 지금 폴더나 다운로드 폴더의 about_me.md (없으면 빈 글)."""
    for d in (os.getcwd(), os.path.join(os.path.expanduser("~"), "Downloads")):
        f = os.path.join(d, "about_me.md")
        if os.path.exists(f):
            return open(f, encoding="utf-8").read()
    return ""
