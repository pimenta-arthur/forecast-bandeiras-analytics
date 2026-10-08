# Metodologia — Previsão de bandeiras tarifárias

Documento vivo: registra o raciocínio, as escolhas feitas e as questões em aberto.
Cada decisão entra no **Registro de decisões** com data, contexto e status.
Nada aqui é verdade estabelecida até ser verificado com dados ou com a regra oficial.

---

## 1. Objetivo

Prever a bandeira tarifária mensal (verde, amarela, vermelha P1, vermelha P2) para os meses
futuros, de M+1 até **no mínimo M+6**. O horizonte final depende do desempenho no backtest.

A saída é organizada em cenários: **limite inferior (LI)**, **esperado** e **limite superior (LS)**.
A saída principal é a **probabilidade de cada cor** em cada mês (D025).

## 2. Abordagem geral

Em vez de aprender a cor da bandeira diretamente do histórico (poucas observações e regras que
mudaram), a ideia é **prever os insumos da regra e aplicar a regra**:

```
ENA (prevista/cenários) ─┐
Carga mensal ────────────┼─► Geração hidráulica (MRE) ─► GSF ─┐
Demais fontes (?) ───────┘                                    ├─► Ábaco ─► Bandeira
                                                    PLD ──────┘     (+ GFOM no regime C)
```

1. **Etapa 1 (foco atual):** estimar o GSF. O ábaco dá a faixa de bandeiras possíveis para aquele GSF.
2. **Etapa 2:** incorporar o PLD para escolher a bandeira dentro da faixa.
3. **Etapa 3:** no regime C, considerar o acionamento por GFOM (ver seção 3).

## 3. Regimes de acionamento da bandeira (2021 em diante)

Legenda:

- **A:** ábaco GSF × PLD (GSF flat, metodologia de jun/2019)
- **E:** Bandeira Escassez Hídrica (regime excepcional da CREG, fora do ábaco)
- **C:** ábaco + acionamento composto (tabela complementar para despacho fora da ordem de mérito, REH 3.306/2024)

| Ano  | Jan | Fev | Mar | Abr  | Mai | Jun | Jul | Ago | Set | Out | Nov | Dez |
|------|-----|-----|-----|------|-----|-----|-----|-----|-----|-----|-----|-----|
| 2021 | A   | A   | A   | A    | A   | A   | A   | A   | E   | E   | E   | E   |
| 2022 | E   | E   | E   | E/A* | A   | A   | A   | A   | A   | A   | A   | A   |
| 2023 | A   | A   | A   | A    | A   | A   | A   | A   | A   | A   | A   | A   |
| 2024 | A   | A   | A   | C    | C   | C   | C   | C   | C   | C   | C   | C   |
| 2025 | C   | C   | C   | C    | C   | C   | C   | C   | C   | C   | C   | C   |
| 2026 | C   | C   | C   | C    | C   | C   | C   | C   | C   | C   |     |     |

\* Abril/2022 é um mês misto: a escassez hídrica valeu até o dia 15; a partir do dia 16 a bandeira voltou a sair do ábaco.

Períodos:

- **Jan–ago/2021 (A):** ábaco normal, em plena crise hídrica.
- **Set/2021–15/abr/2022 (E):** patamar excepcional determinado pela CREG, com fim antecipado em 16/04/2022.
- **Mai/2022–mar/2024 (A):** ábaco normal.
- **Abr/2024 em diante (C):** o ábaco continua sendo a base, mas o GFOM pode subir a cor. Sem GFOM, a bandeira não muda.

### 3.1 Como a bandeira é calculada (fonte: InfoBandeira CCEE nº 102, out/2026)

Conferido reproduzindo os números dos boletins de jan a out/2026: a regra acerta **10 de 10** cores.

**Momento da decisão:** a ANEEL divulga a cor por volta do dia 25 do mês anterior, com base nas
**projeções do PMO (DECOMP revisão 0)** para o mês, e não em valores realizados.

**GSF_band = GH_band / GF_band** (arredondado para 2 casas decimais):

| Componente | Como é obtido | Out/2026 |
|---|---|---|
| GH ONS | Geração hidráulica total prevista pelo DECOMP rv0 do PMO (já inclui o efeito da térmica por segurança energética) | 46.288 MWmed |
| − ANDE + consumo interno de Itaipu | Entrada do NEWAVE (`c_adic.dat`) | 3.445 |
| × (1 − 1,283%) × (1 − 2,454%) | Perdas bruta→conexão e conexão→centro de gravidade (fatores fixos, média do ano anterior) | 41.255 |
| + PCH/CGH × 61,153% × (1 − 0,063%) | Parcela das PCH/CGH que participa do MRE | 1.923 |
| **GH_band** | | **43.178** |
| GF sazonalizada → "flat" | GF_flat = GF_sazo × 744 / (proporção_sazo × 8760); proporção de out/26 = 0,0898 | 58.422 → 55.263 |
| − perdas e indisponibilidade | Histórico de 12 meses (~4,2%) | |
| **GF_band** | | **52.929** |
| **GSF_band** | 43.178 / 52.929 | **0,82** |

> ⚠️ **Fontes diferentes:** todas as variáveis do boletim vêm do `sumario.rv0` do **PMO do ONS**, **exceto o PLD gatilho**,
> que vem do **deck do DECOMP da CCEE usado no cálculo do PLD** (arquivo `cmdeco.rv0`). O CMO do PMO do ONS **não é** o PLD
> gatilho e não deve ser usado como se fosse. Ex.: out/2026, CMO do SE no `sumario.rv0` ≈ R$ 42–46/MWh; PLD gatilho = R$ 90,19/MWh.

**PLD gatilho:** PLD médio do mês (custo marginal do DECOMP **da CCEE**, 1ª semana + expectativa das demais,
limitado ao PLD mínimo/máximo), ponderado pela carga de cada submercado. Out/2026: R$ 90,19/MWh.

**Ábaco:** os limites de PLD de cada cor são `LimPat / (1 − GSF_band)`, limitados ao PLD mínimo e máximo.
Equivalente: a cor depende só do índice **X = PLD_gatilho × (1 − GSF_band)**. Constantes iguais em todos os boletins
de 2026 e **confirmadas no Anexo I da REH 3.306/2024** (`docs/referencias/`). O Anexo I tabela os limites para GSF
de 0,60 a 0,99 com o PLD mín/máx de 2024 (R$ 61,07 / R$ 716,80); com os valores de cada ano, vale a fórmula. GSF ≥ 1,00 é sempre verde.

| Cor | Faixa de X (R$/MWh) |
|---|---|
| Verde | X ≤ 27,48 |
| Amarela | 27,48 < X ≤ 68,99 |
| Vermelha 1 | 68,99 < X ≤ 95,05 |
| Vermelha 2 | X > 95,05 |

Out/2026: X = 90,19 × 0,18 = 16,2, logo **Verde**. Com GSF 0,82, a cor só passaria a amarela com PLD > R$ 152,7.

Consequências práticas (com PLD entre o mínimo de R$ 57,31 e o máximo de R$ 758,27):

- GSF ≥ 0,96: verde qualquer que seja o PLD.
- GSF ≥ 0,91: no máximo amarela. GSF ≥ 0,875: vermelha 2 impossível.
- Abaixo disso, todas as cores são possíveis e o PLD decide.

**GFOM (regime C, Anexo II da REH 3.306/2024):** só se aplica quando o CMSE determina despacho térmico fora da
ordem de mérito. Nesse caso, a cor final depende da cor original e do **despacho térmico total** (MWmed):

| Cor original | Despacho térmico total (MWmed) | Cor final |
|---|---|---|
| Verde | ≤ 6.962 | Verde |
| Verde | 6.962 a 11.362 | Amarela |
| Verde | 11.362 a 14.262 | Vermelha 1 |
| Verde | 14.262 a 16.562 | Vermelha 2 |
| Amarela | ≤ 9.262 | Amarela |
| Amarela | 9.262 a 12.162 | Vermelha 1 |
| Amarela | 12.162 a 16.562 | Vermelha 2 |
| Vermelha 1 | ≤ 11.462 | Vermelha 1 |
| Vermelha 1 | 11.462 a 14.262 | Vermelha 2 |
| Vermelha 2 | ≤ 11.762 | Vermelha 2 |

Em 2026 (jan–out) não houve GFOM. A Tabela 2 dos boletins está com células corrompidas; a fonte é o Anexo II.

**Inconsistência a verificar:** a Tabela 16 usa sempre R$ 785,27 como PLD máximo, mas a Tabela 15 de alguns
boletins (jun, jul, out) traz R$ 758,27. Provável erro de digitação; não afeta a cor.

### 3.2 Validação em 2026

| Mês | GH_band | GF_band | GSF | PLD gatilho | X | Cor publicada | Cor pela regra |
|---|---|---|---|---|---|---|---|
| jan | 50.469 | 52.985 | 0,95 | 183,05 | 9,2 | Verde | Verde |
| fev | 53.196 | 52.965 | 1,00 | 354,65 | 0,0 | Verde | Verde |
| mar | 54.397 | 52.859 | 1,03 | 427,08 | 0,0 | Verde | Verde |
| abr | 51.385 | 52.806 | 0,97 | 258,01 | 7,7 | Verde | Verde |
| mai | 42.280 | 52.851 | 0,80 | 237,58 | 47,5 | Amarela | Amarela |
| jun | 37.478 | 52.888 | 0,71 | 222,92 | 64,6 | Amarela | Amarela |
| jul | 37.226 | 52.899 | 0,70 | 171,48 | 51,4 | Amarela | Amarela |
| ago | 37.885 | 52.911 | 0,72 | 128,67 | 36,0 | Amarela | Amarela |
| set | 40.251 | 52.869 | 0,76 | 163,44 | 39,2 | Amarela | Amarela |
| out | 43.178 | 52.929 | 0,82 | 90,19 | 16,2 | Verde | Verde |

Observações:

- **GF_band é praticamente constante** (52,8 a 53,0 mil MWmed). Toda a variação do GSF vem do GH_band (37 a 54 mil).
- **Período úmido (jan–abr):** GSF ≥ 0,95 e bandeira verde mesmo com PLD alto (R$ 355 em fev, R$ 427 em mar). O GSF decide sozinho.
- **Período seco (mai–set):** GSF entre 0,70 e 0,80; aí é o PLD que separa verde, amarela e vermelha. Junho ficou perto da vermelha 1 (X = 64,6 contra limite de 69).


### 3.3 Reprodução do GH_band a partir do `sumario.rv0` (DECOMP rv0)

Conferido com out/2026: o GSF é reproduzido **só com o `sumario.rv0`** e as horas por patamar.

| Variável do boletim | Bloco do `sumario.rv0` | Out/2026 calculado | Boletim |
|---|---|---|---|
| GH ONS | `GERACAO HIDRAULICA (MWmed) PARA O PATAMAR 1/2/3`, linha `Totais` (inclui Itaipu 50 e 60 Hz) | 46.287 | 46.288 |
| ANDE + consumo interno de Itaipu | `GERACAO HIDRAULICA EM ITAIPU`, linhas `Ande` (uma por patamar) | 3.444,5 | 3.445 |
| PCH/CGH por subsistema | `PEQUENAS USINAS : DESPACHO NO PATAMAR 1/2/3`, linhas `*_PCH` (sem as `gd`) | 3.145 | 3.146 |
| GH_band | Fatores da seção 3.1 | 43.178 | 43.178 |
| GSF_band | GH_band / GF_band | 0,8158 → 0,82 | 0,82 |

