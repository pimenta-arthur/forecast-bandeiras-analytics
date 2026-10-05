"""Carregamento de dados.

Funções para ler os dados brutos de data/raw/ (somente leitura), aplicar a
limpeza básica (tipos, datas, valores ausentes) e salvar/ler os dados limpos
em formato parquet em data/processed/.
"""

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
DATA_RAW = RAIZ / "data" / "raw"
DATA_PROCESSED = RAIZ / "data" / "processed"

PATAMARES = ["PESADO", "MEDIO", "LEVE"]  # mesma ordem dos patamares 1, 2 e 3 do DECOMP
SUBSISTEMAS = {"SECO": "SE", "SUL": "S", "NE": "NE", "N": "N"}


def _normaliza(texto) -> str:
    """Remove acentos, espaços nas pontas e passa para maiúsculas."""
    return (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", "ignore")
        .decode()
        .strip()
        .upper()
    )


# ---------------------------------------------------------------------------
# Patamares de carga (CCEE, arquivo horário AAC001)
# ---------------------------------------------------------------------------


def ler_patamares(ano: int) -> pd.DataFrame:
    """Lê o arquivo horário de patamares da CCEE (AAC001) de um ano.

    O layout muda entre anos (2025: colunas DIA + HORA; 2026: DATA REFERÊNCIA),
    então a linha de cabeçalho e as colunas são localizadas pelo nome.

    Retorna um DataFrame com uma linha por hora: `ts` (início da hora) e `patamar`
    (PESADO, MEDIO ou LEVE).
    """
    arquivo = next((DATA_RAW / "patamar" / str(ano)).glob("AAC001*.xlsx"))
    bruto = pd.read_excel(arquivo, header=None)
    linha = next(
        i for i, r in bruto.iterrows() if any(_normaliza(v) == "PATAMAR" for v in r)
    )
    df = bruto.iloc[linha + 1 :].copy()
    df.columns = [_normaliza(c) for c in bruto.iloc[linha]]

    if "DATA REFERENCIA" in df:
        ts = pd.to_datetime(df["DATA REFERENCIA"])
    else:
        ts = pd.to_datetime(df["DIA"]) + pd.to_timedelta(df["HORA"].astype(str))

    out = pd.DataFrame({"ts": ts, "patamar": df["PATAMAR"].map(_normaliza)}).dropna()
    if len(out) not in (8760, 8784):
        raise ValueError(
            f"{arquivo.name}: esperado um ano de horas, encontrado {len(out)}"
        )
    return out.reset_index(drop=True)


def horas_por_semana(ano: int, mes: int) -> pd.DataFrame:
    """Horas de cada patamar em cada semana operativa, contando só as horas dentro do mês.

    A semana operativa vai de sábado a sexta; a semana 1 é a que contém o dia 1.
    Retorna uma tabela patamar (linhas: PESADO, MEDIO, LEVE) x semana (colunas 1..n),
    no mesmo formato da Tabela 11 do boletim InfoBandeira.
    """
    h = ler_patamares(ano)
    h = h[h.ts.dt.month == mes].copy()
    dia = h.ts.dt.normalize()
    h["inicio_semana"] = dia - pd.to_timedelta((dia.dt.dayofweek - 5) % 7, unit="D")
    h["semana"] = h.inicio_semana.rank(method="dense").astype(int)
    tabela = h.groupby(["patamar", "semana"]).size().unstack(fill_value=0)
    return tabela.reindex(PATAMARES, fill_value=0)


# ---------------------------------------------------------------------------
# Sumário do DECOMP rv0 do PMO (ONS)
# ---------------------------------------------------------------------------


def caminho_sumario(ano: int, mes: int) -> Path:
    """Caminho do sumario.rv0 do PMO de um mês."""
    return DATA_RAW / "ons_decomp" / str(ano) / f"{ano}_{mes:02d}" / "sumario.rv0"


def _numeros(linha: str, n: int) -> list[float]:
    """Últimos n números de uma linha de tabela do sumário."""
    return [float(v) for v in linha.split()[-n:]]


def _bloco(linhas: list[str], titulo: str) -> list[str]:
    """Linhas de um bloco do sumário, do título até a linha de fechamento da tabela."""
    inicio = next(i for i, ln in enumerate(linhas) if ln.strip() == titulo)
    bloco, bordas = [], 0
    for ln in linhas[inicio + 1 :]:
        if ln.strip().startswith("X-"):
            bordas += 1
            if bordas == 3:  # cabeçalho tem 2 bordas; a 3ª fecha a tabela
                break
            continue
        bloco.append(ln)
    return bloco


def ler_sumario(ano: int, mes: int) -> dict:
    """Extrai do sumario.rv0 os valores por patamar e semana usados no cálculo do GH_band.

    Retorna um dicionário de arrays patamar (3 linhas: pesado, médio, leve) x semana:
    - `gh`: geração hidráulica total (linha `Totais`, inclui Itaipu 50 e 60 Hz), MWmed;
    - `ande`: geração de Itaipu para a ANDE + consumo interno, MWmed;
    - `pch`: dicionário subsistema -> geração das PCH/CGH (linhas `*_PCH`, sem `gd`), MWmed.

    O CMO deste arquivo NÃO é o PLD gatilho (ver CLAUDE.md); por isso não é lido aqui.
    """
    linhas = caminho_sumario(ano, mes).read_text(encoding="latin-1").splitlines()

    titulo_gh = "GERACAO HIDRAULICA (MWmed) PARA O PATAMAR {}"
    cabecalho = next(ln for ln in _bloco(linhas, titulo_gh.format(1)) if "Sem_01" in ln)
    n_sem = len(re.findall(r"Sem_\d+", cabecalho))

    gh = []
    for p in (1, 2, 3):
        totais = next(
            ln
            for ln in _bloco(linhas, titulo_gh.format(p))
            if ln.strip().startswith("Totais")
        )
        gh.append(_numeros(totais, n_sem))

    itaipu = _bloco(linhas, "GERACAO HIDRAULICA EM ITAIPU (MWmed)")
    ande = [_numeros(ln, n_sem) for ln in itaipu if ln.strip().startswith("Ande")]
    if len(ande) != 3:
        raise ValueError(
            f"esperadas 3 linhas 'Ande' (uma por patamar), encontradas {len(ande)}"
        )

    pch = {s: [] for s in SUBSISTEMAS.values()}
    for p in (1, 2, 3):
        for ln in _bloco(linhas, f"PEQUENAS USINAS : DESPACHO NO PATAMAR {p} (MWmed)"):
            m = re.match(r"\s*(\w+)_PCH\s+\w+\s", ln)
            if m and m.group(1) in SUBSISTEMAS:
                pch[SUBSISTEMAS[m.group(1)]].append(_numeros(ln, n_sem))

    return {
        "gh": np.array(gh),
        "ande": np.array(ande),
        "pch": {s: np.array(v) for s, v in pch.items()},
    }
