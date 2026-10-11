# -*- coding: utf-8 -*-
"""화면 · 타이틀 · 상단 HUD · 오른쪽 패널 · 창(신문 · 회사 키우기 · 두뇌 훈련소 · 랭킹 · 업적 · JEV · 도움말)."""
import json
import math

import pygame

import connect_tycoon as ct
from ..career import ACHIEVEMENTS, LEVELS, UPGRADES
from ..policies import OWNER_OPTIONS
from . import art
from .pixel import ACID, GOLD, INK, MUTED, RED, UI_BG, UI_BG2, UI_LINE, WHITE, cover, man, won

OWNER_LABEL = {"staffing": "인력", "order": "재고", "ad": "광고", "refund": "환불", "security": "보안"}
OWNER_SHORT = {"staffing": ["균형", "상담", "결제", "확인"], "order": ["중단", "적게", "보통", "넉넉", "가득"], "ad": ["중단", "유지", "증액"],
               "refund": ["관대", "보통", "엄격"], "security": ["낮음", "보통", "높음"]}
OWNER_TIPS = {
    "staffing": ["균형 · 긴급 4 · 결제 4 · 사람 확인 4", "고객센터 집중 · 긴급 8 · 결제 2 · 사람 확인 3", "결제팀 집중 · 긴급 2 · 결제 8 · 사람 확인 3", "사람 확인 집중 · 긴급 2 · 결제 2 · 사람 확인 8"],
    "order": ["발주를 멈춥니다", "재고 목표 120개 (창고+도착 예정)", "재고 목표 180개 · 규칙 사장과 같음", "재고 목표 240개", "재고 목표 300개 · 품절은 없지만 창고 비용"],
    "ad": ["광고비 0 · 손님이 줄어듭니다", "하루 8만원", "하루 20만원 · 손님 ↑ · 사기 결제 시도 ↑"],
    "refund": ["웬만하면 환불 · 만족 ↑ · 악용 ↑", "8만원 이상이거나 의심되면 사람 확인 (규칙 사장과 같음)", "의심되면 거절 · 악용 ↓ · 불만 ↑"],
    "security": ["거의 다 통과 · 사기 ↑", "의심되면 사람 확인 (규칙 사장과 같음)", "조금만 의심돼도 차단 · 정상 손님도 막힘"],
}
DEPT_ICON = {"staffing": "people", "inventory": "box", "marketing": "mega", "cs": "phone", "refund": "card", "security": "shield"}
HEAD = 20


