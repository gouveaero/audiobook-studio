"""Leitura e escrita de WAV mono sem torch. Escreve em 16 bits; lê também os antigos em float32 (torchaudio)."""
import numpy as np


def read_wav(path):
    """Devolve (amostras float32 em [-1, 1], taxa)."""
    from scipy.io import wavfile
    sr, data = wavfile.read(path)
    if data.ndim == 2:
        data = data[:, 0]
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128.0) / 128.0
    else:
        data = data.astype(np.float32)
    return data, int(sr)


def write_wav(path, samples, sr):
    """Grava mono em 16 bits PCM."""
    from scipy.io import wavfile
    s = np.asarray(samples, dtype=np.float32).reshape(-1)
    wavfile.write(path, int(sr), (np.clip(s, -1.0, 1.0) * 32767.0).astype(np.int16))
