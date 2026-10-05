"""Gráficos da análise exploratória.

Funções que recebem a base mensal (features.base_mensal) e salvam PNG em reports/figures/.
Paleta categórica de referência em ordem fixa (a cor segue a série, nunca a posição).
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

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
    return [MESES[d.month - 1] for d in indice]


def _salvar(fig, nome: str) -> Path:
    FIGURAS.mkdir(parents=True, exist_ok=True)
    caminho = FIGURAS / nome
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
        for xi, yi, m in zip(x, y, _rotulos_mes(base.index)):
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
        "GH_band contra as variáveis candidatas — SIN, 2026 (10 meses)",
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
    for xi, v, mlt in zip(x, base.ena_sin, base.ena_mlt_sin):
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
        "ENA prevista e GH_band do SIN (MWmed); rótulos: ENA em % da MLT",
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
        "O que sobra do GH_band depois da carga residual não acompanha a ENA — SIN, 2026",
        "Resíduo de GH_band ~ carga residual (MWmed)",
        nome,
    )