**Média mensal:** cada bloco traz valores por semana operativa (Sem_01 a Sem_06) e patamar. A média do mês é
Σ valor × horas(patamar, semana no mês) / horas do mês. As horas **não estão no `sumario.rv0`**; vêm das planilhas de patamares da
CCEE em `data/raw/patamar/<ano>/` (ver D018). Aproximação sem fonte externa: inferir as durações semanais
por patamar a partir do bloco `DEMANDA BRUTA` (as médias por subsistema dão um sistema de equações) e ratear pelos
dias da semana que caem no mês. Erro em out/2026: +8 MWmed (0,02%), desprezível (D009).

**Implementação:** `load.ler_sumario`, `load.horas_por_semana`, `regra.calcular_gh_band` e `regra.serie_gh_band`.
**Validação jan–out/2026:** nos 10 meses, GH ONS, ANDE, PCH e GH_band ficam a menos de 1 MWmed do publicado e o GSF
arredondado é idêntico em todos. O boletim de maio/2026 (nº 97) cita "fevereiro de 2026" em alguns trechos por erro de digitação; o conteúdo é de maio.
Série salva em `data/processed/gh_band_2026.parquet`.
Os fatores da CCEE (Tabela 3) mudam no ano: jan–fev/2026 usaram a média de 2024 e, de março em diante, a média de 2025.
Ficam em `regra.FATORES`; para outros anos, cadastrar a partir dos boletins.

**Semanas:** a Sem_01 começa no sábado anterior ao dia 1 (em out/2026, só 48 h no mês) e a última termina depois
do fim do mês (24 h). O relatório de EAR por cenário também traz uma coluna `Mes_02` (mês seguinte).

**Outras variáveis no mesmo arquivo** (mesmo conjunto de informação usado pelo ONS no PMO), úteis na análise exploratória:

- `ENERGIA ARMAZENADA NOS SUBSISTEMAS (% EARM_MAXIMA)`: EAR inicial e por semana.
- `DEMANDA BRUTA (MWmed) POR SUBSISTEMA E POR PATAMAR`: carga prevista.
- `GERACAO TERMICA NOS SUSBSISTEMAS (MWmed) p/ CGC` e por usina: despacho térmico.
- `PEQUENAS USINAS`: PCH, PCT e geração distribuída (`*gd`, inclusive UFV).
- `CUSTO MARGINAL DE OPERACAO`: CMO do PMO do ONS. **Não é o PLD gatilho** (ver aviso na seção 3.1); não usar como PLD.

**Não encontrado no `sumario.rv0`:** geração eólica e solar centralizadas. No balanço de out/2026 (Sem_02, patamar 1),
demanda de 91.169 contra 76.680 de hidráulica + térmica + pequenas usinas: faltam ~14,5 GW. **Resolvido:** são a eólica e a
solar centralizadas do `renovaveis.csv` (seção 3.4); o pouco que sobra é bombeamento (seção 3.6).

### 3.4 Balanço do DECOMP e renováveis centralizadas (out/2026)

A eólica e a solar **centralizadas** não aparecem no `sumario.rv0`; o ONS as declara em um arquivo de entrada
separado, o `renovaveis.csv`. O `sumario.rv0` só traz a geração **distribuída** (MMGD, linhas `*gd` de `PEQUENAS USINAS`).

**Estrutura do `renovaveis.csv`:** 8 parques equivalentes (códigos 1–4 eólica e 11–14 fotovoltaica, para SE, S, NE e N),
todos "centralizado". Registro de geração `PEE-GER-PER-PAT-CEN` por período, patamar e cenário. Os períodos 1 a 6 são as
semanas operativas do mês, com cenário único; o período 7 é o **mês seguinte**, com 228 cenários, e não entra no mês em estudo.
O `oper_parque_eolico.csv` (saída do modelo) traz os mesmos valores em out/2026, sem corte de geração.

**Balanço de out/2026** (média do mês ponderada pelas horas, MWmed):

| Componente | Fonte | MWmed |
|---|---|---|
| Demanda bruta | `sumario.rv0` | 85.286 |
| Hidráulica para o SIN (46.287 − ANDE 3.444) | `sumario.rv0` | 42.843 |
| Térmica | `sumario.rv0` | 5.763 |
| Pequenas usinas (PCH, PCT e MMGD; MMGD = 9.190) | `sumario.rv0` | 17.120 |
| Eólica centralizada (NE = 13.915) | `renovaveis.csv` | 14.789 |
| Solar centralizada | `renovaveis.csv` | 4.837 |
| **Diferença** = consumo de bombeamento (`relato.rv0`, ver 3.6) | | **−65,9** |

O balanço fecha também por patamar (renováveis vs. resíduo: pesado 16.018 vs. 16.006; médio 21.086 vs. 21.023; leve 19.674 vs. 19.585).
A diferença é o **consumo de bombeamento** das usinas elevatórias (`Cbomba` no `relato.rv0`, 65,9 MWmed): com ele, o balanço fecha em −0,08 MWmed.

Implementação: `load.ler_renovaveis(ano, mes)`.

### 3.5 Memorial de cálculo (vale para todos os meses) — exemplo com out/2026

Passo a passo para calcular o GSF_band e o balanço de um mês a partir dos arquivos brutos. Os números são os reais
de out/2026; entre parênteses, o valor publicado no boletim da CCEE. Todas as grandezas são **previstas** pelo ONS no
PMO do mês (DECOMP rv0), não realizadas.

**Arquivos do mês** (`data/raw/ons_decomp/<ano>/<ano>_<mes>/`): `sumario.rv0`, `renovaveis.csv` e `ena.pdf`;
mais as horas por patamar (`data/raw/patamar/<ano>/AAC001`) e o boletim InfoBandeira (conferência e PLD gatilho).

**Passo 1 — Horas por patamar e semana operativa no mês.** Semana operativa de sábado a sexta; contam só as horas
dentro do mês (`load.horas_por_semana`). Out/2026 (744 h):

| Patamar | Sem 1 | Sem 2 | Sem 3 | Sem 4 | Sem 5 | Sem 6 | Total |
|---|---|---|---|---|---|---|---|
| Pesado (1) | 12 | 30 | 24 | 30 | 30 | 0 | 126 |
| Médio (2) | 22 | 69 | 65 | 69 | 69 | 7 | 301 |
| Leve (3) | 14 | 69 | 79 | 69 | 69 | 17 | 317 |

**Passo 2 — Média mensal de qualquer grandeza.** Os arquivos do DECOMP trazem valores por patamar *p* e semana *s*:

> média do mês = Σ_p Σ_s valor(p, s) × horas(p, s) / horas do mês

Exemplo, geração hidráulica total (linha `Totais` dos blocos `GERACAO HIDRAULICA ... PATAMAR p`):

| Patamar | Sem 1 | Sem 2 | Sem 3 | Sem 4 | Sem 5 | Sem 6 |
|---|---|---|---|---|---|---|
| Pesado | 59.461,7 | 60.671,0 | 61.414,7 | 64.851,0 | 64.928,4 | 64.771,2 |
| Médio | 46.871,3 | 46.200,7 | 46.802,5 | 50.199,9 | 49.413,0 | 50.053,6 |
| Leve | 35.121,3 | 35.309,0 | 36.799,7 | 39.991,8 | 40.375,9 | 39.488,9 |

Σ valor × horas = 34.437.728 MWh → **GH ONS = 34.437.728 / 744 = 46.287,3 MWmed** (46.288).

**Passo 3 — GH_band** (`regra.calcular_gh_band`; fatores da CCEE vigentes em `regra.FATORES`):

| Etapa | Conta | Out/2026 |
|---|---|---|
| GH ONS | Passo 2 | 46.287,3 (46.288) |
| − ANDE + consumo interno de Itaipu | Linhas `Ande` do bloco de Itaipu, média do mês | 3.444,5 (3.445) |
| = GH bruta | | 42.842,8 (42.843) |
| × (1 − 1,283%) × (1 − 2,454%) | Perdas bruta→conexão e conexão→centro de gravidade | 41.255,2 (41.255) |
| PCH/CGH | Linhas `*_PCH` (sem `gd`) de `PEQUENAS USINAS`: SE 1.405 + S 1.566 + NE 64 + N 111 | 3.145,3 (3.146) |
| × 61,153% × (1 − 0,063%) | Parcela das PCH no MRE e perda até o centro de gravidade | 1.922,3 (1.923) |
| **= GH_band** | 41.255,2 + 1.922,3 | **43.177,5 (43.178)** |

**Passo 4 — GF_band** (do boletim; quase constante, ~52,8–53,0 mil MWmed em 2026): GF sazonalizada do SIN 58.422 →
"flat" = 58.422 × 744 / (0,089787 × 8.760) = 55.263 → menos perdas e indisponibilidade (~4,2%) = **52.929**.

**Passo 5 — GSF_band** = 43.177,5 / 52.929 = 0,8158 → arredondado em 2 casas = **0,82** (0,82).

**Passo 6 — Cor (etapa 2).** PLD gatilho do deck da CCEE (R$ 90,19; **não** é o CMO do `sumario.rv0`).
X = PLD × (1 − GSF) = 90,19 × 0,18 = 16,2 ≤ 27,48 → **Verde** (Verde). Sem GFOM no mês.

**Passo 7 — Balanço do DECOMP** (`features.balanco_mes`). Fecha a identidade
**carga líquida = hidráulica (SIN) + eólica + solar + térmica + PCH + PCT + resíduo**:

| Termo | Fonte | Out/2026 (MWmed) |
|---|---|---|
| Carga bruta | `sumario.rv0`, bloco `DEMANDA BRUTA` (soma dos subsistemas) | 85.286,2 |
| − MMGD | `sumario.rv0`, linhas `*gd` de `PEQUENAS USINAS` (UFV, PCH, PCT e EOL distribuídas) | 9.190,0 |
| **= Carga líquida** | | **76.096,2** |
| − Eólica centralizada | `renovaveis.csv`, parques 1–4, períodos do mês | 14.789,5 |
| − Solar centralizada | `renovaveis.csv`, parques 11–14, períodos do mês | 4.836,9 |
| − Térmica (inclui nuclear e inflexível) | `sumario.rv0`, linha `Totais` de `GERACAO TERMICA` (nuclear = linhas ANGRA: 1.350) | 5.762,5 |
| − PCH | `sumario.rv0`, linhas `*_PCH` | 3.145,3 |
| − PCT (pequenas térmicas: biomassa, cogeração) | `sumario.rv0`, linhas `*_PCT` | 4.785,1 |
| = Hidráulica para o SIN esperada | | 42.776,9 |
| Hidráulica para o SIN do DECOMP (GH ONS − ANDE) | Passo 3 | 42.842,8 |
| **Resíduo** = −consumo de bombeamento (`Cbomba`, `relato.rv0`: 65,9) | | **−65,9 → fecha em −0,08** |

Variável derivada usada na análise: **carga residual** = carga líquida − eólica − solar − PCH − PCT − nuclear = 47.189,3,
isto é, o que sobra para hidráulica + térmica não nuclear (hidráulica para o SIN ≈ carga residual − térmica sem nuclear).

**Passo 7b — Térmica inflexível × mérito** (`relato.rv0`, `load.ler_relato_termicas`). Para cada usina, semana e patamar:
inflexível = min(geração, GTmin); mérito = geração − inflexível. Out/2026: térmica 5.762,5 = inflexível 5.278,3
(nuclear 1.350,0 + demais 3.928,3) + mérito 484,2 MWmed.

