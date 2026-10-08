"""Backtest das previsões de bandeira com os decks do NEWAVE, sem vazamento de dados.

Simula alguém sentado na data de cada deck (início do mês do deck) prevendo os meses
seguintes. Regra do CLAUDE.md: todo número usado numa previsão tem que estar disponível
nessa data.

- Séries, ENA e custo marginal: saídas do próprio deck.
- ANDE, PCH e carga dos submercados do mês-alvo: entradas do deck (`c_adic.dat`, `sistema.dat`).
- GF_band, fatores de perda da CCEE, PLD mín/máx: os do mês do deck (boletim publicado com o deck).
- σ da probabilidade: só erros de previsões cujo mês-alvo terminou antes do mês do deck.
- ENA de referência: a real (ORÁCULO) até entrar a previsão do ECMWF.
"""

import numpy as np
import pandas as pd

from forecast_bandeiras import load, newave, regra

SUBS = newave.SUBS


def _bloco_largura_fixa(linhas: list[str], inicio: int) -> pd.Series:
    """Lê as linhas de ano após `inicio` (largura fixa: ano + 12 campos de 8) até o próximo cabeçalho."""
    valores = {}
    for ln in linhas[inicio + 1 :]:
        ano = ln[:4]
        if not ano.isdigit():
            break
        for i in range(12):
            campo = ln[7 + 8 * i : 14 + 8 * i].strip()
            if campo:
                valores[pd.Period(f"{ano}-{i + 1:02d}", "M")] = float(campo)
    return pd.Series(valores)


def ler_entradas_deck(ano: int, mes: int) -> dict:
    """ANDE (+ consumo interno de Itaipu), carga e PCH por submercado, projetadas pelo deck."""
    pasta = newave.caminho_deck(ano, mes)
    c_adic = (pasta / "c_adic.dat").read_text(encoding="latin-1").splitlines()
    ande = sum(
        _bloco_largura_fixa(c_adic, i)
        for i, ln in enumerate(c_adic)
        if ln.rstrip().endswith(("ANDE", "CONS.ITAIPU"))
    )
    sistema = (pasta / "sistema.dat").read_text(encoding="latin-1").splitlines()
    i_mercado = next(
        i for i, ln in enumerate(sistema) if "MERCADO DE ENERGIA TOTAL" in ln
    )
    carga, sub_atual = {}, None
    for i, ln in enumerate(sistema[i_mercado + 3 :], start=i_mercado + 3):
        partes = ln.split()
        if len(partes) == 1 and partes[0].isdigit():
            sub_atual = int(partes[0])
            carga[sub_atual] = _bloco_largura_fixa(sistema, i)
        elif partes and not partes[0].isdigit() and partes[0] != "POS":
            break
    i_peq = next(
        i for i, ln in enumerate(sistema) if "GERACAO DE USINAS NAO SIMULADAS" in ln
    )
    pch = {}
    for i, ln in enumerate(sistema[i_peq:], start=i_peq):
        partes = ln.split()
        if len(partes) == 3 and partes[2] == "PCH" and partes[1] == "1":
            pch[int(partes[0])] = _bloco_largura_fixa(sistema, i)
    nomes = {v: k for k, v in SUBS.items()}
    return {
        "ande": ande,
        "carga": pd.DataFrame({nomes[s]: v for s, v in carga.items() if s in nomes}),
        "pch": pd.DataFrame({nomes[s]: v for s, v in pch.items() if s in nomes}),
    }


def _tabela_periodos(df: pd.DataFrame) -> pd.DataFrame:
    """Série x Period (ano-mês), descartando meses zerados (antes do início do estudo)."""
    df = df.assign(
        periodo=[pd.Period(f"{a}-{m:02d}", "M") for a, m in zip(df.ano, df.mes)]
    )
    t = df.pivot_table(index="serie", columns="periodo", values="valor", aggfunc="sum")
    return t.loc[:, t.abs().sum() > 0]


