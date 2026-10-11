# -*- coding: utf-8 -*-
"""notebooks/connect_tycoon_colab.ipynb 만들기 · 셀 내용은 여기서 고칩니다."""
import json
import os

REPO = "https://github.com/wonseokjung/connect-tycoon"

CELLS = [
    ("md", """# 🏢 AI 사장 키우기 · CONNECT TYCOON (Colab)

JEV 의사결정 두뇌를 **강화학습**으로 키우는 기업 경영 시뮬레이터입니다.

이 노트북에서 할 일
1. 회사를 구경하고, 세 사장(무작위 · 규칙 · AI)의 한 달을 비교합니다.
2. 회사의 모든 판단이 **JEV 요청 · 응답**으로 오가는 것을 봅니다.
3. **내 회사의 가치**를 정하고 내 AI 사장을 키웁니다 (지도학습 → PPO).
4. 내 두뇌가 운영하는 하루를 **영상**으로 봅니다.
5. JEV 학습 데이터를 저장하고, **허깅페이스**에 올립니다.

> 왼쪽 🔑(보안 비밀)에 `HF_TOKEN`(Write 권한)을 넣어 두면 마지막 셀에서 바로 올라갑니다."""),
    ("code", f"""# ① 설치 (1분)
!pip -q install "connect-tycoon[game] @ git+{REPO}"
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"   # 화면 없이 게임 그림을 그립니다
import connect_tycoon as ct
print("CONNECT TYCOON", ct.__version__)""", "install"),
    ("md", """## 회사 구경 · 같은 한 달, 세 사장

엔진은 결정적입니다. 같은 시드(7000)면 같은 손님이 옵니다. 그래서 사장만 바꿔서 공정하게 비교할 수 있습니다."""),
    ("code", """company = ct.make_company()
example = ct.CompanyBrain.default()          # CONNECT AI LAB의 예시 AI 사장

for name, ceo in [("무작위", ct.RandomPolicy(0)), ("규칙 사장", ct.RulePolicy()), ("예시 AI 사장", example)]:
    log, days = company.run_month(7000, ceo)
    print(f"{name:8s} 한 달 이익 {sum(d['profit'] for d in days):6.0f}만원 · 월말 고객 만족 {days[-1]['sat']:.0%} · "
          f"위험 사고 {sum(d['incidents'] for d in days):2d}건 · 품절 {sum(d['unmet'] > 0 for d in days):2d}일")""", None),
    ("md", """## 판단 하나 = JEV 요청 하나 + 응답 하나

환불 요청 하나가 들어왔을 때 회사가 두뇌에게 묻는 모양과, 두뇌의 답입니다. OpenRouter의 `typesafe/jev-1.13`과 같은 모양입니다."""),
    ("code", """import json
env = ct.JevEnv(company=company)
request, info = env.reset(options={"month_seed": 7000})
while request["state"]["department"] != "refund":
    request, *_ = env.step(example(request))
print("── 요청 (회사 → 두뇌)"); print(json.dumps(request, ensure_ascii=False, indent=1)[:1500])
print("── 응답 (두뇌 → 회사)"); print(json.dumps(example(request), ensure_ascii=False, indent=1))""", None),
    ("md", """## 내 회사의 가치 · 내 AI 사장 키우기

보상 = 이익 × (만원/10) + 고객 만족 × (만족 변화 × 100) − 위험 × (사고 × 5).
가치를 바꾸면 **다른 성격의 사장**이 나옵니다. 이익만 중요하면 공격적으로, 위험 회피가 중요하면 신중하게.

1. **지도학습** · 규칙 사장의 판단을 따라 합니다 (C1을 만든 SFT와 같은 단계).
2. **PPO** · 한 달을 수백 번 운영하며 보상이 커지도록 판단을 고칩니다."""),
    ("code", """MY_NAME = "my-ceo"                                   # ✏️ 내 두뇌 이름 (영어 · 숫자 · -)
VALUES = {"이익": 1.0, "고객 만족": 1.0, "위험": 1.0}       # ✏️ 내 회사의 가치 (0 ~ 3)
UPGRADES = {}                                         # ✏️ 회사 규모 · 예: {"demand": 1, "logistics": 1}

from connect_tycoon.career import config_for
my_company = ct.make_company(config=config_for(UPGRADES), values=VALUES)
history = []
policy, history = ct.grow_brain(my_company, ct.RulePolicy(), iterations=60, months_per_iter=24, seed=0,
                                log=None, callback=lambda r: print(f"반복 {r['iteration']:>2} · 검증 이익 {r['eval_profit']:.0f}만원") if "eval_profit" in r else None)""", None),
    ("code", """try:
    import matplotlib.pyplot as plt
    ev = [r for r in history if "eval_profit" in r]
    plt.figure(figsize=(7, 3)); plt.plot([r["iteration"] for r in ev], [r["eval_profit"] for r in ev], "o-", color="#7cb342")
    plt.title("검증 달의 한 달 이익 (만원)"); plt.xlabel("PPO 반복"); plt.grid(alpha=.3); plt.show()
except ImportError:
    pass

mine, rule = ct.evaluate(my_company, policy), ct.evaluate(my_company, ct.RulePolicy())
ex = ct.evaluate(my_company, ct.jev.JevPolicy(example, values=my_company.values, config=my_company.cfg, keep=False))
for name, r in [("규칙 사장", rule), ("예시 AI 사장", ex), (f"내 두뇌 · {MY_NAME}", mine)]:
    print(f"{name:16s} 처음 보는 40개월 · 한 달 {r['profit']:6.0f}만원 · 만족 {r['sat']:.0%} · 사고 {r['incidents']:.1f}건 · 품절 {r['stockout_days']:.1f}일")""", None),
    ("code", """spec = ct.CompanyBrain.make_spec(example.spec, policy, name=MY_NAME, values=VALUES, researcher="나",
                                 config=my_company.cfg, results={"test_profit": mine["profit"], "rule_profit": rule["profit"]})
my_brain = ct.CompanyBrain(spec)
my_brain.save("brain.json")
print(json.dumps(my_brain(request)["answers"]["decision"], ensure_ascii=False))   # 아까 그 환불 요청에 내 두뇌는?""", None),
    ("md", """## 내 두뇌가 운영하는 하루 (영상)

게임 화면을 화면 없이 그려서 영상으로 만듭니다. 7층 말풍선이 내 두뇌의 JEV 답입니다."""),
    ("code", """from connect_tycoon.game.record import record
from IPython.display import Video
video = record("brain.json", "my_day", day=2, size="960x600", fps=20, mp4=True, upgrades=UPGRADES or None)
Video(video, embed=True, width=720)""", None),
    ("md", """## JEV 학습 데이터

한 달 동안 오간 (요청, 응답, 보상, 진실)을 한 줄씩 저장합니다. 다른 JEV 모델을 강화학습시키는 데이터가 됩니다."""),
    ("code", """pol = ct.jev.JevPolicy(my_brain, values=my_company.values, config=my_company.cfg)
log, days = my_company.run_month(7000, pol)
rows = ct.jev.dataset(pol.log, log, seed=7000)
ct.jev.write_jsonl(rows, "jev_month.jsonl")
print(len(rows), "줄 →", "jev_month.jsonl"); print(json.dumps(rows[3], ensure_ascii=False)[:600])""", None),
    ("md", """## 허깅페이스에 올리기

`아이디/connect-company-이름` 저장소에 `brain.json`과 모델 카드가 올라갑니다.
그다음 누구든 게임에서 `connect-tycoon play --brain hf:아이디/connect-company-이름`으로 내 두뇌를 사장으로 앉힐 수 있습니다."""),
    ("code", """try:
    from google.colab import userdata
    os.environ["HF_TOKEN"] = userdata.get("HF_TOKEN")
except Exception:
    pass
if os.environ.get("HF_TOKEN"):
    !pip -q install huggingface_hub
    !connect-tycoon push --brain brain.json
else:
    print("HF_TOKEN이 없어 올리기를 건너뜁니다. 왼쪽 🔑에 HF_TOKEN(Write)을 넣고 다시 실행하세요.")""", "push"),
]


def build(path):
    nb = {"cells": [], "metadata": {"colab": {"provenance": [], "toc_visible": True}, "kernelspec": {"name": "python3", "display_name": "Python 3"},
                                    "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 0}
    for kind, src, tag in [(c[0], c[1], c[2] if len(c) > 2 else None) for c in CELLS]:
        cell = {"cell_type": "markdown" if kind == "md" else "code", "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
            if tag: cell["metadata"]["tags"] = [tag]
        nb["cells"].append(cell)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    return path


if __name__ == "__main__":
    print(build(os.path.join(os.path.dirname(__file__), "..", "notebooks", "connect_tycoon_colab.ipynb")))