**Passo 8 — ENA e armazenamento** (variáveis explicativas). ENA prevista do mês por subsistema, em MWmed e % MLT
(`ena.pdf`, Tabela 6, coluna "Previsão Mensal Inicial"): SE 24.870 (105%), S 26.506 (193%), NE 1.929 (61%), N 1.020 (43%);
SIN 54.325 (126,5% MLT, ponderado pela MLT). EAR inicial (`sumario.rv0`, `ENERGIA ARMAZENADA NOS SUBSISTEMAS`):
SE 57,4%, S 82,9%, NE 69,6%, N 74,3%; SIN 62,4% (ponderado pela EARmax dos REEs).

### 3.6 O `relato.rv0` (DECOMP rv0) e a separação da térmica

O `relato.rv0` é o relatório completo do DECOMP (5,5 MB/mês; o `sumario.rv0` é um resumo dele). Blocos usados:

| Bloco | Conteúdo | Uso |
|---|---|---|
| `RELATORIO  DO  BALANCO  ENERGETICO` | Por semana, subsistema e patamar: `Mercado` (carga bruta), `PQUsi` (pequenas usinas, inclui MMGD), `Cbomba` (bombeamento), `Ghid` (no SE inclui Itaipu 50 Hz), `Gter`, `Geol` (eólica + solar centralizadas), intercâmbios, `Itaipu50`, `Itaipu60`; EAR e ENA semanais | Balanço; GH ONS = Σ `Ghid` + `Itaipu60` |
| `RELATORIO  DA  OPERACAO  TERMICA E CONTRATOS` | Geração por usina, subsistema e patamar, com flag `I` (gerando no GTmin) ou `S` (no GTmax); sem flag = entre os dois | Térmica por usina |
| `Relatorio  dos  Dados  de  Usinas  Termicas` | GTmin, GTmax e custo por usina, estágio e patamar | Inflexibilidade |
| `Relatorio dos Dados de Pequenas Usinas` | PCH, PCT e MMGD (`*gd`) por subsistema e estágio | Igual ao `sumario.rv0` |
| `Relatorio de eco das informacoes de ITAIPU` | ANDE por período e patamar | Igual ao `sumario.rv0` |

**Equivalência com `sumario.rv0` + `renovaveis.csv` (out/2026, média do mês):** carga bruta 85.286,2, pequenas usinas
17.120,5, térmica 5.762,5, eólica + solar 19.626,4 e GH ONS 46.287,3 — **diferença zero** em todas.

**Flags da operação térmica** (verificado contra o cadastro em out/2026): toda geração com `I` é igual ao GTmin e toda com
`S` é igual ao GTmax da usina; nenhuma usina gera abaixo do GTmin. A legenda não está no arquivo; a interpretação vem dessa
verificação. **Somar só as linhas com `I` subestima a inflexibilidade** (4.938,9 em out/2026), porque usinas acima do mínimo
(ex.: UTE MAUA 3, GTmin 264, gerando 426) não levam flag. Por isso a parcela inflexível é min(geração, GTmin).

**O que só cada arquivo tem:**
- `relato.rv0`: bombeamento, GTmin/GTmax e flags (separação inflexível × mérito), intercâmbios.
- `renovaveis.csv`: eólica e solar **separadas** (o `relato` traz só `Geol`, a soma das duas, por subsistema).
- `sumario.rv0`: nada exclusivo; tudo o que usamos dele também está no `relato`.

**Origem da nuclear (antes do `relato`):** linhas `ANGRA 1` e `ANGRA 2` do bloco `GERACAO TERMICA` do `sumario.rv0`; o `relato` confirma (1.350 MWmed em out/2026).

### 3.7 Histórico jan/2023–out/2026: fonte única `relato.rv0` e transições

Desde esta etapa, todo o cálculo usa o `relato.rv0` (D022). O `sumario.rv0` só existe em 2026 e não é mais lido no cálculo.
O `renovaveis.csv` só é usado para separar eólica e solar a partir de out/2025.

**Transições no `relato.rv0`** (tratadas na leitura, `load.ler_relato_*`):

| Período | Eólica e solar centralizadas | MMGD | Balanço energético |
|---|---|---|---|
| jan–abr/2023 | Pequenas usinas, linhas `*_EOL` e `*_UFV` (separadas) | Não representada (carga já vinha líquida da MMGD) | Coluna de pequenas usinas chamada `Bacia`; sem `Geol` |
| mai/2023–set/2025 | Pequenas usinas, linhas `*_EOL` e `*_UFV` | Linhas `*gd` | Idem (`Bacia`/`PQUsi`; sem `Geol`) |
| out/2025 em diante | `Geol` do balanço (eólica + solar somadas); separação no `renovaveis.csv` (bate com o `Geol` com diferença zero em out–dez/2025) | Linhas `*gd` | `PQUsi` e `Geol` |

A leitura do balanço localiza as colunas pelo cabeçalho de cada tabela. A coluna `GterAT` (térmica antecipada: GNL despachado
por mérito com antecedência) **não** aparece no bloco por usina e entra na térmica total; com ela o balanço fecha.

**Validação no histórico (46 meses):**

- Balanço: `carga líquida + bombeamento = hidráulica (SIN) + renováveis + térmica + PCH + PCT` fecha com |resíduo| ≤ 0,13 MWmed em todos os meses.
- GSF_band calculado = publicado em **46/46** meses; GH_band a menos de 1 MWmed em 42 meses.
- Cor pela regra = cor publicada em **39/39** meses (nos outros 7 boletins a Tabela 17 é imagem, sem texto).
- Desvios de GH_band > 5 MWmed: **jun/2025 (+256)** = GFOM do mês (265 MWmed): o GH enviado pelo ONS à CCEE já desconta a
  térmica por segurança energética; **abr/2025 (−444)** sem explicação (Q17); out/2023 (+7) e nov/2024 (+10) pequenos.
- Fatores de perda da CCEE (Tabela 3) cadastrados em `regra.FATORES` a partir dos boletins: vigências a partir de jan/2023,
  mar/2023, abr/2024, mar/2025 e mar/2026.

---

## 4. Registro de decisões

| ID   | Data       | Decisão | Motivo | Status |
|------|------------|---------|--------|--------|
| D001 | 2026-10-04 | Granularidade mensal; horizonte mínimo de M+6, a estender conforme o backtest | A bandeira é mensal; seis meses é o mínimo útil | Decidido |
| D002 | 2026-10-04 | Prever os insumos da regra (GSF, depois PLD) e aplicar o ábaco, em vez de classificar a cor diretamente | Histórico curto e regras que mudaram; a regra é conhecida | Decidido (validar com a reconstrução do histórico) |
| D003 | 2026-10-04 | Começar pelo GSF; o PLD fica para a etapa 2 | O GSF define a faixa do ábaco; em 2026 decidiu sozinho a cor dos meses úmidos | Decidido (no período seco o PLD é necessário: ver D010) |
| D004 | 2026-10-04 | Saída em cenários LI / esperado / LS ("base" e "esperado" são o mesmo cenário; usar o nome "esperado") | Incorporar a incerteza hidrológica | Decidido (definir como gerar os cenários) |
| D005 | 2026-10-04 | Meses do regime E (set/2021–abr/2022) saem da base ou recebem uma flag | Não seguiram o ábaco | Proposta (a escolher: excluir ou marcar) |
| D006 | 2026-10-04 | Regimes A e C juntos, com dummy de regime | Em C a cor só difere de A quando há GFOM | Proposta (ver Q4) |
| D007 | 2026-10-04 | Backtest ao longo de 2026, comparando com as bandeiras realizadas; o período de treino será definido depois da análise exploratória | 2026 é o período mais recente e todo no regime vigente (C) | Decidido |
| D008 | 2026-10-04 | Geração hidráulica estimada a partir de armazenamento, ENA, carga e demais fontes. No forecast, usar as projeções mensais do NEWAVE (caso base: carga bruta e geração renovável projetada); no histórico, os dados realizados | Combina os caminhos da Q3 e usa projeções já disponíveis | Decidido (validar na análise exploratória) |
| D009 | 2026-10-04 | A estimativa da geração hidráulica e do GSF é uma **aproximação**: não replicar o cálculo oficial em todos os detalhes | Mais complexidade sem ganho relevante de acurácia (experiência prévia); revisar se o backtest mostrar erro sistemático | Decidido |
| D010 | 2026-10-04 | Trabalhar com o índice X = PLD × (1 − GSF) e com o "PLD de virada" (PLD que muda a cor para um dado GSF). Prever GSF e PLD em paralelo, mantendo o GSF como primeiro passo | O ábaco depende do produto dos dois; o GSF sozinho não define a cor | Proposta |
| D011 | 2026-10-04 | Alvo intermediário = GH_band, GF_band, GSF_band e PLD gatilho **publicados nos boletins** (projeções do PMO), não os valores realizados | A ANEEL decide com projeções; o realizado tem erro de previsão que não precisamos modelar | Proposta |
| D012 | 2026-10-04 | Extrair dos PDFs uma tabela mensal (GH ONS, ANDE, PCH, GH_band, GF_sazo, GF_band, GSF, PLD gatilho, PLD mín/máx, GFOM, cor) para servir de gabarito | Base para reconstruir o histórico e para o backtest | Proposta |
| D013 | 2026-10-04 | GF_band tratado como quase determinístico (GF sazonalizada e proporção conhecidas no início do ano; perdas ~4,2%) | Toda a incerteza do GSF está no numerador (GH) | Proposta |
| D014 | 2026-10-04 | GFOM como cenário (0 no esperado; despacho por segurança no LS), não como variável prevista | Depende de decisão discricionária do CMSE | Proposta |
| D015 | 2026-10-04 | Comparar fontes de previsão no backtest em vez de escolher uma a priori: ENA do ECMWF (SEAS5, % da MLT) para a geração hidráulica; curva forward Dcide para o PLD; NEWAVE como referência de comparação; climatologia/persistência como baseline | Incerteza do NEWAVE nos horizontes longos; escolher pelo desempenho | Proposta |
| D016 | 2026-10-04 | Problema dividido em duas etapas. **Etapa 1:** estimar GH_band e chegar ao GSF, sem PLD (nem Dcide, nem CMO do NEWAVE). **Etapa 2:** incorporar o PLD, que entra no backtest da cor | Separar as fontes de incerteza e entender a geração hidráulica primeiro | Decidido |
| D017 | 2026-10-04 | Fonte do alvo GH_band: `sumario.rv0` de cada mês, com ANDE e PCH tirados do próprio sumário (dispensa o `c_adic.dat` do NEWAVE e a planilha de usinas não simuladas). Os boletins servem de conferência | Reproduz o boletim de out/2026 com erro < 0,1% | Decidido |
| D018 | 2026-10-04 | Horas por patamar: usar o arquivo **horário** `AAC001 - Patamares <ano>.xlsx` e calcular as semanas operativas (sábado a sexta) e as horas por patamar no código. O `AAC002` (consolidação semanal, uma aba por mês) fica só como conferência | Uma tabela só, fácil de agregar; reproduz o `AAC002` em todos os meses de 2025 e 2026 e a Tabela 11 do boletim. O layout do `AAC001` mudou entre 2025 e 2026: a leitura detecta as colunas pelo nome | Decidido |
| D019 | 2026-10-05 | Renováveis centralizadas do `renovaveis.csv` de cada mês (períodos das semanas do mês, cenário 1); o `oper_parque_eolico.csv` não é necessário | Fecha o balanço de out/2026 com erro de 0,08% | Decidido |
| D020 | 2026-10-05 | Carga para o forecast: a fonte de projeção tem carga bruta e líquida (sem MMGD) por submercado; usar a **líquida**, com a mesma definição no histórico (demanda bruta do `sumario.rv0` − MMGD das linhas `*gd`) | Evita prever a MMGD separadamente; as duas são equivalentes se a definição for a mesma | Proposta (conferir a equivalência quando a projeção chegar) |
| D021 | 2026-10-05 | Hipótese de trabalho para a etapa 1: GH_band ≈ f(carga residual − térmica sem nuclear). Carga, renováveis, PCH, PCT e nuclear vêm das projeções de entrada; a térmica sem nuclear é a parcela a modelar com a hidrologia (ENA do ECMWF, EAR) | Carga residual explica o GH_band com r = 0,99 em 2026; a ENA só deve agir via despacho térmico | Proposta (validar com histórico que tenha anos secos, ex.: 2021) |
| D023 | 2026-10-05 | Na etapa 1, modelar a **térmica total sem nuclear** (não só o mérito) como a parcela que responde à hidrologia | Mérito e inflexível se compensam (GNL antecipado entra como inflexível); o resíduo de GH acompanha o total (r = −0,94) | Proposta |
| D024 | 2026-10-05 | Caminho do modelo da etapa 1: GH_band = f(carga residual, térmica sem nuclear), com a carga residual vinda das projeções e a **térmica sem nuclear** modelada com a hidrologia — armazenamento (EAR) como variável principal, ENA prevista (ECMWF, % MLT) como secundária — e com os despachos já comprometidos (GNL antecipado) | Histórico de 46 meses: identidade com R² 0,999; sem sazonalidade, a térmica explica o GH (r = −0,87) e responde mais à EAR (−0,70) que à ENA (−0,38) | Proposta |
| D025 | 2026-10-06 | **Saída principal: probabilidade de cada cor por mês** (ex.: "ago: 70% amarela, 25% vermelha 1, 5% verde"), calculada sobre os cenários (ENA do ECMWF × cenários do NEWAVE, com GSF e preço de cada cenário). Os cenários LI / esperado / LS do GSF e do preço continuam como apoio | Incorpora juntas a incerteza do GSF e do preço; mais útil para o usuário do que uma cor única | Decidido |
| D026 | 2026-10-06 | Configuração de trabalho do teste do NEWAVE: **GSF** com os 10 cenários de ENA do SIN mais próxima no mês; **preço** com os 25 cenários de trajetória de ENA do SIN mais próxima (mais peso nos meses recentes), PLD de cada cenário pela fórmula do gatilho (4 submercados). **Sem** termo de armazenamento futuro: na data da previsão só se conhece o armazenamento atual (já embutido no deck); o armazenamento futuro entra implicitamente pela trajetória de ENA de cada série | Melhor configuração realizável no estresse (seção 8.4); a seção 8.5 usa o armazenamento futuro real (gabarito) e é limite superior | Proposta (revalidar com mais decks e com o ECMWF) |
| D027 | 2026-10-06 | Probabilidade de cada cor pelo **erro histórico da média**: X médio das 25 séries como referência e X real ~ Normal(X médio, σ do erro histórico); cor exibida = cor da média | Melhor Brier (0,235 × 0,33) e maior probabilidade da cor real (76% × 66–69%) nos 3 decks; sem a circularidade de pesar séries pela distância à média (seção 8.7) | **Suspensa: vazamento de dados** — o σ foi estimado com erros de meses posteriores à data do deck. Refazer com σ estimado só com previsões já realizadas na data (decks de anos anteriores) |
| D028 | 2026-10-07 | Horizonte de avaliação do backtest: **M+1 a M+7** | 7 meses é o alcance da previsão sazonal do ECMWF que vai alimentar a ENA de referência | Decidido |
| D029 | 2026-10-07 | Escolha das séries: **k = 15** e **peso igual em toda a trajetória de ENA** (substitui k = 25 e meia-vida 2 da D026). Padrão em `backtest.K_PADRAO` e `backtest.MEIA_VIDA_PADRAO` | Escolhidos só com os alvos de 2025 e confirmados em 2026 (seções 8.9 e 8.10); robusto ao incluir 2026 | Decidido |
| D030 | 2026-10-07 | ENA prevista do ECMWF: **centro = média da abordagem `precip`**; **incerteza = 51 membros recentrados na média `precip`** (dispersão da abordagem `vaz`). Percentis `precip` e média `vaz` descartados | Avaliação da seção 9.1: média `precip` com erro de 8–13% em todos os leads; membros recentrados com faixa calibrada | Proposta (testar no backtest) |
| D031 | 2026-10-07 | Pareamento ECMWF × deck: o deck do mês M usa a **rodada do ECMWF do mesmo mês M** (o deck pode ser segurado até a rodada sair, ~dia 5). Para o próprio mês M, a ENA de referência é a do PMO (`ena.pdf`, já publicada); de M+1 em diante, a do ECMWF. Com isso o horizonte coberto pelo ECMWF é **M+1 a M+6** | Simplifica os testes e é operacionalmente viável; nenhuma informação posterior à data da previsão (~dia 5 de M) | Decidido |
| D032 | 2026-10-08 | Patamares de carga de um ano ainda não publicado (ex.: 2027 visto do deck de set/2026): usar as horas por patamar do **mesmo mês do ano anterior** (`backtest.horas_patamar`, com aviso) | Só a proporção de horas por patamar entra no PLD gatilho e ela muda pouco de um ano para o outro; permite projetar até M+6 na virada do ano | Decidido (aproximação; trocar pelo arquivo oficial quando a CCEE publicar) |
| D022 | 2026-10-05 | Fonte única do DECOMP: `relato.rv0` (balanço, GH, ANDE, PCH/PCT/MMGD, térmica por usina, EAR). `renovaveis.csv` só para separar eólica e solar a partir de out/2025. `sumario.rv0` não é mais necessário | O `relato` reproduz o `sumario` com diferença zero e tem a separação da térmica; cobre todo o histórico | Decidido |

