"""화면 없이 학습 화면을 켜서 v0 → 사람 라벨 → v1 학습까지 돌려 봅니다."""
import time

import pytest

pygame = pytest.importorskip("pygame")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("CONNECT_TYCOON_HOME", str(tmp_path))
    from connect_tycoon.game.app import App
    a = App(headless=True, reset=True, size=(1280, 800))
    yield a
    a.trainer.stop()
    pygame.quit()


def wait(app, cond, sec=90):
    t0 = time.time()
    while not cond() and time.time() - t0 < sec:
        app.step(1 / 30, []); time.sleep(0.005)
    assert cond()


def test_studio_trains_versions_with_human_labels(app):
    from connect_tycoon.game import screens
    screens.new_game(app)
    wait(app, lambda: app.studio.versions)
    v0 = app.studio.versions[0]["profit"]
    app.speed = 8
    for _ in range(3000):
        app.step(1 / 30, [])
        if app.studio.review: break
    assert app.studio.review, "확신이 낮은 판단에서 사람에게 묻지 않았습니다"
    app.studio.answer(0)
    assert len(app.studio.labels) == 1 and app.studio.feedback
    app.studio.train()
    wait(app, lambda: len(app.studio.versions) == 2, 180)
    assert app.studio.versions[1]["profit"] > v0
    assert app.studio.versions[1]["real"]["cases"] > 500             # 실제 데이터 시험
    assert app.career.studio["versions"][-1]["name"] == "v1"


def test_month_continues_without_newspaper(app):
    from connect_tycoon.game import screens
    screens.new_game(app)
    wait(app, lambda: app.studio.versions)
    app.studio.ask = False
    app.director.skip_month()
    app.step(1 / 30, [])
    assert app.career.month == 2 and app.modal is None


def test_review_survives_month_restart(app):
    """카드가 떠 있는 동안 학습이 끝나 새 달이 시작돼도 꺼지지 않아야 합니다."""
    from connect_tycoon.game import screens
    screens.new_game(app)
    wait(app, lambda: app.studio.versions)
    app.speed = 8
    for _ in range(3000):
        app.step(1 / 30, [])
        if app.studio.review: break
    R = app.studio.review
    assert R
    app.start_month(restart=True)               # 학습이 끝나 버전이 바뀐 상황과 같습니다
    assert app.studio.review is None
    app.studio.review = R                       # 오래된 카드에 답해도
    app.studio.answer(0)                        # 예외 없이 라벨이 쌓여야 합니다
    assert len(app.studio.labels) == 1
