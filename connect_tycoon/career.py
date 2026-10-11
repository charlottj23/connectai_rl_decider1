# -*- coding: utf-8 -*-
"""경영 경력 · 게임의 바깥 고리 (달마다 돈을 벌고 → 회사를 키우고 → 두뇌를 다시 키웁니다)

업그레이드는 엔진의 회사 규모(config)를 바꿉니다. 회사가 바뀌면 예전에 배운 두뇌가 덜 맞을 수 있습니다.
그래서 회사를 키울 때마다 두뇌도 다시 훈련시키는 것이 이 게임의 핵심 고리입니다.
"""
import json
import os
import time

from .company import DEFAULT_CONFIG
from .policies import OWNER_DEFAULT

START_CASH = 1000.0      # 창업 자금 1,000만원

UPGRADES = [  # key, 이름, 아이콘, 층, 단계별 효과 설명, 단계별 비용(만원)
    {"key": "demand", "name": "인기 상품", "icon": "star", "floor": "shop", "retrain": False,
     "levels": ["손님 +25% · 문의 +1", "손님 +55% · 문의 +2 · 환불 +1", "손님 +90% · 문의 +3 · 환불 +1"], "cost": [1000, 2500, 5000]},
    {"key": "logistics", "name": "물류 센터", "icon": "truck", "floor": "warehouse", "retrain": True,
     "levels": ["창고 350 · 발주 ×1.3", "창고 480 · 발주 ×1.7", "창고 650 · 발주 ×2.2"], "cost": [600, 1500, 3500]},
    {"key": "staff", "name": "직원 채용", "icon": "people", "floor": "cs", "retrain": True,
     "levels": ["팀마다 +1명 · 하루 2만원", "팀마다 +2명 · 하루 4만원", "팀마다 +3명 · 하루 6만원"], "cost": [500, 1200, 2500]},
    {"key": "fraud", "name": "사기 탐지 AI", "icon": "shield", "floor": "security",
     "levels": ["사기 점수가 또렷해짐", "더 또렷해짐 · 보안 로봇", "거의 확실하게 구별"], "cost": [700, 1600, 3000]},
    {"key": "ad", "name": "광고 대행사", "icon": "mega", "floor": "marketing",
     "levels": ["광고 효과 ×1.3", "광고 효과 ×1.6", "광고 효과 ×2.0 · 비행선"], "cost": [800, 2000, 4000]},
    {"key": "supply", "name": "공급처 계약", "icon": "box", "floor": "warehouse",
     "levels": ["원가 1.50 → 1.38만원", "원가 → 1.27만원", "원가 → 1.17만원"], "cost": [1200, 3000, 6000]},
]
UPG = {u["key"]: u for u in UPGRADES}

LEVELS = [(0, "동네 가게"), (3000, "인기 상점"), (10000, "중소기업"), (30000, "중견기업"), (100000, "대기업"), (300000, "유니콘")]

ACHIEVEMENTS = [  # key, 이름, 설명, 아이콘
    ("open", "개업", "첫 영업일을 마쳤습니다", "star"),
    ("black", "첫 흑자 달", "한 달 이익이 플러스", "coin"),
    ("m1000", "월 1,000만", "한 달 이익 1,000만원", "chart"),
    ("m2000", "월 2,000만", "한 달 이익 2,000만원", "chart"),
    ("m5000", "월 5,000만", "한 달 이익 5,000만원", "rocket"),
    ("safe", "철통 보안", "한 달 동안 위험 사고 0건", "shield"),
    ("stock", "품절 제로", "한 달 동안 품절 0일", "box"),
    ("love", "고객 감동", "월말 고객 만족 95% 이상", "heart"),
    ("invest", "첫 투자", "업그레이드를 샀습니다", "hammer"),
    ("trained", "두뇌 훈련", "AI 사장을 직접 키웠습니다", "cap"),
    ("ai_win", "AI가 더 잘해", "같은 달, AI 사장이 사람의 지시를 이겼습니다", "brain"),
    ("human_win", "사람의 승리", "같은 달, 내 지시가 AI 사장을 이겼습니다", "boss"),
    ("jev", "JEV 기록가", "한 달의 JEV 기록을 저장했습니다", "json"),
    ("hub", "두뇌 수집가", "다른 사람의 두뇌를 불러왔습니다", "hf"),
    ("colony", "개미 군집", "두뇌 연합이 혼자 가장 잘하는 두뇌보다 더 벌었습니다", "ant"),
    ("b1", "1억 클럽", "누적 이익 1억원", "bag"),
    ("unicorn", "유니콘", "누적 이익 30억원", "unicorn"),
]
ACH = {a[0]: a for a in ACHIEVEMENTS}


