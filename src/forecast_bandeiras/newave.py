"""Saídas do NEWAVE por série (nwlistop) e escolha de séries pela ENA.

Lê as 2.000 séries de um deck (geração hidráulica, ENA, custo marginal por submercado),
monta o PLD gatilho de cada série (fórmula do boletim: 4 submercados, limites por patamar,
ponderação pela carga) e escolhe as séries cuja trajetória de ENA mais se aproxima de uma
trajetória de referência (a prevista pelo ECMWF; no backtest, a realizada).
Ver docs/metodologia.md, seções 8.3 a 8.5.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

from forecast_bandeiras import load, regra

SUBS = {"SE": 1, "S": 2, "NE": 3, "N": 4}


def caminho_deck(ano: int, mes: int) -> Path:
    """Pasta com as saídas do NEWAVE do deck de um mês."""
    return load.DATA_RAW / "ons_newave" / str(ano) / f"{ano}_{mes:02d}"


def ler_nwlistop(caminho: Path, somar_patamares: bool = True) -> pd.DataFrame:
    """Lê uma saída anual do nwlistop: colunas ano, serie, (pat), mes, valor.

    Os arquivos são por ano civil (colunas jan–dez); meses anteriores ao início do
    estudo vêm zerados. Arquivos por patamar têm 3 linhas por série; com
    `somar_patamares=True` elas são somadas (vale para grandezas em MWmês).
    """
    linhas, ano, serie, por_pat = [], None, None, False
    for ln in Path(caminho).read_text(encoding="latin-1").splitlines():
        m = re.match(r"\s+ANO:\s+(\d{4})", ln)
        if m:
            ano = int(m.group(1))
            continue
        p = ln.split()
        if p[:1] == ["PAT"]:
            por_pat = True
            continue
        if not ano or not p or not p[0].isdigit():
            continue
        if por_pat and len(p) == 15:
            serie, pat, valores = int(p[0]), int(p[1]), p[2:14]
        elif por_pat and len(p) == 14:
            pat, valores = int(p[0]), p[1:13]
        elif not por_pat and len(p) == 14:
            serie, pat, valores = int(p[0]), 0, p[1:13]
        else:
            continue
        linhas.append([ano, serie, pat] + [float(x) for x in valores])
    df = pd.DataFrame(linhas, columns=["ano", "serie", "pat"] + list(range(1, 13)))
    df = df.melt(id_vars=["ano", "serie", "pat"], var_name="mes", value_name="valor")
    if somar_patamares:
        return df.groupby(["ano", "serie", "mes"], as_index=False).valor.sum()
    return df


def _tabela(df: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Série x mês de um ano."""
    return df[df.ano == ano].pivot(index="serie", columns="mes", values="valor")


def carregar_deck(ano: int, mes: int) -> dict:
    """Carrega gh (SIN) e ENA (SIN e por submercado) do deck, série x mês do ano do deck."""
    pasta = caminho_deck(ano, mes)
    ena = {
        s: _tabela(ler_nwlistop(pasta / f"eafbm00{i}.out"), ano)
        for s, i in SUBS.items()
    }
    return {
        "ano": ano,
        "mes_inicio": mes,
        "gh": _tabela(ler_nwlistop(pasta / "ghtotsin.out"), ano),
        "ena": ena,
        "ena_sin": sum(ena.values()),
    }


def pld_gatilho_series(
    deck: dict, meses, pld_min: float, pld_max: float
) -> pd.DataFrame:
    """PLD gatilho de cada série (série x mês), como no boletim da CCEE.

    Custo marginal limitado ao PLD mín/máx por patamar e submercado, média do mês pelas
    horas de cada patamar e ponderação dos 4 submercados pela carga média do mês
    (`relato.rv0` do PMO do mês).
    """
    pasta = caminho_deck(deck["ano"], deck["mes_inicio"])
    ano = deck["ano"]
    cmo = {
        s: ler_nwlistop(pasta / f"cmarg00{i}.out", somar_patamares=False)
        for s, i in SUBS.items()
    }
    saida = {}
    for mes in meses:
        horas = load.horas_por_semana(ano, mes)
        peso_pat = (horas.sum(axis=1) / horas.to_numpy().sum()).to_numpy()
        bal = load.ler_relato_balanco(ano, mes)
        carga = {
            s: regra.media_mensal_df(bal[bal.subsistema == s], "mercado", horas)
            for s in SUBS
        }
        total = sum(carga.values())
        pld = 0.0
        for s in SUBS:
            d = cmo[s][(cmo[s].ano == ano) & (cmo[s].mes == mes)]
            d = d.pivot(index="serie", columns="pat", values="valor").sort_index(axis=1)
            pld_s = (d.clip(pld_min, pld_max).to_numpy() * peso_pat).sum(axis=1)
            pld = pld + pld_s * carga[s] / total
        saida[mes] = pd.Series(pld, index=d.index)
    return pd.DataFrame(saida)