## 5. Questões em aberto

- ~~**Q1 — Insumo projetado ou realizado?**~~ Resolvida: projetado (DECOMP rv0 do PMO), ver seção 3.1 e D011.
- ~~**Q2 — O que é o "GSF flat"?**~~ Resolvida: GF sazonalizada convertida para média anual, menos perdas e indisponibilidade (seção 3.1).
- **Q3 — Geração hidráulica:** ~~via ENA/EAR ou via resíduo da carga?~~ Encaminhada pela D008 (usar as duas informações). Falta ver na análise exploratória quais variáveis de fato explicam a geração hidráulica.
- **Q4 — GFOM no regime C:** uma dummy de regime não basta, porque a cor só muda quando há GFOM. Vamos precisar de dados de despacho fora da ordem de mérito e, para prever, de alguma estimativa dele. Como tratar?
- **Q5 — Cenários:** como gerar LI/base/LS? Hipótese: percentis históricos da ENA (% da MLT).
- ~~**Q6 — "Base" e "esperado":**~~ Resolvida: são o mesmo cenário (ver D004).
- **Q7 — Backtest sem vazamento:** usar apenas informação disponível na data da previsão (não a ENA realizada). Temos as projeções do NEWAVE **por data de emissão** (os decks de cada mês de 2026), ou só a versão mais recente? Sem as versões históricas, o backtest de 2026 usaria informação que não existia na época.
- **Q9 — Tamanho do backtest:** 2026 tem cerca de 10 meses realizados, todos no regime C. Avaliar se é suficiente ou se vale estender o backtest para trás (ex.: 2025) para ter mais pontos por horizonte (M+1 a M+6).
- **Q8 — Abril/2022 (misto):** tratar como E, como A ou excluir?
- **Q10 — O que temos do NEWAVE?** Só as entradas (carga, renováveis, ENA) ou também as saídas (geração hidráulica e CMO por mês)? Mesmo que não seja a fonte principal (D015), serve de referência de comparação.
- **Q12 — Histórico para ajustar a relação ENA/carga → GH_band:** 2026 tem só 9 meses. Os boletins existem desde ~2018 (out/2026 é o nº 102); trazer 2019–2025 daria ~80 meses.
- **Q13 — Versões históricas das previsões externas:** para o backtest, precisamos das previsões do ECMWF e da curva Dcide **como estavam na data de cada previsão**. O ECMWF tem hindcasts; a Dcide tem histórico de curvas?
- ~~**Q15 — Definição de carga:**~~ A projeção tem carga bruta e líquida (sem MMGD) por submercado; ver D020.
- ~~**Q16 — Eólica e solar centralizadas:**~~ Resolvida: vêm do `renovaveis.csv`, entrada do DECOMP (ver seção 3.4 e D019).
- **Q17 — Abr/2025:** GH ONS do `relato.rv0` 460 MWmed abaixo do boletim (GSF igual). Investigar (outra revisão do PMO? ajuste do ONS?).
- **Q18 — Trajetória do armazenamento:** a EAR é a principal variável da térmica, mas para M+2 a M+6 ela também precisa ser projetada (balanço de energia com a ENA do ECMWF? EAR projetada pelo NEWAVE/PMO?).
- **Q19 — Viés do NEWAVE no 2º semestre de 2026:** de onde vem (carga, renováveis, térmica, vertimento)? Precisa da térmica, do armazenamento e do vertimento por série e das entradas do deck (carga e renováveis por mês).
- **Q20 — Viés do preço na transição úmido → seco:** o custo marginal do NEWAVE fica muito abaixo do PLD gatilho em fev–mai. Causa (armazenamento inicial baixo? CVaR? DECOMP × NEWAVE)? O casamento pelo armazenamento (8.5) reduz o viés, mas fev–mar seguem abaixo do oficial; testar correção de viés por mês e a curva Dcide.
- **Q21 — Viés do armazenamento das séries do NEWAVE:** o armazenamento real do SE ficou abaixo de ~90% das séries do deck de jan/2026. Se for sistemático (com mais decks), estimar e corrigir na escolha das séries do preço.
- **Q22 — Backtest sem vazamento (auditoria):** (1) σ da probabilidade só com erros já realizados na data do deck (decks de 2023–2025); (2) ANDE, PCH e pesos de carga do mês-alvo devem vir do deck do NEWAVE da data, não do PMO do próprio mês; (3) k = 25, k = 10 e meia-vida de 2 meses foram escolhidos em 2026 e precisam ser validados em outros anos; (4) a ENA de referência é a real (oráculo) até entrar o ECMWF.
- ~~**Q23 — Data de disponibilidade do ECMWF:**~~ Resolvida pela D031 (deck M com a rodada de M). as rodadas são datadas no dia 1 do mês, mas o SEAS5 costuma ser liberado por volta do dia 5. O deck do mês M sai no fim de M−1. Qual rodada estava disponível na data de cada deck? Se for a de M−1, o horizonte coberto a partir do deck vai até M+5, não M+7.
- **Q14 — ENA não vira geração hidráulica diretamente:** a hidráulica do DECOMP é, em grande parte, a carga menos eólica, solar e térmica; a ENA entra pelo despacho térmico e pelo armazenamento. A conversão ENA → GH precisa incluir carga e renováveis (ex.: regressão de GH_band em carga líquida, ENA % MLT e EAR).
- **Q11 — Definição do horizonte:** a cor de M é decidida por volta do dia 25 de M−1. Em 04/10/2026, outubro já é conhecido, então M+1 = novembro. Fixar a data de corte de cada previsão no backtest.

## 6. Dados

