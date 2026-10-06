"""Engenharia de features.

Funções para criar as variáveis de entrada a partir dos dados limpos
(ex.: defasagens, médias móveis, variáveis de calendário), sempre tomando
cuidado para não usar informação do futuro (data leakage).
"""

import pandas as pd

from forecast_bandeiras import load, regra

TIPOS_MMGD = {"PCHgd", "PCTgd", "EOLgd", "UFVgd"}


def balanco_mes(ano: int, mes: int) -> dict:
    """Balanço mensal do DECOMP rv0 (MWmed) e variáveis do PMO para um mês, a partir do relato.rv0.

    Segue o memorial de cálculo da seção 3.5 de docs/metodologia.md:
    carga líquida + bombeamento = hidráulica (SIN) + renováveis + térmica + PCH + PCT.
    Todas as variáveis são as previstas pelo ONS no PMO do mês (mesmo conjunto de
    informação que gera o GH_band), não valores realizados.
    """
    horas = load.horas_por_semana(ano, mes)

    def media(df, coluna):
        return regra.media_mensal_df(df, coluna, horas)

    bal = load.ler_relato_balanco(ano, mes)
    peq = load.ler_relato_pequenas(ano, mes)
    ter = load.ler_relato_termicas(ano, mes)
    gh = regra.calcular_gh_band(ano, mes)

    def pequenas(tipos):
        return media(peq[peq.tipo.isin(tipos)], "mw")

    # Eólica e solar centralizadas: nas pequenas usinas até set/2025; no Geol depois.
    eol, ufv = pequenas({"EOL"}), pequenas({"UFV"})
    geol = media(bal, "geol")
    if geol > 0 and load.caminho_renovaveis(ano, mes).exists():
        ren = load.ler_renovaveis(ano, mes)
        eol = sum(
            regra.media_mensal(v, horas) for (f, _), v in ren.items() if f == "EOL"
        )
        ufv = sum(
            regra.media_mensal(v, horas) for (f, _), v in ren.items() if f == "UFV"
        )
    elif geol > 0:
        eol = ufv = float("nan")  # só a soma (Geol) está disponível

    linha = {
        "carga_bruta": media(bal, "mercado"),
        "mmgd": pequenas(TIPOS_MMGD),
        "renovaveis": pequenas({"EOL", "UFV"}) + geol,
        "eol": eol,
        "ufv": ufv,
        "termica": media(bal, "gter") + media(bal, "gterat"),
        "termica_antecipada": media(bal, "gterat"),
        "nuclear": media(ter[ter.nuclear], "ger"),
        "termica_inflexivel": media(ter, "inflexivel"),
        "termica_inflexivel_sem_nuclear": media(ter[~ter.nuclear], "inflexivel"),
        "pch": pequenas({"PCH"}),
        "pct": pequenas({"PCT"}),
        "bombeamento": media(bal, "cbomba"),
        "gh_ons": gh["gh_ons"],
        "ande": gh["ande"],
        "gh_band": gh["gh_band"],
    }
    linha["carga_liquida"] = linha["carga_bruta"] - linha["mmgd"]
    linha["termica_sem_nuclear"] = linha["termica"] - linha["nuclear"]
    # Térmica = inflexível (GTmin, inclui nuclear) + mérito do mês + antecipada (GterAT: GNL
    # despachado por mérito com antecedência; não aparece no bloco por usina).
    linha["termica_merito"] = (
        linha["termica"] - linha["termica_inflexivel"] - linha["termica_antecipada"]
    )
    linha["gh_sin"] = linha["gh_ons"] - linha["ande"]
    # Carga que sobra para hidráulica + térmica não nuclear depois das fontes "dadas".
    linha["carga_residual"] = (
        linha["carga_liquida"]
        - linha["renovaveis"]
        - linha["pch"]
        - linha["pct"]
        - linha["nuclear"]
    )
    # Fechamento do balanço: deve ser ~0.
    linha["residuo"] = (
        linha["carga_liquida"]
        + linha["bombeamento"]
        - linha["gh_sin"]
        - linha["renovaveis"]
        - linha["termica"]
        - linha["pch"]
        - linha["pct"]
    )

    ena = load.ler_ena(ano, mes)
    for sub, r in ena.iterrows():
        linha[f"ena_{sub}"] = r.ena_mes
        linha[f"ena_mlt_{sub}"] = r.ena_mes_mlt
    linha["ena_sin"] = ena.ena_mes.sum()
    linha["ena_mlt_sin"] = (
        100 * ena.ena_mes.sum() / (ena.ena_mes / (ena.ena_mes_mlt / 100)).sum()
    )

    ear = load.ler_relato_ear(ano, mes)
    for sub, r in ear.iterrows():
        linha[f"ear_ini_{sub}"] = r.ear_pct
    earmax = ear.ear_mwmes / (ear.ear_pct / 100)
    linha["ear_ini_sin"] = 100 * ear.ear_mwmes.sum() / earmax.sum()
    return linha


def base_mensal(anos=(2023, 2024, 2025, 2026)) -> pd.DataFrame:
    """Base mensal da etapa 1: balanço do DECOMP, ENA, EAR, GH_band e valores do boletim.

    Meses sem relato.rv0 são ignorados; meses sem boletim ficam com NaN nas colunas do boletim.
    """
    linhas = {}
    for ano in anos:
        for mes in range(1, 13):
            if not load.caminho_relato(ano, mes).exists():
                continue
            linha = balanco_mes(ano, mes)
            try:
                bol = load.ler_boletim(ano, mes)
                linha.update({f"{k}_boletim": v for k, v in bol.items()})
                linha["gsf_calc"] = regra.gsf_band(linha["gh_band"], bol["gf_band"])
                linha["cor_regra"] = regra.cor_bandeira(
                    bol["gsf_band"], bol["pld_gatilho"]
                )
            except StopIteration:
                pass
            linhas[pd.Timestamp(year=ano, month=mes, day=1)] = linha
    return pd.DataFrame.from_dict(linhas, orient="index").rename_axis("mes")
