# -*- coding: utf-8 -*-
"""AI 사장 키우기 · 게임 본체

한 달 = 엔진이 계산한 20일. 사장(나 또는 AI)의 판단은 모두 JEV 요청 · 응답으로 오갑니다.
나의 지시가 바뀌면 그 달을 다시 계산하고(결정적이라 지난 날은 그대로), 내일부터 새 지시가 적용됩니다.
"""
import glob
import json
import os
import random
import re
import threading

import pygame

import connect_tycoon as ct
from .. import jev as J
from ..career import ACH, UPG, Career, home
from . import art, screens
from .audio import Audio
from .director import Director
from .pixel import Canvas, Fonts, man, won
from .studio import Studio
from .trainer import TeamSearch, Trainer
from .ui import UI, Toasts
from .world import World

PANEL_W = 216
MIN_W, MIN_H = 640, 360
TEST_MONTHS = range(7000, 7010)
BRAIN_TIES = [(208, 249, 145), (118, 214, 224), (252, 214, 92), (246, 168, 194), (156, 116, 216), (244, 152, 64)]


def slug(s):
    s = re.sub(r"[^\w가-힣-]+", "-", s.strip()).strip("-").lower()
    return s or "my-brain"


class App:
    def __init__(self, brains=(), size=(1280, 800), fullscreen=False, headless=False, reset=False):
        pygame.init()
        self.headless = headless
        self.win = None
        title = "AI 사장 키우기 · CONNECT TYCOON"
        icon = pygame.transform.scale(art.brain_ceo("happy"), (36, 38))
        if not headless and hasattr(pygame, "Window"):
            # 레티나 화면에서도 도트가 또렷하도록 실제 픽셀 크기로 그립니다
            self.win = pygame.Window(title, size, resizable=True, allow_high_dpi=True)
            try: self.win.set_icon(icon)
            except pygame.error: pass
            if fullscreen: self.win.set_fullscreen(desktop=True)
            self.window = self.win.get_surface()
        else:
            flags = pygame.RESIZABLE | (pygame.FULLSCREEN if fullscreen else 0)
            self.window = pygame.display.set_mode(size, flags)
            pygame.display.set_caption(title)
            try: pygame.display.set_icon(icon)
            except pygame.error: pass
        pygame.key.stop_text_input()
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()
        self.ui = UI(self.fonts)
        self.toasts = Toasts(self.fonts)
        self.world = World(self.fonts)
        self.director = Director(self, self.world, self.fonts)
        self.trainer = Trainer()
        self.teamsearch = TeamSearch()
        self.studio = Studio(self)
        self.saved = None if reset else Career.load()
        self.career = self.saved or Career()
        st = self.career.settings
        self.audio = Audio(sfx=st.get("sfx", True), music=st.get("music", True)) if not headless else Audio(False, False)
        self.speed = st.get("speed", 2)
        self.paused = False
        intuition_brain = ct.CompanyBrain.default()
        self.base = ct.Company(intuition_brain.intuition, ct.load_pool())
        self.roster = self._load_roster(intuition_brain, brains)
        self.refresh_team()
        self.screen, self.modal, self.modal_data = "title", None, {}
        self.feed, self.selected = [], None
        self.schedule = [dict(self.career.owner) for _ in range(20)]
        self.month = None
        self.news = None
        self.rank = {"rows": [], "pending": [], "key": None}
        self.hub = {"text": "", "busy": False, "result": None}
        self.lab = {"values": {"이익": 1.0, "고객 만족": 1.0, "위험": 1.0}, "teacher": "지금 AI 사장", "length": "보통", "name": "내 AI 사장"}
        self.help_page = 0
        self.new_name = "Connect AI Company"
        self.inspect = None
        self.jev_scroll = 0
        self.hints_shown = set()
        self.t_real = 0.0
        self.quit = False
        self.ratio = 1.0
        self.layout()
        self._attract()

    # ── 두뇌 목록 ─────────────────────────────────────────────────────────
    def _load_roster(self, default_brain, extra):
        R = [{"id": "rule", "name": "규칙 사장", "kind": "rule", "source": "사람이 정한 규칙", "tie": (150, 160, 150)},
             {"id": default_brain.name, "name": "제이의 AI 사장", "kind": "brain", "brain": default_brain, "source": "예시 · CONNECT AI LAB", "tie": BRAIN_TIES[0]}]
        seen = {r["id"] for r in R}
        for path in sorted(glob.glob(os.path.join(home(), "brains", "*.json"))):
            try:
                b = ct.CompanyBrain.from_file(path)
            except Exception:
                continue
            if b.name in seen: continue
            seen.add(b.name)
            meta = b.spec.get("company", {}).get("game", {})
            R.append({"id": b.name, "name": meta.get("title", b.name), "kind": "brain", "brain": b, "source": meta.get("source", "내가 키운 두뇌"),
                      "path": path, "tie": BRAIN_TIES[len(R) % len(BRAIN_TIES)]})
        for ref in extra:
            try:
                self._add_brain(ct.CompanyBrain.load(ref), source=ref, save=False, roster=R)
            except Exception as e:
                print("두뇌를 불러오지 못했습니다:", ref, e)
        return R

    def _add_brain(self, brain, source, title=None, save=True, roster=None):
        roster = roster if roster is not None else self.roster
        for r in roster:
            if r["id"] == brain.name:
                r.update(brain=brain, source=source)
                return r
        meta = brain.spec.setdefault("company", {}).setdefault("game", {})
        meta.update({"title": title or meta.get("title") or brain.name, "source": source})
        path = None
        if save:
            path = brain.save(os.path.join(home(), "brains", slug(brain.name) + ".json"))
        r = {"id": brain.name, "name": meta["title"], "kind": "brain", "brain": brain, "source": source, "path": path,
             "tie": BRAIN_TIES[len(roster) % len(BRAIN_TIES)]}
        roster.append(r)
        return r

    def refresh_team(self):
        """두뇌 연합을 두뇌 목록에 (부서마다 다른 두뇌)."""
        ids = {r["id"] for r in self.roster if r["kind"] != "team"}
        team = {d: rid for d, rid in self.career.team.items() if rid in ids}
        self.career.team = team
        self.roster = [r for r in self.roster if r["kind"] != "team"]
        if team:
            self.roster.append({"id": "team", "name": "두뇌 연합", "kind": "team", "source": "부서마다 다른 두뇌 · Connect AI", "tie": (246, 168, 194)})
        if hasattr(self, "rank"):
            self.rank["key"] = None

    def team_members(self):
        base = self.career.ai if self.career.ai != "team" and self.entry(self.career.ai)["kind"] == "brain" else "jay-company"
        return {d: self.career.team.get(d, base) for d in ct.DEPT_ORDER}

    def team_start(self):
        specs = {r["id"]: (r["brain"].spec if r["kind"] == "brain" else None) for r in self.roster if r["kind"] != "team"}
        self.teamsearch.start(self.career.config, specs, ct.train.VAL_SEEDS)
        self.sfx("click")

    def team_poll(self):
        st = self.teamsearch.poll()
        if st == "done":
            res = self.teamsearch.result
            self.career.team = dict(res["assign"])
            self.refresh_team()
            singles = self.teamsearch.singles or {}
            best_single = max(singles.values()) if singles else -1e9
            self.toast(f"두뇌 연합 완성 · 검증 달 {man(res['best'])}원 (혼자 최고 {man(best_single)}원)", "good", "ant")
            if res["best"] > best_single + 1e-6:
                self.unlock("colony")
            self.sfx("level")
        elif st == "error":
            self.toast("연합 찾기 오류: " + self.teamsearch.error["error"][:60], "bad", "warn")

    def entry(self, rid):
        for r in self.roster:
            if r["id"] == rid: return r
        return self.roster[1]

    def policy_for(self, rid, company, keep=False):
        e = self.entry(rid)
        if e["kind"] == "rule":
            return ct.RulePolicy()
        if e["kind"] == "team":
            return ct.TeamPolicy({d: self.policy_for(m, company, keep) for d, m in self.team_members().items() if m != "team"})
        return J.JevPolicy(e["brain"], values=company.values, config=company.cfg, keep=keep, check=False)

    # ── 한 달 계산 ────────────────────────────────────────────────────────
    @property
    def seed(self):
        return 7000 + self.career.month - 1

    def company(self):
        return self.base.with_config(self.career.config, profile=self.career.profile)

    def compute_month(self, mode=None, rid=None, seed=None, schedule=None, keep=True):
        co = self.company()
        mode = mode or self.career.mode
        seed = self.seed if seed is None else seed
        if mode == "owner":
            pol = ct.OwnerPolicy(schedule or self.schedule, demand_scale=co.cfg["base_demand"] / 40.0)
            ceo = "내 경영"
        else:
            rid = rid or self.career.ai
            pol = self.policy_for(rid, co, keep=keep)
            ceo = self.entry(rid)["name"]
        log, days = co.run_month(seed, pol)
        if keep and (isinstance(pol, J.JevPolicy) or hasattr(pol, "trace")):
            asked = [x for x in log if x["dept"] is not None and not x["ruled"]]
            for x, rec in zip(asked, getattr(pol, "trace", None) or pol.log):
                if rec is not None: x["jev"] = rec
        return {"seed": seed, "log": log, "days": days, "mode": mode, "ceo": ceo, "rid": rid, "config": co.cfg, "values": co.values,
                "no": self.career.month}

    def start_month(self, restart=False):
        c = self.career
        if not restart:
            opened = c.open_new_month()
            for k in opened:
                self.toast(f"공사 완료 · {UPG[k]['name']} {c.upgrades[k]}단계 문을 열었습니다", "gold", UPG[k]["icon"])
            self.schedule = [dict(c.owner) for _ in range(20)]
        self.world.upg = dict(c.upgrades)
        self.world.queued = {UPG[k]["floor"] for k in c.queued}
        self.world.company_name = c.company
        self.world.warehouse = c.config["warehouse"]
        self.world.ceo_mode = c.mode
        self.world.season = season_of(c.month)
        self.feed, self.selected = [], None
        self.studio.review = None                  # 새 달이 시작되면 열려 있던 사람 확인 카드는 닫습니다
        self.month = self.compute_month()
        self.director.load(self.month, c.cash)
        self.screen, self.modal = "play", None
        self.paused = False
        self.rank["key"] = None

    def restart_with(self, mode, rid=None):
        self.career.mode = mode
        if rid: self.career.ai = rid
        self.start_month(restart=True)
        who = "내가 직접" if mode == "owner" else self.entry(self.career.ai)["name"]
        self.toast(f"{self.career.month}월을 처음부터 · 사장: {who}", "info", "boss" if mode == "owner" else "brain")

    def set_owner(self, key, value):
        """사장 지시 변경 · 내일부터."""
        if self.career.owner.get(key) == value: return
        self.career.owner[key] = value
        d = self.director.d
        for i in range(d + 1, 20):
            self.schedule[i] = dict(self.schedule[i], **{key: value})
        if self.career.mode == "owner" and self.month:
            self.month = self.compute_month()
            self.director.replace(self.month)
        self.sfx("click")
        self.toast(f"지시 변경 · {screens.OWNER_LABEL[key]} {value} · 내일부터", "info", "news")

    def buy(self, key):
        c = self.career
        ok, cost = c.can_buy(key)
        if not ok:
            self.sfx("fail"); return
        c.buy(key)
        self.director.cash -= cost; self.director.cash0 -= cost
        self.world.queued.add(UPG[key]["floor"])
        self.sfx("buy")
        self.toast(f"{UPG[key]['name']} 공사 시작 · {won(-cost)} · 다음 달 1일에 문을 엽니다", "gold", "hammer")
        self.unlock("invest")

    # ── 엔진 → 화면 소식 ─────────────────────────────────────────────────
    def on_day_start(self, d):
        no = (self.month or {}).get("no", 1) if self.screen == "play" else getattr(self, "_attract_no", 1)
        self.world.weather = weather_of(no, d)
        if self.screen != "play": return
        hints = {0: ("오른쪽 '사장 지시'를 바꿔 보세요. 바꾼 지시는 내일 아침부터 적용됩니다", "owner"),
                 2: ("맨 위층 사장실에서 판단이 내려갑니다. 판단 하나하나가 JEV 요청과 응답입니다", None),
                 4: ("돈을 모아 '회사 키우기'로 업그레이드하고, '두뇌 훈련소'에서 AI 사장을 키우세요", None)}
        if self.career.month == 1 and d in hints and d not in self.hints_shown:
            text, need = hints[d]
            if need is None or need == self.career.mode:
                self.hints_shown.add(d); self.toast(text, "info", "help")

    def on_decision(self, x, silent):
        if self.screen not in ("play", "title"): return
        if self.screen == "play":
            self.studio.on_decision(x, silent)
        item = {"x": x, "day": x["day"]}
        self.feed.append(item)
        if len(self.feed) > 60: self.feed = self.feed[-60:]
        if not silent:
            self.world.ceo_mood = "think"
            self.world.flash["ceo"] = 0.35
            self._mood_reset = self.t_real + 0.6
            if self.screen == "play" and self.career.mode == "ai" and x["dept"] in ("staffing", "inventory", "marketing"):
                self.sfx("think")

    def on_evening(self, eve, silent):
        pass

    def on_day_end(self, d, day, silent):
        if self.screen != "play": return
        if self.unlock("open"): pass

    def on_month_end(self):
        if self.screen != "play":
            self._attract(); return
        if True:                                   # 학습 화면: 결산 창 없이 다음 달로 (모델은 계속 일합니다)
            c = self.career
            c.cash = self.director.cash
            c.close_month(sum(d["profit"] for d in self.month["days"]), summarize(self.month["days"]))
            self.studio.save_state()
            c.save()
            self.start_month()
            return
        c, m = self.career, self.month
        days = m["days"]
        profit = sum(d["profit"] for d in days)
        c.cash = self.director.cash
        played = summarize(days)
        rows = [(m["ceo"], "me", played)]
        co = self.company()
        if m["mode"] == "owner":
            alt = self.compute_month(mode="ai", keep=False)
            rows.append((alt["ceo"], "ai", summarize(alt["days"])))
        else:
            alt = self.compute_month(mode="owner", schedule=[dict(c.owner)] * 20, keep=False)
            rows.append(("내 지시 (지금 설정)", "owner", summarize(alt["days"])))
        if not (m["mode"] == "ai" and m.get("rid") == "rule"):
            rule_days = co.run_month(m["seed"], ct.RulePolicy())[1]
            rows.append(("규칙 사장", "rule", summarize(rule_days)))
        rows.sort(key=lambda r: -r[2]["profit"])
        merged = []
        for row in rows:                          # 결과가 똑같으면 한 줄로 (예: 기본 지시 = 규칙 사장)
            same = next((m_ for m_ in merged if m_[2] == row[2] and m_[1] != "me" and row[1] != "me"), None)
            if same:
                merged[merged.index(same)] = (same[0] + " = " + row[0], same[1], same[2])
            else:
                merged.append(row)
        rows = merged
        lv_before = c.level[0]
        c.close_month(profit, dict(played, ceo=m["ceo"], mode=m["mode"]))
        unlocked = []
        checks = [("black", profit > 0), ("m1000", profit >= 1000), ("m2000", profit >= 2000), ("m5000", profit >= 5000),
                  ("safe", played["incidents"] == 0), ("stock", played["stockout_days"] == 0), ("love", played["sat"] >= 0.95),
                  ("b1", c.earned >= 10000), ("unicorn", c.earned >= 300000)]
        me = played["profit"]
        other = next((r for r in rows if r[1] in ("ai", "owner")), None)
        if other:
            if m["mode"] == "owner" and other[2]["profit"] > me: checks.append(("ai_win", True))
            if m["mode"] == "owner" and me > other[2]["profit"]: checks.append(("human_win", True))
            if m["mode"] == "ai" and me > other[2]["profit"]: checks.append(("ai_win", True))
        for k, ok in checks:
            if ok and self.unlock(k, quiet=True): unlocked.append(k)
        lv_after = c.level[0]
        self.news = {"month": c.month - 1, "rows": rows, "played": played, "profit": profit, "mode": m["mode"], "ceo": m["ceo"],
                     "unlocked": unlocked, "levelup": lv_after > lv_before, "level": c.level, "days": days}
        self.world.trophies = len(c.achievements)
        c.save()
        self.modal = "news"
        self.sfx("level" if self.news["levelup"] else "trophy" if unlocked else "cash")

    def unlock(self, key, quiet=False):
        if self.screen != "play" and key not in ("trained", "hub", "jev", "invest", "colony"):
            return False
        if self.career.unlock(key):
            a = ACH[key]
            self.world.trophies = len(self.career.achievements)
            if not quiet:
                self.toast(f"업적 · {a[1]} — {a[2]}", "gold", "trophy"); self.sfx("trophy")
            return True
        return False

    # ── 소리 · 알림 ───────────────────────────────────────────────────────
    def sfx(self, name):
        if self.screen == "play" and not (self.paused or self.modal):
            self.audio.play(name)
        elif name in ("click", "buy", "fail", "trophy", "level", "cash", "page"):
            self.audio.play(name)

    def toast(self, text, kind="info", icon=None):
        if kind in ("good", "bad"):                # 학습 화면에서는 꼭 필요한 알림만
            self.toasts.push(text, kind, icon)

    # ── 두뇌 랭킹 (한 프레임에 한 달씩 계산) ─────────────────────────────
    def rank_start(self):
        cfg = self.career.config
        self.rank = {"rows": [], "pending": [], "key": json.dumps(cfg, sort_keys=True), "cfg": cfg}
        co = self.company()
        jobs = [("owner", "내 지시 (지금 설정)", None)] + [(r["id"], r["name"], r) for r in self.roster]
        for rid, name, _r in jobs:
            pol = ct.OwnerPolicy(dict(self.career.owner), demand_scale=co.cfg["base_demand"] / 40.0) if rid == "owner" else self.policy_for(rid, co)
            self.rank["pending"].append({"id": rid, "name": name, "pol": pol, "months": [], "seeds": list(TEST_MONTHS)})
        self.rank["co"] = co

    def rank_step(self, budget_ms=12):
        R = self.rank
        if not R.get("pending"): return
        t0 = pygame.time.get_ticks()
        while R["pending"] and pygame.time.get_ticks() - t0 < budget_ms:
            job = R["pending"][0]
            seed = job["seeds"].pop(0)
            job["months"].append(summarize(R["co"].run_month(seed, job["pol"])[1]))
            if not job["seeds"]:
                ms = job["months"]
                R["rows"].append({"id": job["id"], "name": job["name"], **{k: sum(m[k] for m in ms) / len(ms) for k in ms[0] if k != "curve"}})
                R["pending"].pop(0)
                R["rows"].sort(key=lambda r: -r["profit"])

    # ── Hugging Face · 파일 ───────────────────────────────────────────────
    def hub_load(self, text):
        repo = text.strip()
        if not repo or self.hub["busy"]: return
        self.hub.update(busy=True, result=None)

        def work():
            try:
                b = ct.CompanyBrain.from_hub(repo)
                self.hub["result"] = ("ok", b, repo)
            except Exception as e:
                self.hub["result"] = ("err", str(e), repo)
        threading.Thread(target=work, daemon=True).start()

    def hub_poll(self):
        res = self.hub.get("result")
        if not res: return
        self.hub.update(result=None, busy=False)
        if res[0] == "ok":
            r = self._add_brain(res[1], source=f"hf:{res[2]}", title=res[1].name)
            self.toast(f"허깅페이스에서 두뇌를 불러왔습니다 · {r['name']}", "good", "hf")
            self.unlock("hub"); self.rank["key"] = None
        else:
            self.toast(f"불러오지 못했습니다 · {res[1][:60]}", "bad", "warn")

    def drop_file(self, path):
        if self.screen == "play":                     # 학습 화면: 그 brain.json에서 이어서 학습
            self.studio.load_file(path); return
        try:
            b = ct.CompanyBrain.from_file(path)
        except Exception as e:
            self.toast(f"회사 두뇌(brain.json)가 아닙니다 · {str(e)[:50]}", "bad", "warn"); return
        r = self._add_brain(b, source=os.path.basename(path), title=b.name)
        self.toast(f"두뇌를 불러왔습니다 · {r['name']}", "good", "brain")
        self.unlock("hub"); self.rank["key"] = None

    # ── 두뇌 훈련소 ───────────────────────────────────────────────────────
    def lab_start(self):
        L = self.lab
        iters, mpi = {"빠르게": (30, 12), "보통": (60, 24), "꼼꼼히": (120, 24)}[L["length"]]
        start = self.lab_start_brain()
        teacher = dict(self.career.owner) if L["teacher"] == "내 지시" else None
        self.lab["base_spec"] = start.spec if start else self.entry("jay-company")["brain"].spec
        self.trainer.start(self.career.config, L["values"], teacher, iterations=iters, months_per_iter=mpi, seed=random.randrange(10000),
                           start_spec=start.spec if start else None)
        self.sfx("click")

    def lab_start_brain(self):
        """'지금 AI 사장'에서 이어서 훈련할 두뇌 (규칙 사장이 앉아 있으면 없음)."""
        if self.lab["teacher"] != "지금 AI 사장": return None
        e = self.entry(self.career.ai)
        return e.get("brain") if e["kind"] == "brain" else None

    def lab_poll(self):
        st = self.trainer.poll()
        if st == "done":
            res = self.trainer.result
            pol = ct.LinearPolicy.from_json(res["policy"])
            name = self.lab["name"].strip() or "내 AI 사장"
            spec = ct.CompanyBrain.make_spec(self.lab.get("base_spec") or self.entry("jay-company")["brain"].spec, pol, name=slug(name), values=self.lab["values"],
                                             researcher="CONNECT TYCOON 플레이어", config=self.career.config,
                                             results={"test_months": list(TEST_MONTHS), "profit": res["results"]["new"]["profit"],
                                                      "teacher_profit": res["results"]["teacher"]["profit"]})
            brain = ct.CompanyBrain(spec)
            r = self._add_brain(brain, source="두뇌 훈련소", title=name)
            self.lab["trained_id"] = r["id"]
            self.toast(f"새 AI 사장 · {name} · 한 달 {man(res['results']['new']['profit'])}원", "good", "brain")
            self.unlock("trained"); self.sfx("level")
            self.rank["key"] = None
        elif st == "error":
            self.toast("훈련 중 오류: " + self.trainer.error["error"][:60], "bad", "warn")

    # ── JEV 기록 ─────────────────────────────────────────────────────────
    def jev_pair(self, x):
        """판단 하나의 (요청, 응답). AI 달은 실제로 오간 것, 내 지시와 규정은 같은 모양으로 만들어 보여 줍니다."""
        if x.get("jev"):
            return x["jev"]["request"], x["jev"]["response"]
        m = self.month or {}
        req = J.request(x["dept"], x["ev"], m.get("values"), m.get("config"))
        keys = ct.DEPTS[x["dept"]]["keys"]
        k = keys[ct.DEPTS[x["dept"]]["actions"].index(x["action"])]
        who = "회사 규정" if x["ruled"] else "사람 사장의 지시" if m.get("mode") == "owner" else "규칙 사장"
        resp = J.answer(x["dept"], [1.0 if kk == k else 0.0 for kk in keys], model="connect-tycoon/owner" if m.get("mode") == "owner" else "connect-tycoon/rule",
                        reason=who, choice=k)
        return req, resp

    def jev_export(self):
        m = self.month
        if not m: return None
        rows = []
        day_total = {}
        for x in m["log"]:
            day_total[x["day"]] = day_total.get(x["day"], 0.0) + x["reward"]
        for x in m["log"]:
            if x["dept"] is None or x["day"] > self.director.d: continue
            req, resp = self.jev_pair(x)
            rows.append({"env": J.ENV_ID, "seed": m["seed"], "day": x["day"], "department": x["dept"], "ceo": m["ceo"], "ruled": x["ruled"],
                         "request": req, "response": resp, "reward": round(x["reward"], 6), "day_reward": round(day_total[x["day"]], 6),
                         "outcome": {k: x[k] for k in ("truth", "effective", "overflow", "money", "dsat", "incidents") if k in x}})
        path = os.path.join(home(), "jev", f"month{self.career.month:02d}-{slug(m['ceo'])}.jsonl")
        J.write_jsonl(rows, path)
        self.unlock("jev")
        self.toast(f"JEV 기록 {len(rows)}줄 저장 · {path}", "good", "save")
        return path

    # ── 타이틀 화면 뒤에서 도는 회사 ─────────────────────────────────────
    def _attract(self):
        self.world.upg, self.world.queued = {}, set()
        self.world.ceo_mode = "ai"
        self.world.warehouse = 250.0
        co = self.base
        brain = self.entry("jay-company")["brain"]
        seed = random.randrange(7100, 7999)
        self._attract_no = random.randrange(1, 13)
        self.world.season = season_of(self._attract_no)
        pol = J.JevPolicy(brain, values=co.values, config=co.cfg, keep=True, check=False)
        log, days = co.run_month(seed, pol)
        for x, rec in zip([x for x in log if x["dept"] is not None and not x["ruled"]], pol.log):
            x["jev"] = rec
        m = {"seed": seed, "log": log, "days": days, "mode": "ai", "ceo": "데모", "rid": "jay-company", "config": co.cfg, "values": co.values}
        self.director.load(m, 0.0)
        self.director.t = 3.0

    # ── 메인 루프 ─────────────────────────────────────────────────────────
    def layout(self):
        if self.win is not None:
            self.window = self.win.get_surface()
        W, H = self.window.get_size()
        self.ratio = W / self.win.size[0] if self.win is not None and self.win.size[0] else 1.0
        s = max(1, min(W // MIN_W, H // MIN_H))
        vw, vh = W // s, H // s
        if getattr(self, "canvas", None) is None or self.canvas.get_size() != (vw, vh):
            self.canvas = Canvas((vw, vh))
        self.scale, self.vw, self.vh = s, vw, vh
        self.fonts.scale = s
        self.offset = ((W - vw * s) // 2, (H - vh * s) // 2)
        self.panel = self.screen == "play" and vw >= 560
        ww = vw - PANEL_W if self.panel else vw
        self.world.resize(ww, vh, "right" if self.screen == "title" else "center")
        self.world.show_tags = self.screen != "title"
        self.world_rect = pygame.Rect(0, 0, ww, vh)

    def step(self, dt, events):
        self.t_real += dt
        self.layout()
        self.ui.begin(events, self.scale, self.offset, self.ratio)
        for e in events:
            if e.type == pygame.QUIT or e.type == getattr(pygame, "WINDOWCLOSE", -1):
                self.quit = True
            elif e.type == pygame.DROPFILE:
                self.drop_file(e.file)
            elif e.type == getattr(pygame, "WINDOWFOCUSLOST", -1) and self.screen == "play" and not self.paused:
                self.paused, self._autopaused = True, True          # 다른 창을 보면 잠깐 멈춥니다
            elif e.type == getattr(pygame, "WINDOWFOCUSGAINED", -1) and getattr(self, "_autopaused", False):
                self.paused, self._autopaused = False, False
            elif e.type == pygame.KEYDOWN and self.ui.focus is None:
                self.key(e.key)
        if self.ui.focus and (pygame.K_ESCAPE in self.ui.keys or self.ui.released and not self.ui.hover_any):
            pass
        # 층을 누르면 부서 카드
        if self.screen == "play" and self.modal is None and self.ui.released and not self.ui.hover_any:
            mx, my = self.ui.mouse
            if self.world_rect.collidepoint(mx, my) and not getattr(self, "_card_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(mx, my):
                key = self.world.floor_at(mx, my)
                if key == "roof": key = "marketing"
                self.inspect = None if key == self.inspect else key
                if key: self.sfx("click")
        # 게임 시간
        running = self.screen == "title" or (self.screen == "play" and not self.paused and self.modal is None and not self.studio.review)
        gdt = dt * (self.speed if self.screen == "play" else 1.6) if running else 0.0
        self.director.update(gdt)
        self.world_update(gdt, dt)
        if getattr(self, "_mood_reset", 0) and self.t_real > self._mood_reset and self.world.ceo_mood == "think":
            self.world.ceo_mood = "idle"
        self.hub_poll()
        if self.trainer.q is not None:
            if self.studio.job: self.studio.poll()
            else: self.lab_poll()
        if self.teamsearch.q is not None:
            self.team_poll()
        if self.modal == "rank":
            if self.rank.get("key") != json.dumps(self.career.config, sort_keys=True):
                self.rank_start()
            self.rank_step()
        # 그리기
        surf = self.canvas
        surf.ops.clear()
        surf.fill((8, 12, 10))
        surf.set_clip(self.world_rect)
        self.world.draw(surf, gdt)
        surf.set_clip(None)
        screens.draw(self, surf, dt)
        self.ui.tooltip(surf, self.vw, self.vh)
        self.ui.end()
        self.window.fill((0, 0, 0))
        surf.present(self.window, self.scale, self.offset)

    def world_update(self, gdt, dt):
        w = self.world
        w.elevator += (w.elevator_target - w.elevator) * min(1.0, gdt * 6) if gdt else 0
        for a in w.actors: a.update(gdt, w)
        for e in w.fx: e.update(gdt, w)
        w.actors = [a for a in w.actors if a.alive]
        w.fx = [e for e in w.fx if e.alive]
        for d in (w.flash, w.alarm):
            for k in list(d):
                d[k] -= gdt * 1.2
                if d[k] <= 0: del d[k]

    def key(self, k):
        if k == pygame.K_ESCAPE:
            if self.modal: self.modal = None
            elif self.screen == "play":
                self.career.save(); self.saved = self.career; self.screen = "title"; self._attract()
        elif self.screen != "play":
            return
        elif k == pygame.K_SPACE: self.paused = not self.paused
        elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            self.speed = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 4, pygame.K_4: 8}[k]; self.paused = False
        elif k == pygame.K_m: self.toggle_music()
        elif k == pygame.K_h: self.studio.guide, self.studio.show_guide = [], True     # 처음 안내 다시 보기
        elif k == pygame.K_f: self.toggle_fullscreen()
        elif k == pygame.K_TAB and self.modal is None: self.modal = "jev"

    def toggle_fullscreen(self):
        if self.win is not None:
            if getattr(self, "_full", False): self.win.set_windowed()
            else: self.win.set_fullscreen(desktop=True)
            self._full = not getattr(self, "_full", False)
        else:
            pygame.display.toggle_fullscreen()

    def flip(self):
        if self.win is not None: self.win.flip()
        else: pygame.display.flip()

    def toggle_music(self):
        on = not self.audio.music_on
        self.audio.set_music(on); self.career.settings["music"] = on

    def toggle_sfx(self):
        self.audio.sfx_on = not self.audio.sfx_on; self.career.settings["sfx"] = self.audio.sfx_on

    def run(self):
        while not self.quit:
            dt = min(0.05, self.clock.tick(60) / 1000.0)
            events = pygame.event.get()
            self.step(dt, events)
            self.flip()
        self.close()

    def close(self):
        self.career.settings["speed"] = self.speed
        if self.screen == "play":
            self.career.save()
        self.trainer.stop()
        self.teamsearch.stop()
        pygame.quit()


def season_of(month):
    return ((month - 1) // 3) % 4


def weather_of(month, day):
    r = random.Random(month * 100 + day).random()
    s = season_of(month)
    return ["petals" if r < .7 else "clear", "rain" if r < .3 else "clear", "leaves" if r < .8 else "clear", "snow" if r < .75 else "clear"][s]


def summarize(days):
    curve, run = [], 0.0
    for d in days:
        run += d["profit"]; curve.append(run)
    return {"profit": sum(d["profit"] for d in days), "sat": days[-1]["sat"], "incidents": sum(d["incidents"] for d in days), "curve": curve,
            "human_over": sum(d["human_over"] for d in days), "stockout_days": sum(1 for d in days if d["unmet"] > 0),
            "fraud_loss": sum(d["fraud_loss"] for d in days), "abuse_loss": sum(d["abuse_loss"] for d in days),
            "sales": sum(d["sales"] for d in days)}


def main(brains=(), size=(1280, 800), fullscreen=False, reset=False, sfx=True, music=True):
    app = App(brains=brains, size=size, fullscreen=fullscreen, reset=reset)
    if not sfx: app.audio.sfx_on = False; app.career.settings["sfx"] = False          # 촬영 · 강의용 (효과음 끄기)
    if not music: app.audio.set_music(False); app.career.settings["music"] = False
    app.run()
