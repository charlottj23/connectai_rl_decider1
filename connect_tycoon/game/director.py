# -*- coding: utf-8 -*-
"""연출 · 엔진이 계산한 하루(log)를 25초짜리 장면으로 바꿉니다.

    0.5s  인력 배치 → 직원들이 엘리베이터에서 내려 자리로        (아침 판단 세 개는 AI 사장이 JEV로 답합니다)
    1.3s  재고 발주 → 창고          2.1s  광고 → 옥상 광고판
    3~16s 낮의 일 · 엔진이 기록한 시각(t) 그대로: 전화 문의 · 환불 손님 · 온라인 결제 신호
    16.8s 저녁 손님이 몰려와 물건을 사 갑니다 (품절이면 빈손으로)
    22s   하루 정산    24.2s 퇴근    25.5s 다음 날

돈 · 만족 · 재고 숫자는 연출이 아니라 엔진의 기록을 그대로 따라갑니다.
"""
import random

from . import art
from .actors import Actor, Coins, Flyer, Popup, Truck
from .pixel import man
from .world import BW, LEVEL

DAY_LEN = 25.5
T_STAFF, T_INV, T_MKT = 0.5, 1.3, 2.1
T_DAY0, T_DAYLEN = 3.0, 13.0
T_EVE, T_REV, T_SUM, T_NIGHT = 16.8, 19.2, 22.0, 24.2

ACT_ICON = {"즉시 처리": "rocket", "일반 처리": "news", "결제 담당 배정": "card", "사람 확인": "search", "전액 환불": "coin", "부분 환불": "coin",
            "거절": "cross", "허용": "check", "차단": "shield", "균형": "people", "고객센터 집중": "people", "결제팀 집중": "people", "사람 확인 집중": "people",
            "발주 안 함": "box", "소량 발주": "box", "대량 발주": "truck", "중단": "mega", "유지": "mega", "증액": "mega"}
DEPT_ICON = {"staffing": "people", "inventory": "box", "marketing": "mega", "cs": "phone", "refund": "card", "security": "shield"}
FIXED_STAFF = {"shop": 1, "warehouse": 1, "security": 2, "marketing": 3}


