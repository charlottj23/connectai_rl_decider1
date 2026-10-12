# -*- coding: utf-8 -*-
"""학습 화면 · 이 게임의 목적은 하나, 시뮬레이터로 의사결정 모델을 학습시키는 것.

    왼쪽   모델이 회사를 운영하는 빌딩 (판단은 7층 모델에서 층으로 내려가는 빛줄기)
    오른쪽 모델 카드 · 보상 · 사람 라벨 · 학습 버튼 · 버전별 성적

학습 = 강화학습(PPO, 시뮬레이터에서 스스로) + 지도학습(사람 라벨).
모델이 확신이 낮은 판단을 만나면 게임이 잠깐 멈추고 사람에게 묻습니다. 사람이 고른 답은 라벨로 쌓이고,
시뮬레이터가 선택지마다 한 달을 끝까지 다시 돌려 그 답이 좋았는지 바로 알려 줍니다.
"""
import math

import pygame

import connect_tycoon as ct
from ..labels import _Override
from . import art
from .pixel import ACID, MUTED, RED, UI_BG, UI_LINE, WHITE, cover, man

HEAD = 20
PANEL = 216
ASK = ("refund", "security", "cs")
DEPT_ICON = {"staffing": "people", "inventory": "box", "marketing": "mega", "cs": "phone", "refund": "card", "security": "shield"}
LENGTH = 60
SHORT_ACT = {"즉시 처리": "바로 처리", "일반 처리": "순서대로", "결제 담당 배정": "결제팀에", "사람 확인": "담당자 검토", "전액 환불": "전액 환불",
             "부분 환불": "절반 환불", "거절": "거절", "허용": "통과", "차단": "막기"}
QUESTION = {"security": "이 결제를 통과시킬까요?", "refund": "이 환불 요청, 어떻게 할까요?", "cs": "이 문의를 어디로 보낼까요?"}
REWARD_TIP = {"이익": "이익 · 번 돈이 얼마나 중요한가", "고객 만족": "고객 만족 · 손님 기분이 얼마나 중요한가", "위험": "위험 회피 · 사고를 얼마나 피할까"}
STREAM_NAME = {"staffing": "인력", "inventory": "재고", "marketing": "광고", "cs": "문의", "refund": "환불", "security": "결제"}
# 카드에 보이는 손님의 사정 · 엔진의 사유 · 등급 · 신호를 사람이 읽는 말로
REFUND_QUOTE = {"불량": "받아 보니 고장 나 있어요. 환불해 주세요.", "미배송": "주문한 물건이 아직 안 왔어요. 환불해 주세요.",
                "단순 변심": "마음이 바뀌었어요. 환불해 주세요.", "의심": "이유는 말하기 어렵고요, 그냥 환불해 주세요."}
TIER_DESC = {"신규": "신규 · 처음 산 손님", "단골": "단골 · 자주 사는 손님", "VIP": "VIP · 가장 많이 사는 손님"}
STAKES = {"refund": "악용이면 환불한 만큼 손해 · 정상 손님을 거절하면 만족 크게 하락 (VIP는 2배)",
          "security": "사기를 통과시키면 금액만큼 손해 · 정상 결제를 막으면 금액의 30% 손해",
          "cs": "위험한 문의를 사람이 안 보면 사고 · 급한 문의를 미루면 만족 하락"}
REAL_TIP = "학습에 쓰지 않은 실제 기록으로 다시 채점 · 카드 거래 검토 대기열(ULB) · 소매 · 호텔 · 자전거 대여의 하루 수요"
# 처음 켠 사람을 위한 안내 · 순서대로 (id, 제목, 설명, 가리킬 곳). 끝나면 다시 나오지 않습니다 (H로 다시 보기)
GUIDE = [("watch", "v0이 회사를 운영합니다", "규칙 사장을 따라 배운 모델 · 판단이 LIVE에 흐릅니다 (상황 → 행동 · 확신 · 보상)", "live"),
         ("reward", "무엇이 중요한지 정합니다", "이익 · 고객 만족 · 위험 · 모델은 이 비중으로 계산한 결과 점수(보상)를 키우도록 배웁니다", "reward"),
         ("train", "학습 버튼을 누르세요", "시뮬레이터 회사를 60번 × 24달 운영하며 강화학습 (노트북 CPU로 몇 분)", "train"),
         ("curve", "학습 곡선", "3번마다 시험용 달을 운영해 본 한 달 이익 · 가장 좋았던 순간의 모델이 다음 버전이 됩니다", "graph"),
         ("real", "실제 데이터로 시험", "학습에 쓰지 않은 진짜 카드 거래 713건 · 진짜 사기 177건 중 몇 건을 잡았나", "real"),
         ("save", "저장하고 올리기", "저장 = 다운로드 폴더에 brain.json (Colab에서 Qwen의 선생님) · 올리기 = Hugging Face에 내 모델 공개", "save")]