| Dado | Fonte provável | Status |
|------|----------------|--------|
| Histórico de bandeiras realizadas | ANEEL | Disponível (a trazer) |
| Regra/ábaco vigente e REH 3.306/2024 (PDF), em `docs/referencias/` | ANEEL | Recebido; constantes do ábaco e tabela de GFOM conferidas |
| Patamares de carga (horário `AAC001` e semanal `AAC002`), em `data/raw/patamar/<ano>/` | CCEE | 2025 e 2026 recebidos e conferidos |
| Deck do DECOMP da CCEE para o PLD (`cmdeco.rv0`) — etapa 2 | CCEE | A trazer na etapa 2 |
| Renováveis centralizadas (`renovaveis.csv`), na pasta mensal do DECOMP | ONS | Out/2025–out/2026 (antes, separadas no `relato`) |
| Relatório completo do DECOMP (`relato.rv0`) e `ena.pdf`, na pasta mensal | ONS | Jan/2023–out/2026 (46 meses); balanço fecha em ±0,13 MWmed em todos |
| Saídas do DECOMP rv0 por mês (`sumario.rv0` e `ena.pdf`), em `data/raw/ons_decomp/<ano>/<ano>_<mes>/` | ONS | Jan–out/2026 recebidos; `sumario.rv0` conferido contra os boletins; `ena.pdf` ainda não lido |
| GSF histórico | Boletins InfoBandeira (CCEE) | A extrair dos PDFs |
| Geração hidráulica do MRE e garantia física | CCEE | Pendente |
| ENA e EAR por subsistema | ONS | Pendente |
| Carga mensal (realizada) | ONS | Disponível (a trazer) |
| Projeções NEWAVE (caso base mensal: carga bruta, renováveis, ENA) | ONS/CCEE | Disponível (a trazer) |
| Geração eólica, solar e térmica (realizada) | ONS | Disponível (a trazer) |
| GFOM (despacho fora da ordem de mérito) | ONS/CCEE | Pendente |
| PLD gatilho histórico | Boletins InfoBandeira (CCEE) | A extrair dos PDFs |
| Memória de cálculo mensal da bandeira (PDF), em `data/raw/ccee_calculo_bandeira/<ano>/` | CCEE | 2026: jan–out completos; 2019–2025 a trazer (Q12) |
| Saídas do NEWAVE por série (`nwlistop`: `ghtot*`, `eafb*`, `cmarg001–004`), em `data/raw/ccee_newave/<ano>/<ano>_<mes>/` | CCEE (deck de preços) | Jan e fev/2026 |
| Previsão sazonal de ENA (% MLT) | ECMWF SEAS5 | A verificar (incluindo hindcasts) |
| Curva forward de PLD | Dcide | A verificar (histórico de curvas) |

## 7. Próximos passos

> **Princípio para o preço (etapa 2):** melhorar o sinal de preço usando **só o que estará disponível na data da previsão**:
> as 2.000 séries do NEWAVE do deck mais recente e a ENA prevista (ECMWF). O armazenamento futuro real não é insumo; testes
> com ele (seção 8.5) servem só como limite superior e diagnóstico.

**Etapa 1 — dados para a análise exploratória da geração hidráulica** (mensal, 2019–2026, SIN e por subsistema quando houver):

- Alvo: GH_ONS, GH_band, GF_band e GSF dos boletins (2019–2025 e maio/2026).
- Carga (definição consistente com a projeção que será usada no forecast; ver Q15).
- Geração eólica, solar e MMGD.
- ENA (MWmed e % MLT) e EAR (% do máximo, início do mês) por subsistema.
- Geração térmica e nuclear: só para entender o balanço, já que não estará disponível no forecast.
- Se existirem: valores **previstos no PMO** de cada mês (carga, ENA, EAR inicial), que são a informação usada pelo DECOMP.

1. **Reconstruir o histórico:** extrair os boletins (D012), aplicar o ábaco ao GSF/PLD publicados e conferir se reproduzimos as bandeiras acionadas nos meses A e C. Se não reproduzirmos, o problema está no entendimento da regra, não na previsão.
2. Análise exploratória: correlação entre armazenamento, ENA, carga, demais fontes e geração hidráulica; depois geração hidráulica → GSF.

## 8. Resultados da análise exploratória

### 8.1 Etapa 1 — geração hidráulica, jan–out/2026 (`notebooks/01_eda.ipynb`)

Base: `data/processed/base_mensal_2026.parquet` (`features.base_mensal`). Gráficos em `reports/figures/01–03`.

1. **Alvo validado:** GH_band a < 1 MWmed do boletim nos 10 meses; GSF e cor idênticos. Balanço fecha com resíduo
   entre −45 e −76 MWmed (< 0,1% da carga) em todos os meses.
2. **A carga residual explica o GH_band quase sozinha (r = 0,99).** A térmica não nuclear variou pouco em 2026
   (3,4 a 6,5 mil MWmed), então hidráulica ≈ carga residual − térmica.
3. **Queda do período seco:** de jan–abr para jun–set a hidráulica para o SIN caiu 13,8 mil MWmed: carga líquida
   −5,9 mil, eólica +5,9 mil (safra de ventos), PCT +2,9 mil (safra de biomassa), nuclear +0,7 mil, PCH −1,2 mil,
   solar −0,5 mil, térmica sem nuclear +0,1 mil.
4. **ENA (SIN) não acrescenta informação além da carga residual em 2026** (`reports/figures/04` e `05`):
   - ENA em MWmed: r = 0,97 com o GH_band, mas r = 0,96 com a carga residual — sazonalidade compartilhada (período úmido =
     muita água, pouco vento, carga alta), não causa.
   - ENA em % MLT: r = −0,48. No 2º semestre a ENA ficou acima da média (103% a 126%) e o GH_band continuou baixo.
   - GH_band ≈ 0,986 × carga residual − 4.216 (desvio do resíduo 926 MWmed). O resíduo não acompanha a ENA (r = 0,17 em
     MWmed, −0,25 em % MLT) nem a EAR (−0,09); ele espelha a térmica sem nuclear (maio: térmica 3,4 mil, resíduo +1,9 mil;
     setembro: térmica 6,5 mil, resíduo −1,4 mil).
   - Térmica (`relato.rv0`, jan–out): a parcela por **mérito** caiu de 3,0–3,8 mil MWmed (jan–jun) para 0,5–1,8 mil
     (jul–out), acompanhando a ENA acima da média (r = −0,87 com a ENA em % MLT): saíram carvão do NE (Pecém, Itaqui) e
     gás (Maranhão IV/V, Baixada Fluminense). A **inflexível sem nuclear** subiu de 2,3 para 5,2 mil: GNL com despacho
     definido antecipadamente (UTE GNA II +1,6 mil, Barcarena) e carvão do Sul (Candiota, Jorge Lacerda, Pampa Sul).
     Uma compensou a outra; para a hidráulica o que importa é a **térmica total sem nuclear** (r = −0,94 com o resíduo
     de GH; mérito sozinho: −0,15).
   - Atenção: "inflexível" no DECOMP mistura inflexibilidade declarada e GNL despachado por mérito com antecedência
     (que entra no mês como GTmin). A separação inflexível × mérito não é uma separação "estrutural × hidrologia".
5. **ENA em MWmed e GH não fecham balanço:** a ENA usa produtividade de referência e conta cada afluência em toda a cascata, sem descontar vertimento e usos consuntivos; não comparar as duas como "água que entra × água que sai".
6. **Limite:** 10 meses de um ano sem estresse hídrico. Correlações aqui descrevem 2026, não servem para estimar o modelo.

### 8.2 Etapa 1 — histórico jan/2023–out/2026 (46 meses)

Base: `data/processed/base_mensal.parquet`. Gráficos em `reports/figures/03–07`.

| Modelo para o GH_band | R² | Desvio do resíduo (MWmed) |
|---|---|---|
| carga residual | 0,901 | 2.320 |
| carga residual + térmica sem nuclear | 0,999 | 187 |
| ENA (MWmed) | 0,813 | 3.196 |
| ENA (% MLT) | 0,068 | 7.129 |
| carga residual + ENA (% MLT) | 0,904 | 2.294 |
| carga residual + ENA (% MLT) + EAR inicial | 0,945 | 1.727 |

1. **GH_band ≈ 1,01 × carga residual − 0,96 × térmica sem nuclear** (quase uma identidade do balanço).
2. **A ENA não explica o GH_band diretamente:** em níveis, a correlação com a ENA em MWmed (0,90) é sazonalidade; em % MLT, 0,26.
3. **A hidrologia age pela térmica.** Anomalias por mês do ano (sem sazonalidade): GH × térmica r = −0,87; térmica × EAR
   inicial r = −0,70; térmica × ENA (% MLT) r = −0,38. O armazenamento pesa mais que a ENA do mês.
4. **Anos:** 2023 (ENA 98% MLT, EAR 77%): térmica sem nuclear 2,3 mil MWmed, GSF médio 0,90. 2024 (ENA 71%, EAR 61%):
   pico de 10,7 mil em out/2024 (8,0 mil por mérito; ENA 56%, EAR 50%) → vermelha 2. 2025 (ENA 77%, EAR 62%): 7–10 mil
   no 2º semestre → vermelha 1 e 2. 2026 (ENA 94%, EAR 63%): 3,4–6,5 mil.
5. **Ordem de grandeza:** 5 mil MWmed a mais de térmica ≈ −0,1 no GSF — o suficiente para mudar a cor em um ou dois patamares.
6. Ver D024 (caminho do modelo) e Q18 (projeção do armazenamento).

### 8.3 Primeiro teste com o NEWAVE (decks de jan e fev/2026)

Arquivos em `data/raw/ccee_newave/2026/2026_01` e `2026_02` (saídas do `nwlistop`, 2.000 séries × 5 anos, 2026–2030):
`ghtotsin` e `ghtotm001–004` (geração hidráulica total, por patamar, MWmês), `eafbsin` e `eafbm001–004` (energia afluente
bruta), `cmarg001` e `cmarg001-med` (custo marginal do SE). Os arquivos são por **ano civil** (colunas jan–dez): no deck de
fevereiro, janeiro vem zerado porque é anterior ao início do estudo. O cabeçalho ("PLD - JANEIRO - 2026 - Niveis para 27/12")
indica que são do **deck de preços da CCEE**, não do PMO do ONS.

- **Mesmas grandezas do nosso alvo:** no mês 1 do deck de jan, a hidráulica do SIN (média das séries) é 53.060 contra 53.104
  MWmed da GH ONS do DECOMP; a energia afluente bruta é 81.906 contra 81.119 MWmed da ENA do `ena.pdf`.
- **Erro da média das 2.000 séries (deck de jan, jan–out/2026):** 2.841 MWmed em média (≈ 0,054 de GSF). Referência
  ingênua (média do mesmo mês em 2023–2025): 2.479 MWmed (≈ 0,047). Nesta amostra o NEWAVE puro **não** superou a referência.
- **Padrão do erro:** superestima de fev a jun (+1 a +4 mil) e subestima de jul a out (−2 a −5 mil); de ago a out, o valor
  do DECOMP ficou **acima de todas as 2.000 séries**.
- **Teste com a ENA realizada (oráculo, 50 séries de ENA mais parecida por subsistema):** melhora o 1º semestre
  (jun: erro de 3,6 mil → 1,7 mil; abr: 0,9 mil → 0,2 mil), mas não o 2º (ago–out: ~−5 mil). O erro do 2º semestre não é
  hidrológico: carga, renováveis, térmica ou representação diferente entre o NEWAVE de jan/fev e o DECOMP de cada mês.
- **Limite:** 2 decks de um único ano; o 2º semestre de 2026 foi atípico (ENA do Sul em 150–200% da MLT).

### 8.4 Estresse do teste do NEWAVE com "ENA perfeita" (decks de jan e fev/2026)

Todos os testes usam a ENA realizada (oráculo), 2 decks e escolhas feitas na própria amostra: os números são um teto.

