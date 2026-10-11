# -*- coding: utf-8 -*-
"""그림 모음 · 사람 · AI 사장(전전두엽) · 가구 · 탈것 · 아이콘. 전부 글자 지도로 그린 원본 도트입니다."""
import random


from .pixel import INK as INK_, outline, sprite

# ── 사람 (8×13, 테두리를 두르면 10×15) ─────────────────────────────────────
_HEAD = {
    "short": ["..hhhh..", ".hhhhhh.", ".hssssh.", ".sesses.", "..ssss.."],
    "long":  ["..hhhh..", ".hhhhhh.", "hhsssshh", "hhessehh", "h.ssss.h"],
    "bun":   ["...hh...", "..hhhh..", ".hhhhhh.", ".sesses.", "..ssss.."],
    "cap":   ["..xxxx..", ".xxxxxxx", ".hssssh.", ".sesses.", "..ssss.."],
    "spiky": [".h.hh.h.", ".hhhhhh.", ".hssssh.", ".sesses.", "..ssss.."],
    "mask":  ["..hhhh..", ".hhhhhh.", ".hssssh.", ".kwkkwk.", "..ssss.."],
}
_BODY = [".cccccc.", "cccccccc", "sccccccs", ".cccccc.", "..llll.."]
_LEGS = [["..l..l..", "..l..l..", "..f..f.."], ["..l..l..", ".l....l.", ".f....f."]]
_BODY_TIE = [".cwxxwc.", "ccwxxwcc", "scccxccs", ".cccccc.", "..llll.."]
_BODY_STRIPE = [".kkkkkk.", "wwwwwwww", "skkkkkks", ".wwwwww.", "..llll.."]

SKINS = [(248, 214, 182), (234, 192, 150), (196, 144, 104), (150, 104, 72)]
HAIRS = [(40, 30, 24), (92, 58, 36), (150, 96, 52), (226, 196, 120), (70, 70, 84), (186, 72, 58), (30, 30, 34)]
SHIRTS = [(226, 122, 96), (130, 180, 156), (242, 204, 142), (138, 182, 216), (212, 164, 214), (240, 238, 226), (182, 202, 154),
          (244, 152, 64), (118, 214, 224), (250, 120, 150)]
PANTS = [(54, 62, 90), (70, 60, 52), (40, 44, 52), (96, 110, 140), (120, 100, 80)]


def person(skin, hair, shirt, pants=(54, 62, 90), style="short", frame=0, body="plain", acc=None, shoes=(36, 30, 28)):
    head = _HEAD[style]
    torso = _BODY_TIE if body == "tie" else _BODY_STRIPE if body == "stripe" else _BODY
    rows = head + torso + _LEGS[frame % 2]
    dark = tuple(max(0, int(v * 0.78)) for v in shirt)
    pal = {"h": hair, "s": skin, "e": (20, 24, 30), "c": shirt, "C": dark, "l": pants, "f": shoes, "x": acc or (208, 249, 145),
           "w": (246, 247, 238), "k": (20, 22, 26)}
    key = ("person", skin, hair, shirt, pants, style, frame % 2, body, acc, shoes)
    return outline(sprite(rows, pal, key=key), key=key)


class Look:
    """손님 한 명의 생김새."""

    def __init__(self, rng=None, shirt=None, style=None, body="plain", acc=None, hair=None, skin=None, pants=None):
        r = rng or random
        self.skin = skin or r.choice(SKINS)
        self.hair = hair or r.choice(HAIRS)
        self.shirt = shirt or r.choice(SHIRTS)
        self.pants = pants or r.choice(PANTS)
        self.style = style or r.choice(["short", "short", "long", "bun", "spiky", "long"])
        self.body, self.acc = body, acc

    def frame(self, f):
        return person(self.skin, self.hair, self.shirt, self.pants, self.style, f, self.body, self.acc)


