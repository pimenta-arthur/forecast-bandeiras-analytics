"""Gráficos da análise exploratória.

Funções que recebem a base mensal (features.base_mensal) e salvam PNG em reports/figures/.
Paleta categórica de referência em ordem fixa (a cor segue a série, nunca a posição).
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forecast_bandeiras import regra
from forecast_bandeiras.load import RAIZ

FIGURAS = RAIZ / "reports" / "figures"

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_SEC = "#52514e"
GRADE = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]

MESES = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
]


def _estilo(ax, titulo: str, ylabel: str | None = None) -> None:
    """Eixos discretos: grade horizontal leve, sem bordas superior/direita."""
    ax.set_facecolor(SUPERFICIE)
    ax.set_title(
        titulo, loc="left", color=TEXTO, fontsize=12, fontweight="bold", pad=12
    )
    if ylabel:
        ax.set_ylabel(ylabel, color=TEXTO_SEC, fontsize=9)
    ax.grid(axis="y", color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRADE)
    ax.tick_params(colors=TEXTO_SEC, labelsize=9, length=0)


def _milhar(ax, eixo: str = "y") -> None:
    """Números com separador de milhar brasileiro (42.500)."""
    alvo = ax.yaxis if eixo == "y" else ax.xaxis
    alvo.set_major_formatter(lambda v, _: f"{v:,.0f}".replace(",", "."))


def _rotulos_mes(indice: pd.DatetimeIndex) -> list[str]:
    if indice.year.nunique() > 1:
        return [f"{MESES[d.month - 1]}/{d.year % 100:02d}" for d in indice]
    return [MESES[d.month - 1] for d in indice]


def _salvar(fig, nome: str) -> Path:
    caminho = FIGURAS / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=150, bbox_inches="tight", facecolor=SUPERFICIE)
    plt.close(fig)
    return caminho


def balanco_empilhado(base: pd.DataFrame, nome: str = "01_balanco_mensal.png") -> Path:
    """Como a carga líquida é atendida em cada mês (barras empilhadas, MWmed)."""
    fontes = {
        "Hidráulica (SIN)": base.gh_sin,
        "Eólica": base.eol,
        "Solar": base.ufv,
        "Térmica (inclui nuclear)": base.termica,
        "PCH + PCT": base.pch + base.pct,
    }
    x = range(len(base))
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=SUPERFICIE)
    fundo = pd.Series(0.0, index=base.index)
    for (rotulo, valores), cor in zip(fontes.items(), SERIES):
        ax.bar(
            x,
            valores,
            bottom=fundo,
            width=0.6,
            color=cor,
            label=rotulo,
            edgecolor=SUPERFICIE,
            linewidth=2,
        )
        fundo += valores
    ax.plot(
        x,
        base.carga_liquida,
        color=TEXTO,
        linewidth=2,
        marker="o",
        markersize=5,
        label="Carga líquida (sem MMGD)",
    )
    _estilo(ax, "Atendimento da carga líquida por fonte — PMO 2026 (MWmed)")
    _milhar(ax)
    ax.set_xticks(list(x), _rotulos_mes(base.index))
    ax.legend(
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO_SEC,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
    )
    return _salvar(fig, nome)


def gh_vs_carga_residual(
    base: pd.DataFrame, nome: str = "02_gh_carga_residual.png"
) -> Path:
    """GH_band, carga residual e térmica não nuclear ao longo dos meses (mesma unidade)."""
    x = list(range(len(base)))
    fig, ax = plt.subplots(figsize=(10, 4.5), facecolor=SUPERFICIE)
    series = {
        "Carga residual (carga líquida − eólica − solar − PCH − PCT − nuclear)": base.carga_residual,
        "Hidráulica para o SIN": base.gh_sin,
        "Térmica sem nuclear": base.termica_sem_nuclear,
    }
    for (rotulo, valores), cor in zip(series.items(), SERIES):
        ax.plot(
            x, valores, color=cor, linewidth=2, marker="o", markersize=5, label=rotulo
        )
    _estilo(ax, "A hidráulica acompanha a carga residual (MWmed)")
    _milhar(ax)
    ax.set_ylim(0, None)
    ax.set_xticks(x, _rotulos_mes(base.index))
    ax.legend(
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO_SEC,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
    )
    return _salvar(fig, nome)


def _paineis_dispersao(
    base: pd.DataFrame, y: pd.Series, paineis: dict, titulo: str, ylabel: str, nome: str
) -> Path:
    """Um painel de dispersão por variável x (eixos x próprios, mesmo eixo y), com r de Pearson."""
    fig, eixos = plt.subplots(
        1,
        len(paineis),
        figsize=(4.3 * len(paineis), 4.2),
        facecolor=SUPERFICIE,
        sharey=True,
    )
    # Meses do período seco ficam muito próximos: rótulos alternados acima/abaixo.
    deslocamento = {"jun": (6, -12), "jul": (-20, -12), "ago": (6, 6), "fev": (6, -12)}
    for ax, (rotulo, (x, milhar)) in zip(eixos, paineis.items()):
        ax.scatter(
            x, y, s=60, color=SERIES[0], edgecolor=SUPERFICIE, linewidth=2, zorder=3
        )
        rotulos = _rotulos_mes(base.index)
        if len(base) > 12:  # muitos pontos: rotula só os 3 maiores e 3 menores de y
            ordem = y.rank()
            rotulos = [
                r if (o <= 3 or o > len(y) - 3) else "" for r, o in zip(rotulos, ordem)
            ]
        for xi, yi, m in zip(x, y, rotulos):
            ax.annotate(
                m,
                (xi, yi),
                xytext=deslocamento.get(m, (5, 4)),
                textcoords="offset points",
                fontsize=8,
                color=TEXTO_SEC,
            )
        _estilo(ax, f"r = {x.corr(y):.2f}")
        ax.set_xlabel(rotulo, color=TEXTO_SEC, fontsize=9)
        ax.grid(axis="x", color=GRADE, linewidth=0.8)
        if milhar:
            _milhar(ax, "x")
            ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    _milhar(eixos[0])
    margem = (y.max() - y.min()) * 0.12
    eixos[0].set_ylim(y.min() - margem, y.max() + margem)
    eixos[0].set_ylabel(ylabel, color=TEXTO_SEC, fontsize=9)
    fig.suptitle(titulo, x=0.01, ha="left", color=TEXTO, fontsize=12, fontweight="bold")
    fig.tight_layout()
    return _salvar(fig, nome)


def dispersoes_gh(base: pd.DataFrame, nome: str = "03_gh_vs_variaveis.png") -> Path:
    """GH_band contra ENA (MWmed e % MLT), EAR inicial e carga residual (SIN)."""
    paineis = {
        "ENA prevista do mês (MWmed, SIN)": (base.ena_sin, True),
        "ENA prevista do mês (% MLT, SIN)": (base.ena_mlt_sin, False),
        "EAR inicial (% EARmax, SIN)": (base.ear_ini_sin, False),
        "Carga residual (MWmed)": (base.carga_residual, True),
    }
    return _paineis_dispersao(
        base,
        base.gh_band,
        paineis,
        f"GH_band contra as variáveis candidatas — SIN, {len(base)} meses",
        "GH_band (MWmed)",
        nome,
    )


def gh_vs_ena(base: pd.DataFrame, nome: str = "04_gh_vs_ena.png") -> Path:
    """GH_band e ENA prevista do SIN ao longo dos meses (MWmed), com a ENA em % MLT nos pontos."""
    x = list(range(len(base)))
    fig, ax = plt.subplots(figsize=(10, 4.5), facecolor=SUPERFICIE)
    ax.plot(
        x,
        base.ena_sin,
        color=SERIES[0],
        linewidth=2,
        marker="o",
        markersize=5,
        label="ENA prevista do mês (SIN)",
    )
    ax.plot(
        x,
        base.gh_band,
        color=SERIES[1],
        linewidth=2,
        marker="o",
        markersize=5,
        label="GH_band",
    )
    for xi, v, mlt in zip(x, base.ena_sin, base.ena_mlt_sin) if len(base) <= 12 else []:
        ax.annotate(
            f"{mlt:.0f}% MLT",
            (xi, v),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=TEXTO_SEC,
        )
    _estilo(
        ax,
        "ENA prevista e GH_band do SIN (MWmed)"
        + ("; rótulos: ENA em % da MLT" if len(base) <= 12 else ""),
    )
    _milhar(ax)
    ax.set_ylim(0, base.ena_sin.max() * 1.15)
    ax.set_xticks(x, _rotulos_mes(base.index))
    ax.legend(
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO_SEC,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=2,
    )
    return _salvar(fig, nome)


def residuo_vs_ena(
    base: pd.DataFrame, residuo: pd.Series, nome: str = "05_residuo_vs_ena.png"
) -> Path:
    """Resíduo do GH_band depois de descontar a carga residual, contra ENA e EAR (SIN)."""
    paineis = {
        "ENA prevista do mês (MWmed, SIN)": (base.ena_sin, True),
        "ENA prevista do mês (% MLT, SIN)": (base.ena_mlt_sin, False),
        "EAR inicial (% EARmax, SIN)": (base.ear_ini_sin, False),
    }
    return _paineis_dispersao(
        base,
        residuo,
        paineis,
        f"Resíduo de GH_band ~ carga residual contra ENA e EAR — SIN, {len(base)} meses",
        "Resíduo de GH_band ~ carga residual (MWmed)",
        nome,
    )


def serie_historica(base: pd.DataFrame, nome: str = "06_serie_historica.png") -> Path:
    """Carga residual, hidráulica para o SIN e térmica sem nuclear mês a mês (MWmed)."""
    fig, ax = plt.subplots(figsize=(12, 4.8), facecolor=SUPERFICIE)
    series = {
        "Carga residual": base.carga_residual,
        "Hidráulica para o SIN": base.gh_sin,
        "Térmica sem nuclear": base.termica_sem_nuclear,
    }
    for (rotulo, valores), cor in zip(series.items(), SERIES):
        ax.plot(
            base.index,
            valores,
            color=cor,
            linewidth=2,
            marker="o",
            markersize=3.5,
            label=rotulo,
        )
    _estilo(
        ax,
        f"Hidráulica = carga residual − térmica: {base.index[0]:%m/%Y} a {base.index[-1]:%m/%Y} (MWmed)",
    )
    _milhar(ax)
    ax.set_ylim(0, None)
    ax.legend(
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO_SEC,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=3,
    )
    return _salvar(fig, nome)


def anomalias(base: pd.DataFrame, nome: str = "07_anomalias.png") -> Path:
    """Sem a sazonalidade (desvio da média do mesmo mês nos outros anos): GH × térmica × hidrologia."""
    cols = ["gh_band", "termica_sem_nuclear", "ear_ini_sin", "ena_mlt_sin"]
    an = base[cols] - base[cols].groupby(base.index.month).transform("mean")
    paineis = [
        (
            "termica_sem_nuclear",
            "gh_band",
            "Anomalia da térmica sem nuclear (MWmed)",
            "Anomalia do GH_band (MWmed)",
            True,
        ),
        (
            "ear_ini_sin",
            "termica_sem_nuclear",
            "Anomalia da EAR inicial (p.p.)",
            "Anomalia da térmica sem nuclear (MWmed)",
            False,
        ),
        (
            "ena_mlt_sin",
            "termica_sem_nuclear",
            "Anomalia da ENA (p.p. da MLT)",
            "Anomalia da térmica sem nuclear (MWmed)",
            False,
        ),
    ]
    fig, eixos = plt.subplots(1, 3, figsize=(14, 4.4), facecolor=SUPERFICIE)
    rotulos = _rotulos_mes(base.index)
    for ax, (cx, cy, rx, ry, milhar_x) in zip(eixos, paineis):
        ax.scatter(
            an[cx],
            an[cy],
            s=45,
            color=SERIES[0],
            edgecolor=SUPERFICIE,
            linewidth=1.5,
            zorder=3,
        )
        ordem = an[cy].rank()
        for xi, yi, r, o in zip(an[cx], an[cy], rotulos, ordem):
            if o <= 2 or o > len(an) - 2:
                ax.annotate(
                    r,
                    (xi, yi),
                    xytext=(5, 4),
                    textcoords="offset points",
                    fontsize=8,
                    color=TEXTO_SEC,
                )
        _estilo(ax, f"r = {an[cx].corr(an[cy]):.2f}")
        ax.set_xlabel(rx, color=TEXTO_SEC, fontsize=9)
        ax.set_ylabel(ry, color=TEXTO_SEC, fontsize=9)
        ax.grid(axis="x", color=GRADE, linewidth=0.8)
        ax.axhline(0, color=TEXTO_SEC, linewidth=0.8)
        ax.axvline(0, color=TEXTO_SEC, linewidth=0.8)
        _milhar(ax)
        if milhar_x:
            _milhar(ax, "x")
    fig.suptitle(
        "Sem a sazonalidade, a hidrologia aparece pela térmica — anomalias por mês do ano",
        x=0.01,
        ha="left",
        color=TEXTO,
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    return _salvar(fig, nome)


CINZA_FAIXA = "#e4e3df"
CINZA_MEDIANA = "#9a988f"
# Cores das bandeiras (convenção do setor), sempre acompanhadas do nome escrito.
CORES_BANDEIRA = {
    "Verde": "#2e9e5b",
    "Amarela": "#f2c230",
    "Vermelha 1": "#e35d4f",
    "Vermelha 2": "#9e1b1b",
}


def _br(valor: float, casas: int = 1) -> str:
    """Número no formato brasileiro (1.234,5)."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _faixa_e_series(ax, meses, dados, idx, rotulo_escolhidas, media=None):
    """Faixa P10–P90 e mediana de todas as séries, séries escolhidas finas e a média delas."""
    ax.fill_between(
        meses,
        dados.quantile(0.1),
        dados.quantile(0.9),
        color=CINZA_FAIXA,
        label="2.000 séries (P10–P90)",
        zorder=1,
    )
    ax.plot(
        meses,
        dados.median(),
        color=CINZA_MEDIANA,
        linewidth=1,
        linestyle="--",
        label="Mediana das 2.000 séries",
        zorder=2,
    )
    if idx is not None:
        for i, serie in enumerate(idx):
            ax.plot(
                meses,
                dados.loc[serie],
                color=SERIES[0],
                linewidth=0.8,
                alpha=0.25,
                label="Séries escolhidas" if i == 0 else None,
                zorder=3,
            )
        media = dados.loc[idx].mean()
    ax.plot(
        meses, media, color=SERIES[0], linewidth=2.2, label=rotulo_escolhidas, zorder=4
    )
    return media