**GSF — escolha dos cenários.** Trajetória única (1 cenário): erro médio do GSF 0,070 (jan) e 0,050 (fev). Escolhendo
**mês a mês os 10 cenários com ENA do SIN mais próxima da do mês**: 0,033 (jan) e 0,038 (fev); cor certa com o PLD oficial
em 19/19 meses. A ENA do SIN funciona melhor que por subsistema (dimensões demais para 2.000 séries); com 5–10 cenários
o erro estabiliza. Nos mesmos meses (fev–out) os dois decks erram igual (0,037 × 0,038), com o mesmo viés sazonal:
superestima em fev–mai (+0,04 a +0,07) e subestima em ago–set (−0,03 a −0,06). Referência ingênua (média do mesmo mês
em 2023–2025): ≈ 0,047.

**Preço — a trajetória importa.** Escolhendo os cenários do preço pela **trajetória de ENA do SIN até o mês, com mais peso
nos meses recentes** (meia-vida de 2 meses, 25 cenários), o erro do PLD nos meses com GSF < 0,9 cai de R$ 44 (só o mês)
para R$ 32, e a cor certa sobe de 15 para 16–17 em 19. ENA acumulada (do SIN ou por subsistema) dá resultado parecido
(substituta do armazenamento); trajetória por subsistema mês a mês piora muito.

**Preço — 4 submercados.** O "PLD gatilho" de cada cenário passou a seguir a fórmula oficial (custo marginal limitado ao
PLD mín/máx por patamar e submercado, média por horas de patamar, ponderação pela carga do `relato`): resultado
praticamente igual ao do Sudeste sozinho (diferença < R$ 2; mesmas cores), porque nos cenários do NEWAVE os submercados
quase sempre estão acoplados (NE/N descolam > R$ 20 do SE em 3–7% das séries em abr–mai).

**Descolamento real entre submercados (boletins 2023–2026):** a média ponderada pela carga reproduz o PLD gatilho com
diferença zero. Em 38 de 46 meses os 4 submercados tiveram o mesmo PLD. Descolamento relevante só em mar–mai (NE/N no piso
ou bem abaixo do SE): mar/25 (SE − gatilho = +68), abr/25 (+51), mai/25 (+26), mar/26 (+46), mai/26 (+33). Nenhuma cor
mudaria nesta amostra (GSF ≥ 0,94 ou X na mesma faixa), mas maio fica perto da fronteira.

**Principal problema do preço: o nível na transição úmido → seco.** Em fev–mai/2026 o custo marginal do SE nos cenários
escolhidos ficou em R$ 113–190 contra R$ 262–473 do PLD oficial (viés de −R$ 90 a −360). De jun a out o nível é bom.
Na maior parte desses meses o GSF ≥ 0,94 e a cor não muda; em maio (GSF 0,80) muda.

### 8.5 Preço com armazenamento por cenário (`earmfp*`, decks de jan e fev/2026)

> ⚠️ **Limite superior, não realizável:** este teste usa o armazenamento real do início de cada mês futuro, que não é
> conhecido na data da previsão. Na prática o armazenamento entra (1) pela condição inicial do deck mais recente, (2)
> implicitamente pela trajetória de ENA de cada série (o NEWAVE calcula o armazenamento a partir dela), (3) por correção
> de viés aprendida no histórico (ex.: armazenamento do SE sistematicamente abaixo do previsto pelas séries) e (4) pelas
> revisões semanais do DECOMP, se a previsão for feita no meio do mês. A diferença R$ 32 → R$ 22 mede quanto vale
> melhorar a trajetória.

Armazenamento final por série (% EARmax, por submercado e SIN). Para o mês *m*, compara-se o armazenamento do fim de
*m−1* de cada série com o armazenamento inicial real do PMO de *m* (`relato.rv0`).

- **O armazenamento real ficou na parte baixa da distribuição:** no deck de jan, o do SIN abaixo de 70–85% das séries e o
  do **SE abaixo de ~90%**. O sistema chegou a cada mês com menos água no SE do que a maioria dos cenários previa.
- **Só o armazenamento erra para cima** (viés de +R$ 100 a +150 no período seco): séries com reservatório baixo
  costumam ser secas, mas em 2026 o 2º semestre teve ENA alta (Sul muito úmido).
- **Melhor combinação** (estável nos vizinhos): distância = 0,25 × armazenamento por submercado (p.p./5) + ENA do SIN no
  mês (erro relativo/10%) + trajetória de ENA (mais peso nos meses recentes), 25 séries. Contra a trajetória sozinha:
  erro médio do PLD em todos os meses de R$ 80 → **R$ 58**; nos meses com GSF < 0,9, de R$ 32 → **R$ 22**.
- **Maio passa a acertar nos dois decks** (preço de R$ 133/182 → 224/264, contra 238 oficial). A transição úmido → seco
  melhora (mar: 110/174 → 179/243 contra 427; abr: 154/184 → 228/238 contra 258), ainda abaixo do oficial em fev–mar.
- **Novos erros em outubro** (verde → amarela nos dois decks): X ≈ 27,5, exatamente no limite verde/amarela (27,48),
  com GSF levemente subestimado (0,78–0,79 contra 0,82) e preço acima (R$ 125–131 contra 90). Junho do deck de fev
  continua vermelha 1 (preço R$ 309 contra 223). Cor certa: 16/19, a mesma contagem, mas com erros em meses de fronteira.
- Cuidado: grade de pesos escolhida na própria amostra (19 meses-previsão, oráculo de ENA e armazenamento).

### 8.6 Cenários de comparação do NEWAVE (decks de jan e fev/2026, ENA real como referência)

**Cenário referência inicial** (congelado em 2026-10-06; `notebooks/02_newave.ipynb`, figuras em
`reports/figures/cenario_referencia_inicial/`):

- GSF: em cada mês, média das **10 séries** com ENA do SIN do mês mais próxima da referência.
- Preço: **25 séries** pela trajetória de ENA do SIN até o mês (erro relativo², peso cai à metade a cada 2 meses para trás);
  PLD gatilho de cada série pela fórmula do boletim (4 submercados).
- Cor exibida: ábaco com o GSF médio e o PLD médio ("cor pelas médias").
- Probabilidade de cada cor: 10 × 25 = 250 combinações de GSF e preço (tratados como independentes), peso igual.
- Preço Dcide: curva forward do SE publicada na época do deck (`dcide_<publicação>_<deck>.csv`), com o GSF das séries.

**Cenário mesma série** (`notebooks/02b_newave_mesma_serie.ipynb`, figuras em `reports/figures/cenario_mesma_serie/`):
única mudança, o GSF e o preço vêm das **mesmas 25 séries** (escolhidas pela trajetória); probabilidade = fração das 25
séries em cada cor.

| Deck | Cenário | Erro médio GSF | Cor pelas médias | Cor mais provável | Prob. média da cor real | Erro do adicional esperado (R$/MWh) |
|---|---|---|---|---|---|---|
| jan/2026 | referência inicial | 0,033 | 9/10 | 8/10 | 69% | 4,5 |
| jan/2026 | mesma série | 0,043 | 9/10 | 7/10 | 68% | 4,2 |
| fev/2026 | referência inicial | 0,038 | 7/9 | 6/9 | 64% | 4,7 |
| fev/2026 | mesma série | 0,046 | 8/9 | 6/9 | 62% | 6,0 |

Leitura: a escolha pela trajetória é pior para o **nível** do GSF (erro +0,008 a +0,010) do que a escolha pela ENA do mês,
mas parear GSF e preço deixa as **caudas coerentes**: a probabilidade de vermelha sobe nos meses secos (ex.: deck de fev,
jul: 35% → 40%; out: 0% → 8%), como esperado quando série seca traz GSF baixo e preço alto juntos. No agregado, os dois
cenários ficam próximos nesta amostra. Candidato a testar: parear as séries e corrigir o nível do GSF de cada série pela
estimativa da ENA do mês (mantém a coerência e recupera a precisão do nível).

**Memorial da probabilidade de cada cor** (vale para os dois cenários): para cada par (GSF, PLD) — combinação no cenário de
referência, série no cenário mesma série — calcula-se X = PLD × máx(0, 1 − GSF arredondado em 2 casas) e a cor pelos limites
27,48 / 68,99 / 95,05 R$/MWh; a probabilidade é a fração dos pares em cada cor. A "cor pelas médias" não é a cor mais
provável quando a distribuição de preço é bimodal (parte das séries no piso): ex. deck de jan, jul/2026, médias →
amarela (X = 121,8 × 0,30 = 36,5), mas 12 das 25 séries estão no piso (R$ 57) → verde 48%.

**Cenário mediana** (`notebooks/02c_newave_mediana.ipynb`, figuras em `reports/figures/cenario_mediana/`): parte do cenário
mesma série; única mudança, a **cor exibida passa a ser a cor mediana** da distribuição (primeira cor, de verde a vermelha 2,
com probabilidade acumulada ≥ 50%), com a distribuição completa no texto. Na linha da Dcide, a distribuição combina o GSF de
cada uma das 25 séries com o preço da Dcide.

| Deck | Séries: pelas médias | Séries: mediana | Dcide: pelas médias | Dcide: mediana | Prob. média da cor real (séries / Dcide) |
|---|---|---|---|---|---|
| jan/2026 | 9/10 | 9/10 | 6/10 | 6/10 | 68% / 57% |
| fev/2026 | 8/9 | 8/9 | 4/9 | 4/9 | 62% / 45% |

A cor mediana mudou dois meses (deck de fev): mai passou de verde (errado) a amarela (certo; Vd 44% Am 56%) e jun de
amarela (certo) a vermelha 1 (errado; Am 28% V1 56% V2 12%). Mesmo número de acertos, mas a cor exibida passa a ser sempre
coerente com a distribuição mostrada. Na Dcide a distribuição é estreita (só a incerteza do GSF; preço único): quando o
preço da Dcide erra (2º semestre), erra com muita confiança (ex.: jul e ago com V2 96–100%).

**Três decks (jan, fev e mar/2026) — cor pela média × pela mediana** (`notebooks/02d_newave_3decks.ipynb`, figuras em
`reports/figures/cenario_3decks/`; método mesma série; não há curva Dcide para o deck de mar):

| Deck | Séries: média | Séries: mediana | Dcide: média | Dcide: mediana | Erro médio GSF | Erro médio do PLD (R$) | Prob. média da cor real |
|---|---|---|---|---|---|---|---|
| jan/2026 | 9/10 | 9/10 | 6/10 | 6/10 | 0,043 | 90 | 68% |
| fev/2026 | 8/9 | 8/9 | 4/9 | 4/9 | 0,046 | 69 | 62% |
| mar/2026 | 5/8 | 5/8 | — | — | 0,036 | 75 | 68% |

Média e mediana deram a mesma cor em 25 de 27 meses-previsão; as duas diferenças (deck de fev, mai e jun) se compensam
(22/27 acertos nas duas regras). **Maio erra nos três decks** (GSF superestimado em +0,06/+0,07 e preço abaixo do real),
e o deck de mar erra também jun (preço R$ 283 × 223 → V1) e set (verde × amarela).

### 8.7 Probabilidade de cada cor: pesos das séries × calibração pelo erro da média (3 decks, 27 meses-previsão)

Problema: com peso igual nas 25 séries, séries no piso de preço puxam a probabilidade de verde mesmo quando a cor pela
média é amarela. Métodos testados (método mesma série; ENA real como referência):

| Método | Cor mais provável certa | Concorda com a cor da média | Prob. média da cor real | Brier |
|---|---|---|---|---|
| 1. Séries com peso igual | 19/27 | 20/27 | 66% | 0,337 |
| 2. Peso pela proximidade do X da série ao X médio | 20/27 | 23/27 | 69% | 0,330 |
| 3. Peso pela proximidade da ENA da série à de referência | 19/27 | 20/27 | 66% | 0,340 |
| 4. Só as 10 séries de ENA mais próxima | 19/27 | 22/27 | 66% | 0,365 |
| **5. Média + erro histórico da média** | **22/27** | **27/27** | **76%** | **0,235** |

