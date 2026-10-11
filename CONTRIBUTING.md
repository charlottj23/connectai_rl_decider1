# 기여하기

누구든 환영합니다. 새 부서, 새 업그레이드, 더 나은 학습법, 더 귀여운 도트 — 무엇이든 좋습니다.

## 개발 환경

```bash
git clone https://github.com/wonseokjung/connect-tycoon
cd connect-tycoon
python -m venv .venv && source .venv/bin/activate      # 또는 uv venv
pip install -e ".[dev]"
pytest
connect-tycoon play
```

## 꼭 지킬 것

1. **엔진 숫자** · `company.py`를 고친 뒤 `pytest tests/test_engine.py`가 통과해야 합니다. 기본 설정(DEFAULT_CONFIG)의 회사는 강의 Colab과 숫자까지 같아야 합니다. 새 기능은 기본값이 '꺼짐'인 설정으로 넣어 주세요.
2. **숨은 진실은 숨긴다** · 악용 · 사기 · 문의의 진짜 유형은 정책에게 넘기는 `ev`에 넣지 않습니다 (`test_hidden_truth_not_visible_to_policy`).
3. **JEV 왕복** · 새 관측을 넣으면 `jev.request`와 `CompanyBrain.observe`도 같이 고쳐서, JEV로 물어도 숫자로 물어도 같은 판단이 나오게 해 주세요 (`tests/test_jev.py`).
4. **'보통'은 규칙 사장** · 게임의 사장 지시에서 모든 항목의 '보통'은 규칙 사장과 똑같아야 합니다.
5. **파일 없는 그림 · 소리** · 그림은 `game/art.py`의 글자 지도로, 소리는 `game/audio.py`의 합성으로 만듭니다. 외부 이미지 · 음원은 라이선스를 확인할 수 없으면 받지 않습니다.

## 부서를 하나 더 만들려면

1. `company.py` · `DEPTS`, `OBS_NAMES`, 제너레이터 안의 판단(`yield from self._decide(...)`)과 결과 계산
2. `policies.py` · `RulePolicy.act`에 규칙 하나
3. `jev.py` · `INSTRUCTIONS`, `criteria()`, `_STATE_FIELDS` / `brain.py` · `observe()`
4. `game/world.py` · `FLOORS`에 층 하나와 `_room_키` 그리기 / `game/director.py` · `_ev_키` 연출
5. 테스트

## 그림 그리기

```python
BOX = sprite(["ttttt",
              "tNtNt",
              "TTTTT",
              "TTTTT"])        # 글자 하나 = 픽셀 하나 · 색은 pixel.PAL
```

`outline()`으로 테두리를 두르면 배경 위에서도 잘 보입니다. 사람은 `art.Look`으로 머리 모양 · 옷 색을 바꿉니다.

## README 그림 다시 만들기

```bash
python scripts/make_media.py      # docs/images/*.png · hero.gif (ffmpeg 필요)
```
