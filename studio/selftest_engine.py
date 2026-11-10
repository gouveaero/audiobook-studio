"""Motor mínimo só para --self-test no app empacotado (não aparece na UI).

Cópia enxuta do FakeEngine dos testes: áudio sintético sem Pocket.
"""
from __future__ import annotations

import os
import time

import numpy as np

from studio.engines import Engine


class SelftestEngine(Engine):
    id = "selftest"
    model_name = "selftest"
    sample_rate = 16000
    chars_per_second = 15.0
    rate_range = (10.0, 17.0)

    def load(self, voice) -> None:
        self.voice = dict(voice or {})

    def split(self, text: str) -> list:
        return [text]

    def synth(self, text: str, attempt: int):
        delay = float(os.environ.get("FAKE_ENGINE_DELAY", "0.05") or 0.05)
        if delay:
            time.sleep(delay)
        n = max(1, int(round(len(text) / self.chars_per_second * self.sample_rate)))
        t = np.arange(n, dtype=np.float32) / self.sample_rate
        return (0.2 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