- O método 2 é circular (a média vem das próprias séries): melhora a média geral, mas nos meses em que a cor da média erra
  reduz ainda mais a probabilidade da cor real (ex.: deck de jan, mai: 24% → 12%).
- O método 3 quase não muda nada: as 25 séries já têm ENA parecida, então os pesos ficam quase iguais.
- **Método 5 (proposto):** X médio = PLD médio × (1 − GSF médio) das 25 séries é a referência; supõe-se X real ~ Normal(X médio,
  σ), com σ = desvio do erro histórico (X real − X médio) nos meses não úmidos (13,4 R$/MWh; viés +3,4), estimado deixando de
  fora o mês avaliado; a probabilidade de cada cor é a chance de o X real cair em cada faixa (27,48 / 68,99 / 95,05). Com GSF
  médio ≥ 0,96, verde com 100%. A cor mais provável coincide sempre com a cor da média, e a probabilidade reflete quanto a média
  costuma errar — não o espalhamento bimodal das séries. Nos meses em que a cor da média errou, a cor real ainda recebe 20–45%.
- **A probabilidade é só das séries do NEWAVE.** A Dcide é um preço único e aparece apenas com a cor (ábaco com o GSF médio das
  séries e o preço da Dcide). Implementado em `notebooks/02e_newave_calibrado.ipynb` (figuras em `reports/figures/cenario_calibrado/`).
- Cuidados: σ estimado com 27 pontos de um único ano; erro tratado como normal e igual em todas as estações (a transição
  úmido → seco erra mais). Revalidar com mais decks.

> ⚠️ **Correção (2026-10-06): o σ da seção 8.7 tem vazamento de dados.** Para cada previsão, o σ foi estimado com os erros dos
> outros meses de 2026 (sem o próprio mês-alvo), mas a maioria desses meses é **posterior à data do deck** (ex.: deck de fev
> prevendo jul usou os erros de mai, jun, ago, set e out). Na data de cada deck só se conhece o X real de meses já encerrados
> (deck de jan: até dez/2025; fev: até jan/2026; mar: até fev/2026), e jan–fev/2026 são meses úmidos. Logo, **não há erro
> legítimo em 2026 para estimar o σ**: ele precisa vir de decks de anos anteriores, com janela que avança no tempo e,
> idealmente, por horizonte (M+1 … M+6). Os números de Brier e de probabilidade da cor real do método 5 são otimistas e não
> valem como desempenho fora da amostra. A cor pela média (sem σ) não é afetada.

### 8.8 Backtest sem vazamento — 14 decks (fev/2025 a set/2026), h = 1 a 7

`src/forecast_bandeiras/backtest.py`, `notebooks/02f_backtest_sem_vazamento.ipynb`, resultados em
`data/processed/backtest_newave.parquet`, matriz em `reports/figures/backtest_sem_vazamento/10_matriz_backtest.png`.

- **Fora da amostra:** ANDE (+ consumo interno de Itaipu), PCH e carga por submercado do mês-alvo vêm do deck
  (`c_adic.dat`, `sistema.dat`); GF_band, fatores de perda e PLD mín/máx são os do mês do deck; σ usa só erros de alvos
  anteriores ao mês do deck (mínimo de 8; disponível a partir do deck de ago/2025).
- **Dentro da amostra:** k = 25 séries e meia-vida de 2 meses (escolhidos olhando 2026).
- **Oráculo:** ENA de referência = ENA real (até entrar o ECMWF).

| h | Previsões | Acerto da cor (média das séries) | Persistência (cor do mês do deck) | Mesmo mês do ano anterior | Erro médio GSF | Erro médio PLD (R$) | Prob. média da cor real (n) | Brier |
|---|---|---|---|---|---|---|---|---|
| 1 | 14 | 71% | 57% | 50% | 0,033 | 92 | 73% (9) | 0,32 |
| 2 | 13 | 69% | 31% | 46% | 0,050 | 87 | 76% (8) | 0,30 |
| 3 | 13 | 62% | 15% | 31% | 0,040 | 65 | 72% (8) | 0,31 |
| 4 | 13 | 77% | 15% | 23% | 0,035 | 56 | 79% (8) | 0,23 |
| 5 | 13 | 62% | 15% | 23% | 0,046 | 43 | 73% (8) | 0,31 |
| 6 | 12 | 67% | 17% | 17% | 0,039 | 48 | 72% (7) | 0,34 |
| 7 | 11 | 91% | 27% | 18% | 0,037 | 64 | 82% (6) | 0,11 |
| **Total** | **89** | **71%** | **26%** | **30%** | **0,040** | **66** | **75% (54)** | **0,28** |

- A cor da média supera com folga as referências ingênuas em todos os horizontes, e o acerto não cai com o horizonte
  (71% em média de h = 1 a 7; h = 7 com só 11 previsões) — com ENA oráculo; com o ECMWF deve cair.
- **Os erros se concentram na transição úmido → seco:** de 26 erros, 9 em maio e 6 em junho. Nos erros, o GSF previsto
  fica +0,033 acima do real e o PLD R$ 43 abaixo: o método prevê bandeira **mais barata** que a real. Maio/2026 foi previsto
  verde por todos os decks de nov/2025 a abr/2026 (com 68–89% de probabilidade) e foi amarela; maio/2025 também errou.
- **Matriz com a distribuição completa** (`10b_matriz_backtest_distribuicao.png`): dos 12 erros com probabilidade
  disponível, 5 deram ≥ 30% à cor real (ex.: deck de ago/2025 → nov/2025: Am 54% · V1 46%, foi V1; decks de mar e abr/2026
  → set/2026: Vd 52–55% · Am 45–48%, foi Am) e só 2 deram < 10% (mai/2026 pelo deck de nov/2025: Vd 90% · Am 10%; jun/2026
  pelo deck de mai/2026: V1 56% · V2 41% · Am 2%). Probabilidade média da cor prevista: 89% nos acertos e 69% nos erros —
  a probabilidade separa bem as previsões seguras das duvidosas.
- Candidato natural (sem vazamento): **correção de viés por mês do ano**, estimada só com erros de anos anteriores
  (ex.: o erro de maio/2025 corrige as previsões de maio/2026).

### 8.9 Teste dos parâmetros k (número de séries) e meia-vida da trajetória de ENA

Divisão no tempo, sem vazamento: **escolha** com as previsões de alvo em 2025 (decks de 2025; 39 previsões, h = 1 a 7) e
**teste** com os decks de 2026 (33 previsões). ENA de referência = oráculo. `backtest.preparar_deck` (parte cara, uma vez por
deck) + `backtest.prever_com_parametros` (escolha das séries). k ∈ {5, 10, 15, 25, 50, 100, 200}; meia-vida ∈ {0 (só o
mês-alvo), 0,5, 1, 2 (atual), 4, ∞ (peso igual na trajetória toda)}.

| Configuração | 2025 (escolha): acerto | 2025: erro médio de X | 2026 (teste): acerto | 2026: erro médio de X |
|---|---|---|---|---|
| Só o mês-alvo (meia-vida 0), k = 25 | 44% | 21,0 | 76% | 10,8 |
| **Atual: k = 25, meia-vida 2** | 62% | 13,2 | 73% | 10,8 |
| k = 15, meia-vida 2 | 69% | 13,0 | 73% | 10,9 |
| k = 15, peso igual | 72% | 12,5 | 79% | 11,3 |
| **k = 10, peso igual** (menor erro de X em 2025) | 67% | **12,1** | **82%** | 11,2 |
| k = 200, peso igual | 62% | 13,2 | 73% | 14,0 |

- **A trajetória importa muito:** usar só a ENA do mês-alvo é claramente o pior em 2025 (41–49% de acerto, erro de X 20–24).
  Mais memória ajuda: em 2025, meia-vida 4 ou peso igual > meia-vida 2 > 1 > 0,5 > 0.
- **k entre 10 e 15** foi um pouco melhor que 25 em 2025; k = 200 piora. Em 2026, k de 10 a 25 fica parecido.
- A configuração escolhida só com 2025 (k = 10, peso igual) acerta **82%** em 2026 contra 73% da atual (+3 previsões em 33),
  mas o erro de X em 2026 fica levemente pior (11,2 × 10,8). Ganho modesto e dentro do ruído de uma amostra pequena.
- **k por estação não ajuda:** o melhor k por estação em 2025 muda conforme a meia-vida (transição: 10 com meia-vida 2, 50
  com peso igual) e, no teste de 2026, não supera o k fixo (76% × 76%; 79% × 82%).
- **A transição úmido → seco não melhora com nenhum k ou meia-vida:** em 2025 o acerto nos alvos de mar–jun fica em 30–50%
  em todas as combinações. O problema da transição não é de parâmetro; é viés (GSF previsto alto e preço baixo).

### 8.10 Backtest com k = 15 e peso igual (D029) × referência (k = 25, meia-vida 2)

> Marco: commit marcado com a tag **`d029-k15-peso-igual`** (`git checkout d029-k15-peso-igual` para voltar a este ponto).

`notebooks/02g_backtest_k15.ipynb`, `data/processed/backtest_newave_k15.parquet`, figuras em
`reports/figures/backtest_k15_peso_igual/`. A referência continua em `02f`, `backtest_newave.parquet` e
`reports/figures/backtest_sem_vazamento/`. Mesmas regras de vazamento; ENA = oráculo.

| | Referência (k = 25, meia-vida 2) | Atual (k = 15, peso igual) |
|---|---|---|
| Acerto da cor (89 previsões, h = 1 a 7) | 71% | **78%** |
| Acerto nos alvos de 2025 (base da escolha) | 62% | 72% |
| Acerto nos decks de 2026 (teste) | 73% | **79%** |
| Erro médio GSF | 0,040 | 0,040 |
| Erro médio PLD (R$/MWh) | 65,6 | 63,6 |
| Erro médio X | 11,4 | 11,2 |
| Prob. média da cor real | 75% | 76% |
| Brier | 0,28 | **0,26** |

- Seis previsões mudaram de cor e **todas passaram a acertar**; nenhuma passou a errar: fev/25 → jul/25 (V1), mar/25 →
  ago e set/25 (V2), ago/25 → nov/25 (V1), mar e abr/26 → set/26 (Am). A memória maior da trajetória capturou melhor a
  seca de 2025 e a recuperação do 2º semestre de 2026.
- Por horizonte, o ganho aparece de h = 3 em diante (h = 5: 62% → 85%; h = 6: 67% → 83%); h = 1 e 2 não mudam.
- A transição úmido → seco continua sendo o ponto fraco (maio/2026 segue verde em todos os decks).

## 9. ENA prevista: ECMWF (SEAS5)

### 9.1 Avaliação do ECMWF sozinho (`notebooks/03a_ecmwf_avaliacao.ipynb`)

Dados em `data/raw/ecmwf_ena/` (`load.ler_ecmwf_estatisticas`, `load.ler_ecmwf_membros`): 22 rodadas mensais (jan/2025 a
out/2026), datadas no dia 1 do mês de emissão, cada uma cobrindo o mês de emissão (lead 0) e os 6 seguintes (a média e os
percentis `vaz` vão até o lead 5). Por subsistema: ENA (MWmed), MLT e % MLT. Duas abordagens: `precip` (estatística da chuva
→ ENA) e `vaz` (estatística da vazão); média (`av`), percentis (P10 … P90) e 51 membros (os membros são da abordagem `vaz`).
MLT do ECMWF ≈ MLT do ONS (diferença média 0,5%). Verdade: ENA mensal do `ena.pdf` do PMO.

