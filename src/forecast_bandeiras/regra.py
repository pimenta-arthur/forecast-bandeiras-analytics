"""Regra de acionamento da bandeira tarifária.

Reproduz a memória de cálculo do boletim InfoBandeira da CCEE: GH_band a partir do
sumario.rv0 do PMO, GSF_band = GH_band / GF_band e a cor pelo ábaco da REH 3.306/2024.
Detalhes e validação em docs/metodologia.md (seções 3.1 a 3.3).
"""

import numpy as np
import pandas as pd

from forecast_bandeiras import load

# Fatores da CCEE aplicados à geração (Tabela 3 do boletim), em fração.
# Cada conjunto vale a partir do mês indicado; são a média do ano anterior.
FATORES = {
    "2026-01": {
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
            f"sumário com {valores.shape} (patamar x semana), patamares com {h.shape}"
        )
    return float((valores * h).sum() / h.sum())


def calcular_gh_band(ano: int, mes: int) -> dict:
    """Calcula o GH_band do mês a partir do sumario.rv0 e das horas por patamar.

    Retorna as parcelas intermediárias com os mesmos nomes do boletim (MWmed).
    """
    sumario = load.ler_sumario(ano, mes)
    horas = load.horas_por_semana(ano, mes)
    f = fatores_vigentes(ano, mes)

    gh_ons = media_mensal(sumario["gh"], horas)
    ande = media_mensal(sumario["ande"], horas)
    pch = {s: media_mensal(v, horas) for s, v in sumario["pch"].items()}
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

    O PLD gatilho vem do deck da CCEE (cmdeco.rv0), não do CMO do sumario.rv0 do ONS.
    """
    x = pld_gatilho * max(0.0, 1 - gsf)
    for cor, limite in LIMITES_X.items():
        if x <= limite:
            return cor
    return "Vermelha 2"


def serie_gh_band(ano: int, meses=range(1, 13)) -> pd.DataFrame:
    """Calcula o GH_band e as parcelas para vários meses de um ano.

    Meses sem `sumario.rv0` em data/raw/ons_decomp/ são ignorados.
    Retorna um DataFrame indexado pelo mês (Period mensal).
    """
    linhas = {}
    for mes in meses:
        if not load.caminho_sumario(ano, mes).exists():
            continue
        linhas[pd.Period(f"{ano}-{mes:02d}", "M")] = calcular_gh_band(ano, mes)
    return pd.DataFrame.from_dict(linhas, orient="index").rename_axis("mes")
