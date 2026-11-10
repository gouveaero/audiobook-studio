"""Motores de voz. Cada motor implementa `Engine`; `generate.py` só conversa com essa interface.

O motor vem de `config.json` (`"motor"`), com padrão `omnivoice` quando o campo não existe, para os projetos
antigos e a nuvem continuarem iguais. Também aceita um caminho `modulo:Classe` (os testes usam
`tests.fake_engine:FakeEngine`). `torch` e os modelos só são importados dentro de `load`, para os testes
sem modelo não precisarem deles.
"""
import importlib

ENGINES = {
    "omnivoice": "studio.engines.omnivoice:OmniVoiceEngine",
    "pocket": "studio.engines.pocket:PocketEngine",
}
DEFAULT_ENGINE = "omnivoice"


class Engine:
    id: str = ""
    sample_rate: int = 24000
    chars_per_second: float = 15.0        # usado no painel e nas estimativas
    rate_range: tuple = (10.0, 17.0)      # faixa aceitável de caracteres por segundo

    def __init__(self, **options):
        self.options = options

    def load(self, voice) -> None:
        """Carrega o modelo e a voz. `voice` é um dicionário; cada motor lê as chaves que usa."""
        raise NotImplementedError

    def split(self, text: str) -> list:
        """Trechos dentro do limite do motor. Sem limite: o texto inteiro."""
        return [text]

    def synth(self, text: str, attempt: int):
        """Áudio mono float32 (numpy) de `text`; `attempt` muda a semente."""
        raise NotImplementedError


def engine_name(config) -> str:
    """Nome do motor a partir do config.json já lido. Aceita o rótulo antigo do painel ("OmniVoice")."""
    nome = (config or {}).get("motor") or DEFAULT_ENGINE
    nome = str(nome).strip()
    return nome.lower() if nome.lower() in ENGINES else nome


def load_engine(name: str, **options) -> Engine:
    """Instancia o motor pelo nome (`omnivoice`, `pocket`) ou por `modulo:Classe`. Não carrega o modelo."""
    alvo = ENGINES.get(name.lower(), name)
    if ":" not in alvo:
        raise ValueError(f"Motor desconhecido: {name!r}. Opções: {', '.join(sorted(ENGINES))} ou modulo:Classe")
    modulo, classe = alvo.split(":", 1)
    try:
        cls = getattr(importlib.import_module(modulo), classe)
    except (ImportError, AttributeError) as e:
        raise ValueError(f"Motor {name!r} não encontrado ({e})") from e
    return cls(**options)
