"""Motor Pocket TTS (kyutai/pocket-tts 4.0.1), modelo `portuguese_24l`.

A voz vem de um dicionário no formato do manifest.json:
  {"model": "portuguese_24l", "file": "voz_portuguese_24l.safetensors"}   voz exportada (padrão e clonadas)
  {"model": "portuguese_24l", "name": "rafael"}                           voz pronta do catálogo
  {"model": "portuguese_24l", "ref_wav": "ref.wav"}                       clonar agora: exige login no Hugging Face
Sem login, o Pocket baixa os pesos sem clonagem; a voz exportada e as vozes prontas funcionam, e clonar é recusado.
"""
import re

from . import Engine

MAX_TOKENS = 50     # limite do Pocket por pedaço; acima disso ele avisa "generation may skip words"
TARGET_TOKENS = 40  # alvo do pré-corte, com folga para o que o Pocket acrescenta ao preparar o texto

_FECHA = "\"'\u201d\u2019)\\]\u00bb"
_FIM_DE_FRASE = re.compile(r"[.!?\u2026]+[" + _FECHA + r"]*(?=\s)")
_PAUSA = re.compile(r"[,;:][" + _FECHA + r"]*(?=\s)")


def _partir(texto, padrao):
    """Corta o texto logo depois de cada ocorrência do padrão (que exige espaço em seguida, logo 3.5 fica inteiro)."""
    partes, ini = [], 0
    for m in padrao.finditer(texto):
        partes.append(texto[ini:m.end()].strip()); ini = m.end()
    resto = texto[ini:].strip()
    if resto:
        partes.append(resto)
    return [x for x in partes if x]


def _por_palavra(texto, n_tokens, alvo):
    partes, atual = [], ""
    for palavra in texto.split():
        cand = (atual + " " + palavra).strip()
        if atual and n_tokens(cand) > alvo:
            partes.append(atual); atual = palavra
        else:
            atual = cand
    if atual:
        partes.append(atual)
    return partes


def _agrupar(partes, n_tokens, alvo):
    grupos, atual = [], ""
    for parte in partes:
        cand = (atual + " " + parte).strip()
        if atual and n_tokens(cand) > alvo:
            grupos.append(atual); atual = parte
        else:
            atual = cand
    if atual:
        grupos.append(atual)
    return grupos


_PALAVRA = re.compile(r"[^\W\d_]+")


def sem_caixa_alta(texto):
    """Palavras em maiúsculas vão para minúsculas: o Pocket as lê devagar e perde palavras. Vale para palavras de
    duas letras ou mais e para letras sozinhas vizinhas delas ("GUERRA É PAZ"); "a letra A" fica. A primeira letra
    do texto continua maiúscula."""
    ms = list(_PALAVRA.finditer(texto))
    alta = [m.group(0).isupper() for m in ms]
    longa = [a and len(m.group(0)) >= 2 for a, m in zip(alta, ms)]
    partes, fim = [], 0
    for i, m in enumerate(ms):
        vizinha_longa = (i > 0 and longa[i - 1]) or (i + 1 < len(ms) and longa[i + 1])
        if alta[i] and (longa[i] or vizinha_longa):
            partes += [texto[fim:m.start()], m.group(0).lower()]; fim = m.end()
    novo = "".join(partes) + texto[fim:]
    if novo != texto and novo[:1].islower() and texto[:1].isupper():
        novo = novo[0].upper() + novo[1:]
    return novo


def cortar(texto, n_tokens, alvo=TARGET_TOKENS):
    """Pedaços de até `alvo` tokens, na ordem de preferência do design: fim de frase; vírgula, ponto e vírgula
    ou dois pontos; e fronteira de palavra como último recurso. `n_tokens(texto)` conta como o modelo conta."""
    texto = sem_caixa_alta(" ".join(texto.split()))
    if not texto:
        return []
    if n_tokens(texto) <= alvo:
        return [texto]
    partes = []
    for frase in _partir(texto, _FIM_DE_FRASE):
        if n_tokens(frase) <= alvo:
            partes.append(frase); continue
        for parte in _partir(frase, _PAUSA):
            partes += [parte] if n_tokens(parte) <= alvo else _por_palavra(parte, n_tokens, alvo)
    return _agrupar(partes, n_tokens, alvo)

CLONAGEM_BLOQUEADA = ("Para usar a sua voz, entre na sua conta do Hugging Face e aceite os termos do Pocket TTS. "
                      "Sem isso, só a voz padrão e as vozes prontas funcionam.")


class PocketEngine(Engine):
    id = "pocket"
    model_name = "portuguese_24l"
    sample_rate = 24000
    chars_per_second = 16.6
    rate_range = (12.0, 19.5)  # calibrada no capítulo de referência (T6): perdas apareceram acima de 20 car/s

    def __init__(self, device="cpu", **options):
        super().__init__(device=device, **options)
        self.device = device
        self.model = self.state = None
        self.model_name = None

    def load(self, voice) -> None:
        voice = dict(voice or {})
        name = voice.get("model", "portuguese_24l")
        if self.model is None or self.model_name != name:
            from pocket_tts import TTSModel
            self.model = TTSModel.load_model(language=name)
            self.model_name = name
            self.sample_rate = self.model.sample_rate
        if voice.get("file"):
            fonte = voice["file"]
        elif voice.get("name"):
            fonte = voice["name"]
        elif voice.get("ref_wav"):
            if not self.model.has_voice_cloning:
                raise RuntimeError(CLONAGEM_BLOQUEADA)
            fonte = voice["ref_wav"]
        else:
            raise ValueError("Voz sem 'file', 'name' nem 'ref_wav'")
        self.state = self.model.get_state_for_audio_prompt(fonte)

    def n_tokens(self, text: str) -> int:
        """Tokens que o Pocket vai contar, depois de preparar o texto como ele prepara."""
        from pocket_tts.models.text_chunking import prepare_text_prompt
        m = self.model
        t, _ = prepare_text_prompt(text, m.pad_with_spaces_for_short_inputs, m.remove_semicolons,
                                   m.append_terminal_punctuation, m.capitalize_first_letter, m.replace_characters)
        return len(m.flow_lm.conditioner.tokenizer(t.strip())[0])

    def split(self, text: str) -> list:
        return cortar(text, self.n_tokens, TARGET_TOKENS)

    def synth(self, text: str, attempt: int):
        import torch
        torch.manual_seed(1000 + attempt)
        w = self.model.generate_audio(self.state, text, max_tokens=MAX_TOKENS)
        return w.detach().float().cpu().numpy().reshape(-1)
