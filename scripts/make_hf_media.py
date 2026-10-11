"""Hugging Face 모델 카드용 브랜드 그림 · docs/brand/banner.gif (움직이는 배너) · docs/brand/results.png (성적 그래프)

    python scripts/make_hf_media.py                 # ffmpeg 필요 · 성적은 runs/eval2.json에서 (없으면 그래프는 건너뜀)
"""
import json
import math
import os
import random
import shutil
import subprocess
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "docs", "brand")
FONT = os.path.join(ROOT, "connect_tycoon", "game", "assets", "fonts")
INK, PAPER, ACID, MUTE, LINE, RED = (5, 8, 7), (244, 246, 238), (208, 249, 145), (140, 149, 144), (31, 39, 36), (255, 106, 92)
pygame.init(); pygame.display.set_mode((1, 1))
_f = {}


def font(px, bold=True):
    k = (px, bold)
    if k not in _f:
        _f[k] = pygame.font.Font(os.path.join(FONT, "Pretendard-ExtraBold.otf" if bold else "Pretendard-SemiBold.otf"), px)
    return _f[k]


def text(s, px, color=PAPER, bold=True):
    return font(px, bold).render(s, True, color)


def banner_frames(n=36, W=1280, H=400):
    rnd = random.Random(11)
    pts = [(rnd.uniform(700, W - 20), rnd.uniform(20, H - 20), rnd.uniform(0, 6.28), rnd.uniform(3, 6)) for _ in range(42)]
    edges = [(i, j, rnd.random()) for i in range(len(pts)) for j in range(i + 1, len(pts))
             if math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) < 150]
    for f in range(n):
        t = f / n                                              # 0 → 1 한 바퀴 (끊김 없이 반복)
        s = pygame.Surface((W, H)); s.fill(INK)
        for x in range(0, W, 40): pygame.draw.line(s, (12, 17, 15), (x, 0), (x, H))
        for y in range(0, H, 40): pygame.draw.line(s, (12, 17, 15), (0, y), (W, y))
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        for i, j, o in edges:
            (x1, y1, _, _), (x2, y2, _, _) = pts[i], pts[j]
            pygame.draw.line(layer, (*ACID, 40), (x1, y1), (x2, y2), 1)
            k = (t + o) % 1.0
            pygame.draw.circle(layer, (*ACID, 220), (int(x1 + (x2 - x1) * k), int(y1 + (y2 - y1) * k)), 2)
        for x, y, ph, r in pts:
            g = 0.5 + 0.5 * math.sin(2 * math.pi * t + ph)
            pygame.draw.circle(layer, (*ACID, int(60 + 150 * g)), (int(x), int(y)), int(r * (0.8 + 0.3 * g)))
        fade = pygame.Surface((W, H), pygame.SRCALPHA)        # 글자 쪽은 네트워크를 옅게
        for x in range(0, 760):
            fade.fill((*INK, int(255 * max(0.0, 1 - x / 760) ** 0.6)), (x, 0, 1, H))
        s.blit(layer, (0, 0)); s.blit(fade, (0, 0))
        s.blit(text("CONNECT AI LAB × AI CITY BUILDERS", 22, MUTE), (64, 70))
        s.blit(text("RL AI COMPANY", 76), (60, 112))
        s.blit(text("DECISION MAKING MODEL", 76, ACID), (60, 196))
        s.blit(text("시뮬레이터에서 강화학습으로 만든 회사 의사결정 모델", 26, (200, 208, 202), bold=False), (64, 300))
        on = int(t * 4) % 2 == 0
        pygame.draw.circle(s, ACID if on else (70, 90, 55), (72, 358), 6)
        s.blit(text("LIVE  ·  상황 → 행동 → 보상", 20, ACID), (88, 346))
        yield s


def gif(frames, path, fps=12):
    tmp = tempfile.mkdtemp()
    try:
        for i, s in enumerate(frames):
            pygame.image.save(s, os.path.join(tmp, f"{i:04d}.png"))
        pal = os.path.join(tmp, "pal.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "%04d.png"),
                        "-vf", "palettegen=max_colors=64", pal], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "%04d.png"), "-i", pal,
                        "-lavfi", "paletteuse=dither=none", "-loop", "0", path], check=True)
    finally:
        shutil.rmtree(tmp)
    return path


def results_png(res, path, teacher=None, W=1280, H=560):
    """성적 그래프 · 한 달 이익 · 실제 카드 거래 손실 줄임 (학습 전 → 지도학습 → 강화학습)."""
    s = pygame.Surface((W, H)); s.fill(INK)
    s.blit(text("학습 단계별 성적", 34), (56, 36))
    s.blit(text("처음 보는 달 · 학습에 쓰지 않은 실제 카드 거래 713건", 20, MUTE, bold=False), (58, 84))
    names = list(res)
    panels = [("시뮬레이터 · 한 달 이익 (만원)", [res[n]["profit"] for n in names], teacher and teacher.get("profit"), "{:+,.0f}"),
              ("실제 카드 거래 · 손실 줄임", [res[n]["card"]["saved"] * 100 for n in names], teacher and teacher.get("saved"), "{:.0f}%")]
    for pi, (title, vals, ref, fmt) in enumerate(panels):
        x0, y0, w, h = 56 + pi * 600, 140, 560, 360
        s.blit(text(title, 22, PAPER), (x0, y0))
        lo, hi = min(0, min(vals)), max(max(vals), ref or 0) * 1.15
        base = y0 + 50 + int((hi / (hi - lo)) * (h - 90))
        pygame.draw.line(s, LINE, (x0, base), (x0 + w, base), 2)
        bw = 120
        for i, (n, v) in enumerate(zip(names, vals)):
            bx = x0 + 30 + i * 175
            top = base - int(v / (hi - lo) * (h - 90))
            col = ACID if i == len(vals) - 1 else (RED if v < 0 else (98, 120, 80))
            pygame.draw.rect(s, col, (bx, min(top, base), bw, abs(base - top) or 2), border_radius=8)
            lab = text(fmt.format(v), 24, col)
            s.blit(lab, (bx + bw // 2 - lab.get_width() // 2, (top - 34) if v >= 0 else (top + 8)))
            nm = text(n, 18, PAPER if i == len(vals) - 1 else MUTE, bold=i == len(vals) - 1)
            s.blit(nm, (bx + bw // 2 - nm.get_width() // 2, y0 + h + 4))
        if ref:
            ry = base - int(ref / (hi - lo) * (h - 90))
            for xx in range(x0, x0 + w, 14): pygame.draw.line(s, MUTE, (xx, ry), (xx + 7, ry), 2)
            s.blit(text(f"선생님 정책 {fmt.format(ref)}", 16, MUTE, bold=False), (x0 + w - 170, ry - 22))
    pygame.image.save(s, path)
    return path


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(gif(banner_frames(), os.path.join(OUT, "banner.gif")))
    ev = os.path.join(ROOT, "runs", "eval2.json")
    if os.path.exists(ev):
        r = json.load(open(ev, encoding="utf-8"))
        res = {"학습 전": r["Qwen 학습 전"], "지도학습": r["sft"], "강화학습": r["rl"]}
        print(results_png(res, os.path.join(OUT, "results.png"), teacher={"profit": 1362, "saved": 84}))
    for f in os.listdir(OUT):
        print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")
