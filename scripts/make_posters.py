# -*- coding: utf-8 -*-
"""유튜브 커뮤니티 · SNS용 정사각형 이미지 (1440×1440). docs/images의 화면을 브랜드 배경 위에 얹습니다.

    python scripts/make_media.py && python scripts/make_posters.py
"""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

ROOT = os.path.join(os.path.dirname(__file__), "..")
IMG = os.path.join(ROOT, "docs", "images")
OUT = os.path.join(ROOT, "docs", "youtube")
FONT = os.path.join(ROOT, "connect_tycoon", "game", "assets", "fonts")
W, H = 1440, 1440
BLACK, WHITE, ACID, GRAY, LINE = (6, 9, 10), (246, 247, 238), (208, 249, 145), (140, 148, 144), (36, 42, 40)

pygame.init(); pygame.display.set_mode((1, 1))
_f = {}


def font(px, bold=True):
    k = (px, bold)
    if k not in _f:
        _f[k] = pygame.font.Font(os.path.join(FONT, "Pretendard-ExtraBold.otf" if bold else "Pretendard-SemiBold.otf"), px)
    return _f[k]


def text(s, px, color=WHITE, bold=True):
    return font(px, bold).render(s, True, color)


def base():
    s = pygame.Surface((W, H)); s.fill(BLACK)
    for x in range(0, W, 48):
        pygame.draw.line(s, (14, 18, 17), (x, 0), (x, H))
    for y in range(0, H, 48):
        pygame.draw.line(s, (14, 18, 17), (0, y), (W, y))
    return s


def logo(s, x, y, px=34):
    a = text("CONNECT", px, WHITE); b = text("TYCOON", px, ACID)
    s.blit(a, (x, y)); s.blit(b, (x + a.get_width() + px // 3, y))
    t = text("CONNECT AI LAB", px // 2, GRAY)
    s.blit(t, (x, y + a.get_height() + 2))


def framed(s, img, rect, glow=True):
    r = pygame.Rect(rect)
    im = pygame.transform.smoothscale(img, r.size)
    if glow:
        for i, a in enumerate((18, 30, 50)):
            g = pygame.Surface((r.width + 24 - i * 8, r.height + 24 - i * 8), pygame.SRCALPHA)
            pygame.draw.rect(g, (*ACID, a), g.get_rect(), border_radius=22)
            s.blit(g, (r.x - 12 + i * 4, r.y - 12 + i * 4))
    mask = pygame.Surface(r.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=16)
    im = im.convert_alpha(); im.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(im, r.topleft)
    pygame.draw.rect(s, ACID, r, 2, border_radius=16)


def pill(s, label, x, y, px=30, fill=ACID, color=BLACK):
    t = text(label, px, color)
    r = pygame.Rect(x, y, t.get_width() + px * 1.2, t.get_height() + px * 0.5)
    pygame.draw.rect(s, fill, r, border_radius=r.height // 2)
    s.blit(t, (r.x + px * 0.6, r.y + px * 0.22))
    return r


def load(name):
    return pygame.image.load(os.path.join(IMG, name + ".png"))


def save(s, name):
    p = os.path.join(OUT, name + ".png"); pygame.image.save(s, p); print("✓", p)


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".png"): os.remove(os.path.join(OUT, f))
    studio, review, training, fb = load("studio"), load("review-refund"), load("training"), load("feedback")
    X = 90

    # 1 · 대표
    s = base()
    logo(s, X, 80)
    s.blit(text("시뮬레이터로", 96, WHITE), (X, 210))
    s.blit(text("AI 의사결정 모델을", 96, WHITE), (X, 320))
    s.blit(text("학습시킨다", 96, ACID), (X, 430))
    pill(s, "직접 만드는 중", X + 2, 570)
    framed(s, studio, ((W - 1176) // 2, 668, 1176, 735))
    save(s, "01_main")

    # 2 · 사람 확인
    s = base()
    logo(s, X, 80)
    s.blit(text("AI가 헷갈리면", 96, WHITE), (X, 210))
    s.blit(text("사람에게 묻는다", 96, ACID), (X, 320))
    s.blit(text("확신이 낮은 판단만 · 사람의 답은 지도학습 라벨로", 34, GRAY, bold=False), (X + 2, 450))
    card = review.subsurface(pygame.Rect(290, 130, 790, 470)).copy()
    framed(s, card, (X, 540, W - 2 * X, int((W - 2 * X) * 470 / 790)))
    y2 = 540 + int((W - 2 * X) * 470 / 790) + 60
    r = pill(s, "Human-in-the-loop", X + 2, y2)
    s.blit(text("사람의 답이 곧 상태 → 행동 라벨", 36, WHITE), (X + r.width + 24, y2 + 6))
    save(s, "02_human")

    # 3 · 학습 결과
    s = base()
    logo(s, X, 80)
    s.blit(text("학습 한 번에", 80, WHITE), (X, 210))
    a_ = text("357만", 120, GRAY); s.blit(a_, (X, 310))
    arr = text("→", 100, ACID); s.blit(arr, (X + a_.get_width() + 30, 320))
    s.blit(text("1,500만", 120, ACID), (X + a_.get_width() + 60 + arr.get_width(), 310))
    s.blit(text("한 달 이익 · v0 규칙 따라 하기 → v1 강화학습 + 사람 라벨 6개", 32, GRAY, bold=False), (X + 2, 470))
    framed(s, training, (X, 560, W - 2 * X, int((W - 2 * X) * 1250 / 2000)))
    save(s, "03_result")

    # 4 · 강화학습 고리
    s = base()
    logo(s, X, 80)
    s.blit(text("상태 → 행동", 96, WHITE), (X, 210))
    s.blit(text("→ 보상 → 다음 상태", 96, ACID), (X, 320))
    steps = [("S", "상태", "질문 + 지금 상황"), ("A", "행동", "모델의 선택"), ("R", "보상", "돈 · 만족 · 사고"), ("S'", "다음 상태", "바뀐 회사")]
    bw_ = (W - 2 * X - 3 * 30) // 4
    for i, (k, name, desc) in enumerate(steps):
        x = X + i * (bw_ + 30)
        r = pygame.Rect(x, 480, bw_, 250)
        pygame.draw.rect(s, (13, 17, 16), r, border_radius=20)
        pygame.draw.rect(s, ACID if i in (1, 2) else LINE, r, 2, border_radius=20)
        s.blit(text(k, 88, ACID), (x + 26, 494))
        s.blit(text(name, 40, WHITE), (x + 28, 612))
        s.blit(text(desc, 25, GRAY, bold=False), (x + 29, 670))
    framed(s, fb, (X, 800, 600, 300), glow=False)
    framed(s, studio, (X + 640, 780, W - 2 * X - 640, int((W - 2 * X - 640) * 1250 / 2000)), glow=False)
    s.blit(text("JEV · 강화학습 · Human-in-the-loop · 오픈소스", 32, GRAY, bold=False), (X, 1300))
    save(s, "04_loop")


if __name__ == "__main__":
    main()