def trajetorias_deck(
    ena_sin: pd.DataFrame,
    gsf: pd.DataFrame,
    pld: pd.DataFrame,
    real: pd.DataFrame,
    escolhidas_preco: dict,
    escolhidas_gsf: dict,
    dcide: pd.Series,
    titulo: str,
    nome: str,
    rotulo_gsf: str = "Estimativa (10 séries da ENA do mês)",
) -> Path:
    """ENA, GSF e PLD gatilho do início do deck até cada mês-alvo (uma coluna por alvo).

    - ENA e PLD: séries escolhidas pela trajetória de ENA até o alvo (método do preço).
    - GSF: em cada mês, média das séries escolhidas pela ENA daquele mês (método do GSF).
    - PLD: inclui a curva forward da Dcide (`dcide`, indexada pelo número do mês).
    `real` tem colunas ena_sin, gsf_band_boletim e pld_gatilho_boletim, indexada pelo mês.
    """
    alvos = list(escolhidas_preco)
    fig, eixos = plt.subplots(
        3,
        len(alvos),
        figsize=(4.9 * len(alvos), 11.2),
        facecolor=SUPERFICIE,
        sharey="row",
        squeeze=False,
    )
    inicio = min(pld.columns)
    for c, alvo in enumerate(alvos):
        meses = [m for m in range(inicio, alvo + 1) if m in real.index]
        x_rot = [MESES[m - 1] for m in meses]

        ax = eixos[0, c]
        media = _faixa_e_series(
            ax, meses, ena_sin[meses], escolhidas_preco[alvo], "Média das escolhidas"
        )
        ax.plot(
            meses,
            real.loc[meses, "ena_sin"],
            color=TEXTO,
            linewidth=2.2,
            marker="o",
            markersize=4,
            label="Real",
            zorder=5,
        )
        v = real.loc[alvo, "ena_sin"]
        _estilo(
            ax,
            f"Alvo: {MESES[alvo - 1]}\nENA real {_br(v / 1000)} mil · escolhidas "
            f"{_br(media.loc[alvo] / 1000)} mil",
        )
        _milhar(ax)

        ax = eixos[1, c]
        est = pd.Series({m: gsf.loc[escolhidas_gsf[m], m].mean() for m in meses})
        _faixa_e_series(
            ax,
            meses,
            gsf[meses],
            None,
            rotulo_gsf,
            media=est,
        )
        ax.plot(
            meses,
            real.loc[meses, "gsf_band_boletim"],
            color=TEXTO,
            linewidth=2.2,
            marker="o",
            markersize=4,
            label=None,
            zorder=5,
        )
        erro = (est.round(2) - real.loc[meses, "gsf_band_boletim"]).abs().mean()
        _estilo(
            ax,
            f"GSF real {_br(real.loc[alvo, 'gsf_band_boletim'], 2)} · estimado "
            f"{_br(est.loc[alvo], 2)} · erro médio {_br(erro, 3)}",
        )

        ax = eixos[2, c]
        media = _faixa_e_series(
            ax, meses, pld[meses], escolhidas_preco[alvo], "Média das escolhidas"
        )
        ax.plot(
            meses,
            real.loc[meses, "pld_gatilho_boletim"],
            color=TEXTO,
            linewidth=2.2,
            marker="o",
            markersize=4,
            zorder=5,
        )
        titulo_pld = (
            f"PLD real R\\$ {_br(real.loc[alvo, 'pld_gatilho_boletim'], 0)} · séries "
            f"R\\$ {_br(media.loc[alvo], 0)}"
        )
        if dcide is not None and not dcide.empty:  # nem todo deck tem curva Dcide
            dc = dcide.reindex(meses)
            ax.plot(
                meses,
                dc,
                color=SERIES[1],
                linewidth=2.2,
                marker="s",
                markersize=4,
                label="Dcide (curva forward, PLD SE)",
                zorder=4,
            )
            titulo_pld += f" · Dcide R\\$ {_br(dc.loc[alvo], 0)}"
        _estilo(ax, titulo_pld)

        for r in range(3):
            eixos[r, c].set_xticks(meses, x_rot)
            eixos[r, c].title.set_fontsize(9.5)
    for r, rotulo in enumerate(
        ["ENA do SIN (MWmed)", "GSF_band", "PLD gatilho (R$/MWh)"]
    ):
        eixos[r, 0].set_ylabel(rotulo, color=TEXTO_SEC, fontsize=9)
    handles, labels = [], []
    for ax in (eixos[0, 0], eixos[1, 0], eixos[2, 0]):
        for h, lab in zip(*ax.get_legend_handles_labels()):
            if lab not in labels:
                handles.append(h)
                labels.append(lab)
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO_SEC,
        bbox_to_anchor=(0.5, -0.03),
    )
    fig.suptitle(titulo, x=0.01, ha="left", color=TEXTO, fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return _salvar(fig, nome)


def trajetorias_ecmwf(
    ena: pd.DataFrame,
    gsf: pd.DataFrame,
    pld: pd.DataFrame,
    referencia: pd.Series,
    real: pd.DataFrame,
    escolhidas: dict,
    cores: dict,
    titulo: str,
    nome: str,
    dcide: pd.Series | None = None,
) -> Path:
    """ENA, GSF e PLD gatilho do mês do deck até cada mês-alvo, com a ENA de referência do ECMWF.

    Uma coluna por mês-alvo; em cada coluna, as séries escolhidas para aquele alvo (pela
    trajetória de ENA até ele) aparecem nas três linhas: GSF e preço vêm das MESMAS séries.
    `ena`, `gsf` e `pld` são série × período; `referencia` é a trajetória de ENA do SIN usada na
    escolha (PMO no mês do deck, ECMWF depois); `real` tem ena_sin, gsf_band_boletim e
    pld_gatilho_boletim indexados pelo período; `cores` mapeia alvo -> (cor prevista, cor real).
    `dcide` (opcional): curva forward da Dcide (PLD SE) indexada pelo período; no título do PLD
    aparece também a cor que se obteria com o GSF médio das séries e o preço da Dcide.
    """
    alvos = list(escolhidas)
    inicio = min(gsf.columns)
    fig, eixos = plt.subplots(
        3,
        len(alvos),
        figsize=(4.1 * len(alvos), 11.2),
        facecolor=SUPERFICIE,
        sharey="row",
        squeeze=False,
    )
    for c, alvo in enumerate(alvos):
        periodos = [inicio + i for i in range((alvo - inicio).n + 1)]
        x = list(range(len(periodos)))
        x_rot = [f"{MESES[p.month - 1]}/{p.year % 100:02d}" for p in periodos]
        idx = escolhidas[alvo]

        def linha_real(ax, coluna, x=x, periodos=periodos):
            ax.plot(
                x,
                real[coluna].reindex(periodos).to_numpy(),
                color=TEXTO,
                linewidth=2.2,
                marker="o",
                markersize=4,
                label="Real",
                zorder=5,
            )

        ax = eixos[0, c]
        dados = ena[periodos].set_axis(x, axis=1)
        _faixa_e_series(ax, x, dados, idx, "Média das escolhidas")
        ax.plot(
            x,
            referencia.reindex(periodos).to_numpy(),
            color=SERIES[1],
            linewidth=2.2,
            marker="s",
            markersize=4,
            label="Referência (PMO no mês do deck; ECMWF depois)",
            zorder=4,
        )
        linha_real(ax, "ena_sin")
        prevista, verdadeira = cores[alvo]
        marca = "acertou" if prevista == verdadeira else "errou"
        _estilo(
            ax,
            f"Alvo {x_rot[-1]} (M+{(alvo - inicio).n}) · {marca}\n"
            f"prevista {prevista} · real {verdadeira}\n"
            f"ENA real {_br(real.loc[alvo, 'ena_sin'] / 1000)} mil · ECMWF "
            f"{_br(referencia.loc[alvo] / 1000)} mil",
        )
        _milhar(ax)

        ax = eixos[1, c]
        dados = gsf[periodos].set_axis(x, axis=1)
        media = _faixa_e_series(ax, x, dados, idx, "Média das escolhidas")
        linha_real(ax, "gsf_band_boletim")
        _estilo(
            ax,
            f"GSF real {_br(real.loc[alvo, 'gsf_band_boletim'], 2)} · séries "
            f"{_br(media.iloc[-1], 2)}",
        )

        ax = eixos[2, c]
        dados = pld[periodos].set_axis(x, axis=1)
        media = _faixa_e_series(ax, x, dados, idx, "Média das escolhidas")
        linha_real(ax, "pld_gatilho_boletim")
        titulo_pld = (
            f"PLD real R\\$ {_br(real.loc[alvo, 'pld_gatilho_boletim'], 0)} · séries "
            f"R\\$ {_br(media.iloc[-1], 0)}"
        )
        if dcide is not None and alvo in dcide.index:
            dc = dcide.reindex(periodos).to_numpy()
            ax.plot(
                x,
                dc,
                color=SERIES[2],
                linewidth=2.2,
                marker="D",
                markersize=4,
                label="Dcide (curva forward, PLD SE)",
                zorder=4,
            )
            gsf_medio = round(gsf.loc[idx, alvo].mean(), 2)
            cor_dcide = regra.cor_bandeira(gsf_medio, dcide.loc[alvo])
            titulo_pld += f"\nDcide R\\$ {_br(dcide.loc[alvo], 0)} → {cor_dcide}"
        _estilo(ax, titulo_pld)
        for r in range(3):
            eixos[r, c].set_xticks(x, x_rot, rotation=45)
            eixos[r, c].title.set_fontsize(9.5)
    for r, rotulo in enumerate(
        ["ENA do SIN (MWmed)", "GSF_band", "PLD gatilho (R$/MWh)"]
    ):
        eixos[r, 0].set_ylabel(rotulo, color=TEXTO_SEC, fontsize=9)
    handles, labels = [], []
    for h, lab in (
        p
        for ax in (eixos[0, 0], eixos[2, -1])
        for p in zip(*ax.get_legend_handles_labels())
    ):
        if lab not in labels:
            handles.append(h)
            labels.append(lab)
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=5,
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO_SEC,
        bbox_to_anchor=(0.5, -0.03),
    )
    fig.suptitle(titulo, x=0.01, ha="left", color=TEXTO, fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return _salvar(fig, nome)


def trajetorias_cenarios(
    ena: pd.DataFrame,
    gsf: pd.DataFrame,
    pld: pd.DataFrame,
    cenarios: dict,
    real: pd.DataFrame,
    titulo: str,
    nome: str,
) -> Path:
    """ENA, GSF e PLD gatilho do mês do deck até cada mês-alvo para vários cenários (ex.: esperado, LI, LS).

    `cenarios` mapeia o rótulo -> {"referencia": trajetória de ENA do SIN (Series por período),
    "escolhidas": {alvo: índice das séries}, "cores": {alvo: cor}}. Em cada coluna (mês-alvo), cada
    cenário mostra sua referência de ENA (tracejada) e a média das suas séries escolhidas nas três
    linhas (GSF e preço das mesmas séries). `real` tem ena_sin, gsf_band_boletim,
    pld_gatilho_boletim e cor_oficial por período (NaN em meses ainda sem valor real).
    """
    primeiro = next(iter(cenarios.values()))
    alvos = list(primeiro["escolhidas"])
    inicio = min(gsf.columns)
    fig, eixos = plt.subplots(
        3,
        len(alvos),
        figsize=(4.1 * len(alvos), 11.6),
        facecolor=SUPERFICIE,
        sharey="row",
        squeeze=False,
    )

    def fmt(v, casas=0, prefixo=""):
        return "—" if pd.isna(v) else f"{prefixo}{_br(v, casas)}"

    for c, alvo in enumerate(alvos):
        periodos = [inicio + i for i in range((alvo - inicio).n + 1)]
        x = list(range(len(periodos)))
        x_rot = [f"{MESES[p.month - 1]}/{p.year % 100:02d}" for p in periodos]
        resumo = {"ena": [], "gsf": [], "pld": []}
        for r, (chave, dados) in enumerate((("ena", ena), ("gsf", gsf), ("pld", pld))):
            ax = eixos[r, c]
            d = dados[periodos]
            ax.fill_between(
                x,
                d.quantile(0.1),
                d.quantile(0.9),
                color=CINZA_FAIXA,
                label="2.000 séries (P10–P90)",
                zorder=1,
            )
            for k, (rot, cen) in enumerate(cenarios.items()):
                media = d.loc[cen["escolhidas"][alvo]].mean().to_numpy()
                ax.plot(
                    x,
                    media,
                    color=SERIES[k],
                    linewidth=2.2,
                    label=f"{rot}: média das 15 séries",
                    zorder=4,
                )
                if chave == "ena":
                    ax.plot(
                        x,
                        cen["referencia"].reindex(periodos).to_numpy(),
                        color=SERIES[k],
                        linewidth=1.4,
                        linestyle="--",
                        marker="s",
                        markersize=3.5,
                        label=f"{rot}: referência ECMWF",
                        zorder=3,
                    )
                resumo[chave].append((rot, media[-1]))
            coluna = {
                "ena": "ena_sin",
                "gsf": "gsf_band_boletim",
                "pld": "pld_gatilho_boletim",
            }[chave]
            ax.plot(
                x,
                real[coluna].reindex(periodos).to_numpy(),
                color=TEXTO,
                linewidth=2.2,
                marker="o",
                markersize=4,
                label="Real",
                zorder=5,
            )
            ax.set_xticks(x, x_rot, rotation=45)
        r_alvo = real.loc[alvo] if alvo in real.index else pd.Series(dtype=float)
        abrev = {"Verde": "Vd", "Amarela": "Am", "Vermelha 1": "V1", "Vermelha 2": "V2"}
        cores = " · ".join(
            f"{rot.split()[0]} {abrev[cen['cores'][alvo]]}"
            for rot, cen in cenarios.items()
        )
        _estilo(
            eixos[0, c],
            f"Alvo {x_rot[-1]} (M+{(alvo - inicio).n}) · real "
            f"{abrev.get(r_alvo.get('cor_oficial'), '—')}\n"
            f"{cores}\nENA real {fmt(r_alvo.get('ena_sin', np.nan) / 1000, 1)}"
            + (" mil" if pd.notna(r_alvo.get("ena_sin", np.nan)) else ""),
        )
        _milhar(eixos[0, c])
        _estilo(
            eixos[1, c],
            f"GSF real {fmt(r_alvo.get('gsf_band_boletim', np.nan), 2)}\n"
            + " · ".join(f"{rot.split()[0]} {_br(v, 2)}" for rot, v in resumo["gsf"]),
        )
        _estilo(
            eixos[2, c],
            f"PLD real {fmt(r_alvo.get('pld_gatilho_boletim', np.nan), 0, 'R\\$ ')}\n"
            + " · ".join(
                f"{rot.split()[0]} R\\$ {_br(v, 0)}" for rot, v in resumo["pld"]
            ),
        )
        for r in range(3):
            eixos[r, c].title.set_fontsize(9.5)
    for r, rotulo in enumerate(
        ["ENA do SIN (MWmed)", "GSF_band", "PLD gatilho (R$/MWh)"]
    ):
        eixos[r, 0].set_ylabel(rotulo, color=TEXTO_SEC, fontsize=9)
    handles, labels = eixos[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO_SEC,
        bbox_to_anchor=(0.5, -0.04),
    )
    fig.suptitle(titulo, x=0.01, ha="left", color=TEXTO, fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return _salvar(fig, nome)


def faixa_bandeiras(tabelas: dict, titulo: str, nome: str) -> Path:
    """Bandeira real, pelas séries (com probabilidade) e pela Dcide, mês a mês, para cada deck.

    `tabelas` mapeia o rótulo do deck -> DataFrame indexado pelo mês com as colunas
    cor_real, cor_series, prob_series (texto), cor_dcide e, opcionalmente, prob_dcide. As faixas de todos os decks
    usam as mesmas colunas (meses do calendário), para ficarem alinhadas; meses anteriores
    ao início de um deck aparecem como célula cinza, sem texto.
    """
    prob_dcide = (
        "prob_dcide" if all("prob_dcide" in t for t in tabelas.values()) else None
    )
    linhas = [
        ("Real", "cor_real", None),
        ("Séries NEWAVE", "cor_series", "prob_series"),
        ("GSF séries + Dcide", "cor_dcide", prob_dcide),
    ]
    meses = sorted(set().union(*(t.index for t in tabelas.values())))
    fig, eixos = plt.subplots(
        len(tabelas),
        1,
        figsize=(17, 2.7 * len(tabelas)),
        facecolor=SUPERFICIE,
        squeeze=False,
    )
    for ax, (rotulo, t) in zip(eixos[:, 0], tabelas.items()):
        ax.set_facecolor(SUPERFICIE)
        for j, mes in enumerate(meses):
            for i, (_, col, prob) in enumerate(linhas):
                if mes not in t.index or pd.isna(t.loc[mes, col]):
                    ax.add_patch(
                        plt.Rectangle(
                            (j, -i),
                            0.94,
                            0.88,
                            color=CINZA_FAIXA,
                            alpha=0.5,
                            linewidth=0,
                        )
                    )
                    continue
                cor = t.loc[mes, col]
                ax.add_patch(
                    plt.Rectangle(
                        (j, -i), 0.94, 0.88, color=CORES_BANDEIRA[cor], linewidth=0
                    )
                )
                txt = cor if prob is None else f"{cor}\n{t.loc[mes, prob]}"
                claro = cor in ("Vermelha 2", "Verde", "Vermelha 1")
                acerto = "" if i == 0 or cor == t.loc[mes, "cor_real"] else " ✗"
                ax.text(
                    j + 0.47,
                    -i + 0.44,
                    txt + acerto,
                    ha="center",
                    va="center",
                    fontsize=7.2,
                    color="#ffffff" if claro else TEXTO,
                )
        ax.set_xlim(-0.05, len(meses))
        ax.set_ylim(-len(linhas) + 0.9, 0.95)
        ax.set_xticks(
            [j + 0.47 for j in range(len(meses))], [MESES[m - 1] for m in meses]
        )
        ax.set_yticks(
            [-i + 0.44 for i in range(len(linhas))], [lin[0] for lin in linhas]
        )
        ax.tick_params(colors=TEXTO_SEC, labelsize=9, length=0)
        for lado in ax.spines.values():
            lado.set_visible(False)
        ax.set_title(rotulo, loc="left", color=TEXTO, fontsize=11, fontweight="bold")
    fig.suptitle(titulo, x=0.01, ha="left", color=TEXTO, fontsize=12, fontweight="bold")
    fig.tight_layout()
    return _salvar(fig, nome)


def faixa_cenarios(tabelas: dict, linhas: list, titulo: str, nome: str) -> Path:
    """Bandeira real e de cada cenário, mês a mês, uma faixa por deck (meses alinhados).

    `tabelas` mapeia o rótulo do deck -> DataFrame indexado por período (mês) com a coluna
    cor_real e as colunas de `linhas`, lista de (rótulo, coluna da cor, coluna do texto ou None,
    critério). Critério do ✗: "igual" (cor diferente da real), "teto" (real pior que a cor: LI)
    ou "piso" (real melhor que a cor: LS). Célula cinza sem texto: mês fora do horizonte do deck.
    """
    ordem = {c: i for i, c in enumerate(CORES_BANDEIRA)}
    linhas = [("Real", "cor_real", None, None), *linhas]
    meses = sorted(set().union(*(t.index for t in tabelas.values())))
    fig, eixos = plt.subplots(
        len(tabelas),
        1,
        figsize=(2.1 * len(meses) + 2, 0.95 * len(linhas) * len(tabelas) + 0.6),
        facecolor=SUPERFICIE,
        squeeze=False,
    )
    for ax, (rotulo, t) in zip(eixos[:, 0], tabelas.items()):
        ax.set_facecolor(SUPERFICIE)
        for j, mes in enumerate(meses):
            for i, (_, col, texto, criterio) in enumerate(linhas):
                if mes not in t.index or pd.isna(t.loc[mes, col]):
                    ax.add_patch(
                        plt.Rectangle(
                            (j, -i),
                            0.94,
                            0.88,
                            color=CINZA_FAIXA,
                            alpha=0.5,
                            linewidth=0,
                        )
                    )
                    continue
                cor = t.loc[mes, col]
                ax.add_patch(
                    plt.Rectangle(
                        (j, -i), 0.94, 0.88, color=CORES_BANDEIRA[cor], linewidth=0
                    )
                )
                real = t.loc[mes, "cor_real"]
                errou = isinstance(real, str) and (
                    (criterio == "igual" and cor != real)
                    or (criterio == "teto" and ordem[real] > ordem[cor])
                    or (criterio == "piso" and ordem[real] < ordem[cor])
                )
                txt = cor + (" ✗" if errou else "")
                if texto is not None:
                    txt += f"\n{t.loc[mes, texto]}"
                claro = cor in ("Vermelha 2", "Verde", "Vermelha 1")
                ax.text(
                    j + 0.47,
                    -i + 0.44,
                    txt,
                    ha="center",
                    va="center",
                    fontsize=7.2,
                    color="#ffffff" if claro else TEXTO,
                )
        ax.set_xlim(-0.05, len(meses))
        ax.set_ylim(-len(linhas) + 0.9, 0.95)
        ax.set_xticks(
            [j + 0.47 for j in range(len(meses))],
            [f"{MESES[m.month - 1]}/{m.year % 100:02d}" for m in meses],
        )
        ax.set_yticks(
            [-i + 0.44 for i in range(len(linhas))], [lin[0] for lin in linhas]
        )
        ax.tick_params(colors=TEXTO_SEC, labelsize=9, length=0)
        for lado in ax.spines.values():
            lado.set_visible(False)
        ax.set_title(rotulo, loc="left", color=TEXTO, fontsize=11, fontweight="bold")
    fig.suptitle(titulo, x=0.01, ha="left", color=TEXTO, fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.35 / fig.get_figheight()))
    return _salvar(fig, nome)


def matriz_backtest(
    previsoes: pd.DataFrame, titulo: str, nome: str, distribuicao: bool = False
) -> Path:
    """Matriz deck × mês-alvo com a cor prevista (cor da média), a probabilidade dessa cor e a cor real.

    `previsoes` precisa das colunas deck, alvo (Period), cor_media, cor_oficial e, opcionalmente,
    p_cor_prevista (probabilidade da cor prevista; vazia quando ainda não há histórico para o σ).
    Com `distribuicao=True`, cada célula mostra a probabilidade de todas as cores (≥ 5%), usando as
    colunas p_Verde, p_Amarela, p_Vermelha 1 e p_Vermelha 2.
    """
    alvos = sorted(previsoes.alvo.unique())
    decks = sorted(previsoes.deck.unique())
    abrev = {"Verde": "Vd", "Amarela": "Am", "Vermelha 1": "V1", "Vermelha 2": "V2"}
    real = previsoes.drop_duplicates("alvo").set_index("alvo").cor_oficial
    fig, ax = plt.subplots(
        figsize=(
            (1.05 if distribuicao else 0.82) * len(alvos) + 2,
            (0.75 if distribuicao else 0.5) * (len(decks) + 1) + 1.4,
        ),
        facecolor=SUPERFICIE,
    )
    ax.set_facecolor(SUPERFICIE)
    linhas = [("Real", None)] + [
        (f"Deck {MESES[d.month - 1]}/{d.year % 100:02d}", d) for d in decks
    ]
    for i, (rotulo, deck) in enumerate(linhas):
        for j, alvo in enumerate(alvos):
            if deck is None:
                cor, txt, ok = real[alvo], abrev[real[alvo]], True
            else:
                r = previsoes[(previsoes.deck == deck) & (previsoes.alvo == alvo)]
                if r.empty:
                    continue
                r = r.iloc[0]
                cor, ok = r.cor_media, r.cor_media == r.cor_oficial
                p = r.get("p_cor_prevista", np.nan)
                if distribuicao and not pd.isna(p):
                    itens = [
                        f"{abrev[c]} {r[f'p_{c}']:.0%}"
                        for c in abrev
                        if r.get(f"p_{c}", 0) >= 0.05
                    ]
                    txt = (
                        abrev[cor]
                        + ("" if ok else " ✗")
                        + "\n"
                        + "\n".join(
                            " ".join(itens[i : i + 2]) for i in range(0, len(itens), 2)
                        )
                    )
                else:
                    txt = (
                        abrev[cor]
                        + ("" if pd.isna(p) else f" {p:.0%}")
                        + ("" if ok else " ✗")
                    )
            ax.add_patch(
                plt.Rectangle(
                    (j, -i), 0.94, 0.86, color=CORES_BANDEIRA[cor], linewidth=0
                )
            )
            claro = cor in ("Vermelha 2", "Verde", "Vermelha 1")
            ax.text(
                j + 0.47,
                -i + 0.43,
                txt,
                ha="center",
                va="center",
                fontsize=6.0 if distribuicao else 6.8,
                color="#ffffff" if claro else TEXTO,
                fontweight="bold" if not ok else "normal",
            )
    ax.set_xlim(-0.05, len(alvos))
    ax.set_ylim(-len(linhas) + 0.9, 0.95)
    ax.set_xticks(
        [j + 0.47 for j in range(len(alvos))],
        [f"{MESES[a.month - 1]}/{a.year % 100:02d}" for a in alvos],
        rotation=90,
    )
    ax.set_yticks([-i + 0.43 for i in range(len(linhas))], [l[0] for l in linhas])
    ax.tick_params(colors=TEXTO_SEC, labelsize=8, length=0)
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_title(titulo, loc="left", color=TEXTO, fontsize=11, fontweight="bold")
    fig.tight_layout()
    return _salvar(fig, nome)


def erro_por_lead(tabela: pd.DataFrame, titulo: str, nome: str, rotulo_y: str) -> Path:
    """Linhas: uma por fonte (colunas da tabela), eixo x = lead (meses após a emissão)."""
    fig, ax = plt.subplots(figsize=(9, 4.6), facecolor=SUPERFICIE)
    for (fonte, valores), cor in zip(tabela.items(), SERIES):
        ax.plot(
            tabela.index,
            valores,
            color=cor,
            linewidth=2,
            marker="o",
            markersize=5,
            label=fonte,
        )
        ax.annotate(
            f"{valores.iloc[-1]:.0f}",
            (tabela.index[-1], valores.iloc[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color=TEXTO_SEC,
        )
    _estilo(ax, titulo)
    ax.set_xlabel("Lead (meses após a emissão)", color=TEXTO_SEC, fontsize=9)
    ax.set_ylabel(rotulo_y, color=TEXTO_SEC, fontsize=9)
    ax.set_ylim(0, None)
    ax.set_xticks(list(tabela.index))
    ax.legend(
        frameon=False,
        fontsize=9,
        labelcolor=TEXTO_SEC,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=2,
    )
    return _salvar(fig, nome)
