"""Gymnasium 환경 · 행동 마스크를 지키며 무작위로 한 달을 운영합니다."""
import gymnasium as gym

import connect_tycoon  # noqa: F401  (ConnectTycoon-v0 등록)

env = gym.make("ConnectTycoon-v0")
obs, info = env.reset(seed=42)
total, done = 0.0, False
while not done:
    action = env.action_space.sample(mask=obs["action_mask"].astype("int8"))
    obs, reward, done, truncated, info = env.step(action)
    total += reward
print(f"에피소드 보상 {total:.1f} · 한 달 이익 {info['month_profit']:.0f}만원")
