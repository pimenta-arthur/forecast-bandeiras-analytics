"""Regra de acionamento da bandeira tarifária.

Reproduz a memória de cálculo do boletim InfoBandeira da CCEE: GH_band a partir do
relato.rv0 do PMO (DECOMP rv0), GSF_band = GH_band / GF_band e a cor pelo ábaco da
REH 3.306/2024. Detalhes e validação em docs/metodologia.md (seções 3.1 a 3.6).
"""

import numpy as np
import pandas as pd

from forecast_bandeiras import load

# Fatores da CCEE aplicados à geração (Tabela 3 do boletim), em fração.
# Cada conjunto vale a partir do mês indicado (média de um ano anterior, atualizada
# por volta de março). Fonte: boletins InfoBandeira de 2023 a 2026.
FATORES = {
    "2023-01": {
        "perda_bruta_conexao": 0.01458,
        "perda_conexao_cg": 0.02506,
        "part_pch_mre": 0.62464,
        "perda_pch_cg": 0.00125,
    },
    "2023-03": {
        "perda_bruta_conexao": 0.01275,
        "perda_conexao_cg": 0.02595,
        "part_pch_mre": 0.65089,
        "perda_pch_cg": 0.00085,
    },
    "2024-04": {
        "perda_bruta_conexao": 0.01391,
        "perda_conexao_cg": 0.02342,
        "part_pch_mre": 0.64795,
        "perda_pch_cg": 0.00082,
    },
    "2025-03": {
        "perda_bruta_conexao": 0.01335,
        "perda_conexao_cg": 0.02151,
        "part_pch_mre": 0.64973,
        "perda_pch_cg": 0.00076,
    },
    "2026-03": {
        "perda_bruta_conexao": 0.01283,
        "perda_conexao_cg": 0.02454,
        "part_pch_mre": 0.61153,
        "perda_pch_cg": 0.00063,
    },
}

# Limites do índice X = PLD × (1 − GSF) para cada cor (Anexo I da REH 3.306/2024), em R$/MWh.
LIMITES_X = {"Verde": 27.48, "Amarela": 68.99, "Vermelha 1": 95.05}


def fatores_vigentes(ano: int, mes: int) -> dict:
    """Fatores da CCEE vigentes no mês (o conjunto mais recente com início até o mês)."""
    periodo = pd.Period(f"{ano}-{mes:02d}", "M")
    validos = [k for k in FATORES if pd.Period(k, "M") <= periodo]
    if not validos:
        raise KeyError(
            f"sem fatores da CCEE cadastrados para {periodo}; incluir em FATORES a partir do boletim"
        )
    return FATORES[max(validos)]


def media_mensal(valores: np.ndarray, horas: pd.DataFrame) -> float:
    """Média mensal (MWmed) de valores patamar x semana, ponderada pelas horas no mês."""
    h = horas.to_numpy()
    if valores.shape != h.shape:
        raise ValueError(
            f"valores com {valores.shape} (patamar x semana), patamares com {h.shape}"
        )
    return float((valores * h).sum() / h.sum())


def media_mensal_df(df: pd.DataFrame, coluna: str, horas: pd.DataFrame) -> float:
    """Média mensal de uma coluna de tabela longa (semana, pat), somando as demais chaves."""
    if df.empty:
        return 0.0
    tabela = df.groupby(["pat", "semana"])[coluna].sum().unstack()
    tabela = tabela.reindex(index=[1, 2, 3], columns=horas.columns).fillna(0)
    return media_mensal(tabela.to_numpy(), horas)


def calcular_gh_band(ano: int, mes: int) -> dict:
    """Calcula o GH_band do mês a partir do relato.rv0 e das horas por patamar.

    GH ONS = Σ Ghid + Itaipu 60 Hz (balanço energético); ANDE do eco de Itaipu;
    PCH das pequenas usinas (linhas *_PCH, sem gd). Retorna as parcelas com os
    mesmos nomes do boletim (MWmed).
    """
    horas = load.horas_por_semana(ano, mes)
    bal = load.ler_relato_balanco(ano, mes)
    peq = load.ler_relato_pequenas(ano, mes)
    f = fatores_vigentes(ano, mes)

    gh_ons = media_mensal_df(bal, "ghid", horas) + media_mensal_df(bal, "it60", horas)
    ande = media_mensal_df(load.ler_relato_ande(ano, mes), "ande", horas)
    pch_linhas = peq[peq.tipo == "PCH"]
    pch = {
        s: media_mensal_df(pch_linhas[pch_linhas.subsistema == s], "mw", horas)
        for s in load.SUBSISTEMAS.values()
    }
    pch_total = sum(pch.values())

    gh_cg = (
        (gh_ons - ande) * (1 - f["perda_bruta_conexao"]) * (1 - f["perda_conexao_cg"])
    )
    pch_cg = pch_total * f["part_pch_mre"] * (1 - f["perda_pch_cg"])

    return {
        "gh_ons": gh_ons,
        "ande": ande,
        **{f"pch_{s}": v for s, v in pch.items()},
        "pch_total": pch_total,
        "gh_cg": gh_cg,
        "pch_cg": pch_cg,
        "gh_band": gh_cg + pch_cg,
    }


def gsf_band(gh_band: float, gf_band: float) -> float:
    """GSF_band = GH_band / GF_band, arredondado em 2 casas como pede a ANEEL."""
    return round(gh_band / gf_band, 2)


def cor_bandeira(gsf: float, pld_gatilho: float) -> str:
    """Cor pelo ábaco (sem GFOM), via X = PLD_gatilho × (1 − GSF).

    O PLD gatilho vem do deck da CCEE (cmdeco.rv0), não do CMO do relato/sumário do ONS.
    """
    x = pld_gatilho * max(0.0, 1 - gsf)
    for cor, limite in LIMITES_X.items():
        if x <= limite:
            return cor
    return "Vermelha 2"
