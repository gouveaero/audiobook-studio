"""Motor falso para testes sem modelo: áudio sintético com duração proporcional ao texto, em milissegundos.

Como o generate.py roda em outro processo nos testes de retomada, a configuração vem do ambiente:
  FAKE_ENGINE_RATE        caracteres por segundo do áudio gerado (padrão 15, dentro da faixa)
  FAKE_ENGINE_FIX_AFTER   a partir desta tentativa (0 = primeira) o ritmo volta ao padrão
  FAKE_ENGINE_MAX_CHARS   corta o trecho em pedaços de até N caracteres (padrão: sem corte)
  FAKE_ENGINE_DELAY       segundos de espera por síntese (simula a lentidão do modelo)
  FAKE_ENGINE_LOG         arquivo onde cada síntese é registrada (uma linha por chamada)
  FAKE_ENGINE_FAIL        texto que, se aparecer no trecho, faz a síntese falhar com RuntimeError
"""
import os
import time

import numpy as np

from studio.engines import Engine


class FakeEngine(Engine):
    id = "fake"
    model_name = "fake"
    sample_rate = 16000
    chars_per_second = 15.0
    rate_range = (10.0, 17.0)

    def load(self, voice) -> None:
        self.voice = dict(voice or {})

    def split(self, text: str) -> list:
        limite = int(os.environ.get("FAKE_ENGINE_MAX_CHARS", "0") or 0)
        if limite <= 0 or len(text) <= limite:
            return [text]
        pedacos, atual = [], ""
        for palavra in text.split():
            cand = (atual + " " + palavra).strip()
            if atual and len(cand) > limite:
                pedacos.append(atual); atual = palavra
            else:
                atual = cand
        if atual:
            pedacos.append(atual)
        return pedacos

    def synth(self, text: str, attempt: int):
        rate = float(os.environ.get("FAKE_ENGINE_RATE", "") or self.chars_per_second)
        fix = os.environ.get("FAKE_ENGINE_FIX_AFTER", "")
        if fix != "" and attempt >= int(fix):
            rate = self.chars_per_second
        falha = os.environ.get("FAKE_ENGINE_FAIL", "")
        if falha and falha in text:
            raise RuntimeError(f"motor falso: falha pedida em {text!r}")
        delay = float(os.environ.get("FAKE_ENGINE_DELAY", "0") or 0)
        if delay:
            time.sleep(delay)
        log = os.environ.get("FAKE_ENGINE_LOG")
        if log:
            with open(log, "a", encoding="utf8") as f:
                f.write(f"{attempt}\t{text}\n")
        n = max(1, int(round(len(text) / rate * self.sample_rate)))
        t = np.arange(n, dtype=np.float32) / self.sample_rate
        return (0.2 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