DEPT_SHIRT = {"cs": (130, 196, 120), "refund": (96, 168, 150), "review": (226, 214, 180), "security": (70, 80, 110),
              "marketing": (244, 170, 64), "shop": (232, 108, 96), "warehouse": (176, 136, 88)}


def staff_look(dept, i):
    rng = random.Random(hash((dept, i)) & 0xFFFF)
    style = "cap" if dept in ("warehouse", "security") else rng.choice(["short", "long", "bun", "spiky"])
    return Look(rng, shirt=DEPT_SHIRT[dept], style=style, body="tie" if dept in ("refund", "review") else "plain",
                acc=(208, 249, 145) if dept != "security" else (40, 44, 60), pants=(44, 48, 60))


def thief_look():
    return Look(random.Random(7), shirt=(30, 30, 34), style="mask", body="stripe", hair=(24, 24, 28), pants=(30, 30, 34), skin=SKINS[1])


# ── AI 사장 · 넥타이를 맨 전전두엽 (16×17) ───────────────────────────────────
_BRAIN = [
    "....pppppppp....",
    "..ppPppPppPppp..",
    ".pPppPpppPppPpp.",
    ".ppPpppPPpppPpp.",
    "pPppPppPpppPppPp",
    "ppwwkppPppwwkppp",
    "ppwwkppppppwwkpp",
    "pPpoppppppppopPp",
    ".pppppkppkppppp.",
    "..pPpppkkppppP..",
    "....pppppppp....",
    ".....uwaawu.....",
    "....uuwaawuu....",
    "...uuuuaauuuu...",
    "...s.uuuuuu.s...",
    ".....uu..uu.....",
    ".....kk..kk.....",
]
_BRAIN_BLINK = list(_BRAIN)
_BRAIN_BLINK[5] = "ppkkkppPppkkkppp"
_BRAIN_BLINK[6] = "pppppppppppppppp"
_BRAIN_THINK = list(_BRAIN)
_BRAIN_THINK[5] = "ppwkwppPppwkwppp"
_BRAIN_THINK[6] = "ppwwwppppppwwwpp"
_BRAIN_HAPPY = list(_BRAIN)
_BRAIN_HAPPY[5] = "ppkppkpPppkppkpp"
_BRAIN_HAPPY[6] = "pppkkppppppkkppp"
_BRAIN_HAPPY[8] = ".ppppkppppkpppp."
_BRAIN_HAPPY[9] = "..pPppkkkkpppP.."
_BRAIN_SAD = list(_BRAIN)
_BRAIN_SAD[8] = ".pppppppppppppp."
_BRAIN_SAD[9] = "..pPpppkkppppP.."
_BRAIN_SAD[10] = "....ppkppkpp...."


BRAND_BRAIN = {"p": (208, 249, 145), "P": (118, 168, 64), "o": (208, 249, 145), "w": (246, 247, 238), "k": (6, 9, 10),
               "u": (30, 36, 34), "U": (20, 24, 22), "a": (246, 247, 238), "s": (200, 204, 200)}


def brain_ceo(mood="idle", acid=(208, 249, 145), brand=False):
    """넥타이를 맨 전전두엽. brand=True면 형광 연두 모델 (볼터치 없음)."""
    rows = {"idle": _BRAIN, "blink": _BRAIN_BLINK, "think": _BRAIN_THINK, "happy": _BRAIN_HAPPY, "sad": _BRAIN_SAD}[mood]
    pal = dict(BRAND_BRAIN) if brand else {"a": acid}
    key = ("brain", mood, acid, brand)
    return outline(sprite(rows, pal, key=key), (6, 9, 10) if brand else INK_, key=key)


def player_face():
    return Look(random.Random(3), shirt=(52, 92, 156), style="short", body="tie", hair=(40, 30, 24), acc=(208, 249, 145)).frame(0)