def distancia_trajetoria(
    ena_sin: pd.DataFrame, referencia: pd.Series, meia_vida: float = 2.0
) -> pd.Series:
    """Distância de cada série à trajetória de ENA de referência (erro relativo ao quadrado).

    `referencia` é indexada pelos meses da trajetória (do início do deck ao mês-alvo);
    os meses mais recentes pesam mais (meia-vida em meses).
    """
    meses = list(referencia.index)
    pesos = 0.5 ** (np.arange(len(meses))[::-1] / meia_vida)
    erro = (ena_sin[meses] - referencia.values) / referencia.values
    return (erro**2 * pesos).sum(axis=1) / pesos.sum()


def escolher_series(
    ena_sin: pd.DataFrame, referencia: pd.Series, k: int = 25
) -> pd.Index:
    """As k séries de trajetória de ENA mais próxima da referência."""
    return distancia_trajetoria(ena_sin, referencia).nsmallest(k).index


def gsf_series(deck: dict, base_mes: pd.DataFrame) -> pd.DataFrame:
    """GSF_band de cada série (série x mês), sem arredondar.

    Converte a geração hidráulica total da série em GH_band com os ajustes reais do mês
    (ANDE, perdas e PCH no MRE, da base mensal) e divide pelo GF_band oficial.
    `base_mes` é a base mensal do ano do deck indexada pelo número do mês.
    """
    saida = {}
    for mes in base_mes.index:
        if mes not in deck["gh"].columns:
            continue
        r = base_mes.loc[mes]
        f = regra.fatores_vigentes(deck["ano"], mes)
        kf = (1 - f["perda_bruta_conexao"]) * (1 - f["perda_conexao_cg"])
        pch_cg = r.gh_band - (r.gh_ons - r.ande) * kf
        saida[mes] = ((deck["gh"][mes] - r.ande) * kf + pch_cg) / r.gf_band_boletim
    return pd.DataFrame(saida)


def escolher_series_mes(
    ena_sin: pd.DataFrame, mes: int, ena_ref: float, k: int = 10
) -> pd.Index:
    """As k séries com ENA do SIN no mês mais próxima da referência (método do GSF)."""
    return ((ena_sin[mes] - ena_ref).abs()).nsmallest(k).index


def probabilidade_cores(gsf: pd.Series, pld: pd.Series) -> pd.Series:
    """Probabilidade de cada cor combinando todas as séries de GSF com todas as de preço."""
    cores = [regra.cor_bandeira(round(g, 2), p) for g in gsf for p in pld]
    ordem = ["Verde", "Amarela", "Vermelha 1", "Vermelha 2"]
    return pd.Series(cores).value_counts(normalize=True).reindex(ordem, fill_value=0.0)


def probabilidade_cores_pareada(gsf: pd.Series, pld: pd.Series) -> pd.Series:
    """Probabilidade de cada cor usando o GSF e o preço da MESMA série (fração das séries).

    `gsf` e `pld` são indexados pelas mesmas séries; mantém a coerência de cada cenário
    (série seca: GSF baixo e preço alto juntos).
    """
    cores = [regra.cor_bandeira(round(gsf[s], 2), pld[s]) for s in gsf.index]
    ordem = ["Verde", "Amarela", "Vermelha 1", "Vermelha 2"]
    return pd.Series(cores).value_counts(normalize=True).reindex(ordem, fill_value=0.0)


def cor_mediana(prob: pd.Series) -> str:
    """Cor mediana: a primeira cor (verde → vermelha 2) em que a probabilidade acumulada chega a 50%."""
    acumulada = (
        prob.reindex(["Verde", "Amarela", "Vermelha 1", "Vermelha 2"])
        .fillna(0)
        .cumsum()
    )
    return acumulada[acumulada >= 0.5 - 1e-9].index[0]


def probabilidade_calibrada(
    x_medio: float, sigma: float, gsf_medio: float
) -> pd.Series:
    """Probabilidade de cada cor a partir do X médio e do erro típico da média (σ).

    X = PLD × (1 − GSF). Supõe-se que o X real fica em torno do X médio com desvio σ
    (normal, sem deslocamento); a probabilidade de cada cor é a chance de o X real cair na
    faixa da cor (limites 27,48 / 68,99 / 95,05 R$/MWh). σ é o desvio padrão do erro
    histórico (X real − X médio). Com GSF médio ≥ 0,96 o preço quase não importa: verde 100%.
    A cor mais provável é sempre a cor da média.
    """
    from scipy.stats import norm

    ordem = ["Verde", "Amarela", "Vermelha 1", "Vermelha 2"]
    if gsf_medio >= 0.96:
        return pd.Series([1.0, 0.0, 0.0, 0.0], index=ordem)
    acumulada = norm.cdf(list(regra.LIMITES_X.values()), loc=x_medio, scale=sigma)
    return pd.Series(np.diff(np.r_[0.0, acumulada, 1.0]), index=ordem)
