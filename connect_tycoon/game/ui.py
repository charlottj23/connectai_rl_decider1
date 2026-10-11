# -*- coding: utf-8 -*-
"""도트 UI · 즉시 모드(immediate mode). 매 프레임 그리면서 눌렸는지 바로 돌려받습니다.

    if ui.button(surf, rect, "다음 달", icon="play", kind="acid"): ...
    value = ui.seg(surf, rect, ["중단", "유지", "증액"], value)
"""
import pygame

from . import art
from .pixel import ACID, ACID_D, INK, UI_BG, UI_LINE, UI_LINE2, WHITE, cover

KIND = {  # 배경, 테두리, 글자 · 브랜드: 검정 바탕 · 얇은 선 · 형광 연두 하나
    "normal": ((13, 17, 16), (58, 66, 62), WHITE),
    "acid": (ACID, ACID, (6, 9, 10)),
    "ghost": ((6, 9, 10), (40, 46, 44), (214, 220, 212)),
    "danger": ((40, 12, 12), (255, 100, 90), WHITE),
    "gold": ((6, 9, 10), ACID, ACID),
}


class UI:
    def __init__(self, fonts):
        self.f = fonts
        self.mouse = (-1, -1)
        self.pressed_at = None
        self.released = False
        self.down = False
        self.wheel = 0
        self.enabled = True
        self.tip = None
        self.focus = None          # 글자 입력 칸
        self.typed, self.backspace, self.enter = "", 0, False
        self.hover_any = False
        self.keys = []

    def begin(self, events, scale, offset=(0, 0), ratio=1.0):
        self.released, self.wheel, self.tip = False, 0, None
        self.typed, self.backspace, self.enter, self.keys = "", 0, False, []
        self.hover_any = False

        def at(pos):   # 창 좌표(포인트) → 실제 픽셀 → 가상 화면
            return (int((pos[0] * ratio - offset[0]) // scale), int((pos[1] * ratio - offset[1]) // scale))
        for e in events:
            if e.type == pygame.MOUSEMOTION:
                self.mouse = at(e.pos)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.mouse = at(e.pos)
                self.pressed_at, self.down = self.mouse, True
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.mouse = at(e.pos)
                self.released, self.down = True, False
            elif e.type == pygame.MOUSEWHEEL:
                self.wheel += e.y
            elif e.type == pygame.TEXTINPUT:
                self.typed += e.text
            elif e.type == pygame.KEYDOWN:
                self.keys.append(e.key)
                if e.key == pygame.K_BACKSPACE: self.backspace += 1
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER): self.enter = True

    def end(self):
        if self.released:
            self.pressed_at = None

    def hover(self, rect):
        return self.enabled and pygame.Rect(rect).collidepoint(self.mouse)

    def clicked(self, rect):
        r = pygame.Rect(rect)
        return self.enabled and self.released and r.collidepoint(self.mouse) and self.pressed_at is not None and r.collidepoint(self.pressed_at)

    # ── 그림 도우미 ───────────────────────────────────────────────────────
    def frame(self, surf, rect, title=None, icon=None, accent=ACID, bg=UI_BG, alpha=None):
        r = pygame.Rect(rect)
        cover(surf, r)
        if alpha is not None:
            s = pygame.Surface(r.size, pygame.SRCALPHA); s.fill((*bg, alpha)); surf.blit(s, r.topleft)
        else:
            pygame.draw.rect(surf, bg, r)
        pygame.draw.rect(surf, UI_LINE, r, 1, border_radius=4)
        if title:
            tx = r.left + 6
            pygame.draw.rect(surf, ACID, (r.left + 1, r.top + 4, 2, 9))           # 형광 연두 머리표
            surf.blit(self.f.text(title, WHITE, bold=True), (tx, r.top + 2))
            pygame.draw.line(surf, UI_LINE, (r.left + 4, r.top + 16), (r.right - 5, r.top + 16))
        return r

    def label(self, surf, text, x, y, color=WHITE, bold=False, right=False, center=False, k=1, mono=False, outline=False):
        img = self.f.text(text, color, bold=bold, k=k, mono=mono, outline_color=INK if outline else None)
        if right: x -= img.get_width()
        if center: x -= img.get_width() // 2
        surf.blit(img, (x, y))
        return img.get_width()

    def para(self, surf, text, x, y, width, color=(214, 222, 210), gap=12, bold=False, max_lines=None):
        lines = self.f.wrap(text, width, bold)
        if max_lines: lines = lines[:max_lines]
        for i, s in enumerate(lines):
            surf.blit(self.f.text(s, color, bold=bold), (x, y + i * gap))
        return y + len(lines) * gap

    def bar(self, surf, rect, frac, color=ACID, bg=(30, 44, 37)):
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, bg, r)
        w = int(r.width * max(0.0, min(1.0, frac)))
        if w: pygame.draw.rect(surf, color, (r.x, r.y, w, r.height))

    # ── 위젯 ──────────────────────────────────────────────────────────────
    def button(self, surf, rect, label="", icon=None, kind="normal", enabled=True, tip=None, active=False):
        r = pygame.Rect(rect)
        bg, edge, fg = KIND[kind]
        hot = enabled and self.hover(r)
        if hot:
            self.hover_any = True
            if tip: self.tip = tip
        if not enabled:
            bg, edge, fg = (22, 30, 26), (40, 52, 46), (90, 100, 94)
        elif active:
            bg, edge, fg = (54, 80, 44), ACID, ACID
        elif hot and kind in ("normal", "ghost"):
            bg, edge = (34, 52, 42), ACID_D
        press = hot and self.down and self.pressed_at and r.collidepoint(self.pressed_at)
        rr = r.move(0, 1) if press else r
        rad = min(7, rr.height // 2)                                   # 알약 모양 버튼
        pygame.draw.rect(surf, bg, rr, border_radius=rad)
        pygame.draw.rect(surf, edge, rr, 1, border_radius=rad)
        room = rr.width - 6
        if label and icon and self.f.width(label, bold=True) + 12 > room:
            icon = None
        while label and self.f.width(label, bold=True) > room and len(label) > 2:
            label = label[:-2] + "…"
        if label and (tip is None) and hot and self.f.width(label, bold=True) > room:
            self.tip = label
        img = self.f.text(label, fg, bold=True) if label else None
        iw = 9 + (3 if label else 0) if icon else 0
        w = (img.get_width() if img else 0) + iw
        x = rr.centerx - w // 2
        if icon:
            surf.blit(art.icon(icon), (x, rr.centery - 4)); x += iw
        if img:
            surf.blit(img, (x, rr.centery - 6))
        return enabled and self.clicked(r)

    def seg(self, surf, rect, options, value, labels=None, tips=None):
        r = pygame.Rect(rect)
        n = len(options)
        out = value
        for i, opt in enumerate(options):
            x0 = r.x + r.width * i // n
            x1 = r.x + r.width * (i + 1) // n
            cell = pygame.Rect(x0, r.y, x1 - x0 + (1 if i < n - 1 else 0), r.height)
            on = opt == value
            hot = self.hover(cell)
            if hot and tips: self.tip = tips[i]
            pygame.draw.rect(surf, ACID if on else (24, 30, 28) if hot else (10, 13, 12), cell, border_radius=3)
            txt = (labels or options)[i]
            img = self.f.text(txt, (6, 9, 10) if on else (190, 198, 192), bold=on)
            surf.blit(img, (cell.centerx - img.get_width() // 2, cell.centery - 6))
            if self.clicked(cell):
                out = opt
        pygame.draw.rect(surf, (40, 46, 44), r, 1, border_radius=3)
        return out

    def slider(self, surf, rect, value, lo, hi, step):
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, (30, 44, 37), (r.x, r.centery - 2, r.width, 4))
        frac = (value - lo) / (hi - lo)
        pygame.draw.rect(surf, ACID, (r.x, r.centery - 2, int(r.width * frac), 4))
        kx = r.x + int(r.width * frac)
        knob = pygame.Rect(kx - 3, r.centery - 5, 7, 10)
        pygame.draw.rect(surf, WHITE, knob); pygame.draw.rect(surf, INK, knob, 1)
        if self.enabled and self.down and self.pressed_at and r.inflate(8, 8).collidepoint(self.pressed_at):
            u = (self.mouse[0] - r.x) / max(1, r.width)
            v = lo + max(0.0, min(1.0, u)) * (hi - lo)
            value = round(round(v / step) * step, 4)
        return value

    def text_field(self, surf, rect, value, placeholder="", key="field"):
        r = pygame.Rect(rect)
        focused = self.focus == key
        if self.clicked(r):
            self.focus = key; focused = True
            pygame.key.start_text_input()
        pygame.draw.rect(surf, (8, 12, 10), r)
        pygame.draw.rect(surf, ACID if focused else UI_LINE2, r, 1)
        if focused:
            value += self.typed
            if self.backspace: value = value[:-self.backspace]
        show = value or placeholder
        img = self.f.text(show, WHITE if value else (90, 104, 96), mono=True)
        surf.set_clip(r.inflate(-4, 0))
        surf.blit(img, (r.x + 3 - max(0, img.get_width() - (r.width - 10)), r.centery - 6))
        surf.set_clip(None)
        if focused and int(pygame.time.get_ticks() / 500) % 2:
            cx = r.x + 4 + min(img.get_width(), r.width - 10) if value else r.x + 4
            pygame.draw.line(surf, ACID, (cx, r.y + 3), (cx, r.bottom - 4))
        return value

    def tooltip(self, surf, vw, vh):
        if not self.tip:
            return
        lines = self.f.wrap(self.tip, 180)
        w = max(self.f.width(s) for s in lines) + 8
        h = len(lines) * 12 + 5
        x = min(vw - w - 2, self.mouse[0] + 10); y = min(vh - h - 2, self.mouse[1] + 12)
        if x + w > vw: x = vw - w - 2
        r = pygame.Rect(x, y, w, h)
        cover(surf, r)
        pygame.draw.rect(surf, (6, 10, 8), r); pygame.draw.rect(surf, ACID_D, r, 1)
        for i, s in enumerate(lines):
            surf.blit(self.f.text(s, WHITE), (x + 4, y + 2 + i * 12))


class Toasts:
    COLORS = {"info": ((6, 9, 10), (214, 220, 212)), "good": ((6, 9, 10), ACID), "bad": ((30, 8, 8), (255, 110, 100)),
              "warn": ((6, 9, 10), (240, 240, 230)), "gold": ((6, 9, 10), ACID)}

    def __init__(self, fonts):
        self.f, self.items = fonts, []

    def push(self, text, kind="info", icon=None):
        if self.items and self.items[-1][0] == text:
            self.items[-1][3] = 0.0; return
        self.items.append([text, kind, icon, 0.0])
        self.items = self.items[-5:]

    def draw(self, surf, x, top, dt, maxw=400):
        """위에서부터 아래로 (새 알림이 맨 위)."""
        y = top + 16
        alive = []
        for it in reversed(self.items):
            it[3] += dt
            if it[3] > 4.0: continue
            alive.append(it)
            text, kind, icon, t = it
            bg, fg = self.COLORS.get(kind, self.COLORS["info"])
            room = maxw - 12 - (11 if icon else 0)
            while self.f.width(text, bold=kind in ("bad", "gold")) > room and len(text) > 4:
                text = text[:-2] + "…"
            img = self.f.text(text, fg, bold=kind in ("bad", "gold"))
            w = img.get_width() + 10 + (11 if icon else 0)
            slide = min(1.0, t * 6)
            r = pygame.Rect(x - int((1 - slide) * 30), y - 16, w, 15)
            cover(surf, r)
            pygame.draw.rect(surf, bg, r); pygame.draw.rect(surf, fg, r, 1)
            tx = r.x + 5
            if icon:
                surf.blit(art.icon(icon), (tx, r.y + 3)); tx += 11
            surf.blit(img, (tx, r.y + 1))
            y += 18
        self.items = list(reversed(alive))
