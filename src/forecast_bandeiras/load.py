"""Carregamento de dados.

Funções para ler os dados brutos de data/raw/ (somente leitura), aplicar a
limpeza básica (tipos, datas, valores ausentes) e salvar/ler os dados limpos
em formato parquet em data/processed/.
"""

import gzip
import io
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
DATA_RAW = RAIZ / "data" / "raw"
DATA_PROCESSED = RAIZ / "data" / "processed"

PATAMARES = ["PESADO", "MEDIO", "LEVE"]  # mesma ordem dos patamares 1, 2 e 3 do DECOMP
SUBSISTEMAS = {"SECO": "SE", "SUL": "S", "NE": "NE", "N": "N"}


def _normaliza(texto) -> str:
    """Remove acentos, espaços nas pontas e passa para maiúsculas."""
    return (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", "ignore")
        .decode()
        .strip()
        .upper()
    )


# ---------------------------------------------------------------------------
# Patamares de carga (CCEE, arquivo horário AAC001)
# ---------------------------------------------------------------------------


def ler_patamares(ano: int) -> pd.DataFrame:
    """Lê o arquivo horário de patamares da CCEE (AAC001) de um ano.

    O layout muda entre anos (2025: colunas DIA + HORA; 2026: DATA REFERÊNCIA),
    então a linha de cabeçalho e as colunas são localizadas pelo nome.

    Retorna um DataFrame com uma linha por hora: `ts` (início da hora) e `patamar`
    (PESADO, MEDIO ou LEVE).
    """
    arquivo = next((DATA_RAW / "patamar" / str(ano)).glob("AAC001*.xlsx"))
    bruto = pd.read_excel(arquivo, header=None)
    linha = next(
        i for i, r in bruto.iterrows() if any(_normaliza(v) == "PATAMAR" for v in r)
    )
    df = bruto.iloc[linha + 1 :].copy()
    df.columns = [_normaliza(c) for c in bruto.iloc[linha]]

    if "DATA REFERENCIA" in df:
        ts = pd.to_datetime(df["DATA REFERENCIA"])
    else:
        ts = pd.to_datetime(df["DIA"]) + pd.to_timedelta(df["HORA"].astype(str))

    out = pd.DataFrame({"ts": ts, "patamar": df["PATAMAR"].map(_normaliza)}).dropna()
    if len(out) not in (8760, 8784):
        raise ValueError(
            f"{arquivo.name}: esperado um ano de horas, encontrado {len(out)}"
        )
    return out.reset_index(drop=True)


def horas_por_semana(ano: int, mes: int) -> pd.DataFrame:
    """Horas de cada patamar em cada semana operativa, contando só as horas dentro do mês.

    A semana operativa vai de sábado a sexta; a semana 1 é a que contém o dia 1.
    Retorna uma tabela patamar (linhas: PESADO, MEDIO, LEVE) x semana (colunas 1..n),
    no mesmo formato da Tabela 11 do boletim InfoBandeira.
    """
    h = ler_patamares(ano)
    h = h[h.ts.dt.month == mes].copy()
    dia = h.ts.dt.normalize()
    h["inicio_semana"] = dia - pd.to_timedelta((dia.dt.dayofweek - 5) % 7, unit="D")
    h["semana"] = h.inicio_semana.rank(method="dense").astype(int)
    tabela = h.groupby(["patamar", "semana"]).size().unstack(fill_value=0)
    return tabela.reindex(PATAMARES, fill_value=0)


# ---------------------------------------------------------------------------
# Sumário do DECOMP rv0 do PMO (ONS)
# ---------------------------------------------------------------------------


def caminho_sumario(ano: int, mes: int) -> Path:
    """Caminho do sumario.rv0 do PMO de um mês."""
    return DATA_RAW / "ons_decomp" / str(ano) / f"{ano}_{mes:02d}" / "sumario.rv0"


def _numeros(linha: str, n: int) -> list[float]:
    """Últimos n números de uma linha de tabela do sumário."""
    return [float(v) for v in linha.split()[-n:]]