# ── 가구 ─────────────────────────────────────────────────────────────────
DESK = sprite(["tttttttttttttt", "TTTTTTTTTTTTTT", ".N..........N.", ".N..........N.", ".N..........N.", ".N..........N."])
COUNTER = sprite(["tttttttttttttttttttttt", "TTTTTTTTTTTTTTTTTTTTTT", "nnnnnnnnnnnnnnnnnnnnnn", "nNnnnnnnnnnnnnnnnnnnNn",
                  "nNnnnnnnnnnnnnnnnnnnNn", "nNnnnnnnnnnnnnnnnnnnNn", "nnnnnnnnnnnnnnnnnnnnnn", "NNNNNNNNNNNNNNNNNNNNNN"])
REGISTER = outline(sprite(["gggggg", "gkkkkg", "gaaakg", "gggggg", "GGGGGG"]))
PLANT = sprite(["..e.e..", ".eEeeE.", "eEeEeEe", ".eEeEe.", "..eEe..", "...E...", "..nnn..", "..nNn..", "..nnn.."])
BENCH = sprite(["nnnnnnnnnnnn", "NNNNNNNNNNNN", ".k........k.", ".k........k."])
COOLER = sprite(["bbbbb", "bcccb", "bcccb", "wwwww", "wgggw", "wgggw", "wgwgw", "wgggw", "wwwww"])
SOFA = sprite(["..vvvvvvvvvvvvvv..", ".vVVVVVVVVVVVVVVv.", "vvVvvvvvvvvvvvvVvv", "vVVVVVVVVVVVVVVVVv", "vvvvvvvvvvvvvvvvvv", "VV..............VV"])
CEO_DESK = sprite(["kkkkkkkkkkkkkkkkkkkkkk", "zzzzzzzzzzzzzzzzzzzzzz", "zNNNNNNNNNNNNNNNNNNNNz", "zN.aaaa...........N..z",
                   "zNNNNNNNNNNNNNNNNNNNNz", "zz..................zz", "zz..................zz", "zz..................zz"])
SAFE = outline(sprite(["GGGGGGGG", "GggggggG", "GgkkkkgG", "GgkyykgG", "GgkkkkgG", "GggggggG", "GGGGGGGG"]))
FORKLIFT = outline(sprite(["....kk........", "....k.k.......", "..yyyyyy..k...", "..yYYYYy..k...", "yyyyyyyy..k...", "yYYYYYYyy.kkkk", ".kk...kk......", ".kk...kk......"]))
ROBOT = outline(sprite(["..kk..", ".cccc.", "cakkac", "cccccc", ".kccK.", "kccccK", "k.cc.K", "..cc..", ".k..k."]))
SCANNER = sprite([".cccccccccc.", "cC........Cc", "cC........Cc", "cC........Cc", "cC........Cc", "cC........Cc", "cC........Cc", "cC........Cc", "kk........kk"])
PHONE = outline(sprite(["k...k", "kkkkk", "kgggk", "kkkkk"]))
TROPHY = outline(sprite(["yyyyy", "yYyyy", ".yyy.", "..y..", ".YYY."]))
CHART = sprite(["wwwwwwwwwwww", "w..........w", "w.......e..w", "w....e.e...w", "w..e..e....w", "w.e........w", "wwwwwwwwwwww"])
BOARD = sprite(["gggggggggggggg", "gwwwwwwwwwwwwg", "gwbbw.rr.wyywg", "gwwwwwwwwwwwwg", "gw.kk.kkk.k.wg", "gwwwwwwwwwwwwg", "gggggggggggggg", "....g....g...."])
DOCS = sprite(["wwwwww", "Wwwwww", "wWwwww", "wwWwww", "Wwwwww"])


def monitor(glow):
    key = ("mon", glow)
    return sprite(["kkkkkkk", "kmmmmmk", "kmmmmmk", "kkkkkkk", "...k...", "..kkk.."], {"m": glow}, key=key)


