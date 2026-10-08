"""Trajetórias de ENA de referência para escolher as séries do NEWAVE (D030, D031).

O deck do mês M usa a rodada do ECMWF do mesmo mês M. Para o próprio mês M a referência é a ENA
do PMO (`ena.pdf`, já publicada na data); de M+1 em diante, a do ECMWF (ENA do SIN = soma dos
subsistemas):
- média: média da abordagem `precip`;
- membros: 51 membros (abordagem `vaz`) recentrados na média `precip`, por mês-alvo e subsistema.
"""

from functools import lru_cache

import pandas as pd

from forecast_bandeiras import load

CHAVE = ["emissao", "alvo", "subsistema"]


@lru_cache(maxsize=1)
def _produtos() -> tuple[pd.Series, pd.DataFrame]:
    est = load.ler_ecmwf_estatisticas()
    mem = load.ler_ecmwf_membros()
    est = est[est.alvo >= est.emissao]
    mem = mem[mem.alvo >= mem.emissao]
    media = (
        est[(est.estatistica == "av") & (est.abordagem == "precip")]
        .set_index(CHAVE)
        .ena
    )
    media_membros = mem.groupby(CHAVE).ena.transform("mean")
    mem = mem.assign(
        ena_recentrada=mem.ena
        * mem.set_index(CHAVE).index.map(media).to_numpy()
        / media_membros
    )
    return media, mem


def rodadas_disponiveis() -> list[pd.Period]:
    """Meses de emissão com média `precip` e membros."""
    media, mem = _produtos()
    return sorted(set(media.index.get_level_values("emissao")) & set(mem.emissao))


def referencia_media(deck: pd.Period, base: pd.DataFrame) -> pd.Series:
    """ENA do SIN de referência (média `precip`) do mês do deck em diante, indexada por Period."""
    media, _ = _produtos()
    ecmwf = media.xs(deck, level="emissao").groupby(level="alvo").sum()
    ref = ecmwf[ecmwf.index > deck]
    return pd.concat([pd.Series({deck: base.loc[deck, "ena_sin"]}), ref])


def referencia_membros(deck: pd.Period, base: pd.DataFrame) -> pd.DataFrame:
    """ENA do SIN de referência por membro recentrado (membro × mês), do mês do deck em diante."""
    _, mem = _produtos()
    m = mem[(mem.emissao == deck) & (mem.alvo > deck)]
    tab = m.groupby(["membro", "alvo"]).ena_recentrada.sum().unstack()
    tab.insert(0, deck, base.loc[deck, "ena_sin"])
    return tab


def referencia_quantil(deck: pd.Period, base: pd.DataFrame, q: float) -> pd.Series:
    """Cenário de ENA do SIN = quantil q, mês a mês, dos membros recentrados (q = 0,1: LI seco; 0,9: LS úmido)."""
    return referencia_membros(deck, base).quantile(q).rename(None)


def referencia_climatologia(deck: pd.Period, base: pd.DataFrame) -> pd.Series:
    """ENA do SIN = 100% da MLT (MLT do ECMWF da rodada do deck); mês do deck pelo PMO."""
    _, mem = _produtos()
    m = mem[(mem.emissao == deck) & (mem.alvo > deck) & (mem.membro == 0)]
    ref = m.groupby("alvo").mlt.sum()
    return pd.concat([pd.Series({deck: base.loc[deck, "ena_sin"]}), ref])