def _bloco(linhas: list[str], titulo: str) -> list[str]:
    """Linhas de um bloco do sumário, do título até a linha de fechamento da tabela."""
    inicio = next(i for i, ln in enumerate(linhas) if ln.strip() == titulo)
    bloco, bordas = [], 0
    for ln in linhas[inicio + 1 :]:
        if ln.strip().startswith("X-"):
            bordas += 1
            if bordas == 3:  # cabeçalho tem 2 bordas; a 3ª fecha a tabela
                break
            continue
        bloco.append(ln)
    return bloco


def ler_sumario(ano: int, mes: int) -> dict:
    """Extrai do sumario.rv0 os valores por patamar e semana usados no cálculo do GH_band.

    Retorna um dicionário de arrays patamar (3 linhas: pesado, médio, leve) x semana:
    - `gh`: geração hidráulica total (linha `Totais`, inclui Itaipu 50 e 60 Hz), MWmed;
    - `ande`: geração de Itaipu para a ANDE + consumo interno, MWmed;
    - `pch`: dicionário subsistema -> geração das PCH/CGH (linhas `*_PCH`, sem `gd`), MWmed.

    O CMO deste arquivo NÃO é o PLD gatilho (ver CLAUDE.md); por isso não é lido aqui.
    """
    linhas = caminho_sumario(ano, mes).read_text(encoding="latin-1").splitlines()

    titulo_gh = "GERACAO HIDRAULICA (MWmed) PARA O PATAMAR {}"
    cabecalho = next(ln for ln in _bloco(linhas, titulo_gh.format(1)) if "Sem_01" in ln)
    n_sem = len(re.findall(r"Sem_\d+", cabecalho))

    gh = []
    for p in (1, 2, 3):
        totais = next(
            ln
            for ln in _bloco(linhas, titulo_gh.format(p))
            if ln.strip().startswith("Totais")
        )
        gh.append(_numeros(totais, n_sem))

    itaipu = _bloco(linhas, "GERACAO HIDRAULICA EM ITAIPU (MWmed)")
    ande = [_numeros(ln, n_sem) for ln in itaipu if ln.strip().startswith("Ande")]
    if len(ande) != 3:
        raise ValueError(
            f"esperadas 3 linhas 'Ande' (uma por patamar), encontradas {len(ande)}"
        )

    pch = {s: [] for s in SUBSISTEMAS.values()}
    for p in (1, 2, 3):
        for ln in _bloco(linhas, f"PEQUENAS USINAS : DESPACHO NO PATAMAR {p} (MWmed)"):
            m = re.match(r"\s*(\w+)_PCH\s+\w+\s", ln)
            if m and m.group(1) in SUBSISTEMAS:
                pch[SUBSISTEMAS[m.group(1)]].append(_numeros(ln, n_sem))

    return {
        "gh": np.array(gh),
        "ande": np.array(ande),
        "pch": {s: np.array(v) for s, v in pch.items()},
    }


def caminho_renovaveis(ano: int, mes: int) -> Path:
    """Caminho do renovaveis.csv (entrada do DECOMP, só a partir de 2026 na base)."""
    return caminho_sumario(ano, mes).parent / "renovaveis.csv"


def ler_renovaveis(ano: int, mes: int) -> dict:
    """Lê a geração eólica e solar centralizadas do renovaveis.csv (entrada do DECOMP).

    O arquivo tem 8 parques equivalentes (eólica e fotovoltaica por submercado) e
    7 períodos: 1 a n são as semanas operativas do mês (cenário único) e o último é o
    mês seguinte (vários cenários), que é descartado aqui.

    Retorna um dicionário (fonte, subsistema) -> array patamar x semana, em MW,
    com fonte "EOL" ou "UFV" e subsistema SE, S, NE ou N.
    """
    caminho = caminho_renovaveis(ano, mes)
    linhas = [
        ln
        for ln in caminho.read_text(encoding="latin-1").splitlines()
        if ln.startswith("PEE-GER-PER-PAT-CEN")
    ]
    g = pd.read_csv(
        io.StringIO("\n".join(linhas)),
        sep=";",
        header=None,
        names=["id", "pee", "per_ini", "per_fin", "pat", "cen", "mw"],
    )
    n_sem = horas_por_semana(ano, mes).shape[1]
    g = g[g.per_ini <= n_sem]
    if (g.cen != 1).any():
        raise ValueError("esperado cenário único nas semanas do mês")

    codigos = {1: "SE", 2: "S", 3: "NE", 4: "N"}  # 1-4 eólica; 11-14 fotovoltaica
    saida = {}
    for pee, d in g.groupby("pee"):
        fonte = "EOL" if pee < 10 else "UFV"
        tabela = d.pivot(index="pat", columns="per_ini", values="mw").sort_index()
        saida[(fonte, codigos[pee % 10])] = tabela.to_numpy()
    return saida