def server(frame, alarm=False):
    rows = ["kkkkkkkk", "kMMMMMMk", "kMgMgMMk", "kMMMMMMk", "kkkkkkkk", "kMMMMMMk", "kMgMgMMk", "kMMMMMMk", "kkkkkkkk",
            "kMMMMMMk", "kMgMgMMk", "kMMMMMMk", "kkkkkkkk", "kMMMMMMk", "kMgMgMMk", "kMMMMMMk", "kkkkkkkk", ".k....k."]
    rnd = random.Random(frame)
    out = []
    for row in rows:
        out.append("".join(("r" if alarm and rnd.random() < .6 else rnd.choice("aAeg")) if ch == "g" else ch for ch in row))
    return sprite(out, key=("srv", frame % 8, alarm))


BOX = sprite(["ttttt", "tNtNt", "TTTTT", "TTTTT"])
PRODUCT_COLORS = [(232, 108, 96), (98, 158, 228), (252, 214, 92), (130, 196, 120), (212, 164, 214), (244, 152, 64), (118, 214, 224)]


def product(i):
    c = PRODUCT_COLORS[i % len(PRODUCT_COLORS)]
    return sprite(["cc", "cC", "cC"], {"c": c, "C": tuple(int(v * .75) for v in c)}, key=("prod", i % 7))


# ── 바깥 ────────────────────────────────────────────────────────────────
TRUCK = outline(sprite([
    "..........aaaaaaaaaaaaaaaaaaaaa",
    "..........awwwwwwwwwwwwwwwwwwwa",
    "...kkkkk..awwkkkkwwkkkwkwwkkkwa",
    "..kcccck..awwkwwwwkwwkwkwwkwwwa",
    ".kccccck..awwkwwwwkwwkwkkwkkkwa",
    ".kccccck..awwkwwwwkwwkwkwkkwwwa",
    "kkkkkkkkkkawwkkkkwwkkkwkwwkkkwa",
    "kaaaaaaaaaawwwwwwwwwwwwwwwwwwwa",
    "kaayaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "kaaaaaaaaaaAAAAAAAAAAAAAAAAAAAA",
    "kkkGGGkkkkkkkkkkkkkkkkGGGkkkkkk",
    "...GwG................GwG......",
    "...GGG................GGG......",
]))


def car(color):
    key = ("car", color)
    dark = tuple(int(v * .7) for v in color)
    return outline(sprite([
        "....cccccccc......",
        "...cCbbCbbbbc.....",
        "..cCbbbCbbbbbc....",
        "ccccccccccccccccc.",
        "cyccccccccccccccrc",
        "cccccccccccccccccc",
        "CCkkkCCCCCCCCkkkCC",
        "..kgk........kgk..",
    ], {"c": color, "C": dark}, key=key), key=key)


TREE_ROWS = [
    ".....eeeee.....",
    "...eeEeeeEee...",
    "..eEeeeEeeeEe..",
    ".eeeEeeeeEeeee.",
    "eEeeeeEeeeeeEee",
    "eeeEeeeeeEeeeee",
    ".eEeeeEeeeeEee.",
    "..eeEeeeeEeee..",
    "...eeeeEeeee...",
    ".....eeeee.....",
    "......nNn......",
    "......nNn......",
    "......nNn......",
    ".....nnNnn.....",
]
PINE_ROWS = ["....E....", "...eEe...", "..eEeEe..", "...eEe...", "..eEeEe..", ".eEeEeEe.", "..eEeEe..", ".eEeEeEe.", "eEeEeEeEe", "....N....", "....N...."]
SEASONS = ["봄", "여름", "가을", "겨울"]
SEASON_LEAF = [((248, 180, 204), (218, 128, 164)), ((96, 178, 92), (52, 122, 66)), ((244, 152, 64), (196, 96, 40)), ((236, 242, 246), (176, 194, 206))]
PINE_LEAF = [((96, 178, 92), (52, 122, 66)), ((80, 160, 84), (44, 110, 60)), ((110, 150, 80), (70, 110, 56)), ((226, 236, 242), (70, 120, 84))]


def tree(season=1):
    a, b = SEASON_LEAF[season % 4]
    return sprite(TREE_ROWS, {"e": a, "E": b}, key=("tree", season % 4))


