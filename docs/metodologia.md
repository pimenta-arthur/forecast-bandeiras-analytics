# Metodologia — Previsão de bandeiras tarifárias

Documento vivo: registra o raciocínio, as escolhas feitas e as questões em aberto.
Cada decisão entra no **Registro de decisões** com data, contexto e status.
Nada aqui é verdade estabelecida até ser verificado com dados ou com a regra oficial.

---

## 1. Objetivo

Prever a bandeira tarifária mensal (verde, amarela, vermelha P1, vermelha P2) para os meses
futuros, de M+1 até **no mínimo M+6**. O horizonte final depende do desempenho no backtest.

A saída é organizada em cenários: **limite inferior (LI)**, **esperado** e **limite superior (LS)**.

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
demanda de 91.169 contra 76.680 de hidráulica + térmica + pequenas usinas: faltam ~14,5 GW, provavelmente eólica,
solar centralizada e intercâmbio internacional. Ver Q16.

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
| **Diferença não explicada** | | **−65 (0,08% da demanda)** |

O balanço fecha também por patamar (renováveis vs. resíduo: pesado 16.018 vs. 16.006; médio 21.086 vs. 21.023; leve 19.674 vs. 19.585).
A diferença restante deve ser intercâmbio internacional ou arredondamento; irrelevante para a aproximação (D009).

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
| **Resíduo** (intercâmbio internacional, arredondamento) | | **−65,9 (0,09% da carga)** |

Variável derivada usada na análise: **carga residual** = carga líquida − eólica − solar − PCH − PCT − nuclear = 47.189,3,
isto é, o que sobra para hidráulica + térmica não nuclear (hidráulica para o SIN ≈ carga residual − térmica sem nuclear).

**Passo 8 — ENA e armazenamento** (variáveis explicativas). ENA prevista do mês por subsistema, em MWmed e % MLT
(`ena.pdf`, Tabela 6, coluna "Previsão Mensal Inicial"): SE 24.870 (105%), S 26.506 (193%), NE 1.929 (61%), N 1.020 (43%);
SIN 54.325 (126,5% MLT, ponderado pela MLT). EAR inicial (`sumario.rv0`, `ENERGIA ARMAZENADA NOS SUBSISTEMAS`):
SE 57,4%, S 82,9%, NE 69,6%, N 74,3%; SIN 62,4% (ponderado pela EARmax dos REEs).

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
- **Q14 — ENA não vira geração hidráulica diretamente:** a hidráulica do DECOMP é, em grande parte, a carga menos eólica, solar e térmica; a ENA entra pelo despacho térmico e pelo armazenamento. A conversão ENA → GH precisa incluir carga e renováveis (ex.: regressão de GH_band em carga líquida, ENA % MLT e EAR).
- **Q11 — Definição do horizonte:** a cor de M é decidida por volta do dia 25 de M−1. Em 04/10/2026, outubro já é conhecido, então M+1 = novembro. Fixar a data de corte de cada previsão no backtest.

## 6. Dados

| Dado | Fonte provável | Status |
|------|----------------|--------|
| Histórico de bandeiras realizadas | ANEEL | Disponível (a trazer) |
| Regra/ábaco vigente e REH 3.306/2024 (PDF), em `docs/referencias/` | ANEEL | Recebido; constantes do ábaco e tabela de GFOM conferidas |
| Patamares de carga (horário `AAC001` e semanal `AAC002`), em `data/raw/patamar/<ano>/` | CCEE | 2025 e 2026 recebidos e conferidos |
| Deck do DECOMP da CCEE para o PLD (`cmdeco.rv0`) — etapa 2 | CCEE | A trazer na etapa 2 |
| Renováveis centralizadas (`renovaveis.csv`), na pasta mensal do DECOMP | ONS | Out/2026 recebido e conferido; demais meses a trazer |
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
| Previsão sazonal de ENA (% MLT) | ECMWF SEAS5 | A verificar (incluindo hindcasts) |
| Curva forward de PLD | Dcide | A verificar (histórico de curvas) |

## 7. Próximos passos

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
4. **ENA não aparece como motor direto em 2026:** correlação com a ENA em % MLT = −0,48; a correlação de 0,97 com a ENA
   em MWmed é sazonalidade (período úmido = ENA alta, pouco vento, carga alta). A hidrologia deve agir pela térmica por
   mérito, que quase não variou com o armazenamento confortável de 2026 (EAR do SIN entre 47% e 72%).
5. **Limite:** 10 meses de um ano sem estresse hídrico. Correlações aqui descrevem 2026, não servem para estimar o modelo.