def ler_balanco_sumario(ano: int, mes: int) -> dict:
    """Extrai do sumario.rv0 os demais termos do balanço e o armazenamento inicial.

    Retorna (arrays patamar x semana, MWmed):
    - `demanda`: subsistema -> demanda bruta (bloco DEMANDA BRUTA);
    - `termica`: geração térmica total (inclui nuclear e inflexível);
    - `nuclear`: soma das linhas ANGRA do bloco térmico;
    - `pequenas`: (tipo, subsistema) -> geração, com tipo em PCH, PCT, PCHgd,
      PCTgd, EOLgd, UFVgd (os `gd` são a MMGD);
    - `ear_ini`: subsistema -> EAR inicial (% EARmax);
    - `ear_ree`: DataFrame por REE com subsistema, EAR inicial (%) e EARmax (MWmês),
      para agregar o SIN ponderando pela capacidade.
    """
    linhas = caminho_sumario(ano, mes).read_text(encoding="latin-1").splitlines()
    n_sem = ler_sumario(ano, mes)["gh"].shape[1]

    demanda, atual = {}, []
    for ln in _bloco(linhas, "DEMANDA BRUTA (MWmed) POR SUBSISTEMA E POR PATAMAR"):
        rotulo = ln.split()[0] if ln.split() else ""
        if rotulo.startswith("Pat_"):
            atual.append(_numeros(ln, n_sem))
        elif rotulo.startswith("Med_"):
            sub = rotulo.removeprefix("Med_")
            if sub in SUBSISTEMAS.values():
                demanda[sub] = np.array(atual)
            atual = []
        elif rotulo == "Totais":
            break

    termica, nuclear = [], []
    for p in (1, 2, 3):
        bloco = _bloco(linhas, f"GERACAO TERMICA (MWmed) PARA O PATAMAR {p}")
        termica.append(
            _numeros(next(ln for ln in bloco if ln.strip().startswith("Totais")), n_sem)
        )
        angra = [_numeros(ln, n_sem) for ln in bloco if "ANGRA" in ln]
        nuclear.append(np.sum(angra, axis=0) if angra else np.zeros(n_sem))

    padrao = re.compile(r"\s*(SECO|SUL|NE|N)_(PCH|PCT|EOL|UFV)(gd)?\s*(SE|S|NE|N)\s")
    pequenas = {}
    for p in (1, 2, 3):
        for ln in _bloco(linhas, f"PEQUENAS USINAS : DESPACHO NO PATAMAR {p} (MWmed)"):
            m = padrao.match(ln)
            if m:
                chave = (m.group(2) + (m.group(3) or ""), SUBSISTEMAS[m.group(1)])
                pequenas.setdefault(chave, []).append(_numeros(ln, n_sem))

    ear_ini = {}
    for ln in _bloco(linhas, "ENERGIA ARMAZENADA NOS SUBSISTEMAS (% EARM_MAXIMA)"):
        partes = ln.split()
        if partes and partes[0] in SUBSISTEMAS.values():
            ear_ini[partes[0]] = float(partes[2])

    ree = []
    for i, ln in enumerate(linhas):
        m = re.match(
            r"\s*REE:\s*(\d+) - (.+?)\s+SIST:\s*\d+ - (\w+)\s+EAR_ini:\s*([\d.]+)", ln
        )
        if m:
            earm = next(float(x.split()[1]) for x in linhas[i : i + 5] if "EARM:" in x)
            ree.append(
                {
                    "ree": m.group(2).strip(),
                    "subsistema": m.group(3),
                    "ear_ini": float(m.group(4)),
                    "earm": earm,
                }
            )

    return {
        "demanda": demanda,
        "termica": np.array(termica),
        "nuclear": np.array(nuclear),
        "pequenas": {k: np.array(v) for k, v in pequenas.items()},
        "ear_ini": ear_ini,
        "ear_ree": pd.DataFrame(ree),
    }


