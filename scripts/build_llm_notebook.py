"""notebooks/rl_decision_model_qwen_colab.ipynb 만들기 · Colab GPU에서 시뮬레이터 → Qwen 지도학습 → 강화학습 → Hugging Face."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build_notebook as B

REPO = B.REPO
CELLS = [
    ("md", """# RL AI COMPANY DECISION MAKING MODEL · Qwen 강화학습 (Colab)

**CONNECT AI LAB × AI CITY BUILDERS** · [CONNECT TYCOON](https://github.com/wonseokjung/connect-tycoon)

시뮬레이터에서 강화학습한 판단을 언어 모델 **Qwen3.5-0.8B**에 옮기고, 언어 모델을 다시 강화학습시켜 Hugging Face에 올립니다.

1. **선생님** · 작은 정책이 시뮬레이터에서 회사를 수천 달 운영하며 배웁니다 (PPO)
2. **문제집** · 판단마다 선택지를 바꿔 그 달을 끝까지 다시 돌려, 선택지별 점수를 매깁니다
3. **지도학습** · Qwen이 점수가 가장 높은 보기를 따라 배웁니다 (LoRA)
4. **강화학습** · 보기 전체를 한 묶음으로 보고, 점수가 높은 보기의 확률을 올립니다
5. **채점** · 학습 전 · 지도학습 · 강화학습을 같은 시험으로 비교하고, Qwen을 회사 사장 자리에 앉혀 봅니다
6. **공개** · Hugging Face에 어댑터와 모델 카드

> 메뉴 **런타임 → 런타임 유형 변경 → GPU (T4 이상)**. 왼쪽 🔑(보안 비밀)에 `HF_TOKEN`(Write 권한)을 넣어 두면 마지막 셀에서 바로 올라갑니다."""),
    ("code", f"""# 설치 (2~3분)
!pip -q install "connect-tycoon @ git+{REPO}" "transformers==5.18.0" peft accelerate huggingface_hub
import torch, connect_tycoon as ct
print("CONNECT TYCOON", ct.__version__, "· GPU", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "없음 (런타임을 GPU로 바꾸세요)")""", "install"),
    ("md", """## 1 · 선생님 · 시뮬레이터에서 강화학습

공개 데이터로 맞춘 **일반 회사**에서 규칙을 먼저 따라 배우고(지도학습), 회사의 가치로 받은 보상으로 판단을 고칩니다(PPO). CPU로 2~3분."""),
    ("code", """VALUES = {"이익": 1.0, "고객 만족": 1.0, "위험": 1.0}      # 회사의 가치 (보상의 가중치)
company = ct.make_company(profile="general", values=VALUES)
teacher = ct.LinearPolicy()
ct.imitate(company, teacher, ct.RulePolicy(), months=40, steps=1500, soften=1.0)
ct.train_ppo(company, teacher, iterations=60, months_per_iter=24, lr=0.15, seed=1, eval_every=10)
print("선생님 한 달 이익", round(ct.evaluate(company, teacher)["profit"]), "만원 · 규칙 사장", round(ct.evaluate(company, ct.RulePolicy())["profit"]), "만원")""", None),
    ("md", """## 2 · 문제집 · 시뮬레이터가 선택지마다 끝까지 다시 돌려 봅니다

문제 하나는 C1과 같은 모양입니다: 상황 · 질문 · 보기(A, B, C…) → 답은 글자 하나."""),
    ("code", """from connect_tycoon.llm import data as D
TRAIN_MONTHS = 10                                       # 늘릴수록 문제가 많아집니다 (한 달 ≈ 400문제 · 5초)
splits = {"train": range(20000, 20000 + TRAIN_MONTHS), "valid": range(21000, 21002), "test": range(22000, 22002)}
print(D.build(company, teacher, "llm_data", splits=splits, log=None))
ex = D.load("llm_data", "test")[3]
print(ex["task"]["question"]); print(ex["task"]["state"])
for o, s in zip(ex["task"]["options"], ex["scores"]): print(f"  {o['label']} {o['description']:40s} 점수 {s:.1f}")
print("정답", ex["answer"])""", None),
    ("md", """## 3 · 학습 전 Qwen 채점"""),
    ("code", """from connect_tycoon.llm import train_torch as T
test = D.load("llm_data", "test")
base = T.Scorer()
results = {"Qwen 학습 전": D.agreement(test, base.pick)}
print(results)
del base; torch.cuda.empty_cache()""", None),
    ("md", """## 4 · 지도학습 · 점수가 가장 높은 보기를 따라 배우기 (T4 기준 10~20분)"""),
    ("code", """sft = T.sft("llm_data", "adapters/sft", epochs=1, lr=1e-4, batch=8)
results["지도학습"] = D.agreement(test, sft.pick)
print(results["지도학습"])
del sft; torch.cuda.empty_cache()""", None),
    ("md", """## 5 · 강화학습 · 시뮬레이터 점수로 고치기

손실 = −Σ p(보기) · 장점(보기) + β · KL(p ‖ 지도학습 모델). 장점은 그 문제 안에서 평균을 뺀 선택지별 점수입니다.
표본을 뽑는 대신 보기 전체의 확률을 정확히 쓰는 GRPO 방식입니다."""),
    ("code", """rlm, hist = T.rl("llm_data", "adapters/sft", "adapters/rl", steps=150, batch=8, lr=2e-5, beta=0.05)
results["강화학습"] = D.agreement(test, rlm.pick)
for k, v in results.items(): print(f"{k:10s} 정답률 {v['accuracy']:.1%} · 후회 {v['regret']:.2f}")""", None),
    ("md", """## 6 · Qwen을 회사 사장 자리에 앉히기 · 시뮬레이터 + 실제 데이터 시험"""),
    ("code", """from connect_tycoon.llm.policy import LLMPolicy, report
r = report(LLMPolicy(rlm, company.values), company, months=2, demand_months=0)
results["강화학습"].update(r)
print(r)
print("선생님(작은 정책)", round(ct.evaluate(company, teacher, seeds=range(7000, 7002))["profit"]), "만원")""", None),
    ("md", """## 7 · Hugging Face에 올리기

🔑 `HF_TOKEN`을 쓰고, 토큰은 코드에 적지 않습니다."""),
    ("code", """from google.colab import userdata
from connect_tycoon.llm.hub import push
import json
meta = json.load(open("llm_data/meta.json"))
REPO_ID = None                                           # 예: "내아이디/rl-ai-company-decision-model" · 비우면 자동
print(push("adapters/rl", repo=REPO_ID, results=results, meta=meta, backend="torch", token=userdata.get("HF_TOKEN")))""", None),
    ("md", """## (선택) 하나의 모델로 합치고 GGUF로 · Ollama · LM Studio

LoRA를 바탕 모델에 합친 뒤 llama.cpp로 GGUF를 만듭니다."""),
    ("code", """T.merge("adapters/rl", "merged")
!git clone -q --depth 1 https://github.com/ggml-org/llama.cpp
!pip -q install -r llama.cpp/requirements/requirements-convert_hf_to_gguf.txt
!python llama.cpp/convert_hf_to_gguf.py merged --outtype q8_0 --outfile rl-decision-model-q8_0.gguf
print("rl-decision-model-q8_0.gguf")""", None),
]


if __name__ == "__main__":
    B.CELLS = CELLS
    path = B.build(os.path.join(os.path.dirname(__file__), "..", "notebooks", "rl_decision_model_qwen_colab.ipynb"))
    import json
    nb = json.load(open(path, encoding="utf-8"))
    nb["metadata"]["accelerator"] = "GPU"; nb["metadata"]["colab"]["gpuType"] = "T4"
    json.dump(nb, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(path)
