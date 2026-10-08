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

# Parâmetros da escolha de séries (D029): escolhidos só com os alvos de 2025 e testados em 2026
# (seção 8.9 da metodologia). Referência anterior: k = 25, meia-vida = 2.
K_PADRAO = 15
MEIA_VIDA_PADRAO = np.inf  # peso igual em toda a trajetória de ENA


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


def preparar_deck(ano: int, mes: int, base: pd.DataFrame, horizonte: int = 7) -> dict:
    """Parte cara do backtest: lê o deck e calcula GSF e PLD gatilho de TODAS as séries por mês-alvo.

    Tudo com informação disponível na data do deck (ver docstring do módulo). Horizonte padrão
    de 7 meses: alcance da previsão sazonal do ECMWF que alimentará a ENA (D028).
    Retorna dict com inicio, alvos, ena (série × período), gsf e pld (série × mês-alvo).
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

    gsf, pld = {}, {}
    for alvo in alvos:
        # GSF de cada série com ANDE e PCH projetadas pelo deck (sem arredondar).
        gh_band = (gh[alvo] - entradas["ande"][alvo]) * kf + entradas["pch"].loc[
            alvo
        ].sum() * k_pch
        gsf[alvo] = gh_band / gf_band
        # PLD gatilho de cada série: limites por patamar e submercado, horas do calendário,
        # ponderação pela carga projetada pelo deck.
        horas = load.horas_por_semana(alvo.year, alvo.month)
        peso_pat = (horas.sum(axis=1) / horas.to_numpy().sum()).to_numpy()
        carga = entradas["carga"].loc[alvo]
        total = 0.0
        for s in SUBS:
            d = cmo[s][(cmo[s].ano == alvo.year) & (cmo[s].mes == alvo.month)]
            d = d.pivot(index="serie", columns="pat", values="valor").sort_index(axis=1)
            total = (
                total
                + pd.Series(
                    (d.clip(pld_min, pld_max).to_numpy() * peso_pat).sum(axis=1),
                    index=d.index,
                )
                * carga[s]
                / carga.sum()
            )
        pld[alvo] = total
    return {
        "inicio": inicio,
        "alvos": alvos,
        "ena": ena,
        "gsf": pd.DataFrame(gsf),
        "pld": pd.DataFrame(pld),
    }


def distancia_trajetoria(
    ena: pd.DataFrame, referencia: pd.Series, meia_vida: float
) -> pd.Series:
    """Distância de cada série à trajetória de ENA de referência (erro relativo², média ponderada).

    Peso de um mês a `idade` meses do alvo: 0,5 ** (idade / meia_vida). `meia_vida` = 0 usa só o
    mês-alvo; `meia_vida` = inf dá peso igual a toda a trajetória.
    """
    meses = list(referencia.index)
    idade = np.arange(len(meses))[::-1]
    if meia_vida == 0:
        pesos = (idade == 0).astype(float)
    elif np.isinf(meia_vida):
        pesos = np.ones(len(meses))
    else:
        pesos = 0.5 ** (idade / meia_vida)
    erro = (ena[meses] - referencia.values) / referencia.values
    return (erro**2 * pesos).sum(axis=1) / pesos.sum()


def prever_com_parametros(
    prep: dict, base: pd.DataFrame, k=None, meia_vida: float | None = None
) -> pd.DataFrame:
    """Parte barata: escolhe as k séries por mês-alvo e calcula GSF, PLD, X e a cor da média.

    `k` pode ser um inteiro ou uma função mês-alvo (Period) -> inteiro (k por estação).
    A ENA de referência é a real (ORÁCULO). Sem argumentos, usa K_PADRAO e MEIA_VIDA_PADRAO.
    """
    k = K_PADRAO if k is None else k
    meia_vida = MEIA_VIDA_PADRAO if meia_vida is None else meia_vida
    inicio, linhas = prep["inicio"], []
    for alvo in prep["alvos"]:
        trajetoria = [inicio + i for i in range((alvo - inicio).n + 1)]
        ref = pd.Series(base.loc[trajetoria, "ena_sin"].to_numpy(), index=trajetoria)
        k_alvo = k(alvo) if callable(k) else k
        idx = (
            distancia_trajetoria(prep["ena"][trajetoria], ref, meia_vida)
            .nsmallest(k_alvo)
            .index
        )
        gsf_medio = round(prep["gsf"].loc[idx, alvo].mean(), 2)
        pld_medio = float(prep["pld"].loc[idx, alvo].mean())
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


def _escolher(
    prep: dict, referencia: pd.Series, alvo: pd.Period, k: int, meia_vida: float
) -> pd.Index:
    """k séries de trajetória de ENA (do mês do deck ao alvo) mais próxima da referência."""
    trajetoria = [prep["inicio"] + i for i in range((alvo - prep["inicio"]).n + 1)]
    ref = pd.Series(referencia.reindex(trajetoria).to_numpy(), index=trajetoria)
    return (
        distancia_trajetoria(prep["ena"][trajetoria], ref, meia_vida).nsmallest(k).index
    )


def prever_com_referencia(
    prep: dict,
    referencia: pd.Series,
    k: int | None = None,
    meia_vida: float | None = None,
) -> pd.DataFrame:
    """Como `prever_com_parametros`, mas com uma trajetória de ENA de referência dada
    (ex.: média do ECMWF, climatologia). Só os meses-alvo cobertos pela referência."""
    k = K_PADRAO if k is None else k
    meia_vida = MEIA_VIDA_PADRAO if meia_vida is None else meia_vida
    linhas = []
    for alvo in prep["alvos"]:
        if alvo not in referencia.index:
            continue
        idx = _escolher(prep, referencia, alvo, k, meia_vida)
        gsf_medio = round(prep["gsf"].loc[idx, alvo].mean(), 2)
        pld_medio = float(prep["pld"].loc[idx, alvo].mean())
        linhas.append(
            {
                "deck": prep["inicio"],
                "alvo": alvo,
                "h": (alvo - prep["inicio"]).n,
                "gsf_medio": gsf_medio,
                "pld_medio": pld_medio,
                "x_medio": pld_medio * max(0.0, 1 - gsf_medio),
                "cor_media": regra.cor_bandeira(gsf_medio, pld_medio),
            }
        )
    return pd.DataFrame(linhas)


def prever_com_membros(
    prep: dict,
    membros: pd.DataFrame,
    k: int | None = None,
    meia_vida: float | None = None,
) -> pd.DataFrame:
    """Estratégia B: cada membro (linha de `membros`, trajetória de ENA do SIN) escolhe suas k séries.

    Cor exibida = cor da média de todas as séries escolhidas (todos os membros juntos);
    probabilidade de cada cor = fração dos membros cuja média (GSF, PLD) cai em cada cor.
    """
    k = K_PADRAO if k is None else k
    meia_vida = MEIA_VIDA_PADRAO if meia_vida is None else meia_vida
    linhas = []
    for alvo in prep["alvos"]:
        if alvo not in membros.columns:
            continue
        gsfs, plds, cores = [], [], []
        for _, ref in membros.iterrows():
            idx = _escolher(prep, ref, alvo, k, meia_vida)
            g = round(prep["gsf"].loc[idx, alvo].mean(), 2)
            p = float(prep["pld"].loc[idx, alvo].mean())
            gsfs.append(g)
            plds.append(p)
            cores.append(regra.cor_bandeira(g, p))
        gsf_medio, pld_medio = round(float(np.mean(gsfs)), 2), float(np.mean(plds))
        prob = pd.Series(cores).value_counts(normalize=True)
        linhas.append(
            {
                "deck": prep["inicio"],
                "alvo": alvo,
                "h": (alvo - prep["inicio"]).n,
                "gsf_medio": gsf_medio,
                "pld_medio": pld_medio,
                "x_medio": pld_medio * max(0.0, 1 - gsf_medio),
                "cor_media": regra.cor_bandeira(gsf_medio, pld_medio),
                **{
                    f"p_{c}": float(prob.get(c, 0.0))
                    for c in ("Verde", "Amarela", "Vermelha 1", "Vermelha 2")
                },
            }
        )
    return pd.DataFrame(linhas)


def prever_deck(
    ano: int,
    mes: int,
    base: pd.DataFrame,
    horizonte: int = 7,
    k=None,
    meia_vida: float | None = None,
) -> pd.DataFrame:
    """Previsões de um deck para os meses-alvo de h = 0 (mês do deck) a h = `horizonte`.

    `base` é a base mensal (features.base_mensal) indexada por Period, usada só para a
    ENA de referência (oráculo) e para os valores do mês do deck (GF_band, PLD mín/máx).
    Retorna uma linha por mês-alvo com GSF médio, PLD médio, X médio e a cor da média.
    """
    return prever_com_parametros(
        preparar_deck(ano, mes, base, horizonte), base, k, meia_vida
    )


def sigma_disponivel(
    previsoes: pd.DataFrame, deck: pd.Period, minimo: int = 8, horizontes=None
) -> tuple[float, int]:
    """σ do erro de X com previsões cujo mês-alvo terminou antes do mês do deck (sem vazamento).

    Usa só meses não úmidos (GSF médio < 0,96) e, se `horizontes` for dado, só previsões
    desses horizontes (h). Retorna (σ, n); σ = NaN se n < `minimo`.
    """
    ok = (
        (previsoes.alvo < deck)
        & (previsoes.gsf_medio < 0.96)
        & previsoes.erro_x.notna()
    )
    if horizontes is not None:
        ok &= previsoes.h.isin(list(horizontes))
    erros = previsoes.loc[ok, "erro_x"]
    return (erros.std() if len(erros) >= minimo else np.nan), len(erros)


GRUPOS_HORIZONTE = (
    (1, 2, 3),
    (4, 5, 6),
)  # σ separado para curto e longo prazo (seção 9.3)


def grupo_horizonte(h: int) -> tuple[int, ...]:
    """Grupo de horizontes (M+1–3 ou M+4–6) usado para estimar o σ de uma previsão em M+h."""
    return next(g for g in GRUPOS_HORIZONTE if h in g)


def probabilidade_por_grupo(
    historico: pd.DataFrame, deck: pd.Period, h: int, x_medio: float, gsf_medio: float
) -> pd.Series:
    """Probabilidade de cada cor com σ do grupo de horizonte de h, só com erros já realizados na data do deck.

    `historico` são previsões do mesmo método com a coluna erro_x (X real − X médio). Sem
    histórico suficiente, devolve NaN em todas as cores (o método fica suspenso).
    """
    sigma, _ = sigma_disponivel(historico, deck, horizontes=grupo_horizonte(h))
    if np.isnan(sigma):
        return pd.Series(np.nan, index=list(regra.LIMITES_X) + ["Vermelha 2"])
    return newave.probabilidade_calibrada(x_medio, sigma, gsf_medio)


def prever_cenarios(
    prep: dict,
    referencias: dict,
    k: int | None = None,
    meia_vida: float | None = None,
) -> pd.DataFrame:
    """Uma previsão por cenário de ENA (ex.: esperado, LI, LS), lado a lado por mês-alvo.

    `referencias` mapeia o nome do cenário -> trajetória de ENA do SIN (Series por período).
    Colunas: deck, alvo, h e, para cada cenário, gsf_<nome>, pld_<nome>, x_<nome>, cor_<nome>.
    Só os alvos cobertos por todas as referências.
    """
    tabelas = []
    for nome, ref in referencias.items():
        p = prever_com_referencia(prep, ref, k, meia_vida).set_index(
            ["deck", "alvo", "h"]
        )
        tabelas.append(
            p[["gsf_medio", "pld_medio", "x_medio", "cor_media"]].set_axis(
                [f"gsf_{nome}", f"pld_{nome}", f"x_{nome}", f"cor_{nome}"], axis=1
            )
        )
    return pd.concat(tabelas, axis=1, join="inner").reset_index()


def decks_disponiveis() -> list[tuple[int, int]]:
    """(ano, mês) dos decks com as saídas necessárias em data/raw/ccee_newave."""
    raiz = load.DATA_RAW / "ccee_newave"
    saida = []
    for pasta in sorted(raiz.glob("*/*_*")):
        if all(
            (pasta / f).exists()
            for f in ("ghtotsin.out", "cmarg004.out", "sistema.dat", "c_adic.dat")
        ):
            ano, mes = pasta.name.split("_")
            saida.append((int(ano), int(mes)))
    return saida