def _num_br(texto: str) -> float:
    """Converte número no formato brasileiro (1.234,5) para float."""
    return float(texto.replace(".", "").replace(",", "."))


def ler_ena(ano: int, mes: int) -> pd.DataFrame:
    """Lê a Tabela 6 do ena.pdf do PMO: ENA prevista por subsistema.

    Retorna um DataFrame indexado por subsistema (SE, S, NE, N) com a ENA da 1ª semana
    e a previsão mensal inicial, em MWmed e % da MLT.
    """
    import pdfplumber

    caminho = caminho_sumario(ano, mes).parent / "ena.pdf"
    with pdfplumber.open(caminho) as pdf:
        texto = pdf.pages[0].extract_text()
    nomes = {"SUDESTE": "SE", "SUL": "S", "NORDESTE": "NE", "NORTE": "N"}
    linhas = texto.splitlines()
    inicio = next(i for i, ln in enumerate(linhas) if "TABELA 6" in ln)
    dados = {}
    for ln in linhas[inicio : inicio + 12]:
        m = re.match(
            r"(SUDESTE|SUL|NORDESTE|NORTE)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)", ln
        )
        if m:
            dados[nomes[m.group(1)]] = {
                "ena_sem1": _num_br(m.group(2)),
                "ena_sem1_mlt": float(m.group(3)),
                "ena_mes": _num_br(m.group(4)),
                "ena_mes_mlt": float(m.group(5)),
            }
    if len(dados) != 4:
        raise ValueError(f"{caminho}: Tabela 6 com {len(dados)} subsistemas")
    return pd.DataFrame(dados).T


