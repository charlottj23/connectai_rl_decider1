# -*- coding: utf-8 -*-
"""도트 그래픽 도구 · 글자 지도(문자열)로 스프라이트를 만들고, 테두리 · 좌우 반전 · 색 바꾸기를 합니다.
게임의 모든 그림은 이미지 파일 없이 이 파일과 art.py의 코드로 그립니다."""
import os

import pygame

FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

# ── 팔레트 ───────────────────────────────────────────────────────────────
INK = (14, 20, 18)
PAL = {
    "k": INK, "K": (44, 50, 48), "w": (246, 247, 238), "W": (206, 210, 200), "g": (146, 152, 146), "G": (92, 98, 94),
    "a": (208, 249, 145), "A": (138, 190, 84), "r": (232, 76, 66), "R": (164, 42, 46), "o": (244, 152, 64), "O": (196, 104, 40),
    "y": (252, 214, 92), "Y": (214, 168, 56), "b": (98, 158, 228), "B": (52, 92, 156), "c": (118, 214, 224), "C": (60, 140, 160),
    "p": (246, 168, 194), "P": (212, 116, 152), "n": (156, 104, 64), "N": (104, 68, 44), "t": (220, 182, 126), "T": (176, 136, 88),
    "e": (96, 178, 92), "E": (52, 122, 66), "v": (156, 116, 216), "V": (100, 72, 160), "s": (248, 214, 182), "S": (222, 170, 132),
    "m": (60, 64, 82), "M": (36, 40, 56), "q": (250, 236, 210), "z": (70, 52, 40), "u": (40, 64, 104), "U": (26, 40, 70),
}

ACID, ACID_D = PAL["a"], PAL["A"]
WHITE, MUTED, RED, GOLD, BLUE = PAL["w"], (150, 156, 152), (255, 100, 90), (232, 252, 196), PAL["b"]
UI_BG, UI_BG2, UI_LINE, UI_LINE2 = (6, 9, 10), (13, 17, 16), (36, 42, 40), (66, 74, 70)      # 브랜드: 검정 · 흰색 · 형광 연두

_cache = {}


def sprite(rows, pal=None, key=None):
    """rows: 같은 길이의 문자열 목록. '.'은 투명. pal로 글자 색을 덮어씁니다."""
    ck = key or (tuple(rows), tuple(sorted((pal or {}).items())))
    hit = _cache.get(ck)
    if hit is not None:
        return hit
    p = dict(PAL, **(pal or {}))
    h, w = len(rows), max(len(r) for r in rows)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != "." and ch != " ":
                c = p[ch]
                s.set_at((x, y), c if len(c) == 4 else (*c, 255))
    _cache[ck] = s
    return s


