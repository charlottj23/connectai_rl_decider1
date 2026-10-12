"""모두의 모델 모으기 · Hugging Face에서 connectailab-으로 시작하는 모델을 찾아 같은 시험지로 채점하고, 연결(앙상블)해 봅니다.

    connect-tycoon llm collect --out collect            # 찾기 → 공통 시험지 → 채점 → 순위표 · 연결 결과
    from connect_tycoon.llm import collect as C
    models = C.find(); test = C.common_test("collect/test"); res = C.score(models, test); print(C.table(C.leaderboard(res, test)))

공정한 비교를 위해 모두 같은 시험지를 씁니다: 규칙 사장이 운영하는, 아무도 학습에 쓰지 않은 달(23000번대)의 낮 판단(문의 · 환불 · 결제).
연결 방식 세 가지
    평균      모델들의 선택지별 확률을 평균 내서 고릅니다
    투표      각 모델이 고른 답 중 가장 많은 것 (동점이면 평균 확률이 큰 쪽)
    가장 확신  문제마다 가장 확신하는 모델 하나에게 맡깁니다
"""
import json
import os

from .data import load
from .format import LETTERS

PREFIX = "connectailab-"
TEST_SEEDS = range(23000, 23003)


def kind_of(files):
    """저장소 파일 목록 → 모델 종류. mlx(Mac 어댑터) · peft(Colab · PyTorch 어댑터) · brain(작은 강화학습 정책)."""
    files = set(files)
    if "adapter/adapters.safetensors" in files: return "mlx"
    if "adapter_model.safetensors" in files: return "peft"
    if "brain.json" in files: return "brain"
    return "other"


def find(prefix=PREFIX, limit=500, token=None):
    """Hugging Face에서 이름이 prefix로 시작하는 모델 목록."""
    from huggingface_hub import HfApi
    api = HfApi(token=token or os.environ.get("HF_TOKEN"))
    out = []
    for m in api.list_models(search=prefix, limit=limit, full=True):
        name = m.id.split("/")[-1]
        if not name.lower().startswith(prefix):
            continue
        out.append({"repo": m.id, "owner": m.id.split("/")[0], "name": name, "kind": kind_of(s.rfilename for s in (m.siblings or [])),
                    "downloads": getattr(m, "downloads", 0), "likes": getattr(m, "likes", 0), "updated": str(getattr(m, "last_modified", ""))})
    return sorted(out, key=lambda x: x["repo"])


def local(path, name=None):
    """내 컴퓨터의 어댑터 폴더를 비교 목록에 넣습니다 (MLX: adapters.safetensors · PyTorch: adapter_model.safetensors)."""
    files = os.listdir(path)
    kind = "mlx" if "adapters.safetensors" in files else "peft" if "adapter_model.safetensors" in files else "other"
    return {"repo": name or ("local:" + os.path.normpath(path)), "owner": "local", "name": os.path.basename(os.path.normpath(path)),
            "kind": kind, "path": os.path.dirname(os.path.normpath(path)) if kind == "mlx" and os.path.basename(os.path.normpath(path)) == "adapter" else path}


def common_test(out_dir="collect/test", seeds=TEST_SEEDS, log=None):
    """공통 시험지 (한 번 만들면 다시 쓰기). 시뮬레이터 점수가 있는 낮의 일만 남깁니다."""
    path = os.path.join(out_dir, "rl", "test.jsonl")
    if not os.path.exists(path):
        import connect_tycoon as ct
        from .data import build
        build(ct.make_company(profile="general"), ct.RulePolicy(), out_dir, splits={"test": seeds}, log=log)
    return [r for r in load(out_dir, "test") if r.get("label") != "teacher"]


def metrics(probs, rows):
    """선택지별 확률 목록 → 정답률 · 후회 · 평균 확신 · 확신 차이(평균 확신 − 정답률, 0에 가까울수록 정직한 확신)."""
    hit, regret, conf = 0, 0.0, 0.0
    for p, r in zip(probs, rows):
        k = max(range(len(p)), key=lambda i: p[i])
        s = r["scores"]
        hit += s[k] == max(s); regret += max(s) - s[k]; conf += p[k]
    n = max(1, len(rows))
    return {"accuracy": hit / n, "regret": regret / n, "confidence": conf / n, "overconfidence": conf / n - hit / n, "n": len(rows)}


