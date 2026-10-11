"""유튜브 커뮤니티 이미지 (정사각형 1440×1440) · 글은 게시물에 따로 쓰고 이미지는 화면 중심으로."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import make_posters as P
import pygame

W = H = 1440
X = 90
OUT = os.path.join(P.OUT, "notice")


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".png"): os.remove(os.path.join(OUT, f))
    studio, review = P.load("studio"), P.load("review-refund")

    # 1 · 화면 그대로 크게
    s = P.base()
    P.logo(s, X, 80)
    s.blit(P.text("강화학습 시뮬레이터", 96, P.WHITE), (X, 220))
    r = P.pill(s, "개발 중", X + 2, 350, px=34)
    w = W - 2 * X; h = int(w * studio.get_height() / studio.get_width())
    P.framed(s, studio, (X, H - 90 - h, w, h))
    pygame.image.save(s, os.path.join(OUT, "01_simulator.png"))

    # 2 · 사람 확인 카드를 크게
    s = P.base()
    P.logo(s, X, 80)
    s.blit(P.text("AI가 헷갈리면", 96, P.WHITE), (X, 220))
    s.blit(P.text("사람에게 묻는다", 96, P.ACID), (X, 330))
    card = review.subsurface(pygame.Rect(290, 130, 790, 470)).copy()
    w = W - 2 * X; h = int(w * 470 / 790)
    P.framed(s, card, (X, H - 90 - h, w, h))
    pygame.image.save(s, os.path.join(OUT, "02_human.png"))
    print("✓", OUT, r)


if __name__ == "__main__":
    main()
