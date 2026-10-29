"""Normalização de texto em português do Brasil para fala: números, datas, horas, romanos, abreviações.

Cada idioma tem o seu módulo `normalize_<lang>.py` com uma função `normalize(texto) -> texto`.
Sem módulo para o idioma, o texto passa como está (o modelo lê números por conta própria, com mais erros).
"""
import re

from num2words import num2words

ROMAN = re.compile(r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")


def n2w(n, **kw):
    return num2words(n, lang="pt_BR", **kw).replace(",", "")


def roman(s):
    v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    t = 0
    for i, c in enumerate(s):
        t += -v[c] if i + 1 < len(s) and v[c] < v[s[i + 1]] else v[c]
    return t


def roman_words(s, ordinal_ok):
    n = roman(s)
    return n2w(n, to="ordinal") if ordinal_ok and n <= 10 else n2w(n)


def normalize(t):
    t = t.replace("\xa0", " ").replace("’", "'").replace("[...]", "…").replace("[", "").replace("]", "")
    t = re.sub(r"\ba\.\s?C\.", "antes de Cristo", t)
    t = re.sub(r"\bd\.\s?C\.", "depois de Cristo", t)
    # século XIII -> século treze
    t = re.sub(r"\b([Ss]éculos?)\s+([IVXLCDM]{1,8})\b(?!\.\w)",
               lambda m: m.group(1) + " " + roman_words(m.group(2), False) if ROMAN.match(m.group(2)) else m.group(0), t)
    # Henrique VIII -> Henrique oitavo; Pedro II -> Pedro segundo
    def nome(m):
        return m.group(1) + " " + roman_words(m.group(2), True) if ROMAN.match(m.group(2)) else m.group(0)
    t = re.sub(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,})\s+([IVX]{1,6})\b(?!\w)", nome, t)

    def hora(m):
        h = n2w(int(m.group(1))) + (" hora" if int(m.group(1)) == 1 else " horas")
        return h + (" e " + n2w(int(m.group(2))) if m.group(2) and int(m.group(2)) else "")
    t = re.sub(r"\b(\d{1,2})h(\d{2})?\b", hora, t)
    t = re.sub(r"(\d+(?:,\d+)?)\s?%", lambda m: m.group(1) + " por cento", t)
    t = re.sub(r"(?<=\d)\s?[–-]\s?(?=\d)", " a ", t)
    t = re.sub(r"\b(\d{1,3}(?:\.\d{3})+)\b", lambda m: m.group(1).replace(".", ""), t)
    t = re.sub(r"\b(\d+)º\b", lambda m: n2w(int(m.group(1)), to="ordinal"), t)
    t = re.sub(r"\b(\d+),(\d+)\b", lambda m: n2w(float(m.group(1) + "." + m.group(2))) if len(m.group(2)) <= 3 else m.group(0), t)
    t = re.sub(r"\b\d+\b", lambda m: n2w(int(m.group(0))) if int(m.group(0)) < 10**9 else m.group(0), t)
    for a, b in ((r"\bkm\b", "quilômetros"), (r"\bSr\.", "senhor"), (r"\bSra\.", "senhora"), (r"\bDr\.", "doutor")):
        t = re.sub(a, b, t)
    return re.sub(r"\s+", " ", t).strip()


def number_to_words(n):
    return n2w(n)
