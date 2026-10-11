# -*- coding: utf-8 -*-
"""움직이는 것들 · 손님 · 직원 · 도둑 · 트럭 · 날아가는 서류 · 떠오르는 숫자 · 말풍선."""
import math

import pygame

from . import art
from .pixel import INK, WHITE, cover


class Actor:
    """걷는 사람. path = [("walk", x) | ("elev", 층) | ("wait", 초) | ("call", 함수) | ("die",)]."""
    layer = 1

    def __init__(self, look, x, level, speed=42.0):
        self.look, self.x, self.level, self.speed = look, float(x), level, speed
        self.path, self.hidden, self.alive = [], False, True
        self.icon, self.icon_t = None, 0.0
        self.carry = None
        self.anim, self.timer = 0.0, 0.0
        self.y = 0
        self.flash = 0.0

    def go(self, *steps):
        self.path.extend(steps)
        return self

    def say(self, icon, secs=1.6):
        self.icon, self.icon_t = icon, secs

    def update(self, dt, world):
        self.icon_t -= dt
        self.flash = max(0.0, self.flash - dt)
        if not self.path:
            return
        step = self.path[0]
        kind = step[0]
        if kind == "walk":
            tx = step[1]
            d = tx - self.x
            mv = self.speed * dt
            if abs(d) <= mv:
                self.x = tx; self.path.pop(0)
            else:
                self.x += mv if d > 0 else -mv
                self.anim += dt
        elif kind == "elev":
            if not self.hidden:
                self.hidden = True
                self.timer = 0.22 + 0.1 * abs(step[1] - self.level)
                world.elevator_target = step[1] if abs(step[1]) >= abs(world.elevator_target) or True else world.elevator_target
            self.timer -= dt
            if self.timer <= 0:
                self.level = step[1]; self.x = world.shaft_x; self.hidden = False; self.path.pop(0)
        elif kind == "wait":
            if self.timer <= 0 and not getattr(self, "_waiting", False):
                self.timer, self._waiting = step[1], True
            self.timer -= dt
            if self.timer <= 0:
                self._waiting = False; self.path.pop(0)
        elif kind == "call":
            self.path.pop(0); step[1](self)
        elif kind == "die":
            self.alive = False; self.path.clear()

    def draw(self, surf, world):
        if self.hidden:
            return
        moving = bool(self.path) and self.path[0][0] == "walk"
        img = self.look.frame(int(self.anim * 7) % 2 if moving else 0)
        y = world.floor_y(self.level)
        self.y = y
        x = int(self.x) - img.get_width() // 2
        if moving and self.path[0][1] < self.x:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (x, y - img.get_height() + 1))
        if self.flash > 0 and int(self.flash * 10) % 2:
            surf.blit(_tinted(img, (255, 60, 50)), (x, y - img.get_height() + 1))
        if self.carry is not None:
            surf.blit(self.carry, (int(self.x) - self.carry.get_width() // 2, y - img.get_height() - self.carry.get_height() + 4))
        if self.icon and self.icon_t > 0:
            draw_icon_bubble(surf, art.icon(self.icon), int(self.x), y - img.get_height() - 2)


_TINT = {}


def _tinted(img, color):
    key = (id(img), color)
    hit = _TINT.get(key)
    if hit is None:
        m = pygame.mask.from_surface(img)
        hit = _TINT[key] = m.to_surface(setcolor=(*color, 150), unsetcolor=(0, 0, 0, 0))
    return hit


def draw_icon_bubble(surf, ic, cx, bottom):
    w, h = ic.get_width() + 4, ic.get_height() + 4
    r = pygame.Rect(cx - w // 2, bottom - h - 3, w, h)
    pygame.draw.rect(surf, WHITE, r)
    pygame.draw.rect(surf, INK, r, 1)
    pygame.draw.line(surf, WHITE, (cx - 1, r.bottom - 1), (cx + 1, r.bottom - 1))
    surf.set_at((cx, r.bottom), INK); surf.set_at((cx - 1, r.bottom), INK); surf.set_at((cx + 1, r.bottom), INK)
    surf.set_at((cx, r.bottom + 1), INK)
    surf.blit(ic, (r.x + 2, r.y + 2))


class Truck:
    """창고로 들어오는 트럭 · 오른쪽에서 와서 경사로를 내려가 짐을 내리고 떠납니다."""
    layer = 2

    def __init__(self, world, units, on_unload):
        self.units, self.on_unload = units, on_unload
        self.t, self.alive, self.done = 0.0, True, False
        self.x0 = world.ww + 10
        self.y = 0

    def update(self, dt, world):
        self.t += dt
        if self.t > 2.0 and not self.done:
            self.done = True; self.on_unload(self)
        if self.t > 4.6:
            self.alive = False

    def draw(self, surf, world):
        t = self.t
        img = art.TRUCK
        rx, gy = world.ramp_x0, world.gy
        if t < 1.2:      # 길 위로
            x = self.x0 + (rx + 40 - self.x0) * (t / 1.2); y = gy
        elif t < 2.0:    # 경사로를 내려감
            u = (t - 1.2) / 0.8; x = rx + 40 - 38 * u; y = gy + 30 * u
        elif t < 3.0:    # 짐 내리기
            x, y = rx + 2, gy + 30
        elif t < 3.8:    # 다시 올라감
            u = (t - 3.0) / 0.8; x = rx + 2 + 38 * u; y = gy + 30 * (1 - u)
        else:
            u = (t - 3.8) / 0.8; x = rx + 40 + (self.x0 - rx - 40) * u; y = gy
        surf.blit(img, (int(x), int(y) - img.get_height() + 1))


class Flyer:
    """경로를 따라 날아가는 작은 그림 (서류 · 결제 신호 · 동전)."""
    layer = 3

    def __init__(self, img, pts, dur, on_done=None, arc=0.0, trail=False):
        self.img, self.pts, self.dur, self.on_done, self.arc, self.trail = img, pts, dur, on_done, arc, trail
        self.t, self.alive = 0.0, True
        segs = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
        self.total = sum(segs) or 1.0
        self.segs = segs

    def pos(self):
        u = min(1.0, self.t / self.dur) * self.total
        for (a, b), L in zip(zip(self.pts, self.pts[1:]), self.segs):
            if u <= L or L == self.segs[-1] and (a, b) == (self.pts[-2], self.pts[-1]):
                f = 0 if L == 0 else min(1.0, u / L)
                x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
                k = min(1.0, self.t / self.dur)
                return x, y - math.sin(k * math.pi) * self.arc
            u -= L
        return self.pts[-1]

    def update(self, dt, world):
        self.t += dt
        if self.t >= self.dur:
            self.alive = False
            if self.on_done: self.on_done()

    def draw(self, surf, world):
        x, y = self.pos()
        if self.trail:                                          # 모델의 판단이 층으로 내려가는 빛줄기
            x0, y0 = self.pts[0]
            pygame.draw.line(surf, (60, 90, 40), (int(x0), int(y0)), (int(x), int(y)), 1)
            pygame.draw.line(surf, (208, 249, 145), (int(x), int(max(y0, y - 10))), (int(x), int(y)), 1)
        surf.blit(self.img, (int(x) - self.img.get_width() // 2, int(y) - self.img.get_height() // 2))


class Popup:
    """떠오르는 글자 (돈 · 결과)."""

    def __init__(self, fonts, text, x, y, color, life=1.4, big=False, rise=14, icon=None, delay=0.0):
        k = 2 if big else 1
        self.img = fonts.text(text, color, bold=True, outline_color=INK, k=k)
        self.icon = art.icon(icon) if icon else None
        self.x, self.y, self.life, self.rise = x, y, life, rise
        self.t, self.alive, self.delay = -delay, True, delay

    def update(self, dt, world):
        self.t += dt
        if self.t > self.life: self.alive = False

    def draw(self, surf, world):
        if self.t < 0: return
        u = self.t / self.life
        y = self.y - self.rise * min(1.0, u * 1.6)
        w = self.img.get_width() + (11 if self.icon else 0)
        x = int(self.x - w / 2)
        if u > 0.75 and int(self.t * 20) % 2:
            return
        ty = int(y) - self.img.get_height() // 2 + 4
        if self.img.get_width() > 6:
            back = pygame.Rect(x - 2, ty, w + 4, self.img.get_height())
            bg = pygame.Surface(back.size, pygame.SRCALPHA); bg.fill((8, 12, 10, 170)); surf.blit(bg, back.topleft)
        if self.icon:
            surf.blit(self.icon, (x, int(y) - 1)); x += 11
        surf.blit(self.img, (x, ty))


class Speech:
    """한국어 말풍선 (고객 문의 · 환불 사유 · AI 사장의 JEV 답)."""

    def __init__(self, fonts, text, x, bottom, life=2.2, color=(30, 34, 32), bg=WHITE, edge=INK, width=132, icon=None, mono=False):
        lines = fonts.wrap(text, width)[:3]
        self.imgs = [fonts.text(s, color, mono=mono) for s in lines]
        self.rect = None
        self.icon = art.icon(icon) if icon else None
        self.x, self.bottom, self.life, self.bg, self.edge = x, bottom, life, bg, edge
        self.t, self.alive = 0.0, True

    def update(self, dt, world):
        self.t += dt
        if self.t > self.life: self.alive = False

    def draw(self, surf, world):
        pad = 3
        iw = 11 if self.icon else 0
        w = max(i.get_width() for i in self.imgs) + pad * 2 + iw
        h = len(self.imgs) * 11 + pad * 2 - 1
        x = int(max(world.bx + 22, min(world.bx + 224 - w, self.x - w // 2)))
        x = int(max(2, min(world.ww - w - 2, x)))
        y = int(self.bottom - h - 4)
        y = max(24, y)
        r = pygame.Rect(x, y, w, h)
        self.rect = r.inflate(4, 6)
        cover(surf, r.inflate(2, 8))
        pygame.draw.rect(surf, self.bg, r)
        pygame.draw.rect(surf, self.edge, r, 1)
        tx = int(max(r.left + 3, min(r.right - 4, self.x)))
        pygame.draw.polygon(surf, self.bg, [(tx - 2, r.bottom - 1), (tx + 2, r.bottom - 1), (tx, r.bottom + 3)])
        pygame.draw.line(surf, self.edge, (tx - 3, r.bottom), (tx, r.bottom + 3)); pygame.draw.line(surf, self.edge, (tx + 3, r.bottom), (tx, r.bottom + 3))
        if self.icon:
            surf.blit(self.icon, (r.x + pad, r.y + pad))
        for i, img in enumerate(self.imgs):
            surf.blit(img, (r.x + pad + iw, r.y + pad - 1 + i * 11))


class Coins:
    """동전 몇 개가 튀어 오릅니다."""

    def __init__(self, x, y, n=4, seed=0):
        import random
        rr = random.Random(seed)
        self.parts = [[x, y, rr.uniform(-22, 22), rr.uniform(-60, -35)] for _ in range(n)]
        self.t, self.alive = 0.0, True

    def update(self, dt, world):
        self.t += dt
        for p in self.parts:
            p[0] += p[2] * dt; p[1] += p[3] * dt; p[3] += 160 * dt
        if self.t > 0.9: self.alive = False

    def draw(self, surf, world):
        for i, p in enumerate(self.parts):
            surf.blit(art.COIN[int(self.t * 10 + i) % 2], (int(p[0]) - 3, int(p[1]) - 3))