def ler_boletim(ano: int, mes: int) -> dict:
    """Lê do boletim InfoBandeira (CCEE) os valores da Tabela 15 e a cor publicada."""
    import pdfplumber

    pasta = DATA_RAW / "ccee_calculo_bandeira" / str(ano)
    caminho = next(pasta.glob(f"*_{ano}_{mes:02d}.pdf"))
    with pdfplumber.open(caminho) as pdf:
        texto = "\n".join(p.extract_text() or "" for p in pdf.pages)

    padroes = {
        "gh_band": r"𝑮𝑯\s*(?:𝒃𝒂𝒏𝒅\s*)?\(𝑴𝑾𝒎𝒆𝒅\)\s*([\d.]+)",
        "gf_band": r"𝑮𝑭\s*(?:𝒃𝒂𝒏𝒅\s*)?\(𝑴𝑾𝒎𝒆𝒅\)\s*([\d.]+)",
        "gsf_band": r"𝑮𝑺𝑭\s*(?:𝒃𝒂𝒏𝒅\s*)?([\d,]+)",
    }
    saida = {}
    for chave, padrao in padroes.items():
        m = re.search(padrao, texto)
        if not m:
            raise ValueError(f"{caminho.name}: não encontrado {chave}")
        saida[chave] = _num_br(m.group(1))
    # A Tabela 15 traz três PLDs com o mesmo rótulo (máximo, mínimo e gatilho); o gatilho
    # está sempre entre os outros dois, então é a mediana.
    plds = [
        _num_br(v)
        for v in re.findall(r"𝑷𝑳𝑫\s*(?:[^\s(]+\s*)?\(𝑹\$/𝑴𝑾𝒉\)\s*([\d.,]+)", texto)
    ]
    if len(plds) != 3:
        raise ValueError(
            f"{caminho.name}: esperados 3 PLDs na Tabela 15, encontrados {len(plds)}"
        )
    saida["pld_min"], saida["pld_gatilho"], saida["pld_max"] = sorted(plds)

    # Campos opcionais (None se o layout do boletim não permitir a leitura).
    opcionais = {
        "gh_ons": r"GH ONS ([\d.]+)",
        "ande": r"ANDE \+ C\. I\. Itaipu ([\d.]+)",
        "f_bruta_conexao": r"Bruta p/ Conexão\) ([\d,]+)%",
        "f_conexao_cg": r"Hidráulica \(Conexão p/ Centro de Gravidade\) ([\d,]+)%",
        "f_part_pch": r"Participação de PCH e CGH no MRE ([\d,]+)%",
        "f_perda_pch": r"Perda de PCH e CGH \(Conexão p/ Centro de Gravidade\) ([\d,]+)%",
        "gfom": r"𝑮𝑭𝑶𝑴\s*\(𝑴𝑾𝒎𝒆𝒅\)\s*([\d.,]+)",
    }
    for chave, padrao in opcionais.items():
        m = re.search(padrao, texto)
        saida[chave] = _num_br(m.group(1)) if m else None
    for chave in ("f_bruta_conexao", "f_conexao_cg", "f_part_pch", "f_perda_pch"):
        if saida[chave] is not None:
            saida[chave] /= 100

    # Cor: em alguns boletins a Tabela 17 é imagem (sem texto); aí fica None.
    # O texto às vezes traz o nome do mês errado (ex.: maio/2026 cita fevereiro).
    m = re.search(
        rf"\w+ [Dd]e {ano} (Verde|Amarela|Vermelha(?: Patamar)? ?\d?)\s*$",
        texto,
        re.MULTILINE,
    )
    saida["cor"] = m.group(1).strip() if m else None
    return saida


# ---------------------------------------------------------------------------
# Relato do DECOMP rv0 (ONS): balanço energético e operação térmica
# ---------------------------------------------------------------------------


def caminho_relato(ano: int, mes: int) -> Path:
    """Caminho do relato.rv0 do PMO de um mês."""
    return caminho_sumario(ano, mes).parent / "relato.rv0"


def ler_linhas(caminho: str | Path) -> list[str]:
    """Linhas de um arquivo texto do DECOMP (relato ou sumário); aceita `.gz`."""
    caminho = Path(caminho)
    if caminho.suffix == ".gz" or caminho.read_bytes()[:2] == b"\x1f\x8b":
        return gzip.decompress(caminho.read_bytes()).decode("latin-1").splitlines()
    return caminho.read_text(encoding="latin-1").splitlines()


def _linhas_relato(ano: int, mes: int, relato: str | Path | None = None) -> list[str]:
    """Linhas do relato do PMO do mês ou, se `relato` for dado, de um relato qualquer."""
    return ler_linhas(relato if relato is not None else caminho_relato(ano, mes))


