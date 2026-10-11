"""Colab · GPU (PyTorch + transformers + peft)로 지도학습 → 강화학습. Mac의 train_mlx와 같은 문제집 · 같은 손실입니다.

    pip install "transformers==5.18.0" peft accelerate
    from connect_tycoon.llm import train_torch as T
    T.sft("llm_data", "adapters/sft");  T.rl("llm_data", "adapters/sft", "adapters/rl")
"""
import json
import math
import os
import random

from .data import load
from .format import BASE_MODEL, LETTERS, messages
from .train_mlx import advantages


def _device():
    import torch
    if os.environ.get("CT_DEVICE"): return os.environ["CT_DEVICE"]
    return "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"


def _base(model, device):
    import torch
    from transformers import AutoModelForCausalLM
    # A100 · L4처럼 bfloat16을 지원하는 GPU만 bfloat16. T4(Colab 무료)와 CPU · Mac은 float32 (0.8B라 메모리는 충분합니다)
    dtype = torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported() else torch.float32
    return AutoModelForCausalLM.from_pretrained(model, dtype=dtype).to(device)


class Scorer:
    """문제 하나 → 보기 글자별 확률 (train_mlx.Scorer와 같은 쓰임)."""

    def __init__(self, model=BASE_MODEL, adapter=None, net=None, tok=None, device=None):
        from transformers import AutoTokenizer
        self.device = device or _device()
        self.tok = tok or AutoTokenizer.from_pretrained(model)
        if net is None:
            net = _base(model, self.device)
            if adapter:
                from peft import PeftModel
                net = PeftModel.from_pretrained(net, adapter)
        self.model = net
        self.letters = [self.tok.encode(L, add_special_tokens=False)[0] for L in LETTERS]
        self.name = os.path.basename(os.path.normpath(adapter)) if adapter else model

    def ids(self, t):
        text = self.tok.apply_chat_template(messages(t), tokenize=False, add_generation_prompt=True, enable_thinking=False)
        return self.tok(text, add_special_tokens=False)["input_ids"]

    def letter_logits(self, batch_ids):
        """오른쪽을 채운 묶음 → 각 문제 마지막 위치의 보기 글자 점수 (선형 어텐션 층이 있어 왼쪽 채우기는 쓰지 않습니다)."""
        import torch
        L = max(len(x) for x in batch_ids)
        pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else 0
        ids = torch.tensor([x + [pad] * (L - len(x)) for x in batch_ids], device=self.device)
        mask = torch.tensor([[1] * len(x) + [0] * (L - len(x)) for x in batch_ids], device=self.device)
        out = self.model(input_ids=ids, attention_mask=mask).logits
        last = torch.tensor([len(x) - 1 for x in batch_ids], device=self.device)
        return out[torch.arange(len(batch_ids), device=self.device), last][:, self.letters].float()

    def probs(self, t):
        import torch
        self.model.eval()
        with torch.no_grad():
            z = self.letter_logits([self.ids(t)])[0, :len(t["options"])]
        return torch.softmax(z, -1).tolist()

    def pick(self, t):
        p = self.probs(t)
        return LETTERS[max(range(len(p)), key=lambda i: p[i])]


def _sft_rows(data_dir, split="train"):
    rows = []
    with open(os.path.join(data_dir, "sft", f"{split}.jsonl"), encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)["messages"]
            rows.append((json.loads(m[1]["content"]), m[2]["content"]))
    return rows