def ensemble(prob_sets, mode="mean"):
    """모델 여러 개의 확률 → 문제마다 하나의 확률. mode = mean · vote · confident."""
    out = []
    for per_q in zip(*prob_sets):                       # 문제 하나에 대한 모델별 확률
        k = len(per_q[0]); m = len(per_q)
        mean = [sum(p[i] for p in per_q) / m for i in range(k)]
        if mode == "mean":
            out.append(mean)
        elif mode == "vote":
            votes = [0] * k
            for p in per_q: votes[max(range(k), key=lambda i: p[i])] += 1
            best = max(range(k), key=lambda i: (votes[i], mean[i]))
            out.append([votes[i] / m + (1e-6 if i == best else 0.0) for i in range(k)])
        elif mode == "confident":
            out.append(list(max(per_q, key=max)))
        else:
            raise ValueError(mode)
    return out


def _scorer(path, kind, backend):
    if kind == "mlx":
        from .train_mlx import Scorer
        sub = os.path.join(path, "adapter")
        return Scorer(adapter=sub if os.path.isdir(sub) else path)
    from .train_torch import Scorer
    return Scorer(adapter=local)


def score(models, rows, out_dir="collect", max_rows=300, backend="auto", log=print):
    """모델마다 공통 시험지의 선택지별 확률을 구해 저장합니다 (다시 돌리면 저장한 것을 씁니다). 반환 {repo: {probs, metrics}}."""
    import importlib.util
    import platform
    from huggingface_hub import snapshot_download
    rows = rows[:max_rows] if max_rows else rows
    mac = platform.system() == "Darwin" and platform.machine() == "arm64" and importlib.util.find_spec("mlx_lm")
    os.makedirs(os.path.join(out_dir, "probs"), exist_ok=True)
    res = {}
    for m in models:
        cache = os.path.join(out_dir, "probs", m["repo"].replace("/", "__") + ".json")
        if os.path.exists(cache):
            probs = json.load(open(cache, encoding="utf-8"))["probs"]
        else:
            if m["kind"] not in ("mlx", "peft") or (m["kind"] == "mlx" and not mac):
                if log: log(f"건너뜀 · {m['repo']} ({m['kind']} 형식은 이 환경에서 채점하지 않습니다)")
                continue
            if log: log(f"채점 · {m['repo']} · {len(rows)}문제")
            try:
                where = m.get("path") or snapshot_download(m["repo"])          # 내 컴퓨터의 어댑터 폴더도 비교할 수 있습니다
                sc = _scorer(where, m["kind"], backend)
                probs = [sc.probs(r["task"]) for r in rows]
                del sc
            except Exception as e:  # 한 모델이 깨져도 나머지는 계속
                if log: log(f"실패 · {m['repo']} · {e}")
                continue
            finally:
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            json.dump({"repo": m["repo"], "probs": probs, "n": len(rows)}, open(cache, "w", encoding="utf-8"))
        res[m["repo"]] = {"probs": probs, **metrics(probs, rows), "owner": m.get("owner", m["repo"].split("/")[0])}
    return res


def leaderboard(res, rows, modes=("mean", "vote", "confident")):
    """순위표 (후회가 작은 순) + 연결 결과 세 가지. 모델이 2개 이상일 때만 연결을 계산합니다."""
    rows = rows[:min(len(v["probs"]) for v in res.values())] if res else rows
    board = [{"model": repo, "type": "model", **{k: v[k] for k in ("accuracy", "regret", "confidence", "overconfidence", "n")}}
             for repo, v in res.items()]
    if len(res) >= 2:
        sets = [v["probs"][:len(rows)] for v in res.values()]
        label = {"mean": "연결 · 확률 평균", "vote": "연결 · 다수결", "confident": "연결 · 가장 확신"}
        for mode in modes:
            board.append({"model": f"{label[mode]} ({len(sets)}개)", "type": "ensemble", **metrics(ensemble(sets, mode), rows)})
    return sorted(board, key=lambda b: (b["regret"], -b["accuracy"]))


def table(board):
    lines = ["| 순위 | 모델 | 정답률 | 후회 | 평균 확신 | 확신 − 정답률 |", "|---|---|---|---|---|---|"]
    for i, b in enumerate(board, 1):
        lines.append(f"| {i} | {b['model']} | {b['accuracy']:.1%} | {b['regret']:.2f} | {b['confidence']:.0%} | {b['overconfidence']:+.0%} |")
    return "\n".join(lines)


def save(board, out_dir="collect"):
    os.makedirs(out_dir, exist_ok=True)
    json.dump(board, open(os.path.join(out_dir, "leaderboard.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out_dir, "leaderboard.md"), "w", encoding="utf-8").write(table(board) + "\n")
    return os.path.join(out_dir, "leaderboard.md")


__all__ = ["PREFIX", "find", "common_test", "score", "metrics", "ensemble", "leaderboard", "table", "save", "LETTERS"]
