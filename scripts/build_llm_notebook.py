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
!pip -q install flash-linear-attention || echo "(빠른 계산 모듈 없이 진행 · 조금 느릴 뿐 결과는 같습니다)"
!pip -q uninstall -y torchao   # Colab 기본 torchao(0.10)가 최신 peft와 맞지 않습니다 · 이 학습에는 필요 없습니다
import torch, connect_tycoon as ct
print("CONNECT TYCOON", ct.__version__, "· GPU", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "없음 (런타임을 GPU로 바꾸세요)")""", "install"),
    ("md", """## 1 · 선생님 · 내 brain.json 쓰기 또는 새로 학습

**두 가지 중 하나**
- **게임에서 학습한 모델 쓰기** · `USE_MY_BRAIN`을 켜고 실행하면 파일 선택 창이 뜹니다. CONNECT TYCOON 게임의 "brain.json" 버튼으로 내려받은 파일을 고르세요. 게임에서 정한 회사의 가치도 그대로 가져옵니다.
- **여기서 새로 학습** · 끈 채로 실행하면 공개 데이터로 맞춘 일반 회사에서 작은 정책이 규칙을 따라 배우고(지도학습) 보상으로 판단을 고칩니다(PPO). CPU 2~3분.

**왜** · 언어 모델에게 가르칠 선생님이 필요합니다. 새로 학습할 때 `VALUES`(이익 · 고객 만족 · 위험 회피)를 바꾸면 다른 판단을 하는 모델이 나옵니다.

✅ **정상이면** · 선생님 한 달 이익 1,000만원 안팎 · 규칙 사장 300만원 안팎"""),
    ("code", """USE_MY_BRAIN = False                                   #@param {type:"boolean"}
VALUES = {"이익": 1.0, "고객 만족": 1.0, "위험": 1.0}      # 새로 학습할 때 회사의 가치 (보상의 가중치)

if USE_MY_BRAIN:                                       # 게임에서 내려받은 brain.json을 선생님으로
    from google.colab import files
    uploaded = files.upload()
    my_brain = ct.CompanyBrain.load(next(iter(uploaded)))
    VALUES = dict(my_brain.values)
    company = ct.make_company(profile=my_brain.spec["company"].get("profile") or "general", values=VALUES)
    teacher = my_brain.policy
    print("내 모델:", my_brain.name, "· 회사의 가치", VALUES)
else:                                                  # 여기서 새로 학습
    company = ct.make_company(profile="general", values=VALUES)
    teacher = ct.LinearPolicy()
    ct.imitate(company, teacher, ct.RulePolicy(), months=40, steps=1500, soften=1.0)
    ct.train_ppo(company, teacher, iterations=60, months_per_iter=24, lr=0.15, seed=1, eval_every=10)
print("선생님 한 달 이익", round(ct.evaluate(company, teacher)["profit"]), "만원 · 규칙 사장", round(ct.evaluate(company, ct.RulePolicy())["profit"]), "만원")""", None),
    ("md", """## 2 · 문제집 · 시뮬레이터가 선택지마다 끝까지 다시 돌려 봅니다 (1~2분)

**무엇을** · 선생님이 운영하는 달마다, 판단 하나의 선택지를 하나씩 바꿔 그 달을 끝까지 다시 돌립니다. 선택지마다 '그렇게 했으면 그 달 보상이 얼마였나'가 점수가 됩니다.
**왜** · 사람이 정답을 달지 않아도, 시뮬레이터가 결과로 정답을 매깁니다.
**정답 고르는 법** · 낮의 일(문의 · 환불 · 결제)은 점수가 가장 높은 보기, 아침 판단(인력 · 재고 · 광고)은 선생님의 답입니다. 아침 판단은 하루만 바꾼 점수가 작고 흔들려서, 그대로 배우면 모델이 상황을 보지 않고 한 가지 답만 외웁니다.
**모양** · 상황 · 질문 · 보기(A, B, C…) → 답은 글자 하나 (C1과 같은 형식)

✅ **정상이면** · 10달 기준 학습 약 4,000문제 · 검증 약 830 · 시험 약 840"""),
    ("code", """from connect_tycoon.llm import data as D
TRAIN_MONTHS = 10                                       # 늘릴수록 문제가 많아집니다 (한 달 ≈ 400문제 · 5초)
splits = {"train": range(20000, 20000 + TRAIN_MONTHS), "valid": range(21000, 21002), "test": range(22000, 22002)}
print(D.build(company, teacher, "llm_data", splits=splits, log=None))
ex = D.load("llm_data", "test")[3]
print(ex["task"]["question"]); print(ex["task"]["state"])
for o, s in zip(ex["task"]["options"], ex["scores"]): print(f"  {o['label']} {o['description']:40s} 점수 {s:.1f}")
print("정답", ex["answer"])""", None),
    ("md", """## 3 · 학습 전 Qwen 채점

**무엇을** · 아무것도 배우지 않은 Qwen3.5-0.8B에게 시험 문제를 풉니다. 보기 글자의 확률이 선택지별 확률, 가장 큰 값이 확신입니다.
**왜** · 학습 효과를 보려면 출발점을 먼저 재야 합니다.

✅ **정상이면** · 정답률 25~35% (거의 찍는 수준)"""),
    ("code", """from connect_tycoon.llm import train_torch as T
test = D.load("llm_data", "test")
base = T.Scorer()
results = {"Qwen 학습 전": D.agreement(test, base.pick)}
print(results)
del base; torch.cuda.empty_cache()""", None),
    ("md", """## 4 · 지도학습 · 점수가 가장 높은 보기를 따라 배우기 (T4 기준 10~20분)

