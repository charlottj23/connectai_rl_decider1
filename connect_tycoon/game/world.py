# -*- coding: utf-8 -*-
"""세계 · 단면으로 보는 회사 빌딩 (타이니 타워처럼 층마다 부서 하나)

    지붕   광고판 · 안테나(온라인 결제가 들어오는 곳)
    7F    AI 사장실 (전전두엽 사장님)
    6F    마케팅          5F 보안실          4F 사람 확인실
    3F    결제 · 환불     2F 고객센터        1F 매장 (저녁에 손님이 몰려옵니다)
    B1    물류창고 (개미굴 옆, 트럭이 경사로로 들어옵니다)

왼쪽 세로 칸은 엘리베이터와 로비입니다. 오른쪽 바깥은 주차장과 창고 경사로입니다.
"""
import math
import random

import pygame

from . import art
from .pixel import Canvas, mix, shade

FH = 33           # 층 높이
BW = 226          # 빌딩 너비
SHAFT = 18        # 엘리베이터 칸 너비

FLOORS = [  # level, key, 이름, 벽 색, 바닥 색 · 브랜드: 검정에 가까운 벽, 바닥은 회색 선
    (-1, "warehouse", "물류창고", (24, 24, 22), (58, 60, 58)),
    (0, "shop", "매장", (30, 30, 28), (70, 72, 70)),
    (1, "cs", "고객센터", (22, 28, 24), (60, 66, 62)),
    (2, "refund", "결제 · 환불", (22, 27, 27), (60, 66, 64)),
    (3, "review", "사람 확인실", (28, 28, 26), (66, 66, 64)),
    (4, "security", "보안실", (16, 18, 22), (50, 52, 58)),
    (5, "marketing", "마케팅", (28, 26, 22), (66, 64, 60)),
    (6, "ceo", "AI 사장실", (12, 18, 14), (52, 64, 56)),
]
LEVEL = {k: lv for lv, k, *_ in FLOORS}
NAMES = {k: n for _, k, n, *_ in FLOORS}
FLOOR_ICON = {"warehouse": "box", "shop": "coin", "cs": "phone", "refund": "card", "review": "search", "security": "shield", "marketing": "mega", "ceo": "brain"}
SHORT = {"warehouse": "물류창고", "shop": "매장", "cs": "고객센터", "refund": "환불", "review": "확인실", "security": "보안실", "marketing": "마케팅", "ceo": "사장실"}
TAG_COLOR = {"warehouse": (230, 234, 228), "shop": (230, 234, 228), "cs": (230, 234, 228), "refund": (230, 234, 228),
             "review": (230, 234, 228), "security": (230, 234, 228), "marketing": (230, 234, 228), "ceo": (208, 249, 145)}

SKY = {  # 시간대별 하늘 (위, 아래)
    "night": ((10, 16, 38), (30, 40, 74)),
    "dawn": ((96, 128, 196), (250, 196, 150)),
    "day": ((92, 168, 230), (192, 230, 244)),
    "dusk": ((80, 76, 150), (250, 150, 92)),
}


def sky_colors(p):
    """하루 진행(0~1) → 하늘 위/아래 색과 밤 정도(0~1)."""
    keys = [(0.0, "dawn"), (0.12, "day"), (0.62, "day"), (0.76, "dusk"), (0.88, "night"), (1.0, "night")]
    for (a, ka), (b, kb) in zip(keys, keys[1:]):
        if a <= p <= b:
            t = 0 if b == a else (p - a) / (b - a)
            top = mix(SKY[ka][0], SKY[kb][0], t); bot = mix(SKY[ka][1], SKY[kb][1], t)
            break
    night = max(0.0, min(1.0, (p - 0.74) / 0.14)) if p > 0.74 else max(0.0, 1 - p / 0.1) * 0.5
    return top, bot, night