def draw(app, surf, dt):
    ui = app.ui
    if app.screen == "title":
        ui.enabled = True
        title(app, surf, dt)
        return
    if app.screen == "play":                     # 학습 화면 하나
        ui.enabled = True
        app.studio.draw(surf, dt)
        app.toasts.draw(surf, 6, HEAD + 4, dt, app.world_rect.width - 12)
        return
    ui.enabled = app.modal is None
    if app.inspect:
        dept_card(app, surf)
    else:
        app._card_rect = pygame.Rect(0, 0, 0, 0)
    hud(app, surf)
    if app.panel:
        panel(app, surf)
    app.toasts.draw(surf, 6, HEAD + 4, dt, app.world_rect.width - 12)
    D = app.director
    if D.month and D.t < 2.2 and app.modal is None:
        a = min(1.0, D.t / 0.25) * min(1.0, (2.2 - D.t) / 0.4)
        no = (app.month or {}).get("no", app.career.month)
        txt = app.fonts.text(f"{no}월 {D.d + 1}일째 · {ct.company.WEEK[D.d % 5]}요일", WHITE, bold=True, k=2, outline_color=INK)
        sub = app.fonts.text("월말 결산까지 " + (f"{19 - D.d}일" if D.d < 19 else "오늘!"), GOLD if D.d >= 17 else (200, 214, 196), bold=True, outline_color=INK)
        by = HEAD + 26 - int((1 - min(1.0, D.t / 0.25)) * 10)
        for img, yy in ((txt, by), (sub, by + txt.get_height())):
            img.set_alpha(int(255 * a))
            surf.blit(img, (app.world_rect.centerx - img.get_width() // 2, yy))
            img.set_alpha(255)
    if app.paused and app.modal is None:
        t = app.fonts.text("일시정지 · 스페이스로 계속", WHITE, bold=True, outline_color=INK)
        surf.blit(t, (app.world_rect.centerx - t.get_width() // 2, 28))
    if app.modal:
        ui.enabled = True
        cover(surf, (0, 0, app.vw, app.vh))
        ov = pygame.Surface((app.vw, app.vh), pygame.SRCALPHA); ov.fill((0, 0, 0, 120)); surf.blit(ov, (0, 0))
        MODALS[app.modal](app, surf)


def win(app, surf, w, h, title, icon=None, close=True):
    vw, vh = app.vw, app.vh
    w, h = min(w, vw - 12), min(h, vh - 12)
    r = pygame.Rect((vw - w) // 2, (vh - h) // 2, w, h)
    pygame.draw.rect(surf, INK, r.move(2, 2))
    app.ui.frame(surf, r, title, icon)
    if close and app.ui.button(surf, (r.right - 17, r.top + 3, 13, 12), "", "cross", kind="ghost"):
        app.modal = None; app.sfx("click")
    return r


# ── 타이틀 ────────────────────────────────────────────────────────────────
_NET = {}


def _neural(surf, w, h, t):
    """타이틀 왼쪽의 뉴런 네트워크 · 점이 숨 쉬고, 연결선을 따라 신호가 흐릅니다."""
    key = (w, h)
    if key not in _NET:
        import random
        rnd = random.Random(7)
        pts = [(rnd.uniform(8, w - 8), rnd.uniform(8, h - 8), rnd.uniform(0, 6.28)) for _ in range(34)]
        edges = [(i, j, rnd.random()) for i in range(len(pts)) for j in range(i + 1, len(pts))
                 if math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) < 70]
        _NET.clear(); _NET[key] = (pts, edges)
    pts, edges = _NET[key]
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    for i, j, o in edges:
        (x1, y1, _), (x2, y2, _) = pts[i], pts[j]
        fade = min(1.0, max(0.15, (min(y1, y2) / h - 0.45) * 3))      # 글자가 있는 위쪽은 옅게, 아래쪽은 또렷하게
        pygame.draw.line(layer, (208, 249, 145, int(34 * fade)), (x1, y1), (x2, y2))
        k = (t * 0.35 + o) % 1.0
        pygame.draw.circle(layer, (208, 249, 145, int(170 * fade)), (int(x1 + (x2 - x1) * k), int(y1 + (y2 - y1) * k)), 1)
    for x, y, ph in pts:
        g = 0.5 + 0.5 * math.sin(t * 1.4 + ph)
        fade = min(1.0, max(0.15, (y / h - 0.45) * 3))
        pygame.draw.circle(layer, (208, 249, 145, int((40 + 80 * g) * fade)), (int(x), int(y)), 2)
    surf.blit(layer, (0, 0))


def title(app, surf, dt):
    """타이틀 · 이 게임은 '기업 의사결정 모델을 강화학습으로 만드는 도구'로 시작합니다."""
    ui, f = app.ui, app.fonts
    vw, vh = app.vw, app.vh
    t = app.t_real
    colw = min(250, app.world.bx - 30)
    # 왼쪽: 검정 패널 (빌딩 쪽으로 부드럽게 사라짐)
    shade_w = colw + 46
    ov = pygame.Surface((shade_w, vh), pygame.SRCALPHA)
    for i in range(shade_w):
        a = 240 if i < colw + 12 else int(240 * max(0.0, 1 - (i - colw - 12) / 34))
        pygame.draw.line(ov, (6, 9, 10, a), (i, 0), (i, vh))
    surf.blit(ov, (0, 0))
    cover(surf, (0, 0, colw + 16, vh))
    _neural(surf, colw + 16, vh, t)
    x0 = 18
    y = max(14, vh // 2 - 180)
    ui.label(surf, "RL AI COMPANY DECISION MAKING MODEL", x0, y, ACID, bold=True)
    y += 16
    big = f.text("CONNECT", WHITE, bold=True, k=3)
    surf.blit(big, (x0 - 1, y)); y += big.get_height() - 4
    big2 = f.text("TYCOON", ACID, bold=True, k=3)
    surf.blit(big2, (x0 - 1, y))
    # 형광 두뇌 (모델) · 숨 쉬듯 빛남
    b = art.brain_ceo("think" if int(t * 0.7) % 3 == 0 else "idle", brand=True)
    b = pygame.transform.scale(b, (b.get_width() * 2, b.get_height() * 2))
    bx_ = x0 + big2.get_width() + 8
    glow = 0.5 + 0.5 * math.sin(t * 2.2)
    pygame.draw.circle(surf, (int(30 + 40 * glow), int(44 + 60 * glow), int(20 + 22 * glow)), (bx_ + b.get_width() // 2, y + 14), 21, 1)
    surf.blit(b, (bx_, y - 4 + int(math.sin(t * 2) * 2)))
    y += big2.get_height() + 6
    y = ui.para(surf, "강화학습으로 회사 의사결정 모델을 만듭니다", x0, y, colw - 4, (214, 220, 212), gap=14) + 8
    c = app.saved
    bw = colw - 4
    if c is not None and (c.month > 1 or (c.studio or {}).get("versions")):
        if ui.button(surf, (x0, y, bw, 22), "이어하기", "play", kind="acid"):
            app.career = c; app.studio.restore(); app.start_month(restart=c.opened == c.month); app.sfx("level")
        y += 27
        if ui.button(surf, (x0, y, bw, 18), "새로 시작", "star", kind="ghost"):
            app.modal_data["confirm_new"] = True
        y += 23
    else:
        app.new_name = ui.text_field(surf, (x0, y, bw, 16), app.new_name, "Connect AI Company", key="company")[:24]
        y += 22
        if ui.button(surf, (x0, y, bw, 22), "학습 시작", "play", kind="acid"):
            new_game(app)
        y += 27
    if app.modal_data.get("confirm_new"):
        ui.label(surf, "지금 회사가 지워집니다. 정말?", x0, y, (255, 200, 190), bold=True)
        if ui.button(surf, (x0, y + 13, bw // 2 - 2, 16), "처음부터", kind="danger"):
            app.modal_data["confirm_new"] = False; new_game(app)
        if ui.button(surf, (x0 + bw // 2 + 2, y + 13, bw // 2 - 2, 16), "취소"):
            app.modal_data["confirm_new"] = False
        y += 34
    if ui.button(surf, (x0, y, bw, 18), "끝내기", "cross", kind="ghost"):
        app.quit = True
    ui.label(surf, "CONNECT AI LAB × AI CITY BUILDERS", x0, vh - 28, (150, 156, 152), bold=True)
    ui.label(surf, "오픈소스 · Apache-2.0", x0, vh - 14, (90, 98, 94))
    if app.modal == "help":
        cover(surf, (0, 0, vw, vh))
        ov2 = pygame.Surface((vw, vh), pygame.SRCALPHA); ov2.fill((0, 0, 0, 140)); surf.blit(ov2, (0, 0))
        help_view(app, surf)


def new_game(app):
    from ..career import Career
    keep = app.career.settings
    app.career = Career()
    app.career.settings = keep
    app.career.company = (app.new_name or "").strip() or "Connect AI Company"
    app.ui.focus = None; pygame.key.stop_text_input()
    app.saved = None
    app.studio.begin()
    app.start_month()
    app.sfx("level")


# ── 상단 HUD ──────────────────────────────────────────────────────────────
def hud(app, surf):
    ui, _f, c, D = app.ui, app.fonts, app.career, app.director
    vw = app.vw
    cover(surf, (0, 0, vw, HEAD + 1))
    bar = pygame.Surface((vw, HEAD), pygame.SRCALPHA); bar.fill((8, 14, 11, 225)); surf.blit(bar, (0, 0))
    pygame.draw.line(surf, UI_LINE, (0, HEAD), (vw, HEAD))
    x = 4

    def item(icon, text, color=WHITE, bold=True, tip=None, minw=0):
        nonlocal x
        surf.blit(art.icon(icon), (x, 5))
        w = ui.label(surf, text, x + 12, 3, color, bold=bold)
        r = pygame.Rect(x, 0, max(minw, w + 14), HEAD)
        if tip and ui.hover(r): ui.tip = tip
        x += max(minw, w + 14) + 6
        return r

    roomy = vw >= 700
    if roomy:
        item("brain", c.company, ACID)
    shown = getattr(app, "_cash_shown", D.cash)
    shown += (D.cash - shown) * 0.2 if abs(D.cash - shown) > 0.05 else (D.cash - shown)
    app._cash_shown = shown
    item("coin", won(shown), ACID if shown >= 0 else RED, tip="회사 돈. 업그레이드를 사면 줄고, 하루가 끝날 때마다 이익만큼 늘어납니다", minw=86)
    d = D.d
    no = (app.month or {}).get("no", c.month)
    season = art.SEASONS[((no - 1) // 3) % 4]
    item("cal", f"{no}월 · {d // 5 + 1}주 {ct.company.WEEK[d % 5]}" if not roomy else f"{no}월 {season} · {d // 5 + 1}주 {ct.company.WEEK[d % 5]}", WHITE,
         tip=f"{season} · 한 달 = 영업일 20일 · 오늘은 {d + 1}일째 · 계절은 그림만 바꿉니다")
    p = app.world.p
    surf.blit(art.icon("sun" if p < .62 else "dusk" if p < .84 else "moon"), (x, 5)); x += 14
    lv, name, nxt = c.level
    r = item("star", f"Lv{lv + 1} {name}" if roomy else f"Lv{lv + 1}", GOLD, tip=f"Lv{lv + 1} {name} · 누적 이익 {man(c.earned)}원" + (f" · 다음 단계까지 {man(nxt - c.earned)}원" if nxt else " · 최고 단계"))
    if nxt:
        prev = LEVELS[lv][0]
        ui.bar(surf, (r.x + 12, 15, r.width - 14, 2), (c.earned - prev) / (nxt - prev), GOLD)
    sat = D.sat
    item("smile" if sat > .8 else "meh" if sat > .62 else "sad", f"{sat * 100:.0f}%", WHITE, tip="고객 만족 · 내일 손님 수를 바꿉니다")
    item("box", f"{int(D.stock)}", WHITE, tip=f"창고 재고 (한도 {int(app.world.warehouse)})")
    if D.month_inc:
        item("alarm", f"{D.month_inc}", RED, tip="이번 달 위험 사고 (놓친 위험 문의 + 통과된 사기 결제)")
    # 오른쪽: 속도 · 소리
    bx = vw - 4
    controls = [("music" if app.audio.music_on else "mute", "music", "배경 음악 (M)"), ("sound" if app.audio.sfx_on else "mute", "sfx", "효과음")]
    for ic, act, tip in controls:
        bx -= 16
        if ui.button(surf, (bx, 3, 15, 14), "", ic, kind="ghost", tip=tip):
            app.toggle_music() if act == "music" else app.toggle_sfx()
    bx -= 6
    speeds = [("skip", "end", "월말까지 건너뛰기"), ("fff", 8, "8배속 (4)"), ("ff", 4, "4배속 (3)"), ("play", 2, "2배속 (2)"), ("play", 1, "보통 속도 (1)"), ("pause", 0, "일시정지 (스페이스)")]
    for ic, sp, tip in speeds:
        bx -= 16
        active = (sp == 0 and app.paused) or (sp == app.speed and not app.paused)
        lab = "" if sp != 1 else ""
        if ui.button(surf, (bx, 3, 15, 14), lab, ic, kind="ghost", tip=tip, active=active):
            if sp == "end":
                app.director.skip_month()
            elif sp == 0:
                app.paused = not app.paused
            else:
                app.speed, app.paused = sp, False
            app.sfx("click")
    if app.speed == 1 and not app.paused:
        pass


# ── 오른쪽 패널 ───────────────────────────────────────────────────────────
def panel(app, surf):
    ui, _f, c = app.ui, app.fonts, app.career
    x0 = app.vw - 216
    W = 216
    pygame.draw.rect(surf, UI_BG, (x0, HEAD + 1, W, app.vh - HEAD - 1))
    pygame.draw.line(surf, UI_LINE, (x0, HEAD + 1), (x0, app.vh))
    x, y = x0 + 4, HEAD + 4
    w = W - 8
    # 사장 카드
    ui.frame(surf, (x, y, w, 36))
    if c.mode == "ai":
        e = app.entry(c.ai)
        surf.blit(art.brain_ceo(app.world.ceo_mood if app.world.ceo_mood != "blink" else "idle", e["tie"]), (x + 4, y + 9))
        ui.label(surf, "이번 달 사장 · AI", x + 26, y + 3, MUTED)
        ui.label(surf, e["name"], x + 26, y + 17, ACID, bold=True)
    else:
        surf.blit(art.player_face(), (x + 7, y + 11))
        ui.label(surf, "이번 달 사장 · 사람", x + 26, y + 3, MUTED)
        ui.label(surf, "내가 직접 경영", x + 26, y + 17, ACID, bold=True)
    if ui.button(surf, (x + w - 48, y + 10, 44, 16), "바꾸기", tip="사장을 바꾸면 이번 달을 처음부터 다시 합니다"):
        app.modal = "ceo"; app.sfx("click")
    y += 40
    bottom_tools = app.vh - 44
    chart_h = 46
    body_h = bottom_tools - chart_h - 6 - y
    if c.mode == "owner":
        owner_box(app, surf, x, y, w, body_h)
    else:
        ai_box(app, surf, x, y, w, body_h)
    y = bottom_tools - chart_h - 4
    month_chart(app, surf, x, y, w, chart_h)
    toolbar(app, surf, x, bottom_tools, w)


def owner_box(app, surf, x, y, w, h):
    ui = app.ui
    ui.frame(surf, (x, y, w, h), "사장 지시 · 내일 아침부터", "boss")
    yy = y + 20
    for key in ("staffing", "order", "ad", "refund", "security"):
        ui.label(surf, OWNER_LABEL[key], x + 4, yy + 1, (190, 204, 188), bold=True)
        opts = OWNER_OPTIONS[key]
        v = ui.seg(surf, (x + 30, yy, w - 34, 14), opts, app.career.owner[key], OWNER_SHORT[key], OWNER_TIPS[key])
        if v != app.career.owner[key]:
            app.set_owner(key, v)
        yy += 18
    yy += 2
    pygame.draw.line(surf, UI_LINE, (x + 4, yy), (x + w - 5, yy))
    yy += 3
    ui.label(surf, "오늘의 판단", x + 4, yy, MUTED, bold=True)
    if ui.button(surf, (x + w - 64, yy - 1, 60, 13), "JEV 보기", "json", kind="ghost", tip="판단 하나하나가 JEV 요청과 응답입니다 (Tab)"):
        app.modal = "jev"
    yy += 14
    feed_list(app, surf, x + 2, yy, w - 4, y + h - yy - 2)


def ai_box(app, surf, x, y, w, h):
    ui, _f = app.ui, app.fonts
    ui.frame(surf, (x, y, w, h), "AI 사장의 판단 · JEV", "brain")
    yy = y + 20
    feed = [it for it in app.feed if it["day"] == app.director.d or True]
    last = app.selected or (feed[-1] if feed else None)
    if last is None:
        ui.label(surf, "아침 판단을 기다리는 중…", x + 6, yy, MUTED)
        return
    xrec = last["x"]
    req, resp = app.jev_pair(xrec)
    dept = xrec["dept"]
    surf.blit(art.icon(DEPT_ICON[dept]), (x + 4, yy + 1))
    ui.label(surf, ct.DEPTS[dept]["name"], x + 16, yy, ACID, bold=True)
    ui.label(surf, f"{xrec['day'] + 1}일째", x + w - 6, yy, MUTED, right=True)
    yy += 13
    yy = ui.para(surf, situation(xrec), x + 5, yy, w - 10, (214, 222, 210), max_lines=2) + 2
    ans = resp["answers"]["decision"]
    crit = req["questions"]["decision"]["criteria"]
    keys, acts = ct.DEPTS[dept]["keys"], ct.DEPTS[dept]["actions"]
    for k in crit:
        p = ans.get("probabilities", {}).get(k, 0.0)
        on = k == ans["choice"]
        name = acts[keys.index(k)]
        ui.label(surf, name, x + 5, yy, ACID if on else (180, 192, 178), bold=on)
        ui.bar(surf, (x + 74, yy + 4, w - 112, 5), p, ACID if on else (90, 110, 96))
        ui.label(surf, f"{p:.2f}", x + w - 6, yy, ACID if on else MUTED, right=True)
        yy += 11
    reason = ans.get("reason", "")
    ui.label(surf, f'"choice": "{ans["choice"]}" · 확신 {ans.get("confidence", 1):.2f}', x + 5, yy + 1, WHITE, mono=True)
    yy += 12
    if reason:
        who = resp.get("model", "")
        if app.career.ai == "team" and who:
            reason = f"{reason} · {who.split('/')[-1]}"
        ui.label(surf, reason, x + 5, yy, MUTED); yy += 12
    if ui.button(surf, (x + w - 66, y + 3, 62, 13), "JEV 원문", "json", kind="ghost", tip="이 판단의 JEV 요청과 응답 전체 (Tab)"):
        app.modal = "jev"
    pygame.draw.line(surf, UI_LINE, (x + 4, yy + 1), (x + w - 5, yy + 1))
    feed_list(app, surf, x + 2, yy + 4, w - 4, y + h - yy - 6)


def feed_list(app, surf, x, y, w, h):
    ui, f = app.ui, app.fonts
    if not app.feed or h < 11:
        return
    # 가장 최근 판단은 크게 · 문장 끝까지
    top = app.feed[-1]["x"]
    head = f"{top['action']} · " + situation(top)
    lines = f.wrap(head, w - 16)[:3]
    box = pygame.Rect(x, y, w, len(lines) * 12 + 3)
    pygame.draw.rect(surf, (26, 40, 32), box)
    surf.blit(art.icon(DEPT_ICON[top["dept"]]), (x + 2, y + 2))
    for k, s_ in enumerate(lines):
        ui.label(surf, s_, x + 14, y + 1 + k * 12, ACID if k == 0 else WHITE, bold=k == 0)
    y += box.height + 2
    h -= box.height + 2
    n = max(0, h // 11)
    items = app.feed[-1 - n:-1] if n else []
    for i, it in enumerate(reversed(items)):
        xr = it["x"]
        r = pygame.Rect(x, y + i * 11, w, 11)
        if ui.hover(r):
            ui.tip = f"{xr['action']} · {situation(xr)} · 클릭하면 JEV"
        sel = app.selected is it
        if ui.hover(r):
            pygame.draw.rect(surf, (30, 46, 38), r)
            if ui.clicked(r):
                app.selected = None if sel else it
        if sel: pygame.draw.rect(surf, (40, 64, 46), r)
        surf.blit(art.icon(DEPT_ICON[xr["dept"]]), (x + 1, r.y + 1))
        good = xr["reward"] >= 0
        col = (200, 210, 196) if good else (255, 150, 130)
        txt = f"{xr['action']}"
        ui.label(surf, txt, x + 13, r.y - 1, ACID if xr.get("ruled") is False else (190, 180, 120), bold=True)
        tail = situation(xr, short=True)
        tw = app.fonts.width(txt, bold=True)
        avail = w - 18 - tw
        if avail > 20:
            while tail and app.fonts.width(tail) > avail: tail = tail[:-2] + "…" if len(tail) > 2 else ""
            ui.label(surf, tail, x + 17 + tw, r.y - 1, col)


def situation(x, short=False):
    ev, d = x.get("ev", {}), x["dept"]
    if d == "staffing":
        return "어제 넘친 일 · 문의 {} · 사람 확인 {}".format(ev.get("yesterday_cs_overflow", 0), ev.get("yesterday_human_overflow", 0)) if not short else "아침 인력 배치"
    if d == "inventory":
        c = ev["ctx"]
        return f"재고 {int(c['stock'])} · 도착 예정 {int(c['incoming'])} · 최근 판매 {ev['recent_sales']:.0f}" if not short else f"재고 {int(c['stock'])}"
    if d == "marketing":
        return f"광고 효과 {ev['ctx']['ad']:.2f} · 어제 이익 {ev['profit_yesterday']:.0f}만원" if not short else "오늘 광고"
    if d == "cs":
        return ev["message"]
    if d == "refund":
        s = f"{int(ev['amount'])}만원 · {ev['reason']} · {ev['tier']}"
        return s + f" · 사기 점수 {ev['fraud_score']:.2f}" if not short else s
    if d == "security":
        s = f"결제 {int(ev['amount'])}만원 · 사기 점수 {ev['fraud_score']:.2f}"
        if not short:
            s += " · 새 기기" if ev["new_device"] else ""
            s += " · 해외" if ev["overseas"] else ""
        return s
    return ""


def month_chart(app, surf, x, y, w, h):
    ui = app.ui
    D = app.director
    days = D.days if D.month else []
    done = days[:D.d + (1 if D.t >= 22.0 else 0)]
    total = sum(d["profit"] for d in done)
    ui.frame(surf, (x, y, w, h), f"이번 달 하루 이익 · 합계 {man(total)}원", "chart")
    if not done: return
    hi = max(1.0, max(abs(d["profit"]) for d in done))
    bw = (w - 10) / 20
    base = y + h - 6
    for i, d in enumerate(done):
        v = d["profit"] / hi
        bh = max(1, int(abs(v) * (h - 24)))
        rr = pygame.Rect(x + 5 + int(i * bw), base - bh if v >= 0 else base - 1, max(1, int(bw) - 1), bh)
        pygame.draw.rect(surf, ACID if v >= 0 else RED, rr)
        if ui.hover(rr.inflate(0, 20)):
            ui.tip = f"{i + 1}일 · 이익 {won(d['profit'], True)} · 판매 {int(d['sales'])}/{int(d['demand'])} · 만족 {d['sat']:.0%}"


def toolbar(app, surf, x, y, w):
    ui = app.ui
    tools = [("회사 키우기", "hammer", "shop", "번 돈으로 업그레이드 · 다음 달부터 회사가 커집니다"),
             ("두뇌 훈련소", "cap", "lab", "AI 사장을 강화학습으로 키웁니다"),
             ("두뇌 랭킹", "crown", "rank", "누구의 두뇌가 돈을 가장 많이 버나"),
             ("업적", "trophy", "trophy", "모은 트로피"),
             ("JEV 기록", "json", "jev", "판단의 JEV 원문 · 학습 데이터로 저장"),
             ("도움말", "help", "help", "게임 방법과 강화학습 이야기")]
    bw = (w - 4) // 3
    for i, (label, icon, modal, tip) in enumerate(tools):
        r = (x + (i % 3) * (bw + 2), y + (i // 3) * 20, bw, 18)
        busy = modal == "lab" and app.trainer.running
        if ui.button(surf, r, label, icon, tip=tip, kind="gold" if busy else "normal"):
            app.modal = modal; app.sfx("click")


# ── 층 카드 (층을 누르면) ─────────────────────────────────────────────────
CARD = {
    "warehouse": ("물류창고", "box", "inventory", "발주한 물건이 이틀 뒤 트럭으로 들어옵니다. 창고 한도를 넘으면 버리고, 남은 재고는 매일 보관 비용이 듭니다."),
    "shop": ("매장", "coin", None, "저녁에 손님이 와서 물건을 삽니다. 손님 수는 요일 · 광고 · 고객 만족으로 정해지고, 재고가 없으면 품절입니다."),
    "cs": ("고객센터", "phone", "cs", "전화 문의를 어디로 보낼지 정합니다. 위험한 문의는 사람이 봐야 하고, 급한 문의는 바로 처리해야 합니다."),
    "refund": ("결제 · 환불", "card", "refund", "환불 요청을 처리합니다. 악용인지 아닌지는 사기 점수로만 짐작할 수 있습니다."),
    "review": ("사람 확인실", "search", None, "사람이 직접 확인하는 곳 (전전두엽의 '멈춤'). 확실하지만 자리가 적고 건당 0.8만원이 듭니다. 고객센터 · 환불 · 보안이 함께 씁니다."),
    "security": ("보안실", "shield", "security", "온라인 결제를 통과시킬지 정합니다. 광고를 늘리면 사기 시도도 늘어납니다."),
    "marketing": ("마케팅", "mega", "marketing", "광고는 며칠 동안 손님을 늘립니다. 옥상 광고판이 오늘의 광고입니다."),
    "ceo": ("사장실", "brain", "staffing", "아침마다 인력 배치를 정하고, 회사의 모든 판단이 여기서 JEV로 내려갑니다."),
}


def dept_stats(app, key):
    """이번 달 그 부서가 내린 판단 (오늘은 이미 화면에 나온 것까지만)."""
    D = app.director
    if not D.month: return {}
    dept = CARD[key][2]
    shown = {id(it["x"]) for it in app.feed if it["day"] == D.d}
    done = lambda x: x["day"] < D.d or id(x) in shown
    if key == "review":
        rows = [x for x in D.month["log"] if x.get("action") == "사람 확인" and done(x)]
    elif dept:
        rows = [x for x in D.month["log"] if x["dept"] == dept and done(x)]
    else:
        rows = []
    today = [x for x in rows if x["day"] == D.d]
    acts = {}
    for x in rows: acts[x["action"]] = acts.get(x["action"], 0) + 1
    out = {"today": len(today), "month": len(rows), "money_month": sum(x.get("money", 0.0) for x in rows), "acts": acts,
           "over_month": sum(1 for x in rows if x.get("overflow")), "inc_month": sum(x.get("incidents", 0) for x in rows)}
    if key == "shop":
        days = D.days[:D.d]
        out.update(sales=sum(d["sales"] for d in days), demand=sum(d["demand"] for d in days), unmet=sum(d["unmet"] for d in days))
    return out


def dept_card(app, surf):
    ui, w, f = app.ui, app.world, app.fonts
    from .world import BW, FH, LEVEL
    key = app.inspect
    name, icon, dept, desc = CARD[key]
    cw = 172
    st = dept_stats(app, key)
    lines = [(s_, (210, 220, 206)) for s_ in f.wrap(desc, cw - 10)[:3]]
    if dept:
        lines += [(s_, ACID) for s_ in f.wrap("JEV 선택지 · " + " · ".join(ct.DEPTS[dept]["keys"]), cw - 10)[:2]]
    if st.get("acts"):
        top = sorted(st["acts"].items(), key=lambda kv: -kv[1])[:3]
        lines += [(s_, WHITE) for s_ in f.wrap("이번 달 · " + " · ".join(f"{a} {n}" for a, n in top), cw - 10)[:2]]
    if key == "shop" and st:
        lines.append((f"이번 달 판매 {int(st['sales'])} / 손님 {int(st['demand'])} · 품절 {int(st['unmet'])}", WHITE))
    elif st:
        bits = [f"오늘 {st['today']}건"]
        if st["over_month"]: bits.append(f"자리 넘침 {st['over_month']}")
        if st["inc_month"]: bits.append(f"사고 {st['inc_month']}")
        if abs(st["money_month"]) >= 1: bits.append(f"돈 {man(st['money_month'], True)}")
        lines += [(s_, MUTED) for s_ in f.wrap(" · ".join(bits), cw - 10)[:2]]
    if key in ("cs", "refund", "review") and key in w.caps:
        lines.append((f"오늘 자리 {w.caps[key]}개 · 쓴 자리 {w.used.get(key, 0)}", GOLD))
    ch = 22 + 12 * len(lines)
    fy = w.floor_y(LEVEL[key])
    right = w.bx + BW + 6
    x = right if right + cw <= app.world_rect.right - 2 else 2
    y = fy + 6 if fy - FH < app.vh / 2 else fy - FH - ch - 6         # 누른 층은 가리지 않게
    y = max(HEAD + 2, min(app.vh - ch - 2, y))
    r = pygame.Rect(x, y, cw, ch)
    app._card_rect = r
    pygame.draw.rect(surf, INK, r.move(2, 2))
    ui.frame(surf, r, name, icon)
    pygame.draw.rect(surf, ACID, (w.bx, fy - FH + 1, BW, FH - 1), 1)
    if ui.button(surf, (r.right - 15, r.top + 3, 12, 11), "", "cross", kind="ghost"):
        app.inspect = None; return
    for i, (s_, col) in enumerate(lines):
        surf.blit(f.text(s_, col), (r.x + 5, r.y + 20 + i * 12))


# ── 창: 월말 신문 ─────────────────────────────────────────────────────────
def news(app, surf):
    ui, _f, N, c = app.ui, app.fonts, app.news, app.career
    r = win(app, surf, 470, 344, f"CONNECT 일보 · {N['month']}월 결산 호외", "news", close=False)
    x, y = r.x + 8, r.y + 22
    me = N["rows"][0][1] == "me"
    head = (f"{N['ceo']}, 이번 달 1위!" if me else f"{N['rows'][0][0]}이(가) 더 벌었습니다")
    ui.label(surf, head, x, y, ACID if me else GOLD, bold=True, k=2)
    y += 26
    ui.label(surf, f"이번 달 이익 {won(N['profit'], True)} · 회사 돈 {won(c.cash)} · 누적 이익 {man(c.earned)}원", x, y, WHITE)
    y += 14
    W = r.width - 16
    cols = [("한 달 이익", W - 236), ("만족", W - 160), ("사고", W - 122), ("넘침", W - 82), ("품절", W - 40)]
    ui.label(surf, "경영자", x, y, MUTED, bold=True)
    for name, cx in cols:
        ui.label(surf, name, x + cx, y, MUTED, bold=True)
    y += 13
    for i, (name, kind, s) in enumerate(N["rows"]):
        rr = pygame.Rect(x - 3, y - 1, r.width - 10, 13)
        if kind == "me": pygame.draw.rect(surf, (40, 64, 46), rr)
        label = f"{i + 1}. {name}" + (" ← 이번 달" if kind == "me" else "")
        while app.fonts.width(label, bold=True) > W - 244 and len(label) > 6: label = label[:-2] + "…"
        ui.label(surf, label, x, y, ACID if kind == "me" else WHITE, bold=kind == "me")
        ui.label(surf, man(s["profit"], True) + "원", x + cols[0][1], y, ACID if s["profit"] >= 0 else RED, bold=True)
        ui.label(surf, f"{s['sat'] * 100:.0f}%", x + cols[1][1], y, WHITE)
        ui.label(surf, f"{s['incidents']}건", x + cols[2][1], y, RED if s["incidents"] else WHITE)
        ui.label(surf, f"{s['human_over']}건", x + cols[3][1], y, WHITE)
        ui.label(surf, f"{s['stockout_days']}일", x + cols[4][1], y, WHITE)
        y += 14
    y += 2
    ui.label(surf, "같은 달 · 같은 손님 · 같은 회사로 비교했습니다 (엔진이 결정적이라 가능합니다).", x, y, MUTED)
    y += 14
    race(app, surf, pygame.Rect(x, y, r.width - 16, 52), N["rows"])
    y += 58
    if N["levelup"]:
        lv = N["level"]
        ui.label(surf, f"회사 등급이 올랐습니다 · Lv{lv[0] + 1} {lv[1]}", x, y, GOLD, bold=True); y += 14
    if N["unlocked"]:
        xx = x
        ui.label(surf, "새 업적", x, y, GOLD, bold=True); xx += 44
        for k in N["unlocked"]:
            a = next(a for a in ACHIEVEMENTS if a[0] == k)
            surf.blit(art.icon(a[3]), (xx, y + 1)); xx += 11
            xx += ui.label(surf, a[1], xx, y, WHITE) + 8
        y += 14
    tip = advice(N)
    ui.para(surf, tip, x, y + 2, r.width - 16, (220, 210, 170))
    by = r.bottom - 24
    if ui.button(surf, (r.x + 8, by, 110, 18), "회사 키우기", "hammer"):
        app.modal = "shop"; app.modal_data["after"] = "news"
    if ui.button(surf, (r.x + 122, by, 110, 18), "두뇌 훈련소", "cap"):
        app.modal = "lab"; app.modal_data["after"] = "news"
    nxt = "AI 사장" if c.mode == "ai" else "직접 경영"
    if ui.button(surf, (r.right - 200, by, 192, 18), f"{c.month}월 시작 · {nxt}", "play", kind="acid"):
        app.start_month(); app.sfx("click")
    if ui.button(surf, (r.right - 200, by - 20, 192, 16), "다음 달 사장 바꾸기", "boss", kind="ghost"):
        app.modal = "ceo"; app.modal_data["ceo_next"] = True


def race(app, surf, box, rows):
    """하루하루 누적 이익 · 같은 달을 누가 어떻게 벌었나."""
    pygame.draw.rect(surf, (8, 12, 10), box); pygame.draw.rect(surf, UI_LINE, box, 1)
    curves = [(name, kind, s["curve"]) for name, kind, s in rows if s.get("curve")]
    if not curves: return
    lo = min(0.0, min(min(c) for _, _, c in curves)); hi = max(1.0, max(max(c) for _, _, c in curves))
    X = lambda i: box.x + 4 + int(i / 19 * (box.width - 70))
    Y = lambda v: box.bottom - 4 - int((v - lo) / (hi - lo) * (box.height - 8))
    if lo < 0:
        pygame.draw.line(surf, (60, 40, 40), (box.x + 2, Y(0)), (box.right - 66, Y(0)))
    colors = {"me": ACID, "ai": (118, 214, 224), "owner": (246, 168, 194), "rule": GOLD}
    for _name, kind, c in reversed(curves):
        col = colors.get(kind, WHITE)
        pts = [(X(k), Y(v)) for k, v in enumerate(c)]
        pygame.draw.lines(surf, col, False, pts, 2 if kind == "me" else 1)
    for i, (name, kind, _c) in enumerate(curves):
        col = colors.get(kind, WHITE)
        label = name if app.fonts.width(name) < 60 else name[:5] + "…"
        app.ui.label(surf, label, box.right - 62, box.y + 3 + i * 12, col, bold=kind == "me")


def advice(N):
    s = N["played"]
    if s["stockout_days"] >= 5: return "조언 · 품절이 잦았습니다. 재고 목표를 '넉넉'이나 '가득'으로 올려 보세요."
    if s["human_over"] >= 30: return "조언 · 사람 확인이 자주 넘쳤습니다. 인력을 '확인' 집중으로 바꾸거나 직원을 채용해 보세요."
    if s["incidents"] >= 6: return "조언 · 사고가 많았습니다. 보안 민감도를 높이거나 사기 탐지 AI를 들여 보세요."
    if N["mode"] == "owner": return "조언 · '두뇌 훈련소'에서 AI 사장을 키워 같은 달을 맡겨 보세요. 판단 하나하나를 보상으로 배웁니다."
    return "조언 · 회사가 커지면 예전 두뇌가 덜 맞을 수 있습니다. 업그레이드 뒤에는 두뇌를 다시 훈련시키세요."


# ── 창: 회사 키우기 ───────────────────────────────────────────────────────
def shop(app, surf):
    ui, c = app.ui, app.career
    r = win(app, surf, 470, 290, "회사 키우기 · 다음 달 1일에 문을 엽니다", "hammer")
    back(app, surf, r)
    ui.label(surf, f"회사 돈 {won(app.director.cash)}", r.right - 26, r.y + 2, ACID, bold=True, right=True)
    cw, ch = (r.width - 22) // 2, 76
    for i, u in enumerate(UPGRADES):
        cx = r.x + 8 + (i % 2) * (cw + 6)
        cy = r.y + 22 + (i // 2) * (ch + 4)
        ui.frame(surf, (cx, cy, cw, ch), bg=UI_BG2)
        lv = c.upgrades.get(u["key"], 0); q = c.queued.get(u["key"], 0)
        surf.blit(art.icon(u["icon"]), (cx + 5, cy + 5))
        ui.label(surf, u["name"], cx + 17, cy + 3, WHITE, bold=True)
        for k in range(3):
            col = ACID if k < lv else GOLD if k < lv + q else (50, 66, 56)
            pygame.draw.rect(surf, col, (cx + cw - 40 + k * 12, cy + 6, 10, 5))
        if lv + q < 3:
            ui.label(surf, f"다음 · {u['levels'][lv + q]}", cx + 5, cy + 18, (214, 222, 210))
        else:
            ui.label(surf, "최고 단계", cx + 5, cy + 18, ACID)
        if lv:
            ui.label(surf, f"지금 · {u['levels'][lv - 1]}", cx + 5, cy + 31, MUTED)
        if q:
            ui.label(surf, "공사 중 · 다음 달 오픈", cx + 5, cy + 44, GOLD)
        elif u.get("retrain") and lv + q < 3:
            ui.label(surf, "AI 사장은 이어서 훈련 필요", cx + 5, cy + (44 if lv else 31), (150, 170, 150))
        ok, cost = c.can_buy(u["key"])
        if cost is not None:
            if ui.button(surf, (cx + cw - 96, cy + ch - 21, 90, 16), f"{man(cost)}원", "coin", kind="gold" if ok else "normal", enabled=ok,
                         tip=None if ok else "돈이 모자랍니다"):
                app.buy(u["key"])
    ui.para(surf, "업그레이드는 엔진의 회사 규모(config)를 바꿉니다. 회사가 바뀌면 예전에 배운 두뇌가 덜 맞을 수 있어요 → 두뇌 훈련소에서 다시 훈련!",
            r.x + 8, r.bottom - 26, r.width - 16, MUTED)


def back(app, surf, r):
    if app.modal_data.get("after") and app.ui.button(surf, (r.right - 70, r.top + 3, 50, 12), "← 신문", kind="ghost"):
        app.modal = app.modal_data.pop("after")


# ── 창: 두뇌 훈련소 ───────────────────────────────────────────────────────
def lab(app, surf):
    ui, _f, L, T = app.ui, app.fonts, app.lab, app.trainer
    r = win(app, surf, 480, 300, "두뇌 훈련소 · 지도학습 → 강화학습(PPO)", "cap")
    back(app, surf, r)
    x, y = r.x + 8, r.y + 22
    lw = 196
    ui.label(surf, "회사의 가치 · 보상의 무게", x, y, ACID, bold=True); y += 14
    for key, name in (("이익", "이익"), ("고객 만족", "고객 만족"), ("위험", "위험 회피")):
        ui.label(surf, name, x, y, WHITE)
        L["values"][key] = ui.slider(surf, (x + 56, y + 1, lw - 92, 10), L["values"][key], 0.0, 3.0, 0.5)
        ui.label(surf, f"{L['values'][key]:.1f}", x + lw - 4, y, ACID, right=True, bold=True)
        y += 15
    cur = app.entry(app.career.ai)
    ui.label(surf, "출발점", x, y + 2, ACID, bold=True)
    ui.label(surf, f"지금 AI 사장 · {cur['name']}", x + lw, y + 2, MUTED, right=True); y += 15
    L["teacher"] = ui.seg(surf, (x, y, lw, 14), ["지금 AI 사장", "규칙 사장", "내 지시"], L["teacher"], ["이어서", "규칙부터", "내 지시부터"],
                          tips=["지금 앉아 있는 AI 사장을 이 회사에서 이어서 훈련합니다 (파인튜닝 · 회사를 키운 뒤에 가장 좋습니다)",
                                "사람이 정한 규칙을 먼저 따라 배운 뒤 강화학습",
                                "내가 패널에서 정한 지시를 먼저 따라 배운 뒤 강화학습 (C1을 만든 방식과 같습니다)"])
    if L["teacher"] == "지금 AI 사장" and cur["kind"] != "brain":
        ui.label(surf, "규칙 사장은 두뇌가 없어 '규칙부터'로 훈련합니다", x, y + 15, GOLD); y += 11
    y += 19
    ui.label(surf, "훈련 길이", x, y + 1, WHITE)
    L["length"] = ui.seg(surf, (x + 56, y, lw - 56, 14), ["빠르게", "보통", "꼼꼼히"], L["length"], tips=["30번 반복 × 12달", "60번 반복 × 24달 (강의 Colab과 같음)", "120번 반복 × 24달 (오래 걸리지만 더 좋아집니다)"])
    y += 19
    ui.label(surf, "두뇌 이름", x, y + 1, WHITE)
    L["name"] = ui.text_field(surf, (x + 56, y, lw - 56, 14), L["name"], "내 AI 사장", key="brainname")[:24]
    y += 20
    if T.running:
        if ui.button(surf, (x, y, lw, 18), "훈련 멈추기", "cross", kind="danger"):
            T.stop(); T.reset()
    else:
        if ui.button(surf, (x, y, lw, 18), "훈련 시작", "play", kind="acid", tip="지금 회사 규모(업그레이드 포함)에서 훈련합니다"):
            app.ui.focus = None; pygame.key.stop_text_input(); app.lab_start()
    y += 24
    ui.para(surf, "이어서 · 지금 AI 사장을 이 회사에서 더 훈련(파인튜닝). 규칙부터 · 내 지시부터 · ① 따라 배우고(지도학습) ② 한 달을 수백 번 운영하며 보상으로 고칩니다(PPO). 결과는 JEV로 답하는 brain.json 한 장.",
            x, y, lw, MUTED)
    # 오른쪽: 진행
    rx, rw = x + lw + 12, r.width - lw - 30
    box = ui.frame(surf, (rx, r.y + 22, rw, r.height - 30), bg=UI_BG2)
    stage = T.stage
    t = app.t_real
    mood = "think" if T.running else "happy" if T.result else "idle"
    b = art.brain_ceo(mood); b = pygame.transform.scale(b, (b.get_width() * 2, b.get_height() * 2))
    surf.blit(b, (rx + 6, box.y + 6 + (int(math.sin(t * 8) * 2) if T.running else 0)))
    ppo = "보상으로 이어서 배우는 중 (PPO 파인튜닝)" if getattr(T, "warm", False) else "② 보상으로 배우는 중 (PPO)"
    msg = {None: "훈련을 기다리는 중", "start": "두뇌를 깨우는 중…", "imitate": "① 선생님을 따라 배우는 중 (지도학습)", "ppo": ppo,
           "row": ppo, "test": "시험 보는 중 (처음 보는 10개월)", "done": "훈련 끝!", "error": "오류"}.get(stage, stage)
    ui.label(surf, msg, rx + 44, box.y + 8, ACID, bold=True)
    rows = T.rows
    if rows:
        it = rows[-1]["iteration"]; n = rows[-1]["iterations"]
        ui.label(surf, f"반복 {it}/{n}", rx + 44, box.y + 21, WHITE)
        ui.bar(surf, (rx + 44, box.y + 33, rw - 52, 4), it / n)
    if T.accuracy:
        acc = sum(T.accuracy.values()) / len(T.accuracy)
        ui.label(surf, f"선생님과 같은 판단 {acc:.0%}", rx + rw - 6, box.y + 21, MUTED, right=True)
    # 학습 곡선
    gy0, gh = box.y + 46, box.height - 112
    pygame.draw.rect(surf, (8, 12, 10), (rx + 6, gy0, rw - 12, gh))
    ev = [r_ for r_ in rows if "eval_profit" in r_]
    if ev:
        vals = [r_["eval_profit"] for r_ in ev]
        lo, hi = min(vals + [0]), max(vals + [1])
        n = rows[-1]["iterations"]
        pts = [(rx + 8 + int((r_["iteration"] / n) * (rw - 16)), gy0 + gh - 3 - int((r_["eval_profit"] - lo) / (hi - lo + 1e-9) * (gh - 8))) for r_ in ev]
        if len(pts) > 1: pygame.draw.lines(surf, ACID, False, pts, 1)
        for p in pts: surf.set_at(p, WHITE)
        ui.label(surf, f"검증 달 이익 {man(vals[-1])}원", rx + 10, gy0 + 2, ACID)
    else:
        ui.label(surf, "학습 곡선 (검증 달의 한 달 이익)", rx + 10, gy0 + 2, MUTED)
    yb = gy0 + gh + 6
    if T.result:
        res = T.result["results"]
        ui.label(surf, f"새 두뇌  {won(res['new']['profit'], True)} / 달", rx + 8, yb, ACID, bold=True)
        ui.label(surf, f"{'출발 두뇌' if getattr(T, 'warm', False) else '선생님'}  {won(res['teacher']['profit'], True)} / 달", rx + 8, yb + 12, WHITE)
        ui.label(surf, f"만족 {res['new']['sat']:.0%} · 사고 {res['new']['incidents']:.1f}건 · 품절 {res['new']['stockout_days']:.1f}일", rx + 8, yb + 24, MUTED)
        tid = app.lab.get("trained_id")
        if tid and ui.button(surf, (rx + 6, box.bottom - 22, rw - 12, 16), "이 두뇌를 AI 사장으로 (이번 달 처음부터)", "brain", kind="acid"):
            app.restart_with("ai", tid)
    elif T.error:
        ui.para(surf, T.error["error"], rx + 8, yb, rw - 16, RED)
    else:
        ui.para(surf, "학습은 다른 프로세스에서 돌아서, 그동안에도 게임을 할 수 있습니다.", rx + 8, yb, rw - 16, MUTED)


# ── 창: 두뇌 랭킹 ─────────────────────────────────────────────────────────
def rank(app, surf):
    ui, R = app.ui, app.rank
    r = win(app, surf, 470, 300, "두뇌 랭킹 · 돈을 가장 많이 버는 두뇌는?", "crown")
    x, y = r.x + 8, r.y + 22
    ui.label(surf, "처음 보는 10개월 평균 · 지금 회사 규모 · 모든 두뇌는 JEV로 답합니다", x, y, MUTED); y += 14
    rows = R.get("rows", [])
    hi = max([1.0] + [abs(q["profit"]) for q in rows])
    for i, q in enumerate(rows[:9]):
        rr = pygame.Rect(x - 2, y - 1, r.width - 12, 15)
        is_ai = q["id"] == app.career.ai and app.career.mode == "ai"
        if is_ai: pygame.draw.rect(surf, (40, 64, 46), rr)
        if i == 0: surf.blit(art.icon("crown"), (x, y + 1))
        else: ui.label(surf, f"{i + 1}", x + 3, y, MUTED, bold=True)
        nm = q["name"]
        while app.fonts.width(nm, bold=True) > 128 and len(nm) > 4: nm = nm[:-2] + "…"
        ui.label(surf, nm, x + 14, y, ACID if i == 0 else WHITE, bold=i == 0)
        bw_ = r.width - 330
        ui.bar(surf, (x + 146, y + 4, bw_, 6), max(0, q["profit"]) / hi, ACID if i == 0 else (110, 150, 110))
        ui.label(surf, man(q["profit"]) + "원", x + 150 + bw_ + 46, y, ACID if q["profit"] >= 0 else RED, bold=True, right=True)
        ui.label(surf, f"만족 {q['sat'] * 100:.0f}% · 사고 {q['incidents']:.1f}", r.right - 10, y, MUTED, right=True)
        if q["id"] not in ("owner",) and ui.hover(rr):
            ui.tip = f"{q['name']} · 클릭하면 이 두뇌가 AI 사장이 되어 이번 달을 처음부터 운영합니다"
            if ui.clicked(rr): app.restart_with("ai", q["id"])
        y += 16
    if R.get("pending"):
        job = R["pending"][0]
        ui.label(surf, f"계산 중 · {job['name']} ({10 - len(job['seeds'])}/10)", x, y, GOLD); y += 14
    if ui.button(surf, (r.right - 160, r.y + 20, 152, 14), "두뇌 연합 만들기", "ant", kind="gold", tip="부서마다 다른 두뇌가 일하는 회사 (Connect AI)"):
        app.modal = "team"; app.sfx("click")
    y = r.bottom - 58
    pygame.draw.line(surf, UI_LINE, (x, y - 4), (r.right - 8, y - 4))
    ui.label(surf, "허깅페이스에서 두뇌 불러오기", x, y, ACID, bold=True)
    ui.label(surf, "아이디/connect-company-이름", x + 160, y, MUTED)
    y += 13
    app.hub["text"] = ui.text_field(surf, (x, y, r.width - 110, 15), app.hub["text"], "wonseokjung/connect-company-jay", key="hub")
    if ui.button(surf, (r.right - 96, y, 88, 15), "불러오는 중…" if app.hub["busy"] else "불러오기", "hf", kind="gold", enabled=not app.hub["busy"]):
        app.ui.focus = None; app.hub_load(app.hub["text"])
    y += 19
    ui.label(surf, "brain.json 파일을 이 창에 끌어다 놓아도 됩니다 · Colab에서 키운 두뇌를 그대로 씁니다", x, y, MUTED)


# ── 창: 업적 ─────────────────────────────────────────────────────────────
def trophy(app, surf):
    ui, c = app.ui, app.career
    r = win(app, surf, 470, 260, f"업적 · {len(c.achievements)}/{len(ACHIEVEMENTS)}", "trophy")
    cw = (r.width - 20) // 2
    for i, (k, name, desc, icon) in enumerate(ACHIEVEMENTS):
        x = r.x + 8 + (i % 2) * (cw + 4)
        y = r.y + 22 + (i // 2) * 28
        got = k in c.achievements
        ui.frame(surf, (x, y, cw, 25), bg=(30, 44, 30) if got else UI_BG2)
        surf.blit(art.icon(icon if got else "lock"), (x + 5, y + 8))
        ui.label(surf, name, x + 18, y + 2, GOLD if got else (120, 130, 120), bold=True)
        ui.label(surf, desc, x + 18, y + 13, WHITE if got else (90, 100, 92))
        if got: ui.label(surf, f"{c.achievements[k]}월", x + cw - 5, y + 2, MUTED, right=True)


# ── 창: JEV 원문 ─────────────────────────────────────────────────────────
def jev(app, surf):
    ui, f = app.ui, app.fonts
    r = win(app, surf, 600, 330, "JEV · 회사의 판단 하나 = 요청 하나 + 응답 하나", "json")
    x, y = r.x + 8, r.y + 22
    item = app.selected or (app.feed[-1] if app.feed else None)
    if item is None:
        ui.label(surf, "아직 판단이 없습니다.", x, y, MUTED); return
    req, resp = app.jev_pair(item["x"])
    colw = (r.width - 24) // 2
    for i, (title_, obj) in enumerate((("요청 (회사 → 두뇌)", req), ("응답 (두뇌 → 회사)", resp))):
        cx = x + i * (colw + 8)
        ui.label(surf, title_, cx, y, ACID, bold=True)
        box = pygame.Rect(cx, y + 13, colw, r.height - 84)
        pygame.draw.rect(surf, (6, 9, 8), box); pygame.draw.rect(surf, UI_LINE, box, 1)
        text = json.dumps(_round(obj), ensure_ascii=False, indent=1)
        lines = []
        for ln in text.split("\n"):
            while app.fonts.width(ln, mono=True) > colw - 8 and len(ln) > 10:
                cut = max(10, int(len(ln) * (colw - 8) / max(1, app.fonts.width(ln, mono=True))))
                lines.append(ln[:cut]); ln = "  " + ln[cut:]
            lines.append(ln)
        scroll = app.jev_scroll if i == 0 else 0
        if i == 0 and ui.hover(box): app.jev_scroll = max(0, min(len(lines) - 5, app.jev_scroll - ui.wheel * 3))
        surf.set_clip(box.inflate(-2, -2))
        for k, ln in enumerate(lines[scroll:]):
            yy = box.y + 3 + k * 11
            if yy > box.bottom: break
            col = ACID if '"choice"' in ln or '"department"' in ln else GOLD if '"probabilities"' in ln or '"confidence"' in ln else (210, 218, 206)
            surf.blit(f.text(ln, col, mono=True), (box.x + 4, yy))
        surf.set_clip(None)
    by = r.bottom - 22
    ui.para(surf, "이 모양 그대로 OpenRouter의 typesafe/jev-1.13에 보낼 수 있고, 어떤 JEV 모델이든 사장 자리에 앉힐 수 있습니다. 왼쪽 상자는 휠로 내려 봅니다.", x, by - 4, r.width - 230, MUTED)
    if ui.button(surf, (r.right - 214, by, 206, 16), "이번 달 JEV 기록 저장 (.jsonl)", "save", kind="acid", tip="(요청, 응답, 보상) 한 줄씩 · JEV 학습 데이터"):
        app.jev_export()


def _round(o):
    if isinstance(o, float): return round(o, 4)
    if isinstance(o, dict): return {k: _round(v) for k, v in o.items()}
    if isinstance(o, list): return [_round(v) for v in o]
    return o


# ── 창: 도움말 ───────────────────────────────────────────────────────────
HELP = [
    ("게임 방법", "money",
     "당신의 회사 Connect AI Company는 한 달(영업일 20일) 동안 문을 엽니다.\n"
     "아침에는 인력 · 재고 · 광고를 정하고, 낮에는 고객 문의 · 환불 · 온라인 결제가 쏟아지고, 저녁에는 손님이 몰려와 물건을 삽니다.\n"
     "목표는 단 하나 · 돈을 많이 버는 것. 그런데 위험한 문의를 놓치거나 사기를 통과시키면 돈과 신뢰를 잃습니다.\n"
     "오른쪽 '사장 지시'를 바꾸면 내일 아침부터 적용됩니다. 월말에는 같은 달을 AI 사장과 규칙 사장이 운영했다면 어땠을지 신문이 알려 줍니다."),
    ("층마다 부서", "people",
     "B1 물류창고 · 발주한 물건이 이틀 뒤 트럭으로 옵니다. 창고가 넘치면 버립니다.\n"
     "1F 매장 · 저녁 손님이 물건을 삽니다. 재고가 없으면 품절!\n"
     "2F 고객센터 · 전화 문의를 즉시 처리 · 일반 처리 · 결제팀 · 사람 확인으로 보냅니다.\n"
     "3F 결제 · 환불 · 환불 손님이 옵니다. 악용인지 아닌지는 아무도 확실히 모릅니다.\n"
     "4F 사람 확인실 · 사람이 직접 봅니다. 확실하지만 자리가 적고 비쌉니다 (전전두엽의 '멈춤').\n"
     "5F 보안실 · 온라인 결제가 안테나로 들어옵니다. 사기를 통과시키면 도둑이 돈가방을 들고 도망칩니다.\n"
     "6F 마케팅 · 광고는 손님을 늘리지만 사기 시도도 늘립니다.  7F 사장실 · 판단이 내려가는 곳."),
    ("두뇌와 JEV", "brain",
     "AI 사장은 사람의 전전두엽처럼 ① 규칙(하향식 통제) ② 직관과 확신 ③ 멈춤(사람 확인)으로 판단합니다.\n"
     "회사의 모든 판단은 JEV 형식으로 오갑니다: 요청 = 상황(state) + 질문(questions · 선택지 criteria), 응답 = choice + probabilities + confidence.\n"
     "그래서 어떤 JEV 모델이든 사장 자리에 앉힐 수 있고, 한 달을 돌리면 (요청, 응답, 보상)이 줄줄이 남습니다. 이것이 JEV를 강화학습시키는 데이터입니다.\n"
     "'JEV 기록' 창에서 지금 판단의 원문을 보고, 한 달 기록을 .jsonl로 저장할 수 있습니다."),
    ("강화학습", "cap",
     "두뇌 훈련소는 두 단계로 AI 사장을 키웁니다.\n"
     "① 지도학습 · 선생님(규칙 사장 또는 내 지시)의 판단을 따라 합니다. C1이 만들어진 방식(SFT)과 같습니다.\n"
     "② 강화학습(PPO) · 한 달을 수백 번 운영하며, 회사의 가치(이익 · 고객 만족 · 위험 회피)로 계산한 보상이 커지도록 판단을 고칩니다.\n"
     "결과는 brain.json 한 장. Colab에서 키운 두뇌도, 허깅페이스에 올린 다른 사람의 두뇌도 '두뇌 랭킹'에서 불러와 대결시킬 수 있습니다."),
    ("단축키", "key",
     "스페이스 · 일시정지      1 · 2 · 3 · 4 · 속도 (1배 · 2배 · 4배 · 8배)\n"
     "Tab · JEV 원문      M · 배경 음악      F · 전체 화면      Esc · 창 닫기 / 메뉴\n"
     "brain.json 파일을 창에 끌어다 놓으면 두뇌를 불러옵니다.\n"
     "저장 위치 · ~/.connect-tycoon (회사 · 두뇌 · JEV 기록)"),
]


def help_view(app, surf):
    ui = app.ui
    r = win(app, surf, 470, 290, "도움말", "help")
    tabs_w = (r.width - 16) // len(HELP)
    for i, (name, _icon, _) in enumerate(HELP):
        if ui.button(surf, (r.x + 8 + i * tabs_w, r.y + 20, tabs_w - 2, 15), name, kind="ghost", active=i == app.help_page):
            app.help_page = i; app.sfx("page")
    name, icon, text = HELP[app.help_page]
    y = r.y + 42
    for para in text.split("\n"):
        y = ui.para(surf, para, r.x + 10, y, r.width - 20, (222, 228, 216)) + 4


# ── 창: 사장 고르기 ───────────────────────────────────────────────────────
def ceo(app, surf):
    ui, c = app.ui, app.career
    nxt = app.modal_data.get("ceo_next")
    r = win(app, surf, 380, 60 + 18 * (len(app.roster) + 1) + 30, "다음 달 사장" if nxt else "사장 바꾸기 · 이번 달을 처음부터", "boss")
    x, y = r.x + 8, r.y + 22
    if ui.button(surf, (x, y, r.width - 16, 16), "내가 직접 경영", "boss", active=c.mode == "owner"):
        pick(app, "owner", None, nxt)
    y += 20
    for e in app.roster:
        lab = f"{e['name']} · {e['source']}"
        if ui.button(surf, (x, y, r.width - 16, 16), lab, {"brain": "brain", "rule": "news", "team": "ant"}[e["kind"]], active=c.mode == "ai" and c.ai == e["id"]):
            pick(app, "ai", e["id"], nxt)
        y += 18
    ui.para(surf, "두뇌 훈련소에서 키운 두뇌와 불러온 두뇌가 여기에 나옵니다.", x, r.bottom - 22, r.width - 16, MUTED)


def pick(app, mode, rid, nxt):
    app.modal_data.pop("ceo_next", None)
    if nxt:
        app.career.mode = mode
        if rid: app.career.ai = rid
        app.modal = "news"
    else:
        app.restart_with(mode, rid)
    app.sfx("click")


def menu(app, surf):
    ui = app.ui
    r = win(app, surf, 220, 120, "메뉴", "gear")
    x, y = r.x + 10, r.y + 24
    if ui.button(surf, (x, y, r.width - 20, 18), "계속하기", "play", kind="acid"):
        app.modal = None
    y += 22
    if ui.button(surf, (x, y, r.width - 20, 18), "저장하고 타이틀로", "save"):
        app.career.save(); app.saved = app.career; app.screen = "title"; app.modal = None; app._attract()
    y += 22
    if ui.button(surf, (x, y, r.width - 20, 18), "저장하고 끝내기", "cross", kind="ghost"):
        app.quit = True


# ── 창: 두뇌 연합 ─────────────────────────────────────────────────────────
def team(app, surf):
    ui, S = app.ui, app.teamsearch
    r = win(app, surf, 480, 304, "두뇌 연합 · 부서마다 다른 두뇌 (Connect AI)", "ant")
    x, y = r.x + 8, r.y + 22
    y = ui.para(surf, "개미 군집처럼 부서마다 다른 두뇌가 일합니다. 모두 JEV로 말하니까 누가 만든 두뇌든 한 회사에서 함께 일할 수 있습니다.", x, y, r.width - 16, (214, 222, 210)) + 4
    opts = [e for e in app.roster if e["kind"] != "team"]
    ids = [e["id"] for e in opts]
    members = app.team_members()
    lw = 236
    for d in ct.DEPT_ORDER:
        surf.blit(art.icon(DEPT_ICON[d]), (x, y + 2))
        ui.label(surf, ct.DEPTS[d]["name"], x + 12, y, WHITE, bold=True)
        cur = members[d] if members[d] in ids else ids[0]
        i = ids.index(cur)
        if ui.button(surf, (x + 70, y - 1, 14, 13), "◀", kind="ghost"):
            app.career.team = dict(members, **{d: ids[(i - 1) % len(ids)]}); app.refresh_team(); app.sfx("click")
        e = opts[i]
        nm = e["name"]
        while app.fonts.width(nm) > lw - 110 and len(nm) > 4: nm = nm[:-2] + "…"
        pygame.draw.rect(surf, (20, 30, 25), (x + 86, y - 1, lw - 104, 13))
        surf.blit(art.icon("brain" if e["kind"] == "brain" else "news"), (x + 89, y + 1))
        ui.label(surf, nm, x + 100, y, ACID if e["kind"] == "brain" else GOLD)
        if ui.button(surf, (x + lw - 16, y - 1, 14, 13), "▶", kind="ghost"):
            app.career.team = dict(members, **{d: ids[(i + 1) % len(ids)]}); app.refresh_team(); app.sfx("click")
        y += 16
    # 오른쪽: 찾기
    rx, rw = x + lw + 10, r.width - lw - 26
    box = ui.frame(surf, (rx, r.y + 50, rw, r.height - 84), "자동으로 최고 조합 찾기", "search", bg=UI_BG2)
    yy = box.y + 20
    if S.running or S.stage in ("start", "singles", "try"):
        ui.label(surf, f"찾는 중 · {S.done}/{S.total}", rx + 5, yy, GOLD, bold=True); yy += 12
        ui.bar(surf, (rx + 5, yy, rw - 10, 4), S.done / max(1, S.total)); yy += 8
        if S.last:
            nm = app.entry(S.last["name"])["name"]
            ui.label(surf, f"{ct.DEPTS[S.last['dept']]['name']} ← {nm[:8]} {man(S.last['value'])}", rx + 5, yy, MUTED); yy += 12
    if S.singles:
        ui.label(surf, "혼자 운영하면 (검증 12개월)", rx + 5, yy, ACID, bold=True); yy += 12
        for rid, v in sorted(S.singles.items(), key=lambda kv: -kv[1])[:5]:
            nm = app.entry(rid)["name"]
            while app.fonts.width(nm) > rw - 70 and len(nm) > 4: nm = nm[:-2] + "…"
            ui.label(surf, nm, rx + 5, yy, WHITE); ui.label(surf, man(v) + "원", rx + rw - 6, yy, WHITE, right=True); yy += 11
    if S.result:
        best_single = max(S.singles.values()) if S.singles else 0
        ui.label(surf, f"연합 {man(S.result['best'])}원", rx + 5, yy + 2, ACID, bold=True)
        diff = S.result["best"] - best_single
        ui.label(surf, f"혼자 최고보다 {man(diff, True)}원", rx + rw - 6, yy + 2, ACID if diff > 0 else MUTED, right=True); yy += 14
    if not (S.running or S.result or S.singles):
        ui.para(surf, "두뇌가 둘 이상이면, 부서마다 가장 잘하는 두뇌를 골라 연합을 만듭니다. 고르는 데는 검증 달만 쓰고 시험 달은 남겨 둡니다.", rx + 5, yy, rw - 10, MUTED)
    by = r.bottom - 24
    if ui.button(surf, (rx, by, rw, 17), "찾는 중…" if S.running else "최고 조합 찾기", "search", kind="gold", enabled=not S.running and len(opts) >= 2):
        app.team_start()
    if ui.button(surf, (x, by, lw, 17), "이 연합을 AI 사장으로 (이번 달 처음부터)", "ant", kind="acid"):
        app.career.team = members; app.refresh_team(); app.restart_with("ai", "team")


MODALS = {"news": news, "shop": shop, "lab": lab, "rank": rank, "trophy": trophy, "jev": jev, "help": help_view, "ceo": ceo, "menu": menu, "team": team}