**무엇을** · 정답 보기 글자를 맞히도록 LoRA를 학습합니다 (모델 전체가 아니라 작은 덧붙임 층만).
**왜** · 강화학습만으로는 출발점(30%)이 너무 낮아 배우기 어렵습니다. 먼저 따라 배워 기본기를 만듭니다.

✅ **정상이면** · 시험 정답률 80% 안팎"""),
    ("code", """sft = T.sft("llm_data", "adapters/sft", epochs=1, lr=1e-4, batch=8)
results["지도학습"] = D.agreement(test, sft.pick)
print(results["지도학습"])
del sft; torch.cuda.empty_cache()""", None),
    ("md", """## 5 · 강화학습 · 시뮬레이터 점수로 고치기 (T4 기준 5~10분)

**무엇을** · 보기 전체를 한 묶음으로 보고, 시뮬레이터 점수가 평균보다 높은 보기의 확률은 올리고 낮은 보기는 내립니다. 지도학습 모델에서 너무 멀어지지 않게 붙잡아 둡니다(KL).
**왜** · 따라 하기는 선생님을 넘을 수 없습니다. 결과로 배워야 더 나아집니다.
**손실** · −Σ p(보기) · 장점(보기) + β · KL(p ‖ 지도학습 모델). 강화학습은 점수가 또렷한 낮의 일에만 씁니다.

✅ **정상이면** · 정답률은 비슷하고 **후회**(고른 답이 최고점에서 모자란 정도)가 지도학습보다 작아집니다"""),
    ("code", """rlm, hist = T.rl("llm_data", "adapters/sft", "adapters/rl", steps=150, batch=8, lr=2e-5, beta=0.05)
results["강화학습"] = D.agreement(test, rlm.pick)
for k, v in results.items(): print(f"{k:10s} 정답률 {v['accuracy']:.1%} · 후회 {v['regret']:.2f}")""", None),
    ("md", """## 6 · Qwen을 회사 사장 자리에 앉히기 · 시뮬레이터 + 실제 데이터 시험 (3~5분)

**무엇을** · Qwen이 처음 보는 2달 동안 회사를 운영하고, 학습에 쓰지 않은 실제 카드 거래 713건(진짜 사기 177건)을 판단합니다.
**왜** · 시험 문제 정답률보다 중요한 것은 실제로 회사를 맡겼을 때의 결과입니다.

✅ **정상이면** · 한 달 이익 흑자 (Mac 첫 실험 757만원) · 실제 카드 거래 손실 줄임 70% 안팎. 선생님보다 아래여도 정상입니다 (첫 실험 · 문제 4천 개)."""),
    ("code", """from connect_tycoon.llm.policy import LLMPolicy, report
r = report(LLMPolicy(rlm, company.values), company, months=2, demand_months=0)
results["강화학습"].update(r)
print(r)
print("선생님(작은 정책)", round(ct.evaluate(company, teacher, seeds=range(7000, 7002))["profit"]), "만원")""", None),
    ("md", """## 7 · Hugging Face에 올리기

1. https://huggingface.co/settings/tokens 에서 **Write** 토큰을 만듭니다.
2. Colab 왼쪽 🔑(보안 비밀)에 이름 `HF_TOKEN`, 값에 토큰을 넣고 **노트북 액세스**를 켭니다.
3. **이름**을 영문으로 적습니다. 업로드 이름은 `connectailab-이름-버전` 입니다 (예: `connectailab-jay-v1`).
   다시 학습해서 올릴 때는 버전을 `v2`, `v3`…으로 올립니다.
4. 아래 셀을 실행하면 내 계정에 모델이 올라갑니다. 모델 카드(성적표 · 만든 방법 · 쓰는 법)와 **Reinforcement Learning** 분류가 함께 붙습니다.

토큰은 코드에 적지 않습니다."""),
    ("code", """from google.colab import userdata
from huggingface_hub import HfApi
from connect_tycoon.llm.hub import push, repo_name
import json, os

try:
    HF_TOKEN = userdata.get("HF_TOKEN")
except Exception:
    HF_TOKEN = None
assert HF_TOKEN, "왼쪽 🔑에 HF_TOKEN(Write 권한)을 넣고 노트북 액세스를 켜 주세요"
me = HfApi(token=HF_TOKEN).whoami()["name"]

NAME = "jay"                                         #@param {type:"string"}
VERSION = "v1"                                       #@param {type:"string"}
PRIVATE = False                                      #@param {type:"boolean"}
MODEL_NAME = repo_name(NAME, VERSION)                # connectailab-이름-버전
meta = json.load(open("llm_data/meta.json"))
url = push("adapters/rl", repo=f"{me}/{MODEL_NAME}", results=results, meta=meta, backend="torch", token=HF_TOKEN, private=PRIVATE)
print("올라갔습니다 ·", url)""", None),
    ("md", """### (선택) 선생님 정책도 올리기

시뮬레이터에서 PPO로 배운 작은 정책(brain.json)입니다. 언어 모델의 선생님이자, 그 자체로 강화학습 모델입니다."""),
    ("code", """TEACHER_NAME = repo_name(NAME, VERSION, "teacher")   # connectailab-이름-버전-teacher
spec = ct.CompanyBrain.make_spec(ct.CompanyBrain.default().spec, teacher, name=TEACHER_NAME, values=VALUES,
                                 researcher=me, config=company.cfg, profile="general",
                                 results={"test_profit": ct.evaluate(company, teacher)["profit"]})
ct.CompanyBrain(spec).save("teacher.json")
os.environ["HF_TOKEN"] = HF_TOKEN
!connect-tycoon push --brain teacher.json --repo {me}/{TEACHER_NAME}""", None),
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
