"""⑤ 공개 · 학습한 언어 모델 어댑터를 모델 카드와 함께 Hugging Face에 올립니다 (토큰은 환경변수 HF_TOKEN)."""
import json
import os

from .format import BASE_MODEL, SYSTEM

YT = "https://www.youtube.com/@CONNECT-AI-LAB"


def card(repo, results=None, meta=None, backend="mlx", base=BASE_MODEL):
    res = results or {}
    rows = []
    for name, r in res.items():
        line = f"| {name} | {r.get('accuracy', 0):.1%} | {r.get('regret', 0):.2f} |"
        if "profit" in r: line += f" {r['profit']:.0f}만원 |"
        else: line += " — |"
        if "card" in r: line += f" {r['card']['saved']:.0%} ({r['card']['caught']}/{r['card']['fraud']}) |"
        else: line += " — |"
        rows.append(line)
    table = "\n".join(["| 모델 | 시험 문제 정답률 | 후회 (작을수록 좋음) | 시뮬레이터 한 달 이익 | 실제 카드 거래 · 손실 줄임 |",
                       "|---|---|---|---|---|"] + rows) if rows else "학습 뒤 `connect-tycoon llm eval` 결과가 여기에 들어갑니다."
    m = meta or {}
    load = (f'from mlx_lm import load\nmodel, tok = load("{base}", adapter_path="adapter")' if backend == "mlx" else
            f'from transformers import AutoModelForCausalLM, AutoTokenizer\nfrom peft import PeftModel\n'
            f'tok = AutoTokenizer.from_pretrained("{base}")\nmodel = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained("{base}"), "{repo}")')
    return f"""---
license: apache-2.0
base_model: {base}
library_name: {"mlx" if backend == "mlx" else "peft"}
language: [ko]
tags: [reinforcement-learning, decision-making, connect-tycoon, connect-ai-lab, lora]
---

# RL AI COMPANY DECISION MAKING MODEL

회사의 판단 하나(상황 · 질문 · 보기)를 읽고 **보기 글자 하나**로 답하는 의사결정 모델입니다. 보기 글자의 확률이 선택지별 확률, 가장 큰 값이 확신입니다.
[CONNECT TYCOON](https://github.com/wonseokjung/connect-tycoon) 시뮬레이터에서 만든 학습 데이터로 `{base}`에 LoRA를 학습했습니다.

## 만든 방법

1. **시뮬레이터 강화학습** · 작은 정책이 회사를 수천 달 운영하며 배웁니다 (PPO). 이 정책이 선생님입니다.
2. **문제집** · 선생님이 운영하는 달마다, 판단 하나의 선택지를 바꿔 그 달을 끝까지 다시 돌려 선택지별 점수를 매깁니다.
3. **지도학습** · 점수가 가장 높은 보기를 따라 배웁니다.
4. **강화학습** · 보기 전체를 한 묶음으로 보고, 시뮬레이터 점수가 평균보다 높은 보기의 확률을 올립니다 (묶음 표준화 장점 + 출발 모델과의 KL).

회사 분포: `{m.get('profile', 'general')}` (공개 데이터로 맞춘 일반 회사) · 문제 수: {json.dumps(m.get('counts', {}), ensure_ascii=False)}

## 성적

{table}

## 쓰는 법

```python
{load}
```

지시문(system): `{SYSTEM}`
문제(user): `{{"state": "...", "question": "...", "options": [{{"label": "A", "key": "...", "description": "..."}}]}}` · 답: 글자 하나

## 만든 곳 · CONNECT AI LAB × AI CITY BUILDERS

- [CONNECT AI LAB 유튜브]({YT}) · AI 1인 기업 · 로컬 AI · 강화학습 무료 강의
- [AI CITY BUILDERS](https://www.aicitybuilders.com) · AI 비즈니스의 정석 · [강화학습 AI 과정](https://www.aicitybuilders.com/robot)
- [Connect AI](https://www.ezerai.xyz) · 기업 의사결정 모델 C1 공동 연구

합성 회사 시뮬레이터 위의 연구 · 교육용 모델입니다. 실제 경영 판단에 쓰기 전에 그 회사의 기록으로 다시 검증하세요.
"""


def push(adapter_dir, repo=None, results=None, meta=None, backend="mlx", token=None, private=False):
    from huggingface_hub import HfApi
    api = HfApi(token=token or os.environ.get("HF_TOKEN"))
    repo = repo or f"{api.whoami()['name']}/rl-ai-company-decision-model"
    api.create_repo(repo, exist_ok=True, private=private)
    api.upload_folder(folder_path=adapter_dir, path_in_repo="adapter" if backend == "mlx" else ".", repo_id=repo,
                      allow_patterns=["adapters.safetensors", "adapter_config.json", "adapter_model.safetensors", "*.json"])
    api.upload_file(path_or_fileobj=card(repo, results, meta, backend).encode("utf-8"), path_in_repo="README.md", repo_id=repo)
    return f"https://huggingface.co/{repo}"