def pine(season=1):
    a, b = PINE_LEAF[season % 4]
    return sprite(PINE_ROWS, {"e": a, "E": b}, key=("pine", season % 4))


TREE, PINE = tree(1), pine(1)
LAMP = sprite(["kkkkkk", "k.yy.k", "kkkkkk", "...k..", "...k..", "...k..", "...k..", "...k..", "...k..", "...k..", "...k..", "...k..", "...k..",
               "...k..", "...k..", "..kkk."])
BUSSTOP = sprite(["aaaaaaaaaaaaaaaaaa", "akkkkkkkkkkkkkkkka", "k................k", "k.ccccccccccccc..k", "k.ccccccccccccc..k", "k.ccccccccccccc..k",
                  "k.ccccccccccccc..k", "k................k", "k.nnnnnnnnnnnnn..k", "k................k", "k................k", "k................k"])
ANT = sprite(["k.k", ".kk"])
CLOUDS = [
    sprite(["....wwww......", "..wwwwwwww....", ".wwwwwwwwwww..", "wwwwwwwwwwwwww", ".WWWWWWWWWWWW."]),
    sprite(["......wwwww.........", "...wwwwwwwwww.wwww..", ".wwwwwwwwwwwwwwwwww.", "wwwwwwwwwwwwwwwwwwww", ".WWWWWWWWWWWWWWWWWW."]),
    sprite(["..www....", ".wwwwww..", "wwwwwwwww", ".WWWWWWW."]),
]
BLIMP = outline(sprite([
    "......aaaaaaaaaaaaaaa.....",
    "...aaawwwwwwwwwwwwwwwaaa..",
    ".aawwwwkwkkwkwkwkkwwwwwwaa",
    "aawwwwwkwkwwkwkwkwwwwwwwwa",
    ".aawwwwkwkkwkkwkkwwwwwwaa.",
    "...aaawwwwwwwwwwwwwwaaa..k",
    "......aaaaaaaaaaaaaa...kkk",
    "..........kkkkk.......k.k.",
]))
SUN = sprite(["...yyyy...", ".yyyyyyyy.", ".yyyyyyyy.", "yyyyyyyyyy", "yyyyyyyyyy", "yyyyyyyyyy", "yyyyyyyyyy", ".yyyyyyyy.", ".yyyyyyyy.", "...yyyy..."])
MOON = sprite(["..wwww..", ".wwwW...", "wwwW....", "wwwW....", "wwwW....", "wwwwW...", ".wwwwwW.", "..wwww.."])

# ── 날아다니는 것 · 말풍선 아이콘 (7×7 안팎) ───────────────────────────────
COIN = [outline(sprite([".yyy.", "yywyy", "yyyYy", "yyyYy", ".YYY."])), outline(sprite(["..y..", ".yyY.", ".yyY.", ".yyY.", "..Y.."]))]
CARD = outline(sprite(["wwwwwww", "kkkkkkk", "wwwwwww", "wyywwww", "wwwwwww"]))
PAPER = outline(sprite(["wwwww.", "wkkkww", "wwwwww", "wkkkkw", "wwwwww", "wkkkww", "wwwwww"]))
PLANE = outline(sprite(["......w", "....www", "..wwwWw", "wwwwWw.", "..wWw..", "...w..."]))
BAG = outline(sprite(["..kk...", ".ttttt.", "ttyyttt", "tytttTt", "ttyyttt", "tttytTt", "tyytTTt", ".TTTTT."]))
BEAM = sprite([".a.", "aaa", ".a."], {"a": (208, 249, 145)})
PACKET = outline(sprite(["ccccc", "cwwwc", "cwkwc", "cwwwc", "ccccc"]))

