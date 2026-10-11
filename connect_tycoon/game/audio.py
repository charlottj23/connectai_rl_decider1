# -*- coding: utf-8 -*-
"""소리 · 8비트 효과음과 배경 음악을 numpy로 합성합니다 (음원 파일이 없습니다)."""
import numpy as np
import pygame

RATE = 22050


def _t(sec):
    return np.arange(int(RATE * sec)) / RATE


def square(freq, sec, duty=0.5, vol=0.3):
    t = _t(sec)
    return vol * np.where((t * freq) % 1.0 < duty, 1.0, -1.0)


def tri(freq, sec, vol=0.3):
    t = _t(sec)
    return vol * (2 * np.abs(2 * ((t * freq) % 1.0) - 1) - 1)


def noise(sec, vol=0.2, seed=0):
    return vol * np.random.default_rng(seed).uniform(-1, 1, int(RATE * sec))


def env(x, attack=0.005, release=0.06):
    n = len(x)
    e = np.ones(n)
    a, r = int(RATE * attack), int(RATE * release)
    if a: e[:a] = np.linspace(0, 1, a)
    if r and r < n: e[-r:] = np.linspace(1, 0, r)
    return x * e


def cat(*xs):
    return np.concatenate(xs)


def note(n):
    """MIDI 번호 → 주파수."""
    return 440.0 * 2 ** ((n - 69) / 12)


def make_sfx():
    s = {}
    s["coin"] = cat(env(square(1046, .05, .25, .18)), env(square(1568, .09, .25, .18), release=.08))
    s["cash"] = cat(env(noise(.04, .25)), env(square(1318, .05, .5, .16)), env(square(1760, .12, .5, .16), release=.1))
    s["ring"] = cat(*[env(square(880 if i % 2 == 0 else 660, .05, .5, .07)) for i in range(6)])
    t = _t(.7); sweep = 0.16 * np.sign(np.sin(2 * np.pi * np.cumsum(600 + 500 * np.abs(np.sin(t * 9))) / RATE))
    s["alarm"] = env(sweep, release=.1)
    s["block"] = cat(env(square(220, .05, .5, .2)), env(square(880, .08, .5, .14)))
    s["truck"] = env(noise(.35, .12, 3) * np.sin(np.linspace(0, 30, int(RATE * .35))) ** 2, release=.2)
    s["click"] = env(square(1200, .015, .5, .12), release=.01)
    s["think"] = env(tri(660, .06, .18) + tri(990, .06, .1))
    s["level"] = cat(*[env(square(note(n), .09, .5, .16)) for n in (72, 76, 79, 84)], env(square(note(88), .25, .5, .16), release=.2))
    s["trophy"] = cat(*[env(square(note(n), .08, .25, .15)) for n in (79, 83, 86)], env(tri(note(91), .3, .25), release=.25))
    s["fail"] = cat(*[env(square(note(n), .1, .5, .14)) for n in (64, 60, 55)])
    s["buy"] = cat(env(square(note(76), .05, .5, .15)), env(square(note(83), .1, .5, .15)))
    s["page"] = env(noise(.05, .08, 7), release=.04)
    return s


def make_music(bpm=112):
    """밝은 4화음 진행 (C · Am · F · G) 16마디 반복."""
    beat = 60 / bpm
    eighth = beat / 2
    chords = [(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)]
    lead_pat = [0, 1, 2, 1, 0, 2, 1, 2]
    melody = [76, 79, 81, 79, 76, 74, 72, 74, 76, 72, 69, 72, 74, 79, 77, 74]
    bars = 16
    out = []
    for bar in range(bars):
        ch = chords[bar % 4]
        seg = []
        for k in range(8):
            nn = ch[lead_pat[k]] + 12
            x = env(square(note(nn), eighth, .25, .045), .002, .03)
            bass = env(tri(note(ch[0] - 24 + (12 if k % 4 == 2 else 0)), eighth, .12), .002, .02)
            m = melody[(bar * 2 + k // 4) % len(melody)]
            mel = env(square(note(m), eighth, .5, .035 if bar % 8 < 6 else .045), .004, .05) if k % 2 == 0 or bar % 2 else 0
            hat = env(noise(.02, .02, k), .001, .015)
            hat = np.pad(hat, (0, len(x) - len(hat)))
            seg.append(x + bass + mel + hat * (1 if k % 2 else .5))
        out.append(np.concatenate(seg))
    return np.concatenate(out)


class Audio:
    def __init__(self, sfx=True, music=True):
        self.ok = False
        self.sfx_on, self.music_on = sfx, music
        self.last = {}
        try:
            pygame.mixer.pre_init(RATE, -16, 2, 512)
            pygame.mixer.init(RATE, -16, 2, 512)
            self.ok = True
        except pygame.error:
            return
        self.sounds = {k: self._snd(v) for k, v in make_sfx().items()}
        self.music = None
        self.channel = None
        if music:
            self.start_music()

    def _snd(self, x):
        a = np.clip(x, -1, 1)
        a = (a * 32000).astype(np.int16)
        return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([a, a])))

    def play(self, name, now=None):
        if not (self.ok and self.sfx_on) or name not in self.sounds:
            return
        t = pygame.time.get_ticks()
        if t - self.last.get(name, -1000) < 90:      # 같은 소리가 너무 겹치지 않게
            return
        self.last[name] = t
        self.sounds[name].play()

    def start_music(self):
        if not self.ok: return
        if self.music is None:
            self.music = self._snd(make_music())
        self.channel = self.music.play(loops=-1)
        if self.channel: self.channel.set_volume(0.55)

    def set_music(self, on):
        self.music_on = on
        if not self.ok: return
        if on and (self.channel is None or not self.channel.get_busy()):
            self.start_music()
        elif not on and self.music is not None:
            self.music.stop()