def outline(surf, color=INK, key=None):
    """불투명한 픽셀 둘레에 1픽셀 테두리 (크기가 2씩 커집니다)."""
    ck = ("ol", key or id(surf), color)
    hit = _cache.get(ck)
    if hit is not None:
        return hit
    w, h = surf.get_size()
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    mask = pygame.mask.from_surface(surf)
    sil = mask.to_surface(setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(sil, (dx, dy))
    out.blit(surf, (1, 1))
    _cache[ck] = out
    return out


def flip(surf, key=None):
    ck = ("fl", key or id(surf))
    hit = _cache.get(ck)
    if hit is None:
        hit = _cache[ck] = pygame.transform.flip(surf, True, False)
    return hit


def tint(surf, color, alpha=255, key=None):
    """모양은 그대로, 색만 한 가지로 (깜빡임 · 그림자)."""
    ck = ("ti", key or id(surf), color, alpha)
    hit = _cache.get(ck)
    if hit is None:
        mask = pygame.mask.from_surface(surf)
        hit = _cache[ck] = mask.to_surface(setcolor=(*color, alpha), unsetcolor=(0, 0, 0, 0))
    return hit


def scale(surf, k, key=None):
    if k == 1:
        return surf
    ck = ("sc", key or id(surf), k)
    hit = _cache.get(ck)
    if hit is None:
        hit = _cache[ck] = pygame.transform.scale(surf, (surf.get_width() * k, surf.get_height() * k))
    return hit


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


# ── 글자 ─────────────────────────────────────────────────────────────────
# 그림은 도트(가상 화면을 정수배로 키움)이지만, 글자는 실제 화면 해상도에서 프리텐다드로 또렷하게 그립니다.
# Fonts.text()는 가상 화면 크기의 '자리표' Surface를 돌려주고, Canvas.blit이 그 자리를 기억했다가
# 화면을 키운 뒤 진짜 글자를 그 자리에 그립니다. 창 · 말풍선처럼 위를 덮는 것은 cover()로 순서를 지킵니다.
HI_FONTS = {"reg": "Pretendard-SemiBold.otf", "bold": "Pretendard-ExtraBold.otf", "mono": "Pretendard-SemiBold.otf"}
TEXT_PX = 12.0          # 가상 화면 기준 글자 크기


class TextSurf(pygame.Surface):
    """가상 화면 위의 글자 자리 (투명). hi = 실제 해상도 글자."""
    hi = None


class Canvas(pygame.Surface):
    def __init__(self, size, flags=0):
        super().__init__(size, flags)
        self.ops = []

    def blit(self, source, dest, area=None, special_flags=0):
        hi = getattr(source, "hi", None)
        if hi is not None:
            x, y = (dest.x, dest.y) if isinstance(dest, pygame.Rect) else (dest[0], dest[1])
            self.ops.append(("t", hi, int(x), int(y), self.get_clip(), source.get_alpha()))
            return pygame.Rect(int(x), int(y), source.get_width(), source.get_height())
        return super().blit(source, dest, area, special_flags)

    def cover(self, rect):
        """이 자리를 덮었습니다 · 앞서 그린 글자 위로 그림을 다시 올립니다."""
        r = pygame.Rect(rect).clip(self.get_clip()).clip(self.get_rect())
        if r.width > 0 and r.height > 0:
            self.ops.append(("c", r))

    def present(self, window, scale, offset):
        """가상 화면을 키워 창에 그리고, 글자를 실제 해상도로 그립니다."""
        ox, oy = offset
        window.blit(pygame.transform.scale(self, (self.get_width() * scale, self.get_height() * scale)), offset)
        for op in self.ops:
            if op[0] == "t":
                _, hi, x, y, clip, alpha = op
                window.set_clip(pygame.Rect(ox + clip.x * scale, oy + clip.y * scale, clip.width * scale, clip.height * scale))
                if alpha is not None and alpha < 255:
                    hi = hi.copy(); hi.set_alpha(alpha)
                window.blit(hi, (ox + x * scale, oy + y * scale))
            else:
                r = op[1]
                window.set_clip(None)
                window.blit(pygame.transform.scale(self.subsurface(r), (r.width * scale, r.height * scale)), (ox + r.x * scale, oy + r.y * scale))
        window.set_clip(None)
        self.ops.clear()


def cover(surf, rect):
    if hasattr(surf, "cover"):
        surf.cover(rect)


class Fonts:
    """scale ≥ 2이면 프리텐다드를 실제 해상도로, 아니면(작은 화면 · 그림 저장) 갈무리 도트 글꼴을 씁니다."""

    def __init__(self):
        self.reg = pygame.font.Font(os.path.join(FONT_DIR, "Galmuri11.ttf"), 11)
        self.bold = pygame.font.Font(os.path.join(FONT_DIR, "Galmuri11-Bold.ttf"), 11)
        self.mono = pygame.font.Font(os.path.join(FONT_DIR, "GalmuriMono11.ttf"), 11)
        self.scale = 1
        self._c, self._hf = {}, {}
        self.has_hi = all(os.path.exists(os.path.join(FONT_DIR, f)) for f in HI_FONTS.values())

    @property
    def hires(self):
        return self.scale >= 2 and self.has_hi

    def _font(self, bold, mono, k):
        px = int(round(TEXT_PX * k * self.scale))
        key = (bold, mono, px)
        f = self._hf.get(key)
        if f is None:
            f = self._hf[key] = pygame.font.Font(os.path.join(FONT_DIR, HI_FONTS["mono" if mono else "bold" if bold else "reg"]), px)
        return f

    def text(self, s, color=WHITE, bold=False, mono=False, k=1, shadow=None, outline_color=None):
        key = (s, color, bold, mono, k, shadow, outline_color, self.scale if self.hires else 0)
        hit = self._c.get(key)
        if hit is not None:
            return hit
        if len(self._c) > 4000:
            self._c.clear()
        if self.hires:
            out = self._c[key] = self._hitext(s, color, bold, mono, k, shadow, outline_color)
            return out
        f = self.mono if mono else self.bold if bold else self.reg
        base = f.render(s, False, color)
        if outline_color or shadow:
            w, h = base.get_size()
            out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
            if outline_color:
                o = f.render(s, False, outline_color)
                for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2), (0, 0), (2, 2), (0, 2), (2, 0)):
                    out.blit(o, (dx, dy))
            elif shadow:
                out.blit(f.render(s, False, shadow), (2, 2))
            out.blit(base, (1, 1))
            base = out
        if k != 1:
            base = pygame.transform.scale(base, (base.get_width() * k, base.get_height() * k))
        self._c[key] = base
        return base

    def _hitext(self, s, color, bold, mono, k, shadow, outline_color):
        S = self.scale
        f = self._font(bold, mono, k)
        base = f.render(s or " ", True, color)
        if outline_color or shadow:
            d = max(1, int(round(S * 0.5 * (1 if k == 1 else 1.5))))
            w, h = base.get_size()
            hi = pygame.Surface((w + 2 * d, h + 2 * d), pygame.SRCALPHA)
            if outline_color:
                o = f.render(s or " ", True, outline_color)
                for dx in (-d, 0, d):
                    for dy in (-d, 0, d):
                        if dx or dy: hi.blit(o, (d + dx, d + dy))
            else:
                hi.blit(f.render(s or " ", True, shadow), (2 * d, 2 * d))
            hi.blit(base, (d, d))
        else:
            hi = base
        w, h = -(-hi.get_width() // S), -(-hi.get_height() // S)
        ph = TextSurf((w, h), pygame.SRCALPHA)
        ph.hi = hi
        return ph

    def width(self, s, bold=False, k=1, mono=False):
        if self.hires:
            return -(-self._font(bold, mono, k).size(s)[0] // self.scale)
        return (self.mono if mono else self.bold if bold else self.reg).size(s)[0] * k

    def wrap(self, s, width, bold=False):
        """한국어는 글자 단위, 영어는 단어 단위로 줄을 나눕니다."""
        lines = []
        for para in s.split("\n"):
            cur = ""
            for ch in para:
                if self.width(cur + ch, bold) > width:
                    cut = cur.rfind(" ")
                    if cut > len(cur) * 0.6 and ord(ch) < 0x1100:
                        lines.append(cur[:cut]); cur = cur[cut + 1:] + ch
                    else:
                        lines.append(cur.rstrip()); cur = ch.lstrip()
                else:
                    cur += ch
            lines.append(cur)
        return lines


def won(man, sign=False):
    """만원 → '₩12,345,000'."""
    v = int(round(man * 10000))
    s = f"₩{abs(v):,}"
    if v < 0: return "-" + s
    return ("+" + s) if sign else s


def man(manwon, sign=False):
    """만원 → '1,234만' (짧게)."""
    v = int(round(manwon))
    if abs(v) >= 10000:
        s = f"{abs(v) / 10000:.1f}억".replace(".0억", "억")
    else:
        s = f"{abs(v):,}만"
    if v < 0: return "-" + s
    return ("+" + s) if sign else s