def prever_deck(
    ano: int, mes: int, base: pd.DataFrame, horizonte: int = 7, k: int = 25
) -> pd.DataFrame:
    """Previsões de um deck para os meses-alvo de h = 0 (mês do deck) a h = `horizonte`.

    Horizonte padrão de 7 meses: alcance da previsão sazonal do ECMWF que alimentará a ENA (D028).

    `base` é a base mensal (features.base_mensal) indexada por Period, usada só para a
    ENA de referência (oráculo) e para os valores do mês do deck (GF_band, PLD mín/máx).
    Retorna uma linha por mês-alvo com GSF médio, PLD médio, X médio e a cor da média.
    """
    pasta = newave.caminho_deck(ano, mes)
    inicio = pd.Period(f"{ano}-{mes:02d}", "M")
    alvos = [inicio + h for h in range(horizonte + 1) if inicio + h in base.index]
    gh = _tabela_periodos(newave.ler_nwlistop(pasta / "ghtotsin.out"))
    ena = sum(
        _tabela_periodos(newave.ler_nwlistop(pasta / f"eafbm00{i}.out"))
        for i in SUBS.values()
    )
    cmo = {
        s: newave.ler_nwlistop(pasta / f"cmarg00{i}.out", somar_patamares=False)
        for s, i in SUBS.items()
    }
    entradas = ler_entradas_deck(ano, mes)

    # Valores conhecidos na data do deck (boletim do mês do deck).
    r0 = base.loc[inicio]
    gf_band, pld_min, pld_max = (
        r0.gf_band_boletim,
        r0.pld_min_boletim,
        r0.pld_max_boletim,
    )
    f = regra.fatores_vigentes(ano, mes)
    kf = (1 - f["perda_bruta_conexao"]) * (1 - f["perda_conexao_cg"])
    k_pch = f["part_pch_mre"] * (1 - f["perda_pch_cg"])

    linhas = []
    for alvo in alvos:
        # Séries: trajetória de ENA do início do deck até o alvo (ENA real = oráculo).
        trajetoria = [inicio + i for i in range((alvo - inicio).n + 1)]
        ref = base.loc[trajetoria, "ena_sin"]
        ref.index = trajetoria
        idx = newave.distancia_trajetoria(ena[trajetoria], ref).nsmallest(k).index

        # GSF de cada série com ANDE e PCH projetadas pelo deck.
        gh_band = (gh.loc[idx, alvo] - entradas["ande"][alvo]) * kf + entradas[
            "pch"
        ].loc[alvo].sum() * k_pch
        gsf_medio = round((gh_band / gf_band).mean(), 2)

        # PLD gatilho de cada série: limites por patamar e submercado, horas do calendário,
        # ponderação pela carga projetada pelo deck.
        horas = load.horas_por_semana(alvo.year, alvo.month)
        peso_pat = (horas.sum(axis=1) / horas.to_numpy().sum()).to_numpy()
        carga = entradas["carga"].loc[alvo]
        pld = 0.0
        for s in SUBS:
            d = cmo[s][(cmo[s].ano == alvo.year) & (cmo[s].mes == alvo.month)]
            d = (
                d.pivot(index="serie", columns="pat", values="valor")
                .sort_index(axis=1)
                .loc[idx]
            )
            pld = (
                pld
                + (d.clip(pld_min, pld_max).to_numpy() * peso_pat).sum(axis=1)
                * carga[s]
                / carga.sum()
            )
        pld_medio = float(np.mean(pld))

        linhas.append(
            {
                "deck": inicio,
                "alvo": alvo,
                "h": (alvo - inicio).n,
                "gsf_medio": gsf_medio,
                "pld_medio": pld_medio,
                "x_medio": pld_medio * max(0.0, 1 - gsf_medio),
                "cor_media": regra.cor_bandeira(gsf_medio, pld_medio),
            }
        )
    return pd.DataFrame(linhas)


def sigma_disponivel(
    previsoes: pd.DataFrame, deck: pd.Period, minimo: int = 8
) -> tuple[float, int]:
    """σ do erro de X com previsões cujo mês-alvo terminou antes do mês do deck (sem vazamento).

    Usa só meses não úmidos (GSF médio < 0,96). Retorna (σ, n); σ = NaN se n < `minimo`.
    """
    ok = (
        (previsoes.alvo < deck)
        & (previsoes.gsf_medio < 0.96)
        & previsoes.erro_x.notna()
    )
    erros = previsoes.loc[ok, "erro_x"]
    return (erros.std() if len(erros) >= minimo else np.nan), len(erros)


def decks_disponiveis() -> list[tuple[int, int]]:
    """(ano, mês) dos decks com as saídas necessárias em data/raw/ons_newave."""
    raiz = load.DATA_RAW / "ons_newave"
    saida = []
    for pasta in sorted(raiz.glob("*/*_*")):
        if all(
            (pasta / f).exists()
            for f in ("ghtotsin.out", "cmarg004.out", "sistema.dat", "c_adic.dat")
        ):
            ano, mes = pasta.name.split("_")
            saida.append((int(ano), int(mes)))
    return saida