def ler_relato_balanco(
    ano: int, mes: int, relato: str | Path | None = None
) -> pd.DataFrame:
    """Lê o RELATORIO DO BALANCO ENERGETICO: uma linha por semana, subsistema e patamar (MWmed).

    As colunas são localizadas pelo cabeçalho de cada tabela, porque o layout mudou ao longo
    do tempo (até set/2025 não há `Geol` e as pequenas usinas se chamam `Bacia`):
    mercado (carga bruta), pqusi (pequenas usinas, inclui MMGD), cbomba (bombeamento),
    ghid (hidráulica; no SE inclui Itaipu 50 Hz), gter, gterat (térmica antecipada),
    geol (eólica + solar centralizadas, a partir de out/2025), it50 e it60 (Itaipu, só no SE).
    GH ONS = soma de ghid + it60. Só as semanas do mês (o mês seguinte é descartado).
    """
    n_sem = horas_por_semana(ano, mes).shape[1]
    nomes = {
        "Mercado": "mercado",
        "PQUsi": "pqusi",
        "Bacia": "pqusi",
        "Cbomba": "cbomba",
        "Ghid": "ghid",
        "Gter": "gter",
        "GterAT": "gterat",
        "Geol": "geol",
    }
    linhas, semana, sub, colunas = [], None, None, None
    for ln in _linhas_relato(ano, mes, relato):
        m = re.search(r"SEMANA (\d) - ESTAGIO", ln)
        if m:
            semana = int(m.group(1))
        m = re.match(r"\s+Subsistema (\w+)\s*$", ln)
        if m:
            sub = m.group(1)
        if ln.split()[:1] == ["Mercado"]:
            cabecalho = ln.split()
            colunas = cabecalho[: cabecalho.index("Interligacao")]
            continue
        m = re.match(r"\s+Pat_(\d)\s+(.*)", ln)
        if m and semana and sub and colunas:
            valores = [float(x) for x in m.group(2).split()[: len(colunas)]]
            linha = {"semana": semana, "subsistema": sub, "pat": int(m.group(1))}
            linha.update({nomes[c]: v for c, v in zip(colunas, valores) if c in nomes})
            it50, it60 = (float(x) for x in ln.split()[-2:]) if sub == "SE" else (0, 0)
            linha.update({"it50": it50, "it60": it60})
            linhas.append(linha)
    df = pd.DataFrame(linhas).drop_duplicates(["semana", "subsistema", "pat"])
    for coluna in ("geol", "gterat"):
        if coluna not in df:
            df[coluna] = 0.0
    return df[df.semana <= n_sem].fillna(0.0).reset_index(drop=True)


def ler_relato_termicas(
    ano: int, mes: int, relato: str | Path | None = None
) -> pd.DataFrame:
    """Geração térmica por usina, semana e patamar, com GTmin/GTmax do cadastro (MWmed).

    Junta o RELATORIO DA OPERACAO TERMICA E CONTRATOS (geração e flag: I = no mínimo,
    S = no máximo, vazio = entre os dois) com o Relatorio dos Dados de Usinas Termicas
    (GTmin e GTmax por estágio e patamar). A parcela inflexível de cada usina é
    min(geração, GTmin); somar só as linhas com flag I subestima a inflexibilidade,
    porque usinas acima do mínimo não levam a flag.
    """
    linhas = _linhas_relato(ano, mes, relato)

    inicio = next(
        i
        for i, ln in enumerate(linhas)
        if ln.strip() == "Relatorio  dos  Dados  de  Usinas  Termicas"
    )
    cadastro, usina = [], None
    for ln in linhas[inicio + 5 :]:
        if ln.strip().startswith("X-"):
            break
        m = re.match(r"\s+\d+ (.{10})\s+(\w+)\s+(\d+)\s+(.*)", ln)
        if m:
            usina = (m.group(1).strip(), m.group(2))
            estagio, valores = int(m.group(3)), m.group(4).split()
        else:
            m = re.match(r"\s+(\d+)\s+([\d.]+\s.*)", ln)
            if not m or usina is None:
                continue
            estagio, valores = int(m.group(1)), m.group(2).split()
        valores = [float(x) for x in valores]
        for p in range(3):
            cadastro.append(
                {
                    "usina": usina[0],
                    "subsistema": usina[1],
                    "semana": estagio,
                    "pat": p + 1,
                    "gtmin": valores[3 * p],
                    "gtmax": valores[3 * p + 1],
                }
            )

    flag = r"\s+([\d.]+)([IS]?)"
    padrao = re.compile(r"\s+(SE|S|NE|N|FC)\s+(.{10})" + flag * 3 + r"\s+[\d.]+")
    operacao, semana = [], None
    for i, ln in enumerate(linhas):
        if "RELATORIO  DA  OPERACAO  TERMICA E CONTRATOS" in ln:
            semana = int(re.search(r"SEMANA (\d)", linhas[i + 2]).group(1))
            continue
        if "RELATORIO  DO  BALANCO  ENERGETICO" in ln:
            semana = None
        m = padrao.match(ln) if semana else None
        if m:
            for p in range(3):
                operacao.append(
                    {
                        "semana": semana,
                        "subsistema": m.group(1),
                        "usina": m.group(2).strip(),
                        "pat": p + 1,
                        "ger": float(m.group(3 + 2 * p)),
                        "flag": m.group(4 + 2 * p),
                    }
                )

    df = pd.DataFrame(operacao).merge(
        pd.DataFrame(cadastro), on=["usina", "subsistema", "semana", "pat"], how="left"
    )
    if df.gtmin.isna().any():
        raise ValueError(f"usinas sem cadastro: {df[df.gtmin.isna()].usina.unique()}")
    df["inflexivel"] = np.minimum(df.ger, df.gtmin)
    df["nuclear"] = df.usina.str.startswith("ANGRA")
    return df


