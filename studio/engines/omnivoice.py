"""Motor OmniVoice (k2-fsa/OmniVoice): clonagem pela referência `voice/ref.wav` + `voice/ref.txt` do projeto.

Mantém exatamente a chamada que `generate.py` fazia antes da interface de motores (R50).
"""
from . import Engine


class OmniVoiceEngine(Engine):
    id = "omnivoice"
    sample_rate = 24000
    chars_per_second = 13.5
    rate_range = (10.0, 17.0)

    def __init__(self, device="cpu", steps=32, **options):
        super().__init__(device=device, steps=steps, **options)
        self.device, self.steps = device, steps
        self.model = self.voice = None

    def load(self, voice) -> None:
        import torch
        from omnivoice.models.omnivoice import OmniVoice
        self.voice = dict(voice)
        self.model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=self.device, dtype=torch.float16)
        self.sample_rate = self.model.sampling_rate

    def synth(self, text: str, attempt: int):
        import torch
        torch.manual_seed(1000 + attempt)
        w = torch.as_tensor(self.model.generate(text=text, language=self.voice.get("language", "pt"),
                                                ref_audio=self.voice["ref_wav"], ref_text=self.voice["ref_txt"],
                                                num_step=self.steps, guidance_scale=2.0)[0]).float()
        w = w if w.dim() == 2 else w[None]
        return w[0].cpu().numpy()
