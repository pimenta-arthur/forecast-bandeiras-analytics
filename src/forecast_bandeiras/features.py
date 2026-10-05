"""Engenharia de features.

Funções para criar as variáveis de entrada a partir dos dados limpos
(ex.: defasagens, médias móveis, variáveis de calendário), sempre tomando
cuidado para não usar informação do futuro (data leakage).
"""

import pandas as pd

from forecast_bandeiras import load, regra


def balanco_mes(ano: int, mes: int) -> dict:
    """Balanço mensal do DECOMP rv0 (MWmed) e variáveis do PMO para um mês.

    Segue o memorial de cálculo da seção 3.5 de docs/metodologia.md:
    hidráulica para o SIN = carga líquida − eólica − solar − térmica − PCH − PCT (+ resíduo).
    Todas as variáveis são as previstas pelo ONS no PMO do mês (mesmo conjunto de
    informação que gera o GH_band), não valores realizados.
    """
    horas = load.horas_por_semana(ano, mes)
    media = lambda arr: regra.media_mensal(arr, horas)
    b = load.ler_balanco_sumario(ano, mes)
    ren = load.ler_renovaveis(ano, mes)
    gh = regra.calcular_gh_band(ano, mes)
    ena = load.ler_ena(ano, mes)

    def soma_pequenas(tipos):
        return sum(media(v) for (t, _), v in b["pequenas"].items() if t in tipos)

    linha = {
        "carga_bruta": sum(media(v) for v in b["demanda"].values()),
        "mmgd": soma_pequenas({"PCHgd", "PCTgd", "EOLgd", "UFVgd"}),
        "eol": sum(media(v) for (f, _), v in ren.items() if f == "EOL"),
        "ufv": sum(media(v) for (f, _), v in ren.items() if f == "UFV"),
        "termica": media(b["termica"]),
        "nuclear": media(b["nuclear"]),
        "pch": soma_pequenas({"PCH"}),
        "pct": soma_pequenas({"PCT"}),
        "gh_ons": gh["gh_ons"],
        "ande": gh["ande"],
        "gh_band": gh["gh_band"],
    }
    linha["carga_liquida"] = linha["carga_bruta"] - linha["mmgd"]
    linha["termica_sem_nuclear"] = linha["termica"] - linha["nuclear"]
    linha["gh_sin"] = linha["gh_ons"] - linha["ande"]
    # Carga que sobra para hidráulica + térmica não nuclear depois das fontes "dadas".
    linha["carga_residual"] = (
        linha["carga_liquida"]
        - linha["eol"]
        - linha["ufv"]
        - linha["pch"]
        - linha["pct"]
        - linha["nuclear"]
    )
    # Fecha a menos do consumo de bombeamento (usinas elevatórias), que só está no relato.
    linha["residuo"] = (
        linha["carga_residual"] - linha["termica_sem_nuclear"] - linha["gh_sin"]
    )

    # Separação da térmica (inflexível x mérito) e bombeamento: só com relato.rv0.
    if load.caminho_relato(ano, mes).exists():
        bal = load.ler_relato_balanco(ano, mes)
        ter = load.ler_relato_termicas(ano, mes)

        def media_df(d, col):
            tabela = d.groupby(["pat", "semana"])[col].sum().unstack()
            tabela = tabela.reindex(index=[1, 2, 3], columns=horas.columns).fillna(0)
            return media(tabela.to_numpy())

        linha["bombeamento"] = media_df(bal, "cbomba")
        linha["termica_inflexivel"] = media_df(ter, "inflexivel")
        linha["termica_inflexivel_sem_nuclear"] = media_df(
            ter[~ter.nuclear], "inflexivel"
        )
        linha["termica_merito"] = linha["termica"] - linha["termica_inflexivel"]

    for sub, r in ena.iterrows():
        linha[f"ena_{sub}"] = r.ena_mes
        linha[f"ena_mlt_{sub}"] = r.ena_mes_mlt
        linha[f"ear_ini_{sub}"] = b["ear_ini"][sub]
    linha["ena_sin"] = ena.ena_mes.sum()
    linha["ena_mlt_sin"] = (
        100 * ena.ena_mes.sum() / (ena.ena_mes / (ena.ena_mes_mlt / 100)).sum()
    )
    ree = b["ear_ree"]
    linha["ear_ini_sin"] = (ree.ear_ini * ree.earm).sum() / ree.earm.sum()
    return linha


def base_mensal(ano: int, meses=range(1, 13)) -> pd.DataFrame:
    """Base mensal da etapa 1: balanço do DECOMP, ENA, EAR, GH_band e valores do boletim.

    Meses sem sumario.rv0 são ignorados; meses sem boletim ficam com NaN nas colunas do boletim.
    """
    linhas = {}
    for mes in meses:
        if not load.caminho_sumario(ano, mes).exists():
            continue
        linha = balanco_mes(ano, mes)
        try:
            bol = load.ler_boletim(ano, mes)
            linha.update({f"{k}_boletim": v for k, v in bol.items()})
            linha["gsf_calc"] = regra.gsf_band(linha["gh_band"], bol["gf_band"])
        except StopIteration:
            pass
        linhas[pd.Timestamp(year=ano, month=mes, day=1)] = linha
    return pd.DataFrame.from_dict(linhas, orient="index").rename_axis("mes")