def ler_relato_pequenas(
    ano: int, mes: int, relato: str | Path | None = None
) -> pd.DataFrame:
    """Lê o Relatorio dos Dados de Pequenas Usinas: geração por usina, subsistema, semana e patamar (MW).

    Colunas: tipo (PCH, PCT, EOL, UFV, PCHgd, PCTgd, EOLgd, UFVgd), subsistema, semana, pat, mw.
    EOL e UFV (centralizadas) só aparecem até set/2025; a partir de out/2025 estão no `geol`
    do balanço. As linhas `gd` (MMGD) só existem a partir de mai/2023.
    """
    n_sem = horas_por_semana(ano, mes).shape[1]
    linhas = _linhas_relato(ano, mes, relato)
    inicio = next(
        i
        for i, ln in enumerate(linhas)
        if ln.strip() == "Relatorio dos Dados de Pequenas Usinas"
    )
    saida, usina, bordas = [], None, 0
    for ln in linhas[inicio + 1 :]:
        if ln.strip().startswith("X-"):
            bordas += 1
            if bordas == 3:
                break
            continue
        m = re.match(
            r"\s+(SECO|SUL|NE|N)_(PCH|PCT|EOL|UFV)(gd)?\s+\w+\s+(\d+)\s+(.*)", ln
        )
        if m:
            usina = (m.group(2) + (m.group(3) or ""), SUBSISTEMAS[m.group(1)])
            estagio, valores = int(m.group(4)), m.group(5).split()
        else:
            m = re.match(r"\s+(\d+)\s+([\d.]+\s.*)", ln)
            if not m or usina is None:
                continue
            estagio, valores = int(m.group(1)), m.group(2).split()
        if estagio > n_sem:
            continue
        for p, v in enumerate(valores[:3], start=1):
            saida.append(
                {
                    "tipo": usina[0],
                    "subsistema": usina[1],
                    "semana": estagio,
                    "pat": p,
                    "mw": float(v),
                }
            )
    return pd.DataFrame(saida)


def ler_relato_ande(
    ano: int, mes: int, relato: str | Path | None = None
) -> pd.DataFrame:
    """ANDE (Itaipu para o Paraguai + consumo interno) por semana e patamar (MWmed)."""
    n_sem = horas_por_semana(ano, mes).shape[1]
    linhas = _linhas_relato(ano, mes, relato)
    inicio = next(
        i
        for i, ln in enumerate(linhas)
        if "Relatorio de eco  das informacoes de ITAIPU" in ln
    )
    saida = []
    for ln in linhas[inicio + 5 :]:
        if ln.strip().startswith("X-"):
            break
        per, pat, *_, ande = ln.split()
        if int(per) <= n_sem:
            saida.append({"semana": int(per), "pat": int(pat), "ande": float(ande)})
    return pd.DataFrame(saida)


def ler_relato_ear(
    ano: int, mes: int, relato: str | Path | None = None
) -> pd.DataFrame:
    """EAR inicial do mês por subsistema (cabeçalho do balanço da semana 1): MWmês e % EARmax."""
    linhas = _linhas_relato(ano, mes, relato)
    inicio = next(
        i for i, ln in enumerate(linhas) if "RELATORIO  DO  BALANCO  ENERGETICO" in ln
    )
    saida = {}
    for i in range(inicio, inicio + 200):
        m = re.match(r"\s+Subsistema (SE|S|NE|N)\s*$", linhas[i])
        if m:
            mwmes = float(re.search(r"EAR_ini:\s*([\d.]+)", linhas[i + 1]).group(1))
            pct = float(linhas[i + 2].split()[0])
            saida[m.group(1)] = {"ear_mwmes": mwmes, "ear_pct": pct}
    return pd.DataFrame(saida).T


