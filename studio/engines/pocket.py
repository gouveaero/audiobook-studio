"""Motor Pocket TTS (kyutai/pocket-tts 4.0.1), modelo `portuguese_24l`.

A voz vem de um dicionário no formato do manifest.json:
  {"model": "portuguese_24l", "file": "voz_portuguese_24l.safetensors"}   voz exportada (padrão e clonadas)
  {"model": "portuguese_24l", "name": "rafael"}                           voz pronta do catálogo
  {"model": "portuguese_24l", "ref_wav": "ref.wav"}                       clonar agora: exige login no Hugging Face
Sem login, o Pocket baixa os pesos sem clonagem; a voz exportada e as vozes prontas funcionam, e clonar é recusado.
"""
from . import Engine

MAX_TOKENS = 50  # limite do Pocket por pedaço; acima disso ele avisa "generation may skip words"

CLONAGEM_BLOQUEADA = ("Para usar a sua voz, entre na sua conta do Hugging Face e aceite os termos do Pocket TTS. "
                      "Sem isso, só a voz padrão e as vozes prontas funcionam.")


class PocketEngine(Engine):
    id = "pocket"
    sample_rate = 24000
    chars_per_second = 16.6
    rate_range = (10.0, 22.0)  # provisória; calibrada na T6

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

    def synth(self, text: str, attempt: int):
        import torch
        torch.manual_seed(1000 + attempt)
        w = self.model.generate_audio(self.state, text, max_tokens=MAX_TOKENS)
        return w.detach().float().cpu().numpy().reshape(-1)
