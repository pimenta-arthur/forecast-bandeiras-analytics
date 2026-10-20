"""Cálculo da bandeira a partir de relatos do DECOMP (relato.rv0), sem passar pelo NEWAVE.

Reproduz o fluxo do boletim da CCEE com os arquivos que o usuário carrega:

- **PLD gatilho** vem do relato do DECOMP da **CCEE** (custo marginal por semana, patamar e
  submercado, limitado ao PLD mín/máx, média do mês pelas horas de cada patamar e ponderação
  dos 4 submercados pela carga). Validado contra os boletins: 45 de 45 meses (jan/2023 a
  out/2026) fecham em centavos usando a publicação certa do deck (rv0 original ou reedição).
- **GH_band / GSF** vêm do relato do **ONS** quando ele é informado (fonte oficial do boletim).
  Sem ele, usa-se o relato da CCEE como aproximação e a saída avisa a fonte.

Aceita várias execuções (cenários); a probabilidade de cada cor é a fração das execuções.
Não inclui GFOM (despacho térmico fora da ordem de mérito). Ver docs/metodologia.md (D034).
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from forecast_bandeiras import load, regra

SUBS = ["SE", "S", "NE", "N"]  # ordem dos blocos do custo marginal; o 5º (FC) não entra
COLUNAS_BASE = ["gf_band_boletim", "pld_min_boletim", "pld_max_boletim"]


def ler_cmo(relato: str | Path) -> dict[str, np.ndarray]:
    """Custo marginal (R$/MWh) por submercado: matriz patamar (3) x semana, do relato do DECOMP."""
    linhas = load.ler_linhas(relato)
    inicio = next(
        (i for i, ln in enumerate(linhas) if "CUSTO MARGINAL DE OPERACAO" in ln), None
    )
    if inicio is None:
        raise ValueError("bloco 'CUSTO MARGINAL DE OPERACAO' não encontrado no relato")
    saida, atual = {}, []
    bordas = 0
    for ln in linhas[inicio:]:
        p = ln.split()
        if not p:
            continue
        if p[0].startswith("X-"):  # 2 bordas do cabeçalho + 1 de fechamento da tabela
            bordas += 1
            if bordas == 3:
                break
            continue
        if p[0].startswith("Pat_"):
            atual.append([float(x) for x in p[1:]])
        elif p[0].startswith("Med_"):
            saida[p[0][4:]] = np.array(atual)
            atual = []
    faltam = [s for s in SUBS if s not in saida]
    if faltam:
        raise ValueError(f"custo marginal sem os submercados {faltam}")
    return saida


def carga_submercados(ano: int, mes: int, relato: str | Path) -> dict[str, float]:
    """Carga bruta média do mês (MWmed) de cada submercado, do balanço do relato."""
    horas = load.horas_por_semana(ano, mes)
    try:
        bal = load.ler_relato_balanco(ano, mes, relato)
    except AttributeError:  # arquivo sem o bloco do balanço (ex.: sumário)
        bal = pd.DataFrame()
    if bal.empty:
        raise ValueError(f"{relato}: sem o balanço energético (é o relato completo?)")
    return {
        s: regra.media_mensal_df(bal[bal.subsistema == s], "mercado", horas)
        for s in SUBS
    }


def pld_gatilho(
    ano: int,
    mes: int,
    relato_ccee: str | Path,
    pld_min: float,
    pld_max: float,
    relato_carga: str | Path | None = None,
) -> dict:
    """PLD gatilho do mês (R$/MWh) a partir do relato do DECOMP da CCEE.

    A carga dos submercados vem do próprio relato da CCEE; `relato_carga` é o plano B (com
    aviso) quando o arquivo da CCEE não traz o balanço. Retorna o valor e o PLD médio de cada
    submercado (já limitado a mín/máx).
    """
    horas = load.horas_por_semana(ano, mes).to_numpy()
    n_sem = horas.shape[1]
    cmo = ler_cmo(relato_ccee)
    try:
        carga = carga_submercados(ano, mes, relato_ccee)
    except ValueError:
        if relato_carga is None:
            raise
        warnings.warn(
            "relato da CCEE sem balanço: carga dos submercados tirada do relato do ONS",
            stacklevel=2,
        )
        carga = carga_submercados(ano, mes, relato_carga)
    total = sum(carga.values())
    por_sub = {}
    for s in SUBS:
        if cmo[s].shape[1] < n_sem:
            raise ValueError(
                f"{s}: custo marginal com {cmo[s].shape[1]} semanas, o mês tem {n_sem}"
            )
        lim = np.clip(cmo[s][:, :n_sem], pld_min, pld_max)
        por_sub[s] = float((lim * horas).sum() / horas.sum())
    return {
        "pld_gatilho": sum(por_sub[s] * carga[s] / total for s in SUBS),
        "pld_submercado": por_sub,
    }


def valores_publicados(ano: int, mes: int) -> dict:
    """GF_band e PLD mín/máx do último boletim publicado até o mês (padrão quando não informados).

    São as premissas D013: GF_band quase constante; PLD mín/máx mudam todo ano. Se o último
    boletim é de outro ano que o do mês, os limites de PLD podem estar defasados (aviso).
    """
    base = pd.read_parquet(load.DATA_PROCESSED / "base_mensal.parquet")
    periodo = pd.Timestamp(ano, mes, 1)
    base = base[base.index <= periodo].dropna(subset=COLUNAS_BASE)
    if base.empty:
        raise ValueError(
            "sem boletim publicado até o mês; informe gf_band, pld_min e pld_max"
        )
    ultimo = base.iloc[-1]
    origem = base.index[-1]
    rotulo = f"{origem:%Y-%m}"
    if origem.year != ano:
        warnings.warn(
            f"PLD mín/máx do boletim de {rotulo} usados para {ano}-{mes:02d}: podem estar defasados",
            stacklevel=3,
        )
    return {
        "gf_band": float(ultimo.gf_band_boletim),
        "pld_min": float(ultimo.pld_min_boletim),
        "pld_max": float(ultimo.pld_max_boletim),
        "origem": rotulo,
    }


def _folga(x: float, gsf: float, pld: float) -> dict:
    """Distância de X até os limites da cor, e o PLD/GSF em que a cor muda para a de cima."""
    inferior, superior = 0.0, np.inf
    for limite in regra.LIMITES_X.values():
        if x <= limite:
            superior = limite
            break
        inferior = limite
    return {
        "x_limite_inferior": inferior,
        "x_limite_superior": superior,
        "folga_para_cor_acima_x": superior - x,
        "folga_para_cor_abaixo_x": x - inferior,
        "pld_cor_acima": superior / (1 - gsf) if gsf < 1 else np.nan,
        "gsf_cor_acima": 1 - superior / pld
        if np.isfinite(superior) and pld
        else np.nan,
    }


def calcular_bandeira(
    ano: int,
    mes: int,
    relato_ccee: str | Path | None = None,
    relato_ons: str | Path | None = None,
    gf_band: float | None = None,
    pld_min: float | None = None,
    pld_max: float | None = None,
    pld_gatilho_manual: float | None = None,
) -> dict:
    """Bandeira de um mês a partir dos relatos do DECOMP.

    - `relato_ccee`: fornece o PLD gatilho (e o GH_band, se não houver `relato_ons`).
    - `relato_ons`: fornece o GH_band (fonte oficial); o PLD gatilho precisa de `relato_ccee`
      ou de `pld_gatilho_manual`. O CMO do relato do ONS nunca é usado como PLD.
    - `gf_band`, `pld_min`, `pld_max`: se omitidos, os do último boletim publicado.
    Retorna GH_band, GSF, PLD gatilho, X, cor, folgas até a cor vizinha e as fontes usadas.
    """
    if relato_ccee is None and relato_ons is None:
        raise ValueError("informe ao menos um relato (CCEE e/ou ONS)")
    if relato_ccee is None and pld_gatilho_manual is None:
        raise ValueError(
            "só com o relato do ONS é preciso informar pld_gatilho_manual "
            "(o CMO do ONS não é o PLD gatilho)"
        )
    publicados = None
    if None in (gf_band, pld_min, pld_max):
        publicados = valores_publicados(ano, mes)
    gf = gf_band if gf_band is not None else publicados["gf_band"]
    lo = pld_min if pld_min is not None else publicados["pld_min"]
    hi = pld_max if pld_max is not None else publicados["pld_max"]

    fonte_gh = "ONS" if relato_ons is not None else "CCEE (aproximação)"
    gh = regra.calcular_gh_band(ano, mes, relato_ons or relato_ccee)
    gsf = regra.gsf_band(gh["gh_band"], gf)

    if pld_gatilho_manual is not None:
        pld, por_sub, fonte_pld = pld_gatilho_manual, {}, "manual"
    else:
        r = pld_gatilho(ano, mes, relato_ccee, lo, hi, relato_carga=relato_ons)
        pld, por_sub, fonte_pld = r["pld_gatilho"], r["pld_submercado"], "CCEE"

    x = pld * max(0.0, 1 - gsf)
    return {
        "mes": f"{ano}-{mes:02d}",
        "gh_band": gh["gh_band"],
        "gf_band": gf,
        "gsf": gsf,
        "pld_gatilho": pld,
        "pld_submercado": por_sub,
        "x": x,
        "cor": regra.cor_bandeira(gsf, pld),
        **_folga(x, gsf, pld),
        "fontes": {
            "gh": fonte_gh,
            "pld": fonte_pld,
            "gf_band": "informado" if gf_band is not None else publicados["origem"],
            "pld_min_max": (
                "informado"
                if pld_min is not None and pld_max is not None
                else publicados["origem"]
            ),
        },
    }


def calcular_execucoes(ano: int, mes: int, execucoes: list[dict], **comum) -> dict:
    """Várias execuções (cenários) do mesmo mês: tabela por execução e probabilidade das cores.

    Cada item de `execucoes` é um dict com `relato_ccee` e/ou `relato_ons` (e, opcionalmente,
    `nome` e qualquer argumento de `calcular_bandeira`); `comum` vale para todas.
    A probabilidade de cada cor é a fração das execuções (peso igual).
    """
    linhas = []
    for i, e in enumerate(execucoes, start=1):
        e = dict(e)
        nome = e.pop("nome", f"execucao_{i}")
        r = calcular_bandeira(ano, mes, **{**comum, **e})
        linhas.append({"execucao": nome, **r})
    tabela = pd.DataFrame(linhas).set_index("execucao")
    prob = (
        tabela.cor.value_counts(normalize=True)
        .reindex(list(regra.LIMITES_X) + ["Vermelha 2"], fill_value=0.0)
        .rename("probabilidade")
    )
    return {"execucoes": tabela, "probabilidade": prob}
