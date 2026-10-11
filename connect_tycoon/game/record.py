# -*- coding: utf-8 -*-
"""하루를 그림으로 남깁니다 (화면 없이). Colab에서 '내 두뇌가 운영하는 회사' 영상을 만들 때 씁니다.

    connect-tycoon record --brain hf:아이디/connect-company-이름 --out frames --mp4
"""
import json
import os
import shutil
import subprocess
import tempfile


def record(brain="default", out="frames", day=0, seed=7000, size="1280x720", fps=30, mp4=False, upgrades=None, speed=2.0, log=print):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ["CONNECT_TYCOON_HOME"] = tempfile.mkdtemp(prefix="connect-tycoon-rec-")   # 내 저장 파일은 건드리지 않습니다
    import pygame
    from .app import App
    from .director import DAY_LEN
    w, h = (int(v) for v in str(size).lower().split("x"))
    extra = [] if brain in (None, "", "default") else [brain]
    app = App(brains=extra, size=(w, h), headless=True, reset=True)
    rid = app.roster[-1]["id"] if extra else "jay-company"
    c = app.career
    c.month = seed - 6999
    c.mode, c.ai = "ai", rid
    if upgrades:
        c.upgrades = json.loads(upgrades) if isinstance(upgrades, str) else dict(upgrades)
    app.start_month(restart=True)
    app.toasts.items.clear()
    for _ in range(day):
        app.director.skip_day()
    os.makedirs(out, exist_ok=True)
    n = int(DAY_LEN / speed * fps)
    app.speed = speed
    for i in range(n):
        app.step(1.0 / fps, [])
        pygame.image.save(app.window, os.path.join(out, f"frame_{i:05d}.png"))
    log(f"{n}장 → {out}  ({app.entry(rid)['name']} · {seed}번 달 {day + 1}일째)")
    if mp4:
        if not shutil.which("ffmpeg"):
            log("ffmpeg가 없어 mp4는 건너뜁니다"); return out
        video = out.rstrip("/") + ".mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(out, "frame_%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", video], check=True)
        log("영상 →", video)
        return video
    return out
