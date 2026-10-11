# -*- coding: utf-8 -*-
"""README의 그림과 움짤을 학습 화면에서 바로 만듭니다 (화면 없이).

    python scripts/make_media.py            # docs/images/*.png, hero.gif (ffmpeg 필요)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["CONNECT_TYCOON_HOME"] = tempfile.mkdtemp(prefix="ct-media-")
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "images")


def main():
    import pygame
    from connect_tycoon.game import screens
    from connect_tycoon.game.app import App

    for f in os.listdir(OUT) if os.path.isdir(OUT) else []:
        if f.endswith((".png", ".gif")): os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)
    app = App(headless=True, reset=True, size=(2000, 1250))

    def frames(n, dt=1 / 60):
        for _ in range(n): app.step(dt, [])

    def shot(name):
        pygame.image.save(app.window, os.path.join(OUT, name + ".png")); print("✓", name)

    def wait(cond, sec=120):
        t0 = time.time()
        while not cond() and time.time() - t0 < sec:
            app.step(1 / 60, []); time.sleep(0.005)

    frames(120); shot("title")
    screens.new_game(app)
    wait(lambda: app.studio.versions)
    app.speed = 2
    got = set()
    for _ in range(30000):
        app.step(1 / 60, [])
        R = app.studio.review
        if R:
            d = R["x"]["dept"]
            if d in ("refund", "security") and d not in got:
                got.add(d); shot("review-" + d)
            if d == "refund":
                fs = R["x"]["ev"]["fraud_score"]; app.studio.answer(3 if fs > 0.5 else 0)
            elif d == "security":
                fs = R["x"]["ev"]["fraud_score"]; app.studio.answer(1 if fs > 0.7 else 2 if fs > 0.4 else 0)
            else:
                app.studio.answer(1)
            if "feedback" not in got:
                frames(20); got.add("feedback"); shot("feedback")
            app.studio.asked_day = -1
        if {"refund", "security"} <= got and len(app.studio.labels) >= 6: break
    app.studio.ask = False
    app.studio.train()
    t0 = time.time()
    while app.studio.job == "train" and time.time() - t0 < 180:
        app.step(1 / 60, []); time.sleep(0.005)
        if len(app.studio.curve) == 45 and "training" not in got: got.add("training"); shot("training")
    frames(900); shot("studio")

    if shutil.which("ffmpeg"):                    # 움짤: v1이 회사를 운영하는 모습 (640×400 원본 크기)
        gif = App(headless=True, reset=True, size=(640, 400))
        gif.roster = app.roster; gif.studio.versions = list(app.studio.versions); gif.studio.labels = list(app.studio.labels)
        gif.studio.ask = False
        gif.career.mode, gif.career.ai = "ai", app.studio.versions[-1]["rid"]
        gif.screen = "play"; gif.start_month(restart=True)
        gif.director.skip_day()
        gif.speed = 2.0
        tmp = tempfile.mkdtemp()
        for i in range(int(25.5 / 2.0 * 12)):
            gif.step(1 / 12, [])
            pygame.image.save(gif.window, os.path.join(tmp, f"f{i:04d}.png"))
        pal = os.path.join(tmp, "pal.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(tmp, "f%04d.png"), "-vf", "palettegen=max_colors=160", pal], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(tmp, "f%04d.png"), "-i", pal,
                        "-lavfi", "paletteuse=dither=none", os.path.join(OUT, "hero.gif")], check=True)
        print("✓ hero.gif", os.path.getsize(os.path.join(OUT, "hero.gif")) // 1024, "KB")
    app.trainer.stop()


if __name__ == "__main__":
    sys.exit(main())