class World:
    def __init__(self, fonts):
        self.f = fonts
        self.ww = self.wh = 0
        self.t = 0.0
        self.p = 0.3                     # 하루 진행 (0 새벽 ~ 1 밤)
        self.actors, self.fx = [], []
        self.caps = {"cs": 4, "refund": 4, "review": 4}
        self.used = {"cs": 0, "refund": 0, "review": 0}
        self.queue = {"cs": 0, "review": 0}
        self.stock, self.warehouse = 150.0, 250.0
        self.ad_level = 1
        self.upg = {}                    # 업그레이드 단계
        self.queued = set()              # 다음 달 문을 여는 공사
        self.alarm, self.flash = {}, {}
        self.ceo_mode, self.ceo_mood, self.trophies = "ai", "idle", 0
        self.elevator = 0.0
        self.elevator_target = 0.0
        self.seated = {}
        self.monitor_on = {}
        self.company_name = "Connect AI Company"
        self.sky_cache = {}
        rng = random.Random(42)
        self.skyline = [[(rng.randint(14, 34), rng.randint(30, 120), rng.random()) for _ in range(40)] for _ in range(2)]
        self.clouds = [(rng.random() * 700, rng.randint(14, 90), rng.randint(0, 2), 3 + rng.random() * 5) for _ in range(7)]
        self.stars = [(rng.random(), rng.random() * 0.6, rng.random()) for _ in range(70)]
        self.tunnels = None
        self.bg_cars = []
        self.season, self.weather = 0, "clear"
        self.show_tags = True
        self.parts = []

    # ── 배치 ──────────────────────────────────────────────────────────────
    def resize(self, ww, wh, align="center"):
        if (ww, wh, align) == (self.ww, self.wh, getattr(self, "align", None)):
            return
        self.ww, self.wh, self.align = ww, wh, align
        self.gy = wh - FH - 8                             # 1층 바닥선
        self.bx = max((ww - BW) // 2 - 6, min(ww - BW - 64, 132))    # 왼쪽에 층 안내판 자리
        if align == "right":                              # 타이틀: 빌딩은 오른쪽, 왼쪽은 메뉴
            self.bx = max(self.bx, ww - BW - 70)
        self.top = self.gy - 7 * FH                       # 지붕 위 면
        self.shaft_x = self.bx + 3 + SHAFT // 2           # 엘리베이터 문 가운데
        self.rx0, self.rx1 = self.bx + 4 + SHAFT, self.bx + BW - 4
        self.ramp_x0 = self.bx + BW
        self.tunnels = None
        self.sky_cache.clear()

    def floor_y(self, level):
        return self.gy - level * FH if level >= 0 else self.gy + FH

    def room_rect(self, level):
        y = self.floor_y(level)
        return pygame.Rect(self.rx0, y - FH + 3, self.rx1 - self.rx0, FH - 3)

    def desk_x(self, key, i, n=None):
        """책상 i의 가운데 x."""
        x0 = self.rx0 + 30 if key in ("cs", "refund") else self.rx0 + 34
        pitch = 15 if key != "review" else 16
        return x0 + i * pitch

    def max_desks(self, key):
        return 11

    def seat_x(self, key, i):
        """직원 자리 (책상 가운데)."""
        if key in ("cs", "refund", "review"): return self.desk_x(key, i)
        if key == "shop": return self.rx1 - 29
        if key == "warehouse": return self.rx1 - 70
        if key == "security": return self.rx0 + 119 + i * 18
        if key == "marketing": return self.rx0 + 96 + i * 18
        return self.rx0 + 40

    def _seated(self, surf, key, y, only=None):
        for i, look in self.seated.get(key, {}).items():
            if only is not None and i not in only: continue
            img = look.frame(0)
            surf.blit(img, (self.seat_x(key, i) - img.get_width() // 2, y - img.get_height() - 1))

    # ── 그리기 ────────────────────────────────────────────────────────────
    def draw(self, surf, dt):
        """브랜드 화면: 검정 하늘 → 흑백 라인 아트로 바꾼 빌딩 → 형광 연두 강조와 모션 → 말풍선 · 글자."""
        self.t += dt
        top, bot, night = sky_colors(self.p)
        self.night = night
        self.brand_mode = True
        self._sky(surf, top, bot, night)          # 새벽 → 낮 → 노을 → 밤
        self._background(surf, night)
        self._ground(surf, 0.0)
        self._building(surf, 0.0)
        self._roof(surf, 0.0)
        for lv, key, _name, wall, floor in FLOORS:
            self._room(surf, lv, key, wall, floor, 0.0)
        self._elevator(surf)
        self._accents(surf)
        for a in sorted(self.actors, key=lambda a: (a.layer, a.y)):
            a.draw(surf, self)
        self._outside_front(surf, 0.0)
        self._weather(surf, dt, night)
        speech = [e for e in self.fx if hasattr(e, "imgs")]
        for e in self.fx:
            if not hasattr(e, "imgs"): e.draw(surf, self)
        if self.show_tags:
            self._tags(surf)
        for e in speech:                      # 말풍선은 늘 맨 위에 (글자가 덮이지 않게)
            e.draw(surf, self)

    def _sky(self, surf, top, bot, night):
        key = (top, bot, self.wh)
        g = self.sky_cache.get(key)
        if g is None:
            g = pygame.Surface((1, self.wh))
            for y in range(self.wh):
                g.set_at((0, y), mix(top, bot, y / max(1, self.gy)))
            g = pygame.transform.scale(g, (self.ww, self.wh))
            if len(self.sky_cache) > 64: self.sky_cache.clear()
            self.sky_cache[key] = g
        surf.blit(g, (0, 0))
        if night > 0.05:
            for sx, sy, ph in self.stars:
                if math.sin(self.t * 2 + ph * 9) > -0.3:
                    c = mix((40, 50, 80), (240, 240, 220), night * (0.6 + 0.4 * ph))
                    surf.set_at((int(sx * self.ww), int(sy * self.gy)), c)
        # 해 · 달
        p = self.p
        if 0.02 < p < 0.82:
            a = (p - 0.02) / 0.8
            x = int(self.ww * (0.08 + 0.84 * a)); y = int(self.gy * 0.62 - math.sin(a * math.pi) * self.gy * 0.5)
            surf.blit(art.SUN, (x - 5, y - 5))
        if p > 0.8 or p < 0.06:
            surf.blit(art.MOON, (int(self.ww * 0.78), int(self.gy * 0.12)))
        for _i, (cx, cy, kind, sp) in enumerate(self.clouds):
            img = art.CLOUDS[kind]
            x = int((cx + self.t * sp) % (self.ww + 80)) - 40
            surf.blit(img if night < .5 else _dim(img, night), (x, cy))
        if self.upg.get("ad", 0) >= 3:
            bx = int((self.t * 7) % (self.ww + 120)) - 60
            surf.blit(art.BLIMP, (bx, 34 + int(math.sin(self.t) * 2)))

    def _background(self, surf, night):
        # 뒤쪽 도시 두 겹
        for layer, (rows, base, _k) in enumerate(zip(self.skyline, [(120, 150, 170), (80, 104, 120)], [0.5, 0.8])):
            c = mix(base, (20, 26, 44), night * 0.85)
            x = -10 if layer == 0 else -4
            for w, h, ph in rows:
                h2 = int(h * (0.7 if layer == 0 else 0.55))
                pygame.draw.rect(surf, c, (x, self.gy - h2, w, h2))
                if night > 0.3:
                    lit = (250, 220, 140)
                    rr = random.Random(int(ph * 1e6))
                    for wy in range(self.gy - h2 + 4, self.gy - 4, 6):
                        for wx in range(x + 3, x + w - 3, 5):
                            if rr.random() < 0.35:
                                surf.set_at((wx, wy), mix(c, lit, night))
                x += w + (3 if layer == 0 else 6)
                if x > self.ww: break
        # 뒤쪽 길의 자동차 (빌딩 뒤로 지나갑니다)
        if random.random() < 0.01 and len(self.bg_cars) < 3:
            d = random.choice((-1, 1))
            self.bg_cars.append([(-30 if d > 0 else self.ww + 30), d, random.choice(art.PRODUCT_COLORS), 18 + random.random() * 14])
        for c in self.bg_cars:
            c[0] += c[1] * c[3] * 0.016
            img = art.car(tuple(c[2]))
            img = img if c[1] < 0 else pygame.transform.flip(img, True, False)
            surf.blit(_dim(img, 0.25 + night * 0.5), (int(c[0]), self.gy - 9))
        self.bg_cars = [c for c in self.bg_cars if -40 < c[0] < self.ww + 40]

    def _ground(self, surf, night):
        gy = self.gy
        dirt, dirt2 = (12, 14, 13), (26, 30, 28)
        pygame.draw.rect(surf, dirt, (0, gy, self.ww, self.wh - gy))
        if self.tunnels is None:                         # 개미굴
            rr = random.Random(9)
            self.tunnels = []
            for side in (0, 1):
                x0, x1 = (4, self.bx - 6) if side == 0 else (self.ramp_x0 + 44, self.ww - 4)
                if x1 - x0 < 20: continue
                pts = [(rr.randint(x0, x1), gy + 4)]
                for _ in range(6):
                    px, py = pts[-1]
                    pts.append((max(x0, min(x1, px + rr.randint(-18, 18))), max(gy + 4, min(self.wh - 4, py + rr.randint(2, 7)))))
                self.tunnels.append(pts)
        for pts in self.tunnels:
            for a, b in zip(pts, pts[1:]):
                pygame.draw.line(surf, dirt2, a, b, 3)
            for x, y in pts[1:-1:2]:
                pygame.draw.ellipse(surf, dirt2, (x - 4, y - 2, 9, 5))
            n = len(pts) - 1
            for k in range(3):                            # 개미 세 마리씩
                u = (self.t * 0.06 + k / 3) % 1 * n
                i = int(u); fr = u - i
                ax = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * fr; ay = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * fr
                surf.blit(art.ANT, (int(ax) - 1, int(ay) - 1))
        for x in range(0, self.ww, 3):                    # 흙 알갱이
            r = (x * 7919) % 13
            surf.set_at((x, gy + 6 + r * 2 % (self.wh - gy - 6 or 1)), dirt2)
        grass = (208, 249, 145) if self.season != 3 else (232, 238, 242)
        pygame.draw.rect(surf, grass, (0, gy, self.ww, 2))
        walk = (52, 56, 54)
        pygame.draw.rect(surf, walk, (0, gy - 1, self.bx, 3))
        # 오른쪽: 경사로 · 주차장
        rx = self.ramp_x0
        pygame.draw.rect(surf, walk, (rx + 40, gy - 1, self.ww - rx - 40, 3))
        ramp_c = (34, 38, 36)
        pygame.draw.polygon(surf, ramp_c, [(rx, gy), (rx + 40, gy), (rx + 40, gy + 2), (rx + 2, gy + FH), (rx, gy + FH)])
        pygame.draw.rect(surf, ramp_c, (rx, gy, 3, FH))

    def _building(self, surf, night):
        bx, gy, top = self.bx, self.gy, self.top
        frame = (30, 34, 32)
        pygame.draw.rect(surf, frame, (bx, top - 2, BW, gy + FH + 2 - top + 2))
        # 엘리베이터 칸
        shaft = pygame.Rect(bx + 3, top + 1, SHAFT, gy + FH - top - 1)
        pygame.draw.rect(surf, (8, 10, 9), shaft)
        for y in range(shaft.top, shaft.bottom, 4):
            surf.set_at((shaft.left + 2, y), (40, 48, 44)); surf.set_at((shaft.right - 3, y), (40, 48, 44))

    def _roof(self, surf, night):
        bx, top = self.bx, self.top
        pygame.draw.rect(surf, (40, 44, 42), (bx - 2, top - 4, BW + 4, 4))
        pygame.draw.rect(surf, (208, 249, 145), (bx - 2, top - 5, BW + 4, 1))
        # 광고판
        lvl = self.ad_level
        on = lvl > 0
        title = self.f.text(self.company_name, (208, 249, 145) if on else (190, 196, 190), bold=True)
        bw = max(92 + 18 * min(2, self.upg.get("ad", 0)), title.get_width() + 14)      # 회사 이름이 다 들어가게
        bw = min(bw, BW - 60)
        x0 = bx + 26; y0 = top - 31
        for px in (x0 + 8, x0 + bw - 10):
            pygame.draw.rect(surf, (40, 46, 44), (px, y0 + 22, 2, 9))
        y0 += 6
        panel = pygame.Rect(x0, y0, bw, 16)
        pygame.draw.rect(surf, (16, 22, 20), panel)
        edge = (208, 249, 145) if on else (120, 128, 124)
        if lvl == 2 and int(self.t * 4) % 2: edge = (255, 207, 107)
        pygame.draw.rect(surf, edge, panel, 1)
        surf.blit(title, (panel.centerx - title.get_width() // 2, y0 + 1))
        sub = "오늘만 특가!" if lvl == 2 else "좋은 물건 빠른 배송" if lvl == 1 else "광고 중단"
        if lvl == 2:
            sub = sub if int(self.t * 2) % 2 else "★ 대박 세일 ★"
        s = self.f.text(sub, (255, 255, 255) if on else (255, 170, 150))
        del s
        # 안테나 · 접시 (사기 탐지 AI)
        ax = bx + BW - 22
        pygame.draw.line(surf, (90, 100, 96), (ax, top - 4), (ax, top - 26))
        pygame.draw.line(surf, (90, 100, 96), (ax - 4, top - 18), (ax + 4, top - 18))
        blink = (255, 80, 60) if int(self.t * 2) % 2 else (90, 30, 30)
        surf.set_at((ax, top - 27), blink)
        if self.upg.get("fraud", 0) >= 1:
            pygame.draw.circle(surf, (200, 210, 206), (ax - 12, top - 10), 5)
            pygame.draw.circle(surf, (118, 214, 224), (ax - 12, top - 10), 2)
        # 물탱크
        pygame.draw.rect(surf, (90, 104, 98), (bx + BW - 56, top - 14, 16, 10))
        pygame.draw.rect(surf, (60, 72, 68), (bx + BW - 56, top - 14, 16, 2))

    def _room(self, surf, lv, key, wall, floor, night):
        r = self.room_rect(lv)
        y = self.floor_y(lv)
        wallc = wall
        pygame.draw.rect(surf, wallc, r)
        # 벽 무늬
        if key in ("cs", "refund", "review", "marketing", "shop"):
            stripe = shade(wallc, 1.3)
            for x in range(r.left, r.right, 12):
                pygame.draw.line(surf, stripe, (x, r.top), (x, r.bottom - 1))
        if key == "warehouse":
            for x in range(r.left, r.right, 10):
                for yy in range(r.top + 2, r.bottom, 6):
                    surf.set_at((x + (yy // 6 % 2) * 5, yy), shade(wallc, 0.85))
        pygame.draw.rect(surf, floor, (r.left, y - 2, r.width, 2))
        pygame.draw.rect(surf, (44, 48, 46), (self.bx, y, BW, 3))
        # 엘리베이터 문 (층마다)
        dx = self.bx + 5
        door = pygame.Rect(dx, y - 20, SHAFT - 4, 18)
        pygame.draw.rect(surf, (150, 160, 156), door, 1)
        pygame.draw.line(surf, (110, 120, 116), (door.centerx, door.top + 1), (door.centerx, door.bottom - 2))
        arrow = (208, 249, 145) if abs(self.elevator - lv) < 0.2 else (60, 70, 66)
        surf.set_at((door.centerx, door.top - 2), arrow)
        getattr(self, "_room_" + key)(surf, r, y, night)

    # ── 층별 가구 ─────────────────────────────────────────────────────────
    def _room_warehouse(self, surf, r, y, night):
        cap = self.warehouse
        frac = max(0.0, min(1.0, self.stock / max(1.0, cap)))
        n_shelf = 5 + min(3, self.upg.get("logistics", 0))
        total = n_shelf * 6
        full = int(round(frac * total))
        x = r.left + 8
        for s in range(n_shelf):
            pygame.draw.rect(surf, (92, 74, 56), (x, y - 21, 2, 19)); pygame.draw.rect(surf, (92, 74, 56), (x + 13, y - 21, 2, 19))
            for lvl, yy in enumerate((y - 8, y - 15, y - 22)):
                pygame.draw.rect(surf, (120, 96, 70), (x, yy + 4, 15, 1))
                for j in range(2):
                    idx = s * 6 + lvl * 2 + j
                    if idx < full:
                        surf.blit(art.BOX, (x + 2 + j * 6, yy))
            x += 19
        if self.upg.get("logistics", 0) >= 2:
            surf.blit(art.FORKLIFT, (r.right - 44, y - 12))
        self._seated(surf, "warehouse", y + 1)
        # 도크 문
        pygame.draw.rect(surf, (40, 44, 42), (r.right - 2, y - 22, 3, 20))
        gx, gw = r.right - 58, 46                          # 재고 게이지 (글자 대신)
        pygame.draw.rect(surf, (40, 44, 42), (gx, r.top + 4, gw, 4), border_radius=2)
        pygame.draw.rect(surf, (208, 249, 145) if frac > 0.25 else (255, 100, 90), (gx, r.top + 4, max(1, int(gw * frac)), 4), border_radius=2)
        surf.blit(art.icon("box"), (gx - 12, r.top + 1))

    def _room_shop(self, surf, r, y, night):
        frac = max(0.0, min(1.0, self.stock / max(1.0, self.warehouse)))
        n_shelf = 4 + min(2, self.upg.get("demand", 0))
        x = r.left + 10
        k = 0
        for _s in range(n_shelf):
            pygame.draw.rect(surf, (150, 104, 66), (x, y - 20, 18, 18))
            pygame.draw.rect(surf, (120, 82, 52), (x, y - 20, 18, 18), 1)
            for lvl in range(3):
                yy = y - 18 + lvl * 6
                pygame.draw.line(surf, (110, 76, 48), (x + 1, yy + 4), (x + 16, yy + 4))
                for j in range(5):
                    k += 1
                    if (k * 37 % 100) / 100 < frac:
                        surf.blit(art.product(k), (x + 2 + j * 3, yy + 1))
            x += 22
        if self.upg.get("demand", 0) >= 1:
            sale = self.f.text("SALE", (255, 255, 255), bold=True)
            pygame.draw.rect(surf, (232, 76, 66), (r.left + 10, r.top + 1, sale.get_width() + 4, 9))
            surf.blit(sale, (r.left + 12, r.top - 1))
        cx = r.right - 40
        self._seated(surf, "shop", y)
        surf.blit(art.COUNTER, (cx, y - 9))
        surf.blit(art.REGISTER, (cx + 3, y - 16))
        surf.blit(art.PLANT, (r.right - 9, y - 10))
        # 로비 쪽 유리문
        gx = self.bx
        pygame.draw.rect(surf, (150, 200, 220), (gx, y - 22, 3, 20))
        if night > 0.2:
            pygame.draw.rect(surf, (255, 240, 180), (gx - 1, y - 23, 5, 1))
        on = self.p < 0.9
        pygame.draw.rect(surf, (20, 26, 22), (self.bx + 4, y - 26, 14, 5))
        pygame.draw.rect(surf, (208, 249, 145) if on and int(self.t * 2) % 4 else (90, 110, 80), (self.bx + 5, y - 25, 12, 3))

    def _desks(self, surf, key, r, y, glow):
        cap, used = self.caps.get(key, 0), self.used.get(key, 0)
        n = min(self.max_desks(key), max(cap, 4))
        self._seated(surf, key, y)
        for i in range(n):
            x = self.desk_x(key, i)
            on = i < cap
            surf.blit(art.DESK, (x - 7, y - 6))
            if key == "review":
                surf.blit(art.DOCS, (x - 5, y - 11)) if on else None
            else:
                busy = on and i < used and int(self.t * 3 + i) % 2 == 0
                surf.blit(art.monitor(glow if on else (40, 44, 42)) if not busy else art.monitor((255, 255, 255)), (x - 3, y - 12))

    def _room_cs(self, surf, r, y, night):
        surf.blit(art.BOARD, (r.left + 6, r.top + 3))
        self._desks(surf, "cs", r, y, (208, 249, 145))
        q = self.queue.get("cs", 0)
        if q:
            tx = r.right - 18
            for i in range(min(q, 8)):
                surf.blit(art.PAPER, (tx, y - 10 - i * 2))
        surf.blit(art.COOLER, (r.right - 8, y - 11))

    def _room_refund(self, surf, r, y, night):
        won = self.f.text("₩", (60, 140, 120), bold=True, k=2)
        surf.blit(won, (r.right - 26, r.top))
        self._desks(surf, "refund", r, y, (127, 210, 180))

    def _room_review(self, surf, r, y, night):
        self._desks(surf, "review", r, y, (238, 230, 200))
        surf.blit(art.BENCH, (r.right - 30, y - 6))

    def _room_security(self, surf, r, y, night):
        alarm = self.alarm.get("security", 0) > 0
        for i in range(5):
            surf.blit(art.server(int(self.t * 3) + i, alarm), (r.left + 6 + i * 11, y - 20))
        # 세계 지도 화면
        sx = r.left + 66
        pygame.draw.rect(surf, (10, 14, 20), (sx, r.top + 3, 40, 16))
        pygame.draw.rect(surf, (118, 214, 224), (sx, r.top + 3, 40, 16), 1)
        rr = random.Random(5)
        for _ in range(16):
            surf.set_at((sx + 3 + rr.randint(0, 33), r.top + 6 + rr.randint(0, 10)), (60, 140, 160))
        bx = sx + 3 + int((self.t * 9) % 34)
        surf.set_at((bx, r.top + 10), (255, 90, 80))
        self._seated(surf, "security", y)
        for i in range(2):
            surf.blit(art.DESK, (sx + 46 + i * 18, y - 6)); surf.blit(art.monitor((255, 122, 107)), (sx + 50 + i * 18, y - 12))
        lv = self.upg.get("fraud", 0)
        if lv >= 1:
            surf.blit(art.SCANNER, (r.right - 26, y - 10))
            if int(self.t * 3) % 2: pygame.draw.line(surf, (118, 214, 224), (r.right - 24, y - 6), (r.right - 16, y - 6))
        if lv >= 2:
            surf.blit(art.ROBOT, (r.right - 12, y - 12 - int(abs(math.sin(self.t * 3)) * 2)))

    def _room_marketing(self, surf, r, y, night):
        sx, sw = r.left + 8, 54
        pygame.draw.rect(surf, (16, 16, 20), (sx, r.top + 2, sw, 20))
        lvl = self.ad_level
        if lvl > 0:
            ph = self.t * (1.5 if lvl == 1 else 4)
            for i in range(sw - 4):
                h = int(5 + 4 * math.sin(ph + i * 0.3) * (1 if lvl == 2 else 0.5))
                c = (255, 207, 107) if lvl == 1 else ((255, 120, 150) if (i // 6 + int(ph)) % 2 else (255, 207, 107))
                pygame.draw.line(surf, c, (sx + 2 + i, r.top + 20), (sx + 2 + i, r.top + 20 - h))
            ad = self.f.text("AD" if lvl == 1 else "SALE!", (255, 255, 255), bold=True)
            surf.blit(ad, (sx + sw // 2 - ad.get_width() // 2, r.top + 2))
        else:
            off = self.f.text("광고 중단", (255, 170, 150), bold=True)
            surf.blit(off, (sx + sw // 2 - off.get_width() // 2, r.top + 7))
        pygame.draw.rect(surf, (90, 70, 40), (sx, r.top + 2, sw, 20), 1)
        surf.blit(art.CHART, (sx + sw + 6, r.top + 4))
        self._seated(surf, "marketing", y)
        for i in range(3):
            x = sx + sw + 34 + i * 18
            surf.blit(art.DESK, (x - 7, y - 6)); surf.blit(art.monitor((255, 207, 107) if lvl else (60, 60, 60)), (x - 3, y - 12))
        surf.blit(art.PLANT, (r.right - 9, y - 10))

    def _room_ceo(self, surf, r, y, night):
        # 큰 창문 (도시 풍경)
        wx, ww = r.left + 4, 52
        top, bot, _ = sky_colors(self.p)
        pygame.draw.rect(surf, mix(top, bot, 0.6), (wx, r.top + 2, ww, 20))
        for i, h in enumerate((8, 13, 6, 11, 9, 14, 7)):
            pygame.draw.rect(surf, mix((70, 90, 100), (20, 26, 40), night), (wx + 2 + i * 7, r.top + 22 - h, 6, h))
        pygame.draw.rect(surf, (208, 249, 145), (wx, r.top + 2, ww, 20), 1)
        pygame.draw.line(surf, (208, 249, 145), (wx + ww // 2, r.top + 2), (wx + ww // 2, r.top + 21))
        # 트로피 선반
        tx = r.left + 64
        pygame.draw.rect(surf, (70, 56, 40), (tx, r.top + 10, 40, 2))
        for i in range(min(self.trophies, 6)):
            surf.blit(art.TROPHY, (tx + i * 7 - 1, r.top + 3))
        surf.blit(art.SAFE, (tx + 2, y - 10))
        # 사장 책상과 사장님
        dx = r.left + 120
        if self.ceo_mode == "ai":
            mood = self.ceo_mood if self.ceo_mood != "idle" else ("blink" if int(self.t * 10) % 37 == 0 else "idle")
            b = art.brain_ceo(mood)
            bob = int(abs(math.sin(self.t * 2)) * 1.5) if mood == "think" else 0
            surf.blit(b, (dx + 3, y - 20 - bob))
            surf.blit(art.CEO_DESK, (dx - 2, y - 8))
        else:
            surf.blit(art.player_face(), (dx + 6, y - 17))
            surf.blit(art.CEO_DESK, (dx - 2, y - 8))
            surf.blit(art.SOFA, (r.right - 22, y - 6))
            surf.blit(art.brain_ceo("think"), (r.right - 20, y - 22))
        pygame.draw.rect(surf, (208, 249, 145), (dx + 8, y - 6, 6, 2))
        surf.blit(art.PLANT, (r.right - 9, y - 10)) if self.ceo_mode == "ai" else None

    def _elevator(self, surf):
        lv = self.elevator
        y = self.floor_y(0) - lv * FH if lv >= 0 else self.floor_y(0) + (-lv) * FH
        car = pygame.Rect(self.bx + 4, int(y) - FH + 5, SHAFT - 2, FH - 6)
        pygame.draw.rect(surf, (60, 72, 66), car)
        pygame.draw.rect(surf, (208, 249, 145), car, 1)
        pygame.draw.line(surf, (40, 48, 44), (car.centerx, self.top), (car.centerx, car.top))

    def _outside_front(self, surf, night):
        gy = self.gy
        # 왼쪽 길: 버스 정류장 · 가로등 · 나무
        left = self.bx
        tree, pine = art.tree(self.season), art.pine(self.season)
        if left > 96:
            surf.blit(art.BUSSTOP, (left - 78, gy - 12))
        surf.blit(tree, (max(2, left - 40), gy - 14))
        lamp_x = left - 12
        surf.blit(art.LAMP, (lamp_x, gy - 16))
        if night > 0.2:
            glow = pygame.Surface((22, 20), pygame.SRCALPHA)
            pygame.draw.polygon(glow, (255, 230, 150, int(60 * night)), [(9, 2), (13, 2), (21, 19), (1, 19)])
            surf.blit(glow, (lamp_x - 8, gy - 20))
        # 오른쪽: 나무 · 주차장
        rx = self.ramp_x0 + 44
        if self.ww - rx > 30:
            surf.blit(pine, (rx + 4, gy - 11))
        if self.ww - rx > 70:
            surf.blit(art.car((232, 108, 96)), (rx + 22, gy - 9))
        if self.ww - rx > 100:
            surf.blit(tree, (rx + 54, gy - 14))
        if self.ww - rx > 140:
            surf.blit(art.car((98, 158, 228)), (rx + 92, gy - 9))
        if self.season == 3:                                  # 지붕과 땅의 눈
            pygame.draw.rect(surf, (240, 244, 248), (self.bx - 2, self.top - 6, BW + 4, 2))

    def _weather(self, surf, dt, night):
        """계절 날씨 · 봄 꽃잎 · 여름 비(가끔) · 가을 낙엽 · 겨울 눈."""
        kind = self.weather
        rate = {"petals": 6, "rain": 90, "leaves": 7, "snow": 26, "clear": 0}.get(kind, 0)
        if dt > 0 and rate:
            n = rate * dt
            while n > 0:
                if random.random() < n:
                    x = random.uniform(-20, self.ww + 20)
                    if kind == "rain": self.parts.append([x, -4, -30, 220, kind])
                    elif kind == "snow": self.parts.append([x, -4, random.uniform(-8, 8), random.uniform(14, 26), kind])
                    else: self.parts.append([x, -4, random.uniform(8, 22), random.uniform(10, 18), kind])
                n -= 1
        col = {"petals": (250, 196, 214), "rain": (150, 190, 230), "leaves": (236, 140, 60), "snow": (248, 250, 252)}
        keep = []
        for p in self.parts:
            p[0] += p[2] * dt + (math.sin(self.t * 2 + p[0]) * 6 * dt if p[4] in ("petals", "leaves", "snow") else 0)
            p[1] += p[3] * dt
            if p[1] > self.gy or p[0] < -30 or p[0] > self.ww + 30: continue
            keep.append(p)
            c = col.get(p[4], (255, 255, 255))
            if p[4] == "rain":
                pygame.draw.line(surf, c, (int(p[0]), int(p[1])), (int(p[0] - 1), int(p[1] + 3)))
            elif p[4] == "leaves":
                surf.set_at((int(p[0]), int(p[1])), c); surf.set_at((int(p[0]) + 1, int(p[1])), shade(c, .8))
            else:
                surf.set_at((int(p[0]), int(p[1])), c)
        self.parts = keep[-600:]
        if kind == "rain" and dt:
            ov = pygame.Surface((self.ww, self.gy), pygame.SRCALPHA); ov.fill((30, 40, 60, 40)); surf.blit(ov, (0, 0))

    # ── 브랜드 화면 ──────────────────────────────────────────────────────
    def _layer(self, surf):
        L = getattr(self, "_L", None)
        if L is None or L.get_size() != surf.get_size():
            L = self._L = Canvas(surf.get_size(), pygame.SRCALPHA)
        L.fill((0, 0, 0, 0))
        L.set_clip(surf.get_clip())
        return L

    def _brand_sky(self, surf, dt):
        """검정 하늘 · 천천히 흐르는 격자 · 별 · 흰 선으로 그린 도시."""
        surf.fill(BLACK, (0, 0, self.ww, self.wh))
        grid = (16, 22, 20)
        off = int(self.t * 6) % 24
        for x in range(-off, self.ww, 24):
            pygame.draw.line(surf, grid, (x, 0), (x, self.gy))
        for y in range(self.gy - off, 0, -24):
            pygame.draw.line(surf, grid, (0, y), (self.ww, y))
        for sx, sy, ph in self.stars:
            if math.sin(self.t * 1.5 + ph * 9) > 0.2:
                surf.set_at((int(sx * self.ww), int(sy * self.gy)), (120, 128, 124))
        for layer, rows in enumerate(self.skyline):
            col = (34, 40, 38) if layer == 0 else (52, 60, 56)
            x = -10 if layer == 0 else -4
            for w, h, ph in rows:
                h2 = int(h * (0.7 if layer == 0 else 0.55))
                pygame.draw.rect(surf, col, (x, self.gy - h2, w, h2), 1)
                if layer == 1:
                    rr = random.Random(int(ph * 1e6))
                    for wy in range(self.gy - h2 + 4, self.gy - 4, 6):
                        for wx in range(x + 3, x + w - 3, 5):
                            if rr.random() < 0.18:
                                lit = int(self.t * 0.5 + wx * 0.13 + wy) % 7 == 0
                                surf.set_at((wx, wy), ACID if lit else (70, 78, 74))
                x += w + (3 if layer == 0 else 6)
                if x > self.ww: break
        if self.upg.get("ad", 0) >= 3:
            bx = int((self.t * 7) % (self.ww + 120)) - 60
            surf.blit(art.BLIMP, (bx, 34 + int(math.sin(self.t) * 2)))

    def _accents(self, surf):
        """형광 연두: 일하는 자리 · 모델(사장실) · 엘리베이터 · 판단이 내려간 층. 경보는 붉게, 공사는 흰 빗금."""
        t = self.t
        for key in ("cs", "refund"):
            y = self.floor_y(LEVEL[key])
            for i in range(min(self.caps.get(key, 0), self.max_desks(key))):
                x = self.desk_x(key, i)
                busy = i < self.used.get(key, 0) and int(t * 3 + i) % 2 == 0
                pygame.draw.rect(surf, (255, 255, 255) if busy else ACID, (x - 2, y - 11, 5, 2))
        # 사장실: 형광 두뇌 (모델)
        r = self.room_rect(LEVEL["ceo"])
        y = self.floor_y(LEVEL["ceo"])
        dx = r.left + 120
        if self.ceo_mode == "ai":
            mood = self.ceo_mood if self.ceo_mood != "idle" else ("blink" if int(t * 10) % 37 == 0 else "idle")
            b = art.brain_ceo(mood, brand=True)
            bob = int(abs(math.sin(t * 2)) * 1.5) if mood == "think" else 0
            glow = 0.5 + 0.5 * math.sin(t * 3)
            pygame.draw.circle(surf, mix(BLACK, ACID, 0.18 + 0.12 * glow), (dx + 12, y - 12), 13, 1)
            surf.blit(b, (dx + 3, y - 20 - bob))
        else:
            surf.blit(art.brain_ceo("think", brand=True), (r.right - 20, y - 22))
        # 엘리베이터 칸
        lv = self.elevator
        ey = self.floor_y(0) - lv * FH if lv >= 0 else self.floor_y(0) + (-lv) * FH
        pygame.draw.rect(surf, ACID, (self.bx + 4, int(ey) - FH + 5, SHAFT - 2, FH - 6), 1)
        # 광고판 테두리
        # 층 강조 · 경보 · 공사
        for lv_, key, *_ in FLOORS:
            rr = self.room_rect(lv_)
            if self.flash.get(key, 0) > 0:
                k = min(1.0, self.flash[key])
                ov = pygame.Surface(rr.size, pygame.SRCALPHA); ov.fill((*ACID, int(40 * k))); surf.blit(ov, rr.topleft)
                pygame.draw.rect(surf, ACID, rr, 1)
            if self.alarm.get(key, 0) > 0:
                on = int(t * 8) % 2
                ov = pygame.Surface(rr.size, pygame.SRCALPHA); ov.fill((255, 70, 60, 60 if on else 20)); surf.blit(ov, rr.topleft)
                pygame.draw.rect(surf, (255, 90, 80) if on else (120, 30, 30), rr, 1)
            if key in self.queued:
                for x in range(rr.left + 4, rr.right - 4, 14):
                    pygame.draw.line(surf, (200, 204, 200), (x, rr.top + 1), (x + 8, rr.bottom - 2))
                surf.blit(art.icon("hammer"), (rr.right - 14, rr.top + 3))

    def _tags(self, surf):
        """층 안내판 · 빌딩 왼쪽 바깥에 붙은 안내판 (2F 고객센터 3/4)."""
        right = self.bx - 2
        for lv, key, _name, *_ in FLOORS:
            y = self.floor_y(lv) - FH + 1
            floor = "B1" if lv < 0 else f"{lv + 1}F"
            parts = [(floor, (190, 196, 190))]
            imgs = [self.f.text(t, col, bold=i == 1) for i, (t, col) in enumerate(parts)]
            w = sum(i.get_width() for i in imgs) + 3 * (len(imgs) - 1) + 6
            r = pygame.Rect(right - w, y, w, 12)
            if r.left < 1:
                imgs = imgs[1:]; w = sum(i.get_width() for i in imgs) + 3 * (len(imgs) - 1) + 6; r = pygame.Rect(right - w, y, w, 12)
            r = pygame.Rect(right - w - 12, y, w + 12, 12)
            bg = pygame.Surface(r.size, pygame.SRCALPHA); bg.fill((8, 14, 11, 190)); surf.blit(bg, r.topleft)
            surf.blit(art.icon(FLOOR_ICON[key]), (r.x + 2, r.y + 2))
            pygame.draw.line(surf, TAG_COLOR[key], (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
            x = r.x + 14
            for img in imgs:
                surf.blit(img, (x, r.y)); x += img.get_width() + 3
            if self.alarm.get(key, 0) > 0 and int(self.t * 8) % 2:
                pygame.draw.rect(surf, (255, 60, 50), r, 1)

    # ── 효과 도우미: 같은 층에서 겹치지 않게 ─────────────────────────────
    def popup(self, p):
        """떠오르는 글자를 빈 자리에 놓습니다 (같은 줄에 있으면 옆으로, 그래도 차 있으면 조금 늦게)."""
        width = lambda e: e.img.get_width() + (11 if e.icon else 0)
        w = width(p)
        live = [e for e in self.fx if isinstance(e, type(p)) and e.t < e.life * 0.85]

        bubbles = [e.rect for e in self.fx if getattr(e, "rect", None) is not None and e.alive]

        def clash(x, y):
            hit = [e for e in live if abs(y - e.y) < 12 and abs(x - e.x) <= (w + width(e)) / 2 + 4]
            box = pygame.Rect(int(x - w / 2) - 2, int(y - 16), int(w) + 4, 26)    # 떠오르는 동안 지나갈 자리까지
            if any(box.colliderect(b) for b in bubbles):
                hit.append(p)
            return hit
        lo, hi = self.bx + w / 2 + 2, self.bx + BW - w / 2 - 2
        for dy in (0, -12, 12, -24):
            for k in (0, 1, -1, 2, -2):
                x = p.x + k * (w / 2 + 34)
                if lo <= x <= hi and not clash(x, p.y + dy):
                    p.x, p.y = x, p.y + dy
                    self.fx.append(p)
                    return p
        block = [e for e in clash(p.x, p.y) if e is not p]
        p.t = -min(1.6, max([e.life * 0.85 - e.t for e in block] + [0.6]))     # 자리가 날 때까지 잠깐 기다립니다
        self.fx.append(p)
        return p

    def speak(self, level, s):
        """말풍선은 층마다 하나."""
        for e in self.fx:
            if getattr(e, "level", None) == level and e is not s:
                e.alive = False
        s.level = level
        self.fx.append(s)
        return s

    # ── 좌표 도우미 ───────────────────────────────────────────────────────
    def floor_at(self, x, y):
        """화면 좌표 → 층 key (빌딩 밖이면 None)."""
        if not (self.bx <= x <= self.bx + BW):
            return None
        for lv, key, *_ in FLOORS:
            fy = self.floor_y(lv)
            if fy - FH < y <= fy:
                return key
        if self.top - 34 <= y <= self.top:
            return "roof"
        return None

    def landing(self, level):
        """그 층의 엘리베이터 앞 (x, 바닥 y)."""
        return self.shaft_x, self.floor_y(level)



ACID = (208, 249, 145)
BLACK = (6, 9, 10)


def brand_filter(layer):
    """색 그림 → 흑백 와이어프레임. 색이 바뀌는 경계는 흰 선, 면은 검정에 가까운 회색 (원래 밝기를 조금 남김)."""
    import numpy as np
    rgb = pygame.surfarray.pixels3d(layer)
    al = pygame.surfarray.pixels_alpha(layer)
    lum = rgb[..., 0] * 0.30 + rgb[..., 1] * 0.59 + rgb[..., 2] * 0.11
    lum = np.where(al > 0, lum, -60.0)                         # 빈 곳과의 경계도 선이 되게
    e = np.zeros_like(lum)
    dx = np.abs(np.diff(lum, axis=0)); dy = np.abs(np.diff(lum, axis=1))
    e[1:, :] = np.maximum(e[1:, :], dx); e[:, 1:] = np.maximum(e[:, 1:], dy)
    edge = np.clip((e - 18.0) * 6.0, 0, 225)
    fill = 10.0 + np.clip(lum, 0, 255) * 0.10
    v = np.maximum(fill, edge)
    rgb[..., 0] = v; rgb[..., 1] = v; rgb[..., 2] = v
    del rgb, al


def _dim(img, k):
    key = ("dim", id(img), round(k, 1))
    hit = _DIM.get(key)
    if hit is None:
        hit = img.copy()
        hit.fill((int(255 * (1 - k * .6)),) * 3 + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        _DIM[key] = hit
    return hit


_DIM = {}