def sft(data_dir, out, model=BASE_MODEL, epochs=1.0, lr=1e-4, batch=8, rank=8, seed=0, log=print):
    """② 지도학습 · 정답 보기 글자 하나를 맞히도록 LoRA를 학습합니다 (답 글자 위치의 교차 엔트로피)."""
    import torch
    from peft import LoraConfig, get_peft_model
    torch.manual_seed(seed); rnd = random.Random(seed)
    sc = Scorer(model)
    net = get_peft_model(sc.model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.0, target_modules="all-linear", task_type="CAUSAL_LM"))
    net.gradient_checkpointing_enable(); net.enable_input_require_grads(); net.config.use_cache = False
    sc.model = net
    rows = [(sc.ids(t), LETTERS.index(a)) for t, a in _sft_rows(data_dir)]
    steps = max(1, math.ceil(len(rows) * epochs / batch))
    opt = torch.optim.AdamW([p for p in net.parameters() if p.requires_grad], lr=lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(1, steps // 30)) * 0.5 * (1 + math.cos(math.pi * s / steps)))
    if log: log(f"지도학습 · 문제 {len(rows)}개 · {steps}걸음 × {batch} · {sc.device}")
    order = []
    net.train()
    for step in range(steps):
        if len(order) < batch:
            order += rnd.sample(range(len(rows)), len(rows))
        pick, order = order[:batch], order[batch:]
        z = sc.letter_logits([rows[i][0] for i in pick])
        loss = torch.nn.functional.cross_entropy(z, torch.tensor([rows[i][1] for i in pick], device=sc.device))
        loss.backward(); opt.step(); sched.step(); opt.zero_grad()
        if log and (step % 20 == 0 or step == steps - 1): log(f"걸음 {step + 1}/{steps} · 손실 {loss.item():.3f}")
    net.save_pretrained(out); sc.tok.save_pretrained(out)
    net.eval()
    return sc


def rl(data_dir, start, out, model=BASE_MODEL, steps=100, batch=8, lr=5e-6, beta=0.2, eval_every=50, seed=0, max_rows=1500, log=print):
    """③ 강화학습 · train_mlx.rl과 같은 손실: −Σ p · 장점 + β · KL(p ‖ 출발 모델). start는 지도학습 어댑터 폴더."""
    import torch
    from peft import PeftModel

    from .data import agreement
    torch.manual_seed(seed); rnd = random.Random(seed)
    sc = Scorer(model)
    sc.model = PeftModel.from_pretrained(sc.model, start, is_trainable=True)
    rows, valid = [r for r in load(data_dir, "train") if r.get("label") != "teacher"], load(data_dir, "valid")
    if max_rows and len(rows) > max_rows:                     # Mac(train_mlx.rl)과 같은 방식으로 일부만
        rows = rnd.sample(rows, max_rows)
    adv = advantages(rows)
    ids = [sc.ids(r["task"]) for r in rows]
    sc.model.eval()
    with torch.no_grad():                                     # 출발 모델의 확률 (KL 기준)
        ref = []
        for i in range(0, len(rows), 16):
            z = sc.letter_logits(ids[i:i + 16])
            for k, r in enumerate(rows[i:i + 16]):
                ref.append(torch.softmax(z[k, :len(r["scores"])], -1))
    sc.model.gradient_checkpointing_enable(); sc.model.enable_input_require_grads()
    opt = torch.optim.AdamW([p for p in sc.model.parameters() if p.requires_grad], lr=lr, weight_decay=0.0)
    if log: log(f"강화학습 · 문제 {len(rows)}개 · {steps}걸음 × {batch} · 출발 {start}")
    hist = []
    for step in range(1, steps + 1):
        sc.model.train()
        pick = [rnd.randrange(len(rows)) for _ in range(batch)]
        z = sc.letter_logits([ids[i] for i in pick])
        loss = 0.0
        for k, i in enumerate(pick):
            n = len(rows[i]["scores"])
            logp = torch.log_softmax(z[k, :n], -1); p = logp.exp()
            a = torch.tensor(adv[i], device=sc.device)
            loss = loss + (-(p * a).sum() + beta * (p * (logp - ref[i].log())).sum()) / batch
        loss.backward(); opt.step(); opt.zero_grad()
        if step % eval_every == 0 or step == steps:
            ev = agreement(valid, sc.pick)
            hist.append({"step": step, "loss": loss.item(), **ev})
            if log: log(f"걸음 {step:4d} · 손실 {loss.item():+.3f} · 검증 정답률 {ev['accuracy']:.1%} · 후회 {ev['regret']:.2f}")
    sc.model.save_pretrained(out); sc.tok.save_pretrained(out)
    with open(os.path.join(out, "rl_history.json"), "w") as f:
        json.dump({"start": start, "steps": steps, "batch": batch, "lr": lr, "beta": beta, "history": hist}, f, indent=1)
    sc.model.eval()
    return sc, hist


def merge(adapter, out, model=BASE_MODEL):
    """LoRA를 바탕 모델에 합쳐 하나의 모델로 저장합니다 (GGUF 변환 · Ollama · LM Studio용)."""
    from peft import PeftModel
    from transformers import AutoTokenizer
    net = PeftModel.from_pretrained(_base(model, "cpu"), adapter).merge_and_unload()
    net.save_pretrained(out); AutoTokenizer.from_pretrained(model).save_pretrained(out)
    return out
