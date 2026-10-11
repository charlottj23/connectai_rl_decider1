# -*- coding: utf-8 -*-
"""CompanyEnv.render() 용 · 지금 회사 상태를 빌딩 그림 한 장으로 (numpy 배열 H×W×3)."""
import os

_STATE = {}


def render_rgb(env, scale=2):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import numpy as np
    import pygame
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    from .pixel import Fonts
    from .world import World
    if "world" not in _STATE:
        _STATE["fonts"] = Fonts()
        _STATE["world"] = World(_STATE["fonts"])
    w = _STATE["world"]
    w.resize(424, 360)
    staff = [x for x in env.log if x["dept"] == "staffing"]
    if staff:
        cap = staff[-1]["cap"]
        w.caps = {"cs": cap["즉시 처리"], "refund": cap["결제 담당 배정"], "review": cap["사람 확인"]}
    if env.days:
        w.stock = env.days[-1]["stock"]
    w.warehouse = env.company.cfg["warehouse"]
    mk = [x for x in env.log if x["dept"] == "marketing"]
    w.ad_level = ["중단", "유지", "증액"].index(mk[-1]["action"]) if mk else 1
    d = env.decision
    w.p = 0.1 + 0.6 * (d.ev["ctx"]["time"] if d else 1.0)
    surf = pygame.Surface((424, 360))
    w.draw(surf, 0.0)
    if scale != 1:
        surf = pygame.transform.scale(surf, (424 * scale, 360 * scale))
    return np.transpose(pygame.surfarray.array3d(surf), (1, 0, 2)).copy()