class Director:
    def __init__(self, app, world, fonts):
        self.app, self.w, self.f = app, world, fonts
        self.month = None
        self.d, self.t = 0, 0.0
        self.beats, self.bi = [], 0
        self.cash0 = self.cash = 0.0
        self.sat, self.stock = 0.7, 150.0
        self.guests = self.month_inc = 0
        self.done_month = False
        self.rng = random.Random(1)
        self._last_think = -9.0

    # ── 한 달 · 하루 ──────────────────────────────────────────────────────
    def load(self, month, cash0):
        self.month = month
        self.cash0 = self.cash = cash0
        self.month_inc = 0
        self.done_month = False
        self.w.actors.clear(); self.w.fx.clear()
        self.begin_day(0)

    def replace(self, month):
        """사장 지시가 바뀌어 다시 계산한 한 달. 지난 날과 오늘은 그대로이고 내일부터 달라집니다."""
        self.month = month

    @property
    def days(self):
        return self.month["days"]

    def day_log(self, d):
        return [x for x in self.month["log"] if x["day"] == d]

    def begin_day(self, d):
        self.d, self.t, self.bi = d, 0.0, 0
        self.guests = 0
        self.day_profit = 0.0
        day = self.days[d]
        prev = self.days[d - 1] if d else None
        self.sat = prev["sat"] if prev else 0.7
        self.stock = day["stock_morning"] - day["delivered"] if day["delivered"] else day["stock_morning"]
        self.w.stock = max(0.0, self.stock)
        self.w.used = {"cs": 0, "refund": 0, "review": 0}
        self.w.queue = {"cs": 0, "review": 0}
        self.w.ad_level = ["중단", "유지", "증액"].index(prev["marketing"]) if prev else 1
        self.w.seated = {}
        self._last_think = -9.0
        self.app.on_day_start(d)
        log = self.day_log(d)
        B = []
        if day["delivered"]:
            B.append((0.15, lambda s: self._truck(day, s)))
        if day["overflow_waste"]:
            B.append((0.9, lambda s: self._overflow(day, s)))
        morning = [x for x in log if x["dept"] in ("staffing", "inventory", "marketing")]
        for x, at in zip(morning, (T_STAFF, T_INV, T_MKT)):
            B.append((at, (lambda x: lambda s: self._morning(x, s))(x)))
        nref = 0
        for x in log:
            if x["dept"] in ("cs", "refund", "security"):
                at = T_DAY0 + x["t"] * T_DAYLEN
                if x["dept"] == "refund":
                    j = nref; nref += 1
                    lead = self._refund_lead(j, day)
                    B.append((max(T_STAFF + 0.2, at - lead), (lambda x, j, at: lambda s: self._refund_arrive(x, j, at, s))(x, j, at)))
                elif x["dept"] == "cs":
                    B.append((at - 0.9, (lambda x: lambda s: self._cs_ring(x, s))(x)))
                else:
                    B.append((at - 0.9, (lambda x: lambda s: self._packet(x, s))(x)))
                B.append((at, (lambda x: lambda s: self._event(x, s))(x)))
        eve = next(x for x in log if x["dept"] is None)
        B.append((T_EVE, lambda s: self._evening(eve, day, s)))
        B.append((T_REV, lambda s: self._revenue(eve, s)))
        B.append((T_SUM, lambda s: self._summary(day, s)))
        B.append((T_NIGHT, lambda s: self._leave(s)))
        B.append((DAY_LEN, lambda s: self._end(s)))
        B.sort(key=lambda b: b[0])
        self.beats = B

    def update(self, dt):
        if self.month is None or self.done_month:
            return
        self.t += dt
        self.w.p = min(1.0, self.t / DAY_LEN)
        d0 = self.d
        while self.bi < len(self.beats) and self.beats[self.bi][0] <= self.t:
            fn = self.beats[self.bi][1]; self.bi += 1
            fn(False)
            if self.d != d0 or self.done_month:      # 새 날이 시작됨
                return

    def skip_day(self):
        """오늘 남은 일을 숫자만 반영하고 넘깁니다."""
        d0 = self.d
        while self.bi < len(self.beats):
            fn = self.beats[self.bi][1]; self.bi += 1
            fn(True)
            if self.d != d0 or self.done_month:
                return

    def skip_month(self):
        m0 = self.month
        while not self.done_month and self.month is m0:      # 다음 달이 바로 시작되면 거기서 멈춥니다
            self.skip_day()

    # ── 아침 ──────────────────────────────────────────────────────────────
    def _truck(self, day, silent):
        def unload(truck):
            self.stock = day["stock_morning"]; self.w.stock = self.stock
            if not silent:
                self.w.popup(Popup(self.f, f"+{int(day['delivered'])}", self.w.ramp_x0 - 30, self.w.floor_y(-1) - 16, (240, 240, 230), icon="box"))
                self.app.sfx("truck")
        if silent:
            unload(None); return
        self.w.actors.append(Truck(self.w, day["delivered"], unload))

    def _overflow(self, day, silent):
        if silent: return
        self.w.popup(Popup(self.f, f"-{int(day['overflow_waste'])}", self.w.rx0 + 70, self.w.floor_y(-1) - 18, (255, 120, 100), icon="warn", life=1.6))

    def _think(self, x):
        """모델(7층)의 판단이 빛줄기가 되어 그 층으로 내려갑니다."""
        w = self.w
        if x["dept"] not in ("staffing", "inventory", "marketing") and self.t - self._last_think < 0.8:
            return
        self._last_think = self.t
        target = {"staffing": "cs", "inventory": "warehouse", "marketing": "marketing", "cs": "cs", "refund": "refund", "security": "security"}[x["dept"]]
        bx_, by_ = w.rx0 + 132, w.floor_y(6) - 12
        ty = w.floor_y(LEVEL[target]) - 14
        w.fx.append(Flyer(art.BEAM, [(bx_, by_), (bx_, ty)], 0.35 + 0.05 * (6 - LEVEL[target]),
                          (lambda k=target: w.flash.__setitem__(k, 0.6)), trail=True))

    def _morning(self, x, silent):
        self.cash += x["money"]
        self.app.on_decision(x, silent)
        if not silent: self._think(x)
        dept, a = x["dept"], x["action"]
        if dept == "staffing":
            cap = x["cap"]
            self.w.caps = {"cs": cap["즉시 처리"], "refund": cap["결제 담당 배정"], "review": cap["사람 확인"]}
            if not silent:
                self._staff_arrive()
                if x["money"]:
                    pass
        elif dept == "inventory":
            if not silent:
                self.w.flash["warehouse"] = 1.0
                if x["units"]:
                    self.w.popup(Popup(self.f, f"{x['units']}", self.w.rx0 + 56, self.w.floor_y(-1) - 18, (208, 249, 145), icon="truck", life=1.4))
        elif dept == "marketing":
            self.w.ad_level = ["중단", "유지", "증액"].index(a)
            if not silent:
                self.w.flash["marketing"] = 1.0
                pass

    def _staff_arrive(self):
        w = self.w
        plan = [(k, i) for k in ("cs", "refund", "review") for i in range(min(w.caps[k], w.max_desks(k)))]
        plan += [(k, i) for k, n in FIXED_STAFF.items() for i in range(n)]
        for n, (k, i) in enumerate(plan):
            look = art.staff_look(k, i)
            a = Actor(look, w.shaft_x, LEVEL[k], speed=60)
            a.hidden = True
            tx = self._seat_x(k, i)
            a.go(("wait", 0.02 * n), ("call", lambda me: setattr(me, "hidden", False)), ("walk", tx),
                 ("call", (lambda k, i, look: lambda me: self._sit(me, k, i, look))(k, i, look)))
            w.actors.append(a)

    def _seat_x(self, k, i):
        return self.w.seat_x(k, i)

    def _sit(self, actor, k, i, look):
        actor.alive = False
        self.w.seated.setdefault(k, {})[i] = look

    def _leave(self, silent):
        w = self.w
        if silent:
            w.seated = {}; return
        n = 0
        for k, seats in list(w.seated.items()):
            for i, look in seats.items():
                a = Actor(look, self._seat_x(k, i), LEVEL[k], speed=55)
                a.go(("wait", 0.05 * n), ("walk", w.shaft_x), ("elev", 0), ("walk", w.bx - 8), ("walk", -12), ("die",))
                w.actors.append(a); n += 1
        w.seated = {}

    # ── 낮 ────────────────────────────────────────────────────────────────
    def _refund_lead(self, j, day):
        w = self.w
        cap = max(1, day["cap"]["결제 담당 배정"])
        tx = w.desk_x("refund", j % min(cap, w.max_desks("refund")))
        return (abs((w.bx - 30) - w.shaft_x) + abs(tx - w.shaft_x)) / 46.0 + 0.42

    def _refund_arrive(self, x, j, at, silent):
        if silent: return
        w = self.w
        cap = max(1, w.caps.get("refund", 4))
        tx = w.desk_x("refund", j % min(cap, w.max_desks("refund")))
        look = art.Look(self.rng)
        a = Actor(look, w.bx - 30, 0, speed=46)
        a.go(("walk", w.shaft_x), ("elev", 2), ("walk", tx + 2))
        a.tag = x
        x["_actor"] = a
        w.actors.append(a)

    def _cs_ring(self, x, silent):
        if silent: return
        w = self.w
        i = self.rng.randrange(max(1, min(w.caps.get("cs", 4), w.max_desks("cs"))))
        dx = w.desk_x("cs", i)
        msg = x["ev"]["message"]                                   # 문의는 끝까지 보여 줍니다 (최대 세 줄)
        w.popup(Popup(self.f, " ", dx, w.floor_y(1) - 22, (240, 240, 230), icon="phone", life=0.9, rise=3))
        del msg
        x["_desk"] = dx
        self.app.sfx("ring")

    def _packet(self, x, silent):
        if silent: return
        w = self.w
        ax = w.bx + BW - 22
        y5 = w.floor_y(4)
        pts = [(ax, w.top - 26), (w.bx + BW + 6, w.top - 6), (w.bx + BW + 6, y5 - 14), (w.rx0 + 110, y5 - 14)]
        w.fx.append(Flyer(art.PACKET if x["truth"] == "정상" else art.PACKET, pts, 0.85))

    def _event(self, x, silent):
        self.cash += x["money"]
        self.month_inc += x["incidents"]
        self.sat = x["sat_after"]
        self.guests += 1
        self.app.on_decision(x, silent)
        if silent:
            return
        self._think(x)
        dept = x["dept"]
        getattr(self, "_ev_" + dept)(x)

    def _money_pop(self, x, px, py, delay=0.0):
        if abs(x["money"]) >= 0.95:
            good = x["money"] >= 0
            self.w.popup(Popup(self.f, man(x["money"], True), px, py, (208, 249, 145) if good else (255, 120, 100), delay=delay))

    def _ev_cs(self, x):
        w = self.w
        a, y1 = x["action"], w.floor_y(1)
        dx = x.get("_desk", w.desk_x("cs", 0))
        pass
        if a == "즉시 처리":
            w.used["cs"] += 1; w.flash["cs"] = 0.6
        elif a == "일반 처리":
            w.queue["cs"] += 1
        elif a == "결제 담당 배정":
            w.used["refund"] += 1
            pts = [(dx, y1 - 10), (w.shaft_x + 6, y1 - 10), (w.shaft_x + 6, w.floor_y(2) - 10), (w.desk_x("refund", 0), w.floor_y(2) - 10)]
            w.fx.append(Flyer(art.PLANE, pts, 0.9, lambda: w.flash.__setitem__("refund", 0.5)))
        else:
            w.used["review"] += 1
            pts = [(dx, y1 - 10), (w.shaft_x + 6, y1 - 10), (w.shaft_x + 6, w.floor_y(3) - 10), (w.desk_x("review", 0), w.floor_y(3) - 10)]
            w.fx.append(Flyer(art.PLANE, pts, 1.0, lambda: w.flash.__setitem__("review", 0.5)))
        if x["overflow"]:
            key = {"즉시 처리": "cs", "결제 담당 배정": "refund", "사람 확인": "review"}.get(a, "cs")
            w.alarm[key] = 0.6
            w.popup(Popup(self.f, " ", w.rx0 + 60, w.floor_y(LEVEL[key]) - 20, (255, 120, 100), icon="warn", life=1.0))
        if x["incidents"]:
            w.alarm["cs"] = 1.8
            w.popup(Popup(self.f, " ", w.rx0 + 90, y1 - 22, (255, 90, 80), icon="alarm", life=1.6, rise=6))
            self.app.sfx("alarm")
            self.w.ceo_mood = "sad"
        self._money_pop(x, dx, y1 - 14, 0.3)

    def _ev_refund(self, x):
        w = self.w
        act, eff, truth = x["action"], x.get("effective"), x["truth"]
        actor = x.get("_actor")
        y2 = w.floor_y(2)
        ev = x["ev"]
        px = actor.x if actor else w.desk_x("refund", 0)
        tier = " VIP" if ev["tier"] == "VIP" else ""
        if actor: actor.say("card", 1.0)
        del tier
        w.used["refund"] += 1 if eff in ("전액 환불", "부분 환불") else 0
        w.flash["refund"] = 0.5

        def outcome(me=None):
            if eff in ("전액 환불", "부분 환불"):
                if truth == "악용":
                    self._react(actor, "devil")
                else:
                    self._react(actor, "smile"); w.fx.append(Coins(px, y2 - 12, 3, seed=int(px)))
            else:
                if truth == "악용":
                    self._react(actor, "shield")
                else:
                    self._react(actor, "angry")
            self._money_pop(x, px, y2 - 14, 0.4)
            if actor:
                actor.go(("walk", w.shaft_x), ("elev", 0), ("walk", w.bx - 6), ("walk", -12), ("die",))

        if act == "사람 확인" and actor:
            w.used["review"] += 1
            if x["overflow"] and not x.get("effective") == "거절":
                w.queue["review"] += 1; w.alarm["review"] = 0.6
            rx = w.desk_x("review", self.rng.randrange(max(1, min(w.caps.get("review", 4), 11))))
            actor.say("search", 0.8)
            actor.go(("walk", w.shaft_x), ("elev", 3), ("walk", rx + 3), ("wait", 0.6), ("call", lambda me: outcome()))
        else:
            if actor:
                actor.go(("wait", 0.5), ("call", lambda me: outcome()))
            else:
                outcome()

    def _react(self, actor, icon):
        if actor: actor.say(icon, 1.4)

    def _ev_security(self, x):
        w = self.w
        y5 = w.floor_y(4)
        act, eff, truth = x["action"], x.get("effective"), x["truth"]
        sx = w.rx0 + 110
        w.flash["security"] = 0.5
        amt = int(x["ev"]["amount"])
        if act == "사람 확인":
            pts = [(sx, y5 - 12), (w.shaft_x + 6, y5 - 12), (w.shaft_x + 6, w.floor_y(3) - 10), (w.desk_x("review", 1), w.floor_y(3) - 10)]
            w.fx.append(Flyer(art.PACKET, pts, 0.8))
            w.used["review"] += 1
        if eff == "허용" and truth == "사기":
            w.alarm["security"] = 2.4
            thief = Actor(art.thief_look(), w.rx0 + 30, 4, speed=80)
            thief.carry = art.BAG
            thief.go(("wait", 0.3), ("walk", w.shaft_x), ("elev", 0), ("walk", w.bx - 10), ("walk", -14), ("die",))
            w.actors.append(thief)
            w.popup(Popup(self.f, f"-{amt}만", sx, y5 - 22, (255, 90, 80), icon="alarm", life=1.8, rise=6))
            self.app.sfx("alarm")
            self.w.ceo_mood = "sad"
            x = dict(x, money=0.0)                 # 금액은 위 글자에 이미 있습니다
        elif eff == "차단":
            if truth == "사기":
                w.popup(Popup(self.f, " ", sx, y5 - 22, (208, 249, 145), icon="shield", life=1.0)); self.app.sfx("block")
            else:
                w.popup(Popup(self.f, " ", sx, y5 - 22, (255, 190, 120), icon="sad", life=1.0))
        elif act != "사람 확인":
            w.popup(Popup(self.f, " ", sx, y5 - 22, (170, 200, 190), icon="check", life=0.7, rise=3))
        if x["overflow"]:
            w.popup(Popup(self.f, " ", w.rx0 + 60, w.floor_y(3) - 20, (255, 160, 120), icon="warn", life=1.0))
        self._money_pop(x, sx + 40, y5 - 12, 0.5)

    # ── 저녁 ──────────────────────────────────────────────────────────────
    def _evening(self, eve, day, silent):
        self.app.on_evening(eve, silent)
        if silent:
            return
        w = self.w
        demand, sales = eve["demand"], eve["sales"]
        n = max(3, min(28, int(round(demand / 3))))
        served = int(round(n * sales / demand)) if demand else n
        shop_l, shop_r = w.rx0 + 12, w.rx0 + 12 + 22 * (4 + min(2, w.upg.get("demand", 0))) - 6
        order = list(range(n)); self.rng.shuffle(order)
        for k, i in enumerate(order):
            ok = i < served
            a = Actor(art.Look(self.rng), -10 - self.rng.random() * 30, 0, speed=44 + self.rng.random() * 14)
            shelf = self.rng.uniform(shop_l, shop_r)

            def pick(me, ok=ok):
                if ok:
                    me.carry = art.BOX
                    me.go(("walk", w.rx1 - 32), ("wait", 0.15), ("call", lambda m: self._paid(m)), ("walk", w.bx - 4), ("walk", -14), ("die",))
                else:
                    me.say("angry", 1.6)
                    me.go(("walk", w.bx - 4), ("walk", -14), ("die",))
            a.go(("wait", k * 0.16), ("walk", w.bx - 2), ("walk", shelf), ("wait", 0.25), ("call", pick))
            w.actors.append(a)

    def _paid(self, me):
        if self.rng.random() < 0.4:
            self.w.fx.append(Coins(me.x, self.w.gy - 14, 2, seed=int(me.x)))
            self.app.sfx("coin")

    def _revenue(self, eve, silent):
        self.cash += eve["money"]
        self.stock = self.days[self.d]["stock"]; self.w.stock = self.stock
        if silent: return
        w = self.w
        w.popup(Popup(self.f, man(eve["revenue"], True), w.rx1 - 30, w.gy - 26, (208, 249, 145), life=2.0, icon="coin"))
        self.app.sfx("cash")

    def _summary(self, day, silent):
        self.day_profit = day["profit"]
        self.cash = self.cash0 + sum(d["profit"] for d in self.days[:self.d + 1])     # 반올림 오차 없이 엔진과 맞춥니다
        self.sat = day["sat"]
        self.app.on_day_end(self.d, day, silent)
        if silent: return
        w = self.w
        good = day["profit"] >= 0
        w.popup(Popup(self.f, man(day["profit"], True), w.bx + 113, w.top - 50, (208, 249, 145) if good else (255, 110, 100), life=2.6, big=True, rise=10))
        w.ceo_mood = "happy" if good and day["incidents"] == 0 else "sad" if not good else "idle"

        if day["waste"] > 0 and day["waste"] > day["overflow_waste"]:
            pass

    def _end(self, silent):
        if self.d < len(self.days) - 1:
            self.begin_day(self.d + 1)
            self.t = 0.0
        else:
            self.done_month = True
            self.app.on_month_end()
