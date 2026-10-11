"""시뮬레이터에서 배운 판단을 언어 모델(Qwen3.5-0.8B 등)에 옮기고, 언어 모델을 다시 강화학습시킵니다.

    ① 문제집     data.build      시뮬레이터 판단 → 글로 된 문제 + 선택지별 점수 (선택지마다 한 달을 끝까지 다시 돌려 봄)
    ② 지도학습   train_*.sft     점수가 가장 높은 선택지를 따라 배움 (LoRA)
    ③ 강화학습   train_*.rl      선택지 전체를 한 묶음으로, 시뮬레이터 점수가 높은 답의 확률을 올림 (GRPO 방식)
    ④ 채점       LLMPolicy       언어 모델을 회사 사장 자리에 앉혀 한 달 운영 · 실제 데이터 시험
    ⑤ 공개       hub.push_llm    Hugging Face에 어댑터 · 모델 카드

Mac은 MLX(train_mlx), Colab · GPU는 PyTorch(train_torch). 문제 형식은 C1과 같습니다:
상황 · 질문 · 보기(A, B, C…)를 받고 글자 하나로 답하며, 보기 글자의 확률이 곧 선택지별 확률입니다.
"""
from .format import BASE_MODEL, SYSTEM, LETTERS, task, messages  # noqa: F401