def config_for(levels):
    """업그레이드 단계 → 엔진 설정."""
    L = lambda k: int(levels.get(k, 0))
    c = dict(DEFAULT_CONFIG)
    d = L("demand"); c["base_demand"] = [40.0, 50.0, 62.0, 76.0][d]; c["extra_cs"] = d; c["extra_refund"] = [0, 0, 1, 1][d]
    g = L("logistics"); c["warehouse"] = [250.0, 350.0, 480.0, 650.0][g]; c["order_scale"] = [1.0, 1.3, 1.7, 2.2][g]
    s = L("staff"); c["staff_bonus"] = s; c["wage"] = 2.0 * s
    c["fraud_tool"] = L("fraud")
    c["ad_power"] = [1.0, 1.3, 1.6, 2.0][L("ad")]
    c["unit_cost"] = [1.5, 1.38, 1.27, 1.17][L("supply")]
    return c


def demand_scale(levels):
    return config_for(levels)["base_demand"] / 40.0 * 1.0


def level_of(earned):
    lv = 0
    for i, (need, _) in enumerate(LEVELS):
        if earned >= need: lv = i
    nxt = LEVELS[lv + 1][0] if lv + 1 < len(LEVELS) else None
    return lv, LEVELS[lv][1], nxt


def home():
    h = os.environ.get("CONNECT_TYCOON_HOME") or os.path.join(os.path.expanduser("~"), ".connect-tycoon")
    os.makedirs(os.path.join(h, "brains"), exist_ok=True)
    os.makedirs(os.path.join(h, "jev"), exist_ok=True)
    return h


class Career:
    def __init__(self):
        self.company = "Connect AI Company"
        self.month = 1
        self.cash = START_CASH
        self.earned = 0.0
        self.upgrades = {}
        self.queued = {}
        self.achievements = {}
        self.history = []                       # 달마다 결과
        self.owner = dict(OWNER_DEFAULT)        # 사장 지시 (마지막 설정)
        self.mode = "owner"                     # 이번 달 사장: owner | ai
        self.ai = "jay-company"                 # AI 사장 자리에 앉은 두뇌
        self.settings = {"music": True, "sfx": True, "speed": 2}
        self.created = time.time()
        self.opened = 0                         # 마지막으로 문을 연 달 (이어하기에서 공사 완료를 한 번만 처리)
        self.team = {}                          # 두뇌 연합: 부서 → 두뇌 id
        self.studio = {}                        # 학습 화면: 모델 버전 · 사람 라벨 · 보상
        self.profile = "general"                # 회사의 분포: general(공개 데이터) · lecture(강의 엔진) · 내 회사 프로필

    @property
    def config(self):
        return config_for(self.upgrades)

    @property
    def level(self):
        return level_of(self.earned)

    def can_buy(self, key):
        u = UPG[key]
        lv = self.upgrades.get(key, 0) + self.queued.get(key, 0)
        if lv >= len(u["cost"]): return False, None
        cost = u["cost"][lv]
        return self.cash >= cost, cost

    def buy(self, key):
        ok, cost = self.can_buy(key)
        if not ok: return False
        self.cash -= cost
        self.queued[key] = self.queued.get(key, 0) + 1
        return True

    def open_new_month(self):
        """지난달에 산 업그레이드가 문을 엽니다."""
        opened = []
        self.opened = self.month
        for k, n in self.queued.items():
            self.upgrades[k] = self.upgrades.get(k, 0) + n
            opened.append(k)
        self.queued = {}
        return opened

    def unlock(self, key):
        if key in self.achievements: return False
        self.achievements[key] = self.month
        return True

    def close_month(self, profit, summary):
        self.earned += profit
        self.history.append(dict(summary, month=self.month, profit=profit, cash_after=self.cash))
        self.month += 1

    # ── 저장 ──────────────────────────────────────────────────────────────
    def to_json(self):
        return dict(self.__dict__)

    @classmethod
    def from_json(cls, d):
        c = cls()
        for k, v in d.items():
            if hasattr(c, k): setattr(c, k, v)
        c.settings = dict(cls().settings, **(d.get("settings") or {}))
        c.owner = dict(OWNER_DEFAULT, **(d.get("owner") or {}))
        return c

    def save(self, path=None):
        path = path or os.path.join(home(), "save.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path=None):
        path = path or os.path.join(home(), "save.json")
        if not os.path.exists(path): return None
        try:
            with open(path, encoding="utf-8") as f:
                return cls.from_json(json.load(f))
        except (OSError, ValueError):
            return None
