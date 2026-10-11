# -*- coding: utf-8 -*-
"""고객 문의 직관 · CONNECT AI LAB 1주차 전전두엽 (format: connect-ai-brain/1)

brain.json 한 장(TF-IDF 어휘 + 로지스틱 회귀 계수 + 신호 + 규칙)을 numpy만으로 실행합니다. pickle을 쓰지 않습니다.
회사 엔진은 이 두뇌의 직관 점수와 신호를 고객센터 부서의 관측으로 씁니다.
"""
import json
import math
import re

import numpy as np

__all__ = ["ConnectBrain", "ACTION_KEYS"]
_WHITESPACE = re.compile(r"\s\s+")
ACTION_KEYS = {"즉시 처리": "urgent", "일반 처리": "normal", "결제 담당 배정": "billing", "사람 확인": "human"}


class ConnectBrain:
    def __init__(self, spec):
        if spec.get("format") != "connect-ai-brain/1":
            raise ValueError("connect-ai-brain/1 형식이 아닙니다")
        self.spec = spec
        self.name = spec["name"]
        self.actions = list(spec["actions"])
        self.hold_action = spec.get("hold_action", self.actions[-1])
        self.signals = spec["signals"]
        self.signal_weight = float(spec["signal_weight"])
        self.rule_signals = spec.get("rule_signals", {})
        self.rules = [tuple(r) for r in spec.get("rules", [])]
        self.threshold = float(spec.get("threshold") or 0)
        vec = spec["vectorizer"]
        self.vocabulary = vec["vocabulary"]
        self.idf = np.asarray(vec["idf"], dtype=float)
        self.ngram_range = tuple(vec["ngram_range"])
        clf = spec["classifier"]
        self.classes = list(clf["classes"])
        self.coef = np.asarray(clf["coef"], dtype=float)
        self.intercept = np.asarray(clf["intercept"], dtype=float)
        self._order = [self.classes.index(a) for a in self.actions]
        pol = spec.get("policy")
        self.policy = None
        if pol:
            if pol.get("type") != "linear-softmax":
                raise ValueError("지원하지 않는 정책 형식입니다")
            self.policy = {"W": np.asarray(pol["W"], dtype=float), "b": np.asarray(pol["b"], dtype=float), "obs": pol["obs"]}

    # ── 불러오기 ──────────────────────────────────────────────────────────
    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    @classmethod
    def from_hub(cls, repo_id, filename="brain.json", revision=None):
        from huggingface_hub import hf_hub_download
        return cls.from_file(hf_hub_download(repo_id, filename, revision=revision))

    # ── 특징 (scikit-learn TfidfVectorizer(char_wb, sublinear_tf) 와 같은 계산) ──
    def _char_wb_ngrams(self, text):
        text = _WHITESPACE.sub(" ", text.lower())
        lo, hi = self.ngram_range
        grams = []
        for word in text.split():
            w = " " + word + " "
            for n in range(lo, hi + 1):
                offset = 0
                grams.append(w[offset:offset + n])
                while offset + n < len(w):
                    offset += 1
                    grams.append(w[offset:offset + n])
                if offset == 0:
                    break
        return grams

    def detect(self, text):
        return {name: int(any(w in text for w in words)) for name, words in self.signals.items()}

    def _features(self, text):
        x = np.zeros(len(self.idf))
        counts = {}
        for g in self._char_wb_ngrams(text):
            j = self.vocabulary.get(g)
            if j is not None:
                counts[j] = counts.get(j, 0) + 1
        for j, tf in counts.items():
            x[j] = (1.0 + math.log(tf)) * self.idf[j]
        norm = np.linalg.norm(x)
        if norm > 0:
            x /= norm
        sig = np.array(list(self.detect(text).values()), dtype=float) * self.signal_weight
        return np.concatenate([x, sig])

    # ── 직관 ──────────────────────────────────────────────────────────────
    def scores(self, text):
        """행동 후보별 직관 점수 (actions 순서). 보정된 확률이 아닙니다."""
        z = self.coef @ self._features(text) + self.intercept
        p = np.exp(z - z.max())
        p /= p.sum()
        return p[self._order]

    def rule_hit(self, text):
        sig = dict(self.detect(text))
        sig.update({k: int(any(w in text for w in ws)) for k, ws in self.rule_signals.items()})
        for signal, action in self.rules:
            if sig.get(signal):
                return signal, action
        return None

    # ── 강화학습 정책 ─────────────────────────────────────────────────────
    def observe(self, text, state=None):
        """정책의 관측 13개: 직관 점수 4 · 신호 3 · 확신 · 남은 긴급팀/결제팀/사람(0–1) · 하루 진행(0–1) · 낯선 업종(0/1)."""
        state = state or {}
        s = self.scores(text)
        top = np.sort(s)
        left = state.get("left", {})
        cap = [left.get(a, 1.0) for a in ("즉시 처리", "결제 담당 배정", "사람 확인")]
        sig = list(self.detect(text).values())[:3]
        return np.concatenate([s, sig, [top[-1] - top[-2]], cap, [state.get("progress", 0.0), float(state.get("foreign", 0))]])

    def policy_probs(self, obs):
        z = self.policy["W"] @ obs + self.policy["b"]
        e = np.exp(z - z.max())
        return e / e.sum()

    # ── 판단 ──────────────────────────────────────────────────────────────
    def __call__(self, request):
        """brain(request) == brain.jev(request): JEV 형식의 요청을 받아 JEV 형식으로 답합니다."""
        return self.jev(request)

    def decide(self, text, state=None):
        hit = self.rule_hit(text)                                            # ① 규칙
        if hit:
            return {"action": hit[1], "reason": f"규칙 · {hit[0]} → {hit[1]}", "words_read": 0}
        tokens = text.split()
        if self.policy is not None:                                          # ② 강화학습 정책
            p = self.policy_probs(self.observe(text, state))
            a = int(np.argmax(p))
            return {"action": self.actions[a], "reason": f"강화학습 정책 · {p[a]:.2f}", "words_read": len(tokens)}
        return self.decide_theta(text, rule_checked=True)

    def decide_theta(self, text, rule_checked=False):
        """강화학습 전의 전전두엽: 규칙 → 확신이 θ를 넘을 때까지 읽기 → 억제."""
        if not rule_checked:
            hit = self.rule_hit(text)
            if hit:
                return {"action": hit[1], "reason": f"규칙 · {hit[0]} → {hit[1]}", "words_read": 0}
        tokens = text.split()
        if not self.threshold:                                               # 멈춤 기준이 없으면 직관 그대로
            s = self.scores(text)
            return {"action": self.actions[int(s.argmax())], "reason": "직관 · 점수 1등", "words_read": len(tokens)}
        for i in range(1, len(tokens) + 1):                                  # ② 확신이 θ를 넘을 때까지 읽기
            s = self.scores(" ".join(tokens[:i]))
            if s.max() >= self.threshold:
                return {"action": self.actions[int(s.argmax())],
                        "reason": f"확신 {s.max():.2f} ≥ 멈춤 기준 {self.threshold} · {i}/{len(tokens)} 어절에서 결정", "words_read": i}
        return {"action": self.hold_action, "reason": f"멈춤 · 확신이 끝까지 기준 {self.threshold} 미만 → 사람 확인", "words_read": len(tokens)}  # ③ 억제

    def jev(self, request=None, *, state=None, question="이 문의에 대한 다음 행동은?", criteria=None, desk_state=None):
        """JEV(typesafe/jev-1.13 · OpenRouter Decisions API)와 같은 입력과 출력.

        request = {"state": 문의(문자열) 또는 {"message": 문의, ...},
                   "questions": {"decision": {"type": "choice", "instructions": "...",
                                              "criteria": {"billing": "결제 담당 배정", "human": "사람 확인", ...}}}}
        반환     = {"model": ..., "answers": {"decision": {"type": "choice", "choice": key,
                                                         "probabilities": {key: p}, "confidence": p_max}}}
        criteria의 key: urgent(즉시 처리) · normal(일반 처리) · billing(결제 담당 배정) · human(사람 확인)
        probabilities와 confidence는 이 두뇌의 점수이며, 보정된 확률이 아닙니다.
        """
        if request is None:
            request = {"state": state, "questions": {"decision": {"type": "choice", "instructions": question,
                       "criteria": criteria or {ACTION_KEYS[a]: a for a in self.actions}}}}
        st = request["state"]
        text = st if isinstance(st, str) else str(st.get("message") or st.get("text") or st.get("body") or " ".join(map(str, st.values())))
        back = {v: k for k, v in ACTION_KEYS.items()}
        p = self.policy_probs(self.observe(text, desk_state)) if self.policy is not None else self.scores(text)
        hit = self.rule_hit(text)
        answers = {}
        for qname, q in request["questions"].items():
            if q.get("type", "choice") != "choice":
                raise ValueError("이 두뇌는 type='choice' 질문만 답합니다")
            keys = list(q["criteria"])
            if len(keys) < 2 or any(k not in back for k in keys):
                raise ValueError(f"criteria key는 {sorted(back)} 중에서 2개 이상 고르세요")
            idx = [self.actions.index(back[k]) for k in keys]
            sub = p[idx] / p[idx].sum()
            probs = {k: round(float(v), 4) for k, v in zip(keys, sub)}
            if self.policy is not None:
                choice, reason = keys[int(np.argmax(sub))], "강화학습 정책"
            else:                                                            # 직관 + 멈춤
                d = self.decide_theta(text, rule_checked=True)
                key = ACTION_KEYS[d["action"]]
                choice, reason = (key, d["reason"]) if key in keys else (keys[int(np.argmax(sub))], "직관 · 점수 1등")
            if hit and ACTION_KEYS[hit[1]] in keys:                        # 규칙은 확정 판단: 확률 1
                gut = keys[int(np.argmax(sub))]
                choice, reason = ACTION_KEYS[hit[1]], f"규칙 · {hit[0]} → {hit[1]} (직관은 {back[gut]} {probs[gut]:.2f})"
                probs = {k: (1.0 if k == choice else 0.0) for k in keys}
            answers[qname] = {"type": "choice", "choice": choice, "probabilities": probs,
                              "confidence": probs[choice], "reason": reason}
        return {"model": f"connect-ai/{self.name}", "answers": answers}

    def __repr__(self):
        kind = "강화학습 정책" if self.policy is not None else f"θ={self.threshold}"
        return f"ConnectBrain(name={self.name!r}, experience={self.spec.get('experience')!r}, {kind})"
