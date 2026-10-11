"""① 문제집 · 시뮬레이터의 판단을 언어 모델 학습 데이터로.

선생님 정책(시뮬레이터에서 강화학습한 brain.json)이 한 달을 운영하는 동안, 판단마다 선택지를 하나씩 바꿔
그 달을 끝까지 다시 돌립니다(labels.counterfactual). 그러면 선택지마다 '그렇게 했으면 그 달의 보상이 얼마였나'가 나옵니다.

    sft/train.jsonl   {"messages": [system, user(문제), assistant(점수가 가장 높은 보기 글자)]}   ← mlx_lm.lora · peft 그대로
    rl/train.jsonl    {"task": 문제, "scores": [선택지별 점수], "teacher": 선생님이 고른 글자, "dept": ...}

달(seed)로 나눠서 train · valid · test가 섞이지 않게 합니다.
"""
import json
import os

from .. import labels
from ..company import DEPTS, MORNING
from .format import LETTERS, messages, task

SPLITS = {"train": range(20000, 20030), "valid": range(21000, 21004), "test": range(22000, 22004)}


def rows_for_month(company, teacher, seed, stride=1, min_gap=1e-6):
    out = []
    for r in labels.counterfactual(company, teacher, seed, stride=stride):
        acts = DEPTS[r["dept"]]["actions"]
        scores = [r["q"][a] for a in acts]
        if max(scores) - min(scores) < min_gap and r["dept"] not in MORNING:   # 무엇을 골라도 결과가 같은 판단은 배울 것이 없습니다
            continue
        t = task(r["dept"], r["ev"], company.values)
        best = max(range(len(acts)), key=lambda i: scores[i])
        teacher = acts.index(r["chosen"])
        # 아침 판단(인력 · 재고 · 광고)은 하루만 바꾼 점수가 작고 흔들려서, 수천 달 운영한 선생님의 답을 정답으로 씁니다.
        # 낮의 일(문의 · 환불 · 결제)은 시뮬레이터가 끝까지 돌려 본 점수로 정답을 고릅니다.
        morning = r["dept"] in MORNING
        out.append({"task": t, "scores": [round(s, 4) for s in scores], "answer": LETTERS[teacher if morning else best],
                    "label": "teacher" if morning else "simulator", "teacher": LETTERS[teacher], "dept": r["dept"], "seed": seed, "index": r["index"]})
    return out


def build(company, teacher, out_dir, splits=None, stride=1, sft_gap=0.2, log=print):
    """문제집을 만듭니다. 반환: {split: 문제 수}. 30달이면 노트북 CPU로 몇 분 걸립니다."""
    splits = splits or SPLITS
    os.makedirs(os.path.join(out_dir, "sft"), exist_ok=True); os.makedirs(os.path.join(out_dir, "rl"), exist_ok=True)
    counts = {}
    for name, seeds in splits.items():
        rows = []
        for i, s in enumerate(seeds):
            rows += rows_for_month(company, teacher, s, stride=stride)
            if log: log(f"{name} {i + 1}/{len(seeds)}달 · 문제 {len(rows)}개")
        with open(os.path.join(out_dir, "sft", f"{name}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:                                    # 1등과 2등이 거의 같은 문제는 따라 배울 정답이 없습니다
                s = sorted(r["scores"])
                if r.get("label") == "teacher" or s[-1] - s[-2] >= sft_gap:
                    f.write(json.dumps({"messages": messages(r["task"], r["answer"])}, ensure_ascii=False) + "\n")
        with open(os.path.join(out_dir, "rl", f"{name}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        counts[name] = len(rows)
    by = {}
    for r in load(out_dir, "train"):
        by[r["dept"]] = by.get(r["dept"], 0) + 1
    meta = {"counts": counts, "train_by_dept": by, "profile": company.profile_name, "values": company.values,
            "teacher": getattr(teacher, "name", type(teacher).__name__), "splits": {k: [v.start, v.stop] for k, v in splits.items()}}
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return counts


def load(out_dir, split="train"):
    with open(os.path.join(out_dir, "rl", f"{split}.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def agreement(rows, pick):
    """pick(task) → 글자. 정답(점수 최고) 일치율과, 고른 답의 점수가 최고점에서 얼마나 모자란지(후회, 작을수록 좋음)."""
    hit, regret = 0, 0.0
    for r in rows:
        k = LETTERS.index(pick(r["task"]))
        hit += (LETTERS[k] == r["answer"]) if r.get("label") == "teacher" else (r["scores"][k] == max(r["scores"]))
        regret += max(r["scores"]) - r["scores"][k]
    n = max(1, len(rows))
    return {"accuracy": hit / n, "regret": regret / n, "n": len(rows)}