_ICON_ROWS = {
    "coin":   ["..kkkkk..", ".kyyyyyk.", "kyywyyyYk", "kywyyyyYk", "kyyyyyyYk", "kyyyyyyYk", "kyyyyyYYk", ".kYYYYYk.", "..kkkkk.."],
    "cal":    ["kkkkkkkkk", "krrrrrrrk", "kkkkkkkkk", "kwwwwwwwk", "kwkwkwkwk", "kwwwwwwwk", "kwkwkwrwk", "kwwwwwwwk", "kkkkkkkkk"],
    "sun":    ["....y....", ".y..y..y.", "..yyyyy..", "..yyyyy..", "yyyyyyyyy", "..yyyyy..", "..yyyyy..", ".y..y..y.", "....y...."],
    "moon":   ["...kkk...", "..kwwk...", ".kwwk....", ".kwwk....", ".kwwk....", ".kwwwk...", "..kwwwkk.", "...kkkk..", "........."],
    "dusk":   [".........", ".........", "...ooo...", "..ooooo..", ".ooooooo.", "kkkkkkkkk", ".........", "..k.k.k..", "........."],
    "star":   ["....k....", "...kyk...", "kkkkykkkk", "kyyyyyyyk", ".kyyyyyk.", "..kyyyk..", ".kyykyyk.", ".kyk.kyk.", ".kk...kk."],
    "smile":  ["..kkkkk..", ".kyyyyyk.", "kyykyykyk", "kyyyyyyyk", "kykyyykyk", "kyykkkyyk", "kyyyyyyyk", ".kyyyyyk.", "..kkkkk.."],
    "meh":    ["..kkkkk..", ".kyyyyyk.", "kyykyykyk", "kyyyyyyyk", "kyyyyyyyk", "kykkkkkyk", "kyyyyyyyk", ".kyyyyyk.", "..kkkkk.."],
    "sad":    ["..kkkkk..", ".kbbbbbk.", "kbbkbbkbk", "kbbbbbbbk", "kbbbbbbbk", "kbbkkkbbk", "kbkbbbkbk", ".kbbbbbk.", "..kkkkk.."],
    "angry":  ["..kkkkk..", ".krrrrrk.", "krkrrrkrk", "krrkrkrrk", "krrrrrrrk", "krrkkkrrk", "krkrrrkrk", ".krrrrrk.", "..kkkkk.."],
    "devil":  ["k.kkkkk.k", "kkrrrrrkk", "krrkrkrrk", "krrrrrrrk", "krkrrrkrk", "krrkkkrrk", "krrrrrrrk", ".krrrrrk.", "..kkkkk.."],
    "box":    [".........", ".kkkkkkk.", "kttNtttTk", "kkkkkkkkk", "kttttttTk", "kttttttTk", "kttttttTk", "kTTTTTTTk", "kkkkkkkkk"],
    "people": [".kk...kk.", "kssk.kssk", "kssk.kssk", ".kk...kk.", "kcck.kbbk", "kcccbbbbk", "kcck.kbbk", "kcck.kbbk", "kkkk.kkkk"],
    "alarm":  ["...kkk...", "..krrrk..", ".krwrrrk.", ".krwrrrk.", ".krrrrrk.", ".krrrrrk.", "kkkkkkkkk", "kgggggggk", "kkkkkkkkk"],
    "shield": ["kkkkkkkkk", "kaaaaaaak", "kaawaaaAk", "kawwwaaAk", "kaawaaaAk", ".kaaaaAk.", ".kaaaaAk.", "..kaaAk..", "...kkk..."],
    "brain":  ["..kkkkk..", ".kppPppk.", "kpPppPppk", "kppPppPpk", "kpPppPppk", "kppppppPk", ".kpPppPk.", "..kkakk..", "...kak..."],
    "chart":  ["k........", "k......e.", "k.....ee.", "k..e.eee.", "k.eeeeee.", "k.eeeeee.", "keeeeeeee", "kkkkkkkkk", "........."],
    "trophy": ["kkkkkkkkk", "kyyyyyyyk", "kyyyyyyYk", ".kyyyyYk.", "..kyyYk..", "...kyk...", "...kYk...", "..kYYYk..", "..kkkkk.."],
    "hammer": [".kkkkk...", "kgggggk..", "kgggggkk.", ".kkknkkk.", "...knk...", "...knk...", "...knk...", "...knk...", "...kkk..."],
    "cap":    ["....k....", "..kkakk..", "kkkkkkkkk", ".kkkkkk.a", "..kkkkk.a", "..kkkkk.a", "........k", ".........", "........."],
    "news":   ["kkkkkkkkk", "kwwwwwwwk", "kwkkkwwwk", "kwkkkwkwk", "kwwwwwwwk", "kwkkkkkwk", "kwwwwwwwk", "kwkkkkkwk", "kkkkkkkkk"],
    "help":   ["..kkkkk..", ".kbbbbbk.", "kbbwwwbbk", "kbbbbwbbk", "kbbbwwbbk", "kbbbwbbbk", "kbbbbbbbk", ".kbbwbbk.", "..kkkkk.."],
    "sound":  ["....k....", "...kk..k.", "kkkwk.k..", "kwwwk..k.", "kwwwk..k.", "kkkwk.k..", "...kk..k.", "....k....", "........."],
    "mute":   ["....k....", "...kk....", "kkkwk.r.r", "kwwwk..r.", "kwwwk.r.r", "kkkwk....", "...kk....", "....k....", "........."],
    "music":  ["...kkkkkk", "...kaaaak", "...kkkkkk", "...k....k", "...k....k", ".kkk..kkk", "kaak.kaak", "kaak.kaak", ".kk...kk."],
    "pause":  [".........", ".kkk.kkk.", ".kwk.kwk.", ".kwk.kwk.", ".kwk.kwk.", ".kwk.kwk.", ".kwk.kwk.", ".kkk.kkk.", "........."],
    "play":   [".kk......", ".kwk.....", ".kwwk....", ".kwwwk...", ".kwwwwk..", ".kwwwk...", ".kwwk....", ".kwk.....", ".kk......"],
    "ff":     ["kk..kk...", "kwk.kwk..", "kwwkkwwk.", "kwwwkwwwk", "kwwkkwwk.", "kwk.kwk..", "kk..kk...", ".........", "........."],
    "fff":    ["k.k.k....", "kkkkkkk..", "kwkwkwkk.", "kwwkwwkwk", "kwkwkwkk.", "kkkkkkk..", "k.k.k....", ".........", "........."],
    "skip":   ["kk..kk.kk", "kwk.kwkkk", "kwwkkwwkk", "kwwwkwwwk", "kwwkkwwkk", "kwk.kwkkk", "kk..kk.kk", ".........", "........."],
    "check":  [".........", ".......kk", "......kak", ".....kak.", "kk..kak..", "kakkak...", ".kaak....", "..kk.....", "........."],
    "cross":  [".........", "kk.....kk", "krk...krk", ".krk.krk.", "..krkrk..", ".krk.krk.", "krk...krk", "kk.....kk", "........."],
    "phone":  [".kkkkkkk.", "kgggggggk", "kgkkkkkgk", "kkkgggkkk", "..kgkgk..", ".kgggggk.", ".kgkgkgk.", ".kgggggk.", ".kkkkkkk."],
    "card":   [".........", "kkkkkkkkk", "kwwwwwwwk", "kkkkkkkkk", "kwwwwwwwk", "kwyywwwwk", "kwwwwwwwk", "kkkkkkkkk", "........."],
    "search": ["..kkk....", ".kwwwk...", "kwwcwwk..", "kwcwwwk..", "kwwwwwk..", ".kwwwkk..", "..kkkkkk.", "......kkk", ".......kk"],
    "truck":  [".........", "kkkkkk...", "kaaaakkk.", "kaaaakwwk", "kaaaakwwk", "kkkkkkkkk", ".kgk..kgk", ".kkk..kkk", "........."],
    "mega":   [".......kk", ".....kkok", "kkkkkoook", "kwkoooook", "kwkoooook", "kkkkkoook", "..kk.kkok", "..kk...kk", "..kk....."],
    "crown":  [".........", "k...k...k", "kk.kyk.kk", "kykkykkyk", "kyyyyyyyk", "kyrryrryk", "kyyyyyyyk", "kkkkkkkkk", "........."],
    "heart":  [".........", ".kk...kk.", "krrk.krrk", "krwrkrrrk", "krrrrrrrk", ".krrrrrk.", "..krrrk..", "...krk...", "....k...."],
    "warn":   ["....k....", "...kyk...", "...kyk...", "..kykyk..", "..kykyk..", ".kyyyyyk.", ".kyykyyk.", "kyyyyyyyk", "kkkkkkkkk"],
    "bag":    ["...kk....", "..ktk....", ".kttttk..", "ktyyttTk.", "ktyttyTk.", "ktyyttTk.", "kttyytTk.", ".kTTTTk..", "..kkkk..."],
    "gear":   ["...k.k...", ".kkgkgkk.", ".kgggggk.", "kgggkgggk", ".ggk.kgg.", "kgggkgggk", ".kgggggk.", ".kkgkgkk.", "...k.k..."],
    "save":   ["kkkkkkkk.", "kbwwwwbbk", "kbwwwwbbk", "kbbbbbbbk", "kbkkkkkbk", "kbkwwwkbk", "kbkwwwkbk", "kbkkkkkbk", "kkkkkkkkk"],
    "hf":     ["..kkkkk..", ".kyyyyyk.", "kyykyykyk", "kyyyyyyyk", "kyykkkyyk", "kykyyykyk", "kyyyyyyyk", "kyykyykyk", ".kkk.kkk."],
    "json":   [".........", ".kk...kk.", "k.......k", "k..k.k..k", ".k.....k.", "k..k.k..k", "k.......k", ".kk...kk.", "........."],
    "boss":   [".........", "..kkkkk..", ".khhhhhk.", ".kssssskk", ".ksksksk.", "..kssskk.", ".kbbabbk.", "kbbbabbbk", "kkkkkkkkk"],
    "ant":    [".........", "k...k....", ".k.k.....", "..kkk.kk.", ".kkkkkkkk", "..kkk.kk.", ".k.k.k.k.", "k..k.k..k", "........."],
    "lock":   ["..kkkkk..", ".kk...kk.", ".k.....k.", "kkkkkkkkk", "kyyyyyyyk", "kyyykyyyk", "kyyykyyyk", "kyyyyyyyk", "kkkkkkkkk"],
    "up":     ["....k....", "...kak...", "..kaaak..", ".kaaaaak.", "kkkaaakkk", "..kaaak..", "..kaaak..", "..kaaak..", "..kkkkk.."],
    "down":   ["..kkkkk..", "..krrrk..", "..krrrk..", "..krrrk..", "kkkrrrkkk", ".krrrrrk.", "..krrrk..", "...krk...", "....k...."],
    "key":    [".kkk.....", "kyyyk....", "kykyk....", "kyyykkkkk", ".kkkyyyyk", "....kkyk.", "......kk.", ".........", "........."],
    "dice":   ["kkkkkkkkk", "kwwwwwwwk", "kwkwwwkwk", "kwwwwwwwk", "kwwwkwwwk", "kwwwwwwwk", "kwkwwwkwk", "kwwwwwwwk", "kkkkkkkkk"],
    "rocket": ["....k....", "...kwk...", "...kwk...", "..kwbwk..", "..kwwwk..", "..kwwwk..", ".kwkwkwk.", "kk.kok.kk", "....r...."],
    "unicorn":["......k..", ".....kyk.", "..kkkwwk.", ".kwwwwkwk", "kwwkwwwwk", "kwwwwwwk.", ".kpwwwk..", "..kkwwk..", "...kkkk.."],
}
ICON_PAL = {"h": (40, 30, 24)}


def icon(name):
    return sprite(_ICON_ROWS[name], ICON_PAL, key=("icon", name))


ICONS = list(_ICON_ROWS)