| Erro da ENA do SIN (% da ENA do PMO) | lead 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| **ECMWF média precip** | **8** | **10** | **9** | **10** | **10** | **12** | **13** |
| ECMWF média vaz | 8 | 15 | 23 | 25 | 26 | 27 | — |
| ECMWF média dos 51 membros (vaz) | 8 | 14 | 22 | 25 | 26 | 25 | 24 |
| Persistência (% MLT do mês anterior) | 9 | 14 | 19 | 21 | 20 | 21 | 21 |
| Climatologia (100% MLT) | 27 | 28 | 30 | 29 | 27 | 26 | 25 |

- **Média `precip`: melhor previsão central** em todos os leads, com viés pequeno (−1% a −7%).
- **Abordagem `vaz` úmida demais** (viés de +8% a +22%). A climatologia tem viés de +18 a +24% porque 2025–2026 foram secos.
- **Percentis `precip` não servem como faixa:** largos e assimétricos (ex.: SE, mar/2026: P10 = 30% e P90 = 296% da MLT).
- **Membros recentrados** (cada membro × média `precip` / média dos membros, por rodada, mês-alvo e subsistema; só produtos
  da própria rodada, sem dado realizado): faixa calibrada para a ENA do SIN — 82% dentro de P10–P90 (ideal 80%), 52% dentro
  de P25–P75 (ideal 50%), 5% abaixo do P10 e 13% acima do P90. Membros originais: 62% e 35%, com 38% abaixo do P10.

### 9.2 Backtest com a ENA do ECMWF — primeiro resultado sem oráculo (`notebooks/03b_backtest_ecmwf.ipynb`)

Módulo `src/forecast_bandeiras/ecmwf.py` (trajetórias de referência) e `backtest.prever_com_referencia` /
`backtest.prever_com_membros`. Decks com rodada do ECMWF: jan/2025 a set/2026 (16); M+1 a M+6; mesmas 89 previsões em todas
as variantes; k = 15, peso igual (D029); pareamento D031. Resultados em `data/processed/backtest_ecmwf.pkl`, matrizes em
`reports/figures/ecmwf/12a_*` e `12b_*`.

| Variante | Acerto da cor | Erro GSF | Erro PLD (R$) | Prob. média da cor real | Brier |
|---|---|---|---|---|---|
| Oráculo (ENA real; teto) | 72% | 0,039 | 66 | 71% | 0,33 |
| **A: ECMWF média `precip`** | **57%** | 0,045 | 88 | 55% | 0,55 |
| B: ECMWF 51 membros recentrados | 54% | 0,044 | 88 | 54% | 0,56 |
| Climatologia (100% MLT; piso) | 38% | 0,063 | 153 | 53% | 0,62 |

| Acerto por horizonte | M+1 | M+2 | M+3 | M+4 | M+5 | M+6 |
|---|---|---|---|---|---|---|
| Oráculo | 69% | 67% | 73% | 67% | 80% | 79% |
| A: ECMWF média | 75% | 67% | 73% | 40% | 53% | 31% |
| B: ECMWF membros | 69% | 73% | 60% | 40% | 47% | 31% |
| Climatologia | 62% | 47% | 40% | 27% | 27% | 23% |

- **Até M+3 o ECMWF entrega praticamente o mesmo que o oráculo**; de M+4 em diante cai para 31–53%, ainda acima da
  climatologia (23–27%). A e B empatam; B não acrescenta acerto.
- **Os erros longos vêm da hidrologia, via preço:** no 2º semestre de 2026 o ECMWF previu seco (ago/26: 28 mil MWmed × 42 mil
  reais; o Sul teve 150–200% da MLT) → séries com PLD de R$ 250–350 (real R$ 130–170) → vermelhas que não ocorreram. No início
  de 2025, o contrário (úmido demais → verde/amarela onde foi vermelha). Nos erros de M+4 a M+6, o GSF errou pouco (−0,002 em
  média); o PLD, +R$ 25 em média e até +R$ 220.
- **A probabilidade ficou confiante demais nos horizontes longos:** o σ é único para todos os horizontes e vem de erros
  majoritariamente de horizontes curtos (ex.: deck de mai/26 → ago/26: V2 92%; real: amarela). Brier 0,55 × 0,33 do oráculo.

### 9.3 σ por horizonte (variante A: ECMWF média)

Pergunta: o σ único (todos os horizontes juntos) deixa a probabilidade confiante demais em M+4 a M+6? Teste: σ estimado só
com erros de alvos já realizados antes do deck (regra do backtest), em quatro formas — único; por grupo (M+1–3 / M+4–6); por
horizonte (com recuo para o grupo e para o único se houver menos de 8 erros); e crescente com h (único × erro médio de h /
erro médio geral). O acerto não muda (a cor exibida é sempre a da média); muda só a distribuição.

| σ | Brier (todos) | Brier M+1–3 | Brier M+4–6 | Confiança M+4–6 | Acerto M+4–6 | Prob. da cor real (todos) |
|---|---|---|---|---|---|---|
| Único (σ ≈ 21) | 0,54 | 0,38 | 0,72 | 69% | 40% | 55% |
| **Por grupo (σ ≈ 15–16 curto; ≈ 25 longo)** | **0,52** | 0,38 | **0,68** | 65% | 40% | **57%** |
| Por horizonte | 0,52 | 0,38 | 0,68 | 65% | 40% | 57% |
| Crescente com h | 0,53 | 0,38 | 0,69 | 66% | 40% | 56% |

- Separar por grupo melhora um pouco (Brier 0,54 → 0,52; no longo 0,72 → 0,68). Por horizonte não acrescenta nada ao grupo.
- Trocar o desvio padrão pela raiz do erro quadrático médio (que inclui o viés) dá praticamente o mesmo resultado.
- No oráculo nada muda (Brier 0,33–0,34): sem erro de hidrologia, o erro de X quase não cresce com o horizonte.
- **O problema continua:** em M+4 a M+6 a confiança média na cor exibida é 65% e o acerto é 40%. O σ que o passado mostra
  (≈ 25) é menor que o erro que aparece depois (desvio de X em M+4–6 no período todo ≈ 37): os erros longos grandes (2º sem/2026)
  ainda não tinham acontecido quando os primeiros decks foram avaliados. Com poucos decks, o σ do passado subestima o futuro.

### 9.4 Erros de M+4 a M+6: GSF ou preço? (variante A: ECMWF média)

Contrafactual em cada previsão errada: troca só o GSF pelo real (mantém o preço previsto) e, separadamente, só o PLD pelo
real. É um diagnóstico com valores realizados (oráculo parcial), não um método de previsão.

| Horizonte | Acerto | Acerto com GSF real | Acerto com PLD real | \|erro GSF\| (oráculo) | \|erro PLD\| R$ (oráculo) |
|---|---|---|---|---|---|
| M+1–3 | 72% | 72% | 91% | 0,038 (0,039) | 83 (81) |
| M+4–6 | 42% | 49% | **86%** | 0,053 (0,040) | 94 (53) |

- Dos 25 erros de cor em M+4–6: 14 se resolvem só com o preço real; 2 só com o GSF real; 5 com qualquer um dos dois;
  4 só com os dois juntos.
- **O GSF piora pouco com o ECMWF** (0,040 → 0,053 em M+4–6), e o erro dele quase não muda a cor. **O preço dobra**
  (R$ 53 → 94): é ele que derruba o acerto. Na conta do erro de X (aproximação de 1ª ordem), a parte do preço é R$ 21 e a
  do GSF, R$ 12, em média, em M+4–6.
- A mesma hidrologia errada mexe nos dois ao mesmo tempo (série seca: GSF baixo e preço alto), mas o preço é muito mais
  sensível a ela. Ex.: deck de mar/26 → ago/26: ENA ECMWF 29 mil × real 42 mil; GSF 0,62 × 0,72; PLD R$ 272 × 129.
- Caso diferente, no deck de jan/25: o PLD real de mar–jul/25 (R$ 208–310) ficou **acima do P90 das 2.000 séries** do
  deck (≈ R$ 75–160). Nenhuma escolha de séries chegaria lá; o erro é do deck, não do ECMWF.
- Figuras: `reports/figures/ecmwf/trajetorias/13_trajetorias_deck_<ano>_<mes>.png` (decks jan/25, mai/25, mar/26, mai/26).
- Comparação com a Dcide (só decks de jan e fev/2026, os únicos com curva; 12 previsões, amostra muito pequena). Cor da Dcide
  = preço da Dcide (PLD SE) com o GSF médio das mesmas séries. Acerto: séries 8/12, Dcide 8/12. Erro médio do PLD: séries
  R$ 113 (viés −42), Dcide R$ 104 (viés +70). A Dcide acerta mai/26 (M+4, deck jan), onde as séries erram por preço baixo,
  e erra jun/26 (M+4, deck fev) por preço alto; em jul–ago/26 as duas erram (vermelha × amarela). A curva da Dcide é quase
  plana (R$ 365 em todo o 2º semestre no deck de fev) e não acompanhou a queda do PLD real para R$ 130–170.
  Figuras: `reports/figures/ecmwf/trajetorias_dcide/14_trajetorias_dcide_deck_2026_<mm>.png`.

### 9.5 Cenários LI / LS no backtest: a faixa contém a bandeira real?

A variante A dá o cenário esperado (cor da média). Para LI (seco, X alto) e LS (úmido, X baixo), três formas, todas com o que
existia na data do deck:
1. **Percentil mensal da ENA dos membros:** trajetória de referência = P10 (LI) e P90 (LS) da ENA do SIN dos 51 membros
   recentrados, mês a mês → 15 séries → GSF, PLD, X e cor (faixa 50%: P25/P75).
2. **X por membro:** cada membro escolhe suas 15 séries (como a variante B); LI/LS = P90/P10 do X entre os membros.
3. **σ calibrado por grupo:** X médio ± 1,28σ (80%) ou ± 0,67σ (50%), σ por grupo M+1–3 / M+4–6 (9.3).

Medida principal: **X real dentro da faixa** (contínua; o ideal é 80% e 50%). A "cor real dentro da faixa" sai sempre acima do
nominal porque a cor é discreta (uma faixa de X pequena dentro de uma cor já "acerta"); por isso vem junto o nº de cores que a
faixa cobre (largura). Amostra comum: 45 previsões com σ disponível (decks ago/25 a set/26); fora da amostra em relação aos
dados, mas a comparação entre os métodos é feita na mesma amostra (dentro da amostra).

| Faixa 80% | X real na faixa (M+1–3 / M+4–6) | Cor real na faixa (M+1–3 / M+4–6) | Nº de cores (M+1–3 / M+4–6) |
|---|---|---|---|
| 1. Percentil mensal da ENA | 76% / **75%** | 96% / 100% | 1,9 / **2,9** |
| 2. X por membro | 80% / 50% | 92% / 95% | 1,8 / 2,7 |
| 3. σ por grupo | 84% / 45% | 92% / 85% | 1,6 / 2,5 |

- Até M+3 as três formas são razoavelmente calibradas (76–84% do X real dentro da faixa de 80%) e a faixa cobre 1,6–1,9 cor.
- **Em M+4–6, só a forma 1 mantém a cobertura (75%), mas a faixa cobre quase todas as cores (2,9 de 4).** As formas 2 e 3
  são mais estreitas e erram para o lado barato: o real foi melhor que o LS (2º semestre de 2026, ECMWF seco demais).
- A ENA real cai dentro de P10–P90 dos membros em 83% (M+1–3) e 77% (M+4–6): a faixa da hidrologia está calibrada; o que
  estreita as formas 2 e 3 é a passagem ENA → preço (média de 15 séries por membro amortece os extremos).