LABEL_TIP = ("label", "모델이 헷갈리면 사람에게 묻습니다", "확신이 75%보다 낮은 판단 · 내가 고른 답은 라벨이 되어 다음 학습에 들어갑니다", None)


class Studio:
    def __init__(self, app):
        self.app = app
        self.versions = []            # [{name, rid, profit, sat, incidents}]
        self.labels = []              # [(부서, 관측, 행동 번호)]
        self.values = {"이익": 1.0, "고객 만족": 1.0, "위험": 1.0}
        self.ask = True
        self.review = None
        self.feedback = None
        self.asked_day = -1
        self.job = None
        self.curve = []
        self.guide = []               # 끝낸 안내 단계
        self.show_guide = True        # 그림 만들 때는 끕니다 (scripts/make_media.py)
        self.rects = {}               # 안내가 가리킬 곳 (그릴 때 기록)
        self.uploading, self.up_result = False, None

    # ── 저장 · 이어하기 ───────────────────────────────────────────────────
    def save_state(self):
        self.app.career.studio = {"versions": [{k: v for k, v in x.items() if k != "human"} for x in self.versions],
                                  "labels": [[d, [round(float(o), 6) for o in obs], a] for d, obs, a in self.labels],
                                  "values": dict(self.values), "ask": self.ask, "guide": list(self.guide)}

    def restore(self):
        st = self.app.career.studio or {}
        ids = {r["id"] for r in self.app.roster}
        self.versions = [v for v in st.get("versions", []) if v.get("rid") in ids]
        self.labels = [tuple(x) for x in st.get("labels", [])]
        self.values = dict(self.values, **st.get("values", {}))
        self.ask = st.get("ask", True)
        self.guide = list(st.get("guide", []))
        self.job, self.review, self.feedback, self.curve = None, None, None, []
        if not self.versions:
            self.begin()

    # ── 모델 버전 ─────────────────────────────────────────────────────────
    @property
    def current(self):
        return self.versions[-1] if self.versions else None

    def begin(self):
        """v0 · 규칙을 따라 배운 빈 모델에서 시작합니다 (강화학습 전)."""
        self.versions, self.labels, self.curve = [], [], []
        self.job = "v0"
        a = self.app
        a.career.mode, a.career.ai = "ai", "rule"
        a.trainer.start(a.career.config, self.values, teacher=None, iterations=0, months_per_iter=12, profile=a.career.profile)

    def train(self):
        a = self.app
        if a.trainer.running or not self.current:
            return
        brain = a.entry(self.current["rid"])["brain"]
        self.job, self.curve = "train", []
        self.done("train")
        a.trainer.start(a.career.config, self.values, iterations=LENGTH, months_per_iter=24, seed=len(self.versions),
                        start_spec=brain.spec, labels=list(self.labels), profile=a.career.profile)
        a.sfx("click")

    def poll(self):
        a = self.app
        st = a.trainer.poll()
        for r in a.trainer.rows[len(self.curve):]:
            if "eval_profit" in r: self.curve.append(r["eval_profit"])
            else: self.curve.append(None)
        if st == "done":
            res = a.trainer.result
            pol = ct.LinearPolicy.from_json(res["policy"])
            n = len(self.versions)
            name = f"v{n}"
            spec = ct.CompanyBrain.make_spec(a.entry("jay-company")["brain"].spec, pol, name=f"{a.career.company}-{name}".replace(" ", "-").lower(),
                                             values=self.values, researcher="CONNECT TYCOON", config=a.career.config,
                                             results={"profit": res["results"]["new"]["profit"], "labels": len(self.labels)},
                                             profile=a.career.profile)
            r = a._add_brain(ct.CompanyBrain(spec), source="학습", title=name)
            nr = res["results"]["new"]
            self.versions.append({"name": name, "rid": r["id"], "profit": nr["profit"], "sat": nr["sat"], "incidents": nr["incidents"],
                                  "human": res["results"].get("human"), "real": res["results"].get("real")})
            self.job = None
            a.career.mode, a.career.ai = "ai", r["id"]
            self.save_state(); a.career.save()
            a.start_month(restart=True)
            a.sfx("level")
        elif st == "error":
            self.job = None
            a.toast("학습 오류: " + a.trainer.error["error"][:60], "bad")

    # ── 사람 확인 (지도학습 라벨) ─────────────────────────────────────────
    def on_decision(self, x, silent):
        if silent or not self.ask or self.review or self.job == "v0" or x["dept"] not in ASK or x.get("ruled"):
            return
        jv = x.get("jev")
        if not jv:
            return
        conf = jv["response"]["answers"]["decision"].get("confidence", 1.0)
        D = self.app.director
        if conf >= 0.75 or self.asked_day == D.d:
            return
        m = self.app.month
        asked = [y for y in m["log"] if y["dept"] is not None and not y["ruled"]]
        k = next((n for n, y in enumerate(asked) if y is x), None)
        if k is None:
            return
        self.asked_day = D.d
        self.review = {"x": x, "conf": conf, "t": 0.0, "month": m, "k": k}       # 그 달과 판단 위치를 함께 기억합니다
        self.app.sfx("think")

    def answer(self, i):
        a, R = self.app, self.review
        x = R["x"]
        acts = ct.DEPTS[x["dept"]]["actions"]
        self.labels.append((x["dept"], list(x["obs"]), i))
        self.done("label")
        self.review = None
        # 시뮬레이터가 선택지마다 그 달을 끝까지 돌려 봅니다 (카드가 뜬 그 달 · 그 판단 기준)
        try:
            m, k = R["month"], R["k"]
            co = a.company()
            pol = a.policy_for(m["rid"], co)
            q = {}
            for act in acts:
                lg, _ = co.run_month(m["seed"], _Override(pol, k, act))
                q[act] = sum(y["reward"] for y in lg)
            best = max(acts, key=lambda s: q[s])
            self.feedback = {"mine": acts[i], "best": best, "gap": q[best] - q[acts[i]], "t": 0.0}
            a.sfx("cash" if acts[i] == best else "fail")
        except Exception:
            self.feedback = {"mine": acts[i], "best": acts[i], "gap": 0.0, "t": 0.0}

    # ── 그리기 ───────────────────────────────────────────────────────────
    def draw(self, surf, dt):
        a = self.app
        if self.feedback:
            self.feedback["t"] += dt
            if self.feedback["t"] > 1.8: self.feedback = None
        self.hud(surf)
        self.stream(surf)
        if a.panel:
            self.panel(surf)
        if self.review:
            self.card(surf)
        elif self.feedback:
            self.result(surf)
        if self.job == "v0":
            self.splash(surf, "모델 준비 중 · 규칙 사장을 따라 배우는 중")
        self.upload_poll()
        if self.show_guide:
            self.coach(surf)

    def hud(self, surf):
        a, ui = self.app, self.app.ui
        vw = a.vw
        cover(surf, (0, 0, vw, HEAD + 1))
        pygame.draw.rect(surf, UI_BG, (0, 0, vw, HEAD))
        pygame.draw.line(surf, UI_LINE, (0, HEAD), (vw, HEAD))
        x = 8
        x += ui.label(surf, "CONNECT", x, 3, WHITE, bold=True) + 4
        ui.label(surf, "TYCOON", x, 3, ACID, bold=True)
        # 한 달 20일 진행 점
        D = a.director
        cx = a.world_rect.centerx - 20 * 7 // 2
        for d in range(20):
            on = d < D.d or (d == D.d and D.t >= 22)
            col = ACID if on else (255, 255, 255) if d == D.d and int(a.t_real * 3) % 2 else (46, 52, 50)
            pygame.draw.rect(surf, col, (cx + d * 7, 8, 5, 5), border_radius=2)
        # 이번 달 이익 · 속도
        done = D.days[:D.d + (1 if D.t >= 22 else 0)] if D.month else []
        prof = sum(d["profit"] for d in done)
        right = vw - 8
        icons = [("pause", 0), ("play", 1), ("ff", 3), ("fff", 8)]
        for ic, sp in reversed(icons):
            right -= 16
            active = (sp == 0 and a.paused) or (sp == a.speed and not a.paused)
            if ui.button(surf, (right, 3, 15, 14), "", ic, kind="ghost", active=active):
                if sp == 0: a.paused = not a.paused
                else: a.speed, a.paused = sp, False
        w_ = ui.label(surf, man(prof, True), right - 8, 3, ACID if prof >= 0 else RED, bold=True, right=True)
        surf.blit(art.icon("coin"), (right - 20 - w_, 5))
        if ui.hover((right - 22 - w_, 0, w_ + 16, HEAD)): ui.tip = "이번 달 이익 (하루가 끝날 때마다 쌓입니다)"

    def stream(self, surf):
        """실시간 판단 스트림 · 모델의 판단이 상황 → 행동(확신) → 보상으로 한 줄씩 흘러갑니다 (S → A → R)."""
        a, ui = self.app, self.app.ui
        if self.review or not a.feed or self.job == "v0":
            return
        w = min(236, a.world_rect.width - 12)
        top = HEAD + 6
        n = max(2, min(6, (a.world.top - 40 - top - 24) // 13))      # 빌딩 간판 위 하늘에 들어가는 만큼
        rows = [it["x"] for it in a.feed[-n:]]
        h = 20 + len(rows) * 13 + 4
        r = pygame.Rect(6, top, w, h)
        self.rects["live"] = r
        cover(surf, r)
        bg = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (6, 9, 10, 238), bg.get_rect(), border_radius=8)
        pygame.draw.rect(bg, (208, 249, 145, 70), bg.get_rect(), 1, border_radius=8)
        surf.blit(bg, r.topleft)
        on = int(a.t_real * 2) % 2 == 0
        pygame.draw.circle(surf, ACID if on else (60, 80, 50), (r.x + 9, r.y + 9), 3)
        ui.label(surf, "LIVE", r.x + 16, r.y + 3, ACID, bold=True)
        ui.label(surf, "상황 → 행동 · 확신 · 보상", r.right - 6, r.y + 3, MUTED, right=True)
        for i, x in enumerate(rows):
            y = r.y + 19 + i * 13
            last = i == len(rows) - 1
            col = WHITE if last else (150, 158, 154)
            if last:
                pygame.draw.rect(surf, ACID, (r.x + 3, y + 2, 2, 9))
            surf.blit(art.icon(DEPT_ICON[x["dept"]]), (r.x + 8, y + 1))
            ev, act = x.get("ev") or {}, SHORT_ACT.get(x["action"], x["action"])
            what = f"{man(ev['amount'])} → {act}" if x["dept"] in ("refund", "security") and "amount" in ev else f"{STREAM_NAME[x['dept']]} → {act}"
            ui.label(surf, what, r.x + 21, y, col)
            rw = x.get("reward", 0.0)
            ui.label(surf, f"{rw:+.1f}", r.right - 6, y, (ACID if rw >= 0 else RED) if last else ((120, 150, 100) if rw >= 0 else (170, 90, 80)), right=True)
            conf = "규정" if x.get("ruled") else (f"{x['jev']['response']['answers']['decision'].get('confidence', 0):.0%}" if x.get("jev") else "")
            ui.label(surf, conf, r.right - 44, y, col, right=True)

    def panel(self, surf):
        a, ui = self.app, self.app.ui
        x0 = a.vw - PANEL
        cover(surf, (x0, HEAD + 1, PANEL, a.vh - HEAD - 1))
        pygame.draw.rect(surf, UI_BG, (x0, HEAD + 1, PANEL, a.vh - HEAD - 1))
        pygame.draw.line(surf, UI_LINE, (x0, HEAD + 1), (x0, a.vh))
        x, w = x0 + 6, PANEL - 12
        y = HEAD + 6
        cur = self.current
        # 모델 카드
        ui.frame(surf, (x, y, w, 56))
        b = art.brain_ceo("think" if a.trainer.running else "idle", brand=True)
        b = pygame.transform.scale(b, (b.get_width() * 2, b.get_height() * 2))
        surf.blit(b, (x + 4, y + 10 + (int(math.sin(a.t_real * 6) * 2) if a.trainer.running else 0)))
        ui.label(surf, "RL MODEL", x + 44, y + 6, MUTED, bold=True)
        ui.label(surf, cur["name"] if cur else "—", x + 44, y + 18, WHITE, bold=True, k=2)
        if cur:
            ui.label(surf, man(cur["profit"]), x + w - 6, y + 18, ACID, bold=True, k=2, right=True)
            ui.label(surf, "한 달 이익", x + w - 6, y + 6, MUTED, right=True)
        y += 60
        # 보상
        self.rects["reward"] = pygame.Rect(x, y, w, 62)
        ui.frame(surf, (x, y, w, 62), "보상")
        yy = y + 20
        for key, ic in (("이익", "coin"), ("고객 만족", "smile"), ("위험", "shield")):
            surf.blit(art.icon(ic), (x + 6, yy + 1))
            if ui.hover((x, yy - 1, w, 13)): ui.tip = REWARD_TIP[key]
            self.values[key] = ui.slider(surf, (x + 20, yy + 1, w - 48, 10), self.values[key], 0.0, 3.0, 0.5)
            ui.label(surf, f"{self.values[key]:.1f}", x + w - 6, yy, WHITE, right=True, bold=True)
            yy += 13
        y += 66
        # 사람 라벨
        ui.frame(surf, (x, y, w, 34))
        surf.blit(art.icon("boss"), (x + 6, y + 6))
        ui.label(surf, "사람 라벨", x + 18, y + 4, WHITE, bold=True)
        ui.label(surf, str(len(self.labels)), x + 18, y + 16, ACID, bold=True)
        self.ask = ui.seg(surf, (x + w - 70, y + 9, 64, 15), [True, False], self.ask, ["묻기", "끄기"])
        y += 38
        # 학습 버튼
        self.rects["train"] = pygame.Rect(x, y, w, 26)
        T = a.trainer
        if T.running and self.job == "train":
            it = T.rows[-1]["iteration"] if T.rows else 0
            ui.frame(surf, (x, y, w, 26))
            ui.bar(surf, (x + 6, y + 18, w - 12, 3), it / LENGTH)
            ui.label(surf, f"학습 중 {it}/{LENGTH}", x + 6, y + 3, ACID, bold=True)
        else:
            nxt = f"v{len(self.versions)}"
            if self.job is None:                          # 숨 쉬듯 빛나는 학습 버튼
                g = 0.5 + 0.5 * math.sin(a.t_real * 2.4)
                glow = pygame.Surface((w + 10, 36), pygame.SRCALPHA)
                pygame.draw.rect(glow, (208, 249, 145, int(18 + 34 * g)), glow.get_rect(), border_radius=16)
                surf.blit(glow, (x - 5, y - 5))
            if ui.button(surf, (x, y, w, 26), f"학습  →  {nxt}", "play", kind="acid", enabled=self.job is None):
                self.train()
        y += 30
        # 성적: 학습 중에는 학습 곡선, 아니면 버전별 막대
        h = a.vh - y - 28 - 50
        self.rects["graph"] = pygame.Rect(x, y, w, h)
        ui.frame(surf, (x, y, w, h), "학습 곡선" if self.job == "train" else "버전별 한 달 이익")
        gx, gy, gw, gh = x + 8, y + 22, w - 16, h - 40
        if self.job == "train" and self.curve:
            pts = [(i, v) for i, v in enumerate(self.curve) if v is not None]
            if pts:
                ref = [cur["profit"]] if cur else [0]                  # 지금 버전 기준선도 그래프 안에 들어오게
                lo = min([v for _, v in pts] + ref); hi = max([v for _, v in pts] + ref) + 1
                P = [(gx + int(i / LENGTH * gw), gy + gh - int((v - lo) / (hi - lo + 1e-9) * gh)) for i, v in pts]
                if cur:
                    yb = gy + gh - int((cur["profit"] - lo) / (hi - lo + 1e-9) * gh)
                    pygame.draw.line(surf, (70, 78, 74), (gx, yb), (gx + gw, yb))
                    ui.label(surf, f"{cur['name']} {man(cur['profit'])}", gx + gw, yb - 13, MUTED, right=True)
                if len(P) > 1: pygame.draw.lines(surf, ACID, False, P, 2)
                ui.label(surf, man(pts[-1][1]), gx + gw, gy - 2, ACID, bold=True, right=True)
        elif self.versions:
            vs = self.versions[-7:]
            hi = max(1.0, max(v["profit"] for v in vs))
            bw = min(22, gw // max(1, len(vs)) - 4)
            for i, v in enumerate(vs):
                bh = max(2, int(max(0.0, v["profit"]) / hi * (gh - 12)))
                bx = gx + i * (bw + 4)
                last = v is vs[-1]
                pygame.draw.rect(surf, ACID if last else (70, 90, 60), (bx, gy + gh - bh, bw, bh), border_radius=2)
                ui.label(surf, v["name"], bx + bw // 2, gy + gh + 2, WHITE if last else MUTED, center=True)
        # 실제 데이터 시험: 학습에 쓰지 않은 실제 기록으로 다시 채점
        ry = y + h + 4
        self.rects["real"] = pygame.Rect(x, ry, w, 46)
        ui.frame(surf, (x, ry, w, 46), "실제 데이터 시험")
        if ui.hover((x, ry, w, 46)): ui.tip = REAL_TIP
        real = cur.get("real") if cur else None
        for i, (ic, name) in enumerate((("shield", f"실제 결제 {real['cases'] if real else ''}건"), ("coin", "실제 수요 재생"))):
            yy = ry + 18 + i * 13
            surf.blit(art.icon(ic), (x + 6, yy + 1))
            ui.label(surf, name, x + 20, yy, MUTED)
            val = "—" if not real else (f"사기 {real['caught']}/{real['fraud']} 잡음" if i == 0 else man(real["demand"]))
            ui.label(surf, val, x + w - 6, yy, ACID if real else MUTED, bold=True, right=True)
        # 저장
        by = a.vh - 24
        self.rects["save"] = pygame.Rect(x, by, w, 18)
        bw = (w - 4) // 3
        if ui.button(surf, (x, by, bw, 18), "저장", "save", kind="ghost", enabled=bool(cur) and not self.job,
                     tip="brain.json을 다운로드 폴더에 · Colab 1단계에서 이 파일을 올리면 Qwen의 선생님이 됩니다"):
            self.save()
        if ui.button(surf, (x + bw + 2, by, bw, 18), "…" if self.uploading else "올리기", "hf", kind="ghost",
                     enabled=bool(cur) and not self.job and not self.uploading,
                     tip="Hugging Face에 내 모델 공개 · connectailab-rl-아이디-버전-teacher (처음 한 번 터미널에서 hf auth login)"):
            self.upload()
        if ui.button(surf, (x + 2 * (bw + 2), by, w - 2 * (bw + 2), 18), "처음부터", "dice", kind="ghost", enabled=not self.job):
            self.begin()

    def save(self):
        import os
        import shutil
        a = self.app
        e = a.entry(self.current["rid"])
        folder = os.path.join(os.path.expanduser("~"), "Downloads")       # 묻지 않고 다운로드 폴더에 (Colab 1단계에서 이 파일을 올립니다)
        os.makedirs(folder, exist_ok=True)
        dst, n = os.path.join(folder, f"{e['brain'].name}.json"), 2
        while os.path.exists(dst):                                          # 덮어쓰지 않고 -2, -3 … 을 붙입니다
            dst, n = os.path.join(folder, f"{e['brain'].name}-{n}.json"), n + 1
        if e.get("path"):
            shutil.copy(e["path"], dst)
        else:
            e["brain"].save(dst)
        a.toast(f"저장 · {dst}", "good", "save")
        self.done("save")

    def upload(self):
        """올리기 · 지금 버전의 brain.json을 Hugging Face에 (모델 카드 · 성적 · 자기소개 about_me.md 함께)."""
        import os
        import tempfile
        import threading
        a = self.app
        if self.uploading or not self.current:
            return
        e, version = a.entry(self.current["rid"]), self.current["name"]
        self.uploading = True
        a.toast("Hugging Face에 올리는 중 · 모델 카드에 넣을 성적을 계산합니다 (1분 안팎)", "info", "hf")

        def work():
            try:
                from huggingface_hub import HfApi
            except ImportError:
                self.up_result = ("bad", '올리기 도구가 없습니다 · pip install -e ".[game]" 로 다시 설치해 주세요'); return
            try:
                HfApi(token=os.environ.get("HF_TOKEN")).whoami()
            except Exception:
                self.up_result = ("bad", "먼저 터미널에서 hf auth login 을 한 번 해 주세요 (Write 토큰)"); return
            try:
                from ..hub import find_about, push_brain
                from ..llm.hub import make_author
                path = e.get("path")
                if not path:
                    path = os.path.join(tempfile.mkdtemp(), "brain.json"); e["brain"].save(path)
                self.up_result = ("good", push_brain(path, version=version, author=make_author(find_about())))
            except Exception as ex:
                self.up_result = ("bad", f"올리지 못했습니다 · {str(ex)[:70]}")
        threading.Thread(target=work, daemon=True).start()

    def upload_poll(self):
        res, self.up_result = self.up_result, None
        if not res:
            return
        self.uploading = False
        a = self.app
        if res[0] == "good":
            a.toast("올렸습니다 · " + res[1].replace("https://", ""), "good", "hf"); a.sfx("level")
            self.done("save")
            try:
                import webbrowser
                webbrowser.open(res[1])
            except Exception:
                pass
        else:
            a.toast(res[1], "bad", "warn")

    # ── 처음 켠 사람을 위한 안내 ──────────────────────────────────────────
    def done(self, key):
        """이 단계와 그 앞 단계를 모두 끝낸 것으로 (예: 학습을 먼저 눌렀다면 앞의 안내는 건너뜀)."""
        ids = [g[0] for g in GUIDE]
        upto = ids[:ids.index(key) + 1] if key in ids else [key]
        self.guide = list(dict.fromkeys(self.guide + upto))
        self.save_state()

    def step_now(self):
        if self.job == "v0" or not self.versions:
            return None
        if self.review:
            return LABEL_TIP if "label" not in self.guide else None
        for g in GUIDE:
            if g[0] in self.guide:
                continue
            if g[0] == "curve" and self.job != "train":
                if len(self.versions) > 1: self.done("curve"); continue      # 학습이 끝났으면 넘어갑니다
                return None
            if g[0] == "real" and len(self.versions) < 2:
                return None                                                  # 학습한 모델이 생긴 뒤에
            return g
        return None

    def coach(self, surf):
        a, ui, f = self.app, self.app.ui, self.app.fonts
        g = self.step_now()
        if not g:
            return
        key, head, body, target = g
        seq = [x[0] for x in GUIDE]
        n = seq.index(key) + 1 if key in seq else None
        # 가리킬 곳 · 형광 테두리가 숨 쉬듯
        if target and target in self.rects:
            t = self.rects[target].inflate(6, 6)
            on = 0.5 + 0.5 * math.sin(a.t_real * 5)
            glow = pygame.Surface(t.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (208, 249, 145, int(90 + 150 * on)), glow.get_rect(), 2, border_radius=8)
            surf.blit(glow, t.topleft)
        wr = a.world_rect
        W = min(340, wr.width - 12)
        lines = []                                    # 안내 글은 띄어쓰기에서만 줄을 바꿉니다
        for word in body.split(" "):
            if lines and f.width(lines[-1] + " " + word) <= W - 20: lines[-1] += " " + word
            else: lines.append(word)
        lines = lines[:3]
        H = 34 + len(lines) * 13 + (22 if key != "label" else 6)
        r = pygame.Rect(6, wr.bottom - H - 6, W, H)
        cover(surf, r)
        bg = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (6, 9, 10, 244), bg.get_rect(), border_radius=8)
        pygame.draw.rect(bg, (208, 249, 145, 200), bg.get_rect(), 1, border_radius=8)
        surf.blit(bg, r.topleft)
        ui.label(surf, f"STEP {n}/{len(GUIDE)}" if n else "TIP", r.x + 10, r.y + 6, ACID, bold=True)
        ui.label(surf, "H 다시 보기", r.right - 10, r.y + 6, MUTED, right=True)
        ui.label(surf, head, r.x + 10, r.y + 19, WHITE, bold=True)
        for i, line in enumerate(lines):
            ui.label(surf, line, r.x + 10, r.y + 34 + i * 13, (200, 208, 198))
        by = r.bottom - 20
        if key in ("watch", "reward", "real", "save"):
            if ui.button(surf, (r.right - 60, by, 52, 15), "다음" if key != "save" else "알겠어요", kind="acid"):
                self.done(key); a.sfx("click")
        elif key == "train":
            ui.label(surf, "→ 오른쪽 형광 버튼", r.right - 10, by + 2, ACID, bold=True, right=True)
        if key != "label" and ui.button(surf, (r.x + 8, by, 64, 15), "안내 끄기", kind="ghost"):
            self.done(GUIDE[-1][0]); self.done("label")

    def card(self, surf):
        """사람 확인 카드 · 모델이 확신하지 못한 판단을 사람이 고릅니다."""
        a, ui, f = self.app, self.app.ui, self.app.fonts
        R = self.review
        x = R["x"]; ev = x["ev"]; dept = x["dept"]
        resp = x["jev"]["response"]["answers"]["decision"]
        W = 290
        lines = f.wrap(ev["message"], W - 24)[:3] if dept == "cs" else []
        stakes = STAKES[dept].split(" · ")                              # 두 줄 · 끊는 곳을 정해 둡니다
        H = 22 + 30 + (len(lines) * 13 + 6 if dept == "cs" else 76) + 13 * len(stakes) + 6 + 58
        wr = a.world_rect
        r = pygame.Rect(wr.centerx - W // 2, HEAD + 30, W, H)
        cover(surf, r.inflate(4, 4))
        pygame.draw.rect(surf, (6, 9, 10), r, border_radius=8)
        pygame.draw.rect(surf, ACID, r, 1, border_radius=8)
        surf.blit(art.icon("boss"), (r.x + 8, r.y + 7))
        ui.label(surf, "당신의 판단이 필요해요", r.x + 20, r.y + 5, ACID, bold=True)
        name = ct.DEPTS[dept]["name"]
        ui.label(surf, name, r.right - 8, r.y + 5, MUTED, right=True)
        surf.blit(art.icon(DEPT_ICON[dept]), (r.right - 20 - f.width(name), r.y + 7))
        ui.label(surf, QUESTION[dept], r.x + 10, r.y + 22, WHITE, bold=True, k=2)
        yy = r.y + 22 + 32
        if dept in ("refund", "security"):
            ui.label(surf, man(ev["amount"]) + "원", r.x + 10, yy, WHITE, bold=True, k=2)
            ax = r.x + 16 + f.width(man(ev["amount"]) + "원", bold=True, k=2)
            if dept == "refund":
                who, sub = TIER_DESC.get(ev["tier"], ev["tier"]), f"환불 사유 · {ev['reason']}"
                quote = REFUND_QUOTE.get(ev["reason"], "환불해 주세요.")
            else:
                sig = [t for t, on in (("새 기기에서", ev["new_device"]), ("해외에서", ev["overseas"]), ("짧은 시간에 여러 번", ev["velocity"] > 0.5)) if on]
                who, sub = "온라인 결제", "평소와 다른 점 " + str(len(sig)) + "개"
                quote = " · ".join(sig) + " 결제" if sig else "평소 쓰던 기기 · 국내 · 평소 속도로 결제"
            ui.label(surf, who, ax, yy + 2, WHITE, bold=True)
            ui.label(surf, sub, ax, yy + 15, MUTED)
            yy += 30
            qb = pygame.Rect(r.x + 10, yy, W - 20, 18)                 # 손님의 말 (말풍선)
            pygame.draw.rect(surf, (24, 30, 28), qb, border_radius=6)
            pygame.draw.polygon(surf, (24, 30, 28), [(qb.x + 12, qb.y), (qb.x + 18, qb.y - 5), (qb.x + 22, qb.y)])
            ui.label(surf, ("“" + quote + "”") if dept == "refund" else quote, qb.x + 7, qb.y + 3, WHITE)
            yy += 26
            fs = ev["fraud_score"]
            ui.label(surf, "악용 의심" if dept == "refund" else "사기 의심", r.x + 10, yy, MUTED)
            bx, bw = r.x + 62, W - 110
            pygame.draw.rect(surf, (30, 36, 34), (bx, yy + 4, bw, 6), border_radius=3)
            pygame.draw.rect(surf, ACID if fs < 0.5 else RED, (bx, yy + 4, int(bw * fs), 6), border_radius=3)
            ui.label(surf, f"{fs:.2f}", r.right - 10, yy, WHITE, bold=True, right=True)
            yy += 18
        else:
            for k_, line in enumerate(lines):
                ui.label(surf, line, r.x + 10, yy + k_ * 13, WHITE)
        for k_, line in enumerate(stakes):                                  # 각 선택의 결과 (결과표)
            ui.label(surf, line, r.x + 10, r.bottom - 60 - 13 * (len(stakes) - k_), MUTED)
        acts, keys = ct.DEPTS[dept]["actions"], ct.DEPTS[dept]["keys"]
        n = len(acts)
        bw = (W - 16 - 4 * (n - 1)) // n
        by = r.bottom - 54
        probs = resp.get("probabilities", {})
        top = max(keys, key=lambda k_: probs.get(k_, 0.0))
        for i, act in enumerate(acts):
            bx = r.x + 8 + i * (bw + 4)
            if ui.button(surf, (bx, by, bw, 18), SHORT_ACT.get(act, act), kind="normal", tip=act):
                self.answer(i); return
            p = probs.get(keys[i], 0.0)                    # 모델 생각: 이 답을 고를 확률
            pygame.draw.rect(surf, (30, 36, 34), (bx, by + 23, bw - 26, 4), border_radius=2)
            pygame.draw.rect(surf, ACID if keys[i] == top else (90, 110, 80), (bx, by + 23, int((bw - 26) * p), 4), border_radius=2)
            ui.label(surf, f"{p:.0%}", bx + bw, by + 19, ACID if keys[i] == top else MUTED, right=True)
        ui.label(surf, "막대 = 모델 생각", r.x + 8, r.bottom - 16, MUTED)

    def result(self, surf):
        a, ui = self.app, self.app.ui
        F = self.feedback
        good = F["mine"] == F["best"]
        wr = a.world_rect
        r = pygame.Rect(wr.centerx - 110, HEAD + 30, 220, 44)
        cover(surf, r)
        pygame.draw.rect(surf, (6, 9, 10), r, border_radius=8)
        pygame.draw.rect(surf, ACID if good else WHITE, r, 1, border_radius=8)
        surf.blit(art.icon("check" if good else "search"), (r.x + 10, r.y + 8))
        ui.label(surf, "좋은 판단" if good else f"정답은 {SHORT_ACT.get(F['best'], F['best'])}", r.x + 24, r.y + 6, ACID if good else WHITE, bold=True)
        ui.label(surf, "라벨 +1" if good else f"라벨 +1 · 보상 차이 {F['gap']:.1f}", r.x + 24, r.y + 22, MUTED)

    def splash(self, surf, text):
        a, ui = self.app, self.app.ui
        wr = a.world_rect
        r = pygame.Rect(wr.centerx - 110, wr.centery - 16, 220, 32)
        cover(surf, r)
        pygame.draw.rect(surf, (6, 9, 10), r, border_radius=8)
        pygame.draw.rect(surf, ACID, r, 1, border_radius=8)
        ui.label(surf, text, r.centerx, r.y + 9, ACID, bold=True, center=True)