def ler_dcide(ano: int, mes: int) -> pd.Series:
    """Curva forward da Dcide (PLD do SE, R$/MWh) para usar com o deck do NEWAVE de ano/mês.

    Arquivos em data/raw/dcide/ com nome dcide_<data de publicação>_<AAAAMM do deck>.csv.
    Retorna uma série indexada pelo mês de suprimento (Timestamp do 1º dia).
    """
    caminho = next((DATA_RAW / "dcide").glob(f"dcide_*_{ano}{mes:02d}.csv"))
    df = pd.read_csv(caminho, decimal=",", parse_dates=["suprimento"])
    return df.set_index("suprimento")["PLD_SE_CONV"].astype(float).rename("pld_dcide")


# ---------------------------------------------------------------------------
# Previsão sazonal de ENA do ECMWF (SEAS5), por subsistema
# ---------------------------------------------------------------------------

SUBSISTEMAS_ECMWF = {"Sudeste": "SE", "Sul": "S", "Nordeste": "NE", "Norte": "N"}


def _ler_arquivo_ecmwf(caminho: Path) -> pd.DataFrame:
    """Lê um arquivo ENA_MLT_SUBSISTEMA_MENSAL_*: alvo, subsistema, ena (MWmed), mlt, pct_mlt."""
    df = pd.read_csv(caminho, sep=r"\s{2,}", engine="python")
    df.columns = ["alvo", "subsistema", "ena", "mlt", "pct_mlt"]
    df["alvo"] = pd.PeriodIndex(df.alvo.str.strip(), freq="M")
    df["subsistema"] = df.subsistema.str.strip().map(SUBSISTEMAS_ECMWF)
    return df


def ler_ecmwf_estatisticas() -> pd.DataFrame:
    """Média (`av`) e percentis do ECMWF nas abordagens `precip` e `vaz`, todas as rodadas.

    Arquivos em data/raw/ecmwf_ena/ECENSLT_estat/ECENSLT<estat>_<abordagem>/.
    Colunas: emissao (Period do mês de emissão), estatistica (av, p10 … p90), abordagem,
    alvo, subsistema, ena, mlt, pct_mlt.
    """
    partes = []
    for pasta in sorted((DATA_RAW / "ecmwf_ena" / "ECENSLT_estat").glob("ECENSLT*_*")):
        estatistica, abordagem = pasta.name.removeprefix("ECENSLT").split("_", 1)
        for arq in sorted(pasta.glob("*.txt")):
            df = _ler_arquivo_ecmwf(arq)
            df["emissao"] = pd.Period(arq.stem.rsplit("_", 1)[1][:6], "M")
            df["estatistica"], df["abordagem"] = estatistica, abordagem
            partes.append(df)
    return pd.concat(partes, ignore_index=True)


def ler_ecmwf_membros() -> pd.DataFrame:
    """Os 51 membros do ECMWF (m00 a m50), todas as rodadas.

    Arquivos em data/raw/ecmwf_ena/ECENSLTm/<AAAA-MM>/. Colunas: emissao, membro (0–50),
    alvo, subsistema, ena, mlt, pct_mlt.
    """
    partes = []
    for arq in sorted((DATA_RAW / "ecmwf_ena" / "ECENSLTm").glob("*/*.txt")):
        df = _ler_arquivo_ecmwf(arq)
        df["emissao"] = pd.Period(arq.stem.rsplit("_", 1)[1][:6], "M")
        df["membro"] = int(re.search(r"ECENSLTm(\d+)_", arq.name).group(1))
        partes.append(df)
    return pd.concat(partes, ignore_index=True)
