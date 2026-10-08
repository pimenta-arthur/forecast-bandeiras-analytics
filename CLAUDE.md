# forecast-bandeiras

## Objetivo do projeto
Prever a bandeira tarifária mensal (M+1 até no mínimo M+6). **Saída principal: probabilidade de cada cor por mês** (ex.: "ago: 70% amarela, 25% vermelha 1, 5% verde"), calculada sobre os cenários; GSF e preço em cenários LI / esperado / LS como apoio (D025).

- **Variável alvo:** bandeira tarifária do mês. A abordagem é prever os insumos da regra (GSF, depois PLD) e aplicar o ábaco da ANEEL.
- **Variáveis de entrada:** em definição (ENA, carga, geração hidráulica, garantia física, PLD, GFOM...).

**A metodologia, as decisões e as questões em aberto ficam em `docs/metodologia.md`.** Ler antes de propor abordagens e registrar ali toda nova decisão (com ID, data, motivo e status). Tratar o conteúdo como hipótese até ser verificado.

**⚠️ Ponto crítico — fontes do boletim da bandeira:** todas as variáveis da memória de cálculo da CCEE (geração hidráulica, ANDE, PCH, GSF etc.) vêm do `sumario.rv0` do PMO do **ONS**, **exceto o PLD gatilho**, que vem do deck do DECOMP da **CCEE** usado no cálculo do PLD (`cmdeco.rv0`). **CMO do ONS ≠ PLD gatilho:** nunca usar o CMO do `sumario.rv0` como PLD.

## Fase atual
Preparação / análise exploratória. **Não treinar modelos sem pedido explícito.**

## Regras de ambiente
- Sempre `uv add <pacote>` para instalar (`uv add --dev` para ferramentas de desenvolvimento) e `uv run <comando>` para executar. **Nunca usar pip.**
- O projeto usa o Python do Homebrew (`/opt/homebrew/opt/python@3.14/bin/python3`, versão em `.python-version`).
- Se a `.venv` quebrar após uma atualização do Homebrew: apagar a `.venv` e rodar `uv sync`.
- Kernel do Jupyter: `Python 3.14 (forecast-bandeiras)`.

## Estrutura
- `data/raw/` — dados originais, **somente leitura** (nunca modificar ou sobrescrever).
  Os dados brutos são versionados no **git normal** (sem Git LFS): são arquivos de texto que o git compacta ~5× (um deck do NEWAVE de 28 MB vira ~5 MB). Reavaliar só se o repositório for para um remoto e o `.git` passar de ~1 GB.
- `data/processed/` — dados limpos, em parquet.
- `notebooks/` — `01_eda`, `02_features`, `03_modelagem`.
- `src/forecast_bandeiras/` — `load.py` (leitura de `sumario.rv0` e patamares), `regra.py` (GH_band, GSF e cor pelo ábaco), `features.py` (balanço e base mensal), `graficos.py` (figuras da EDA), `newave.py` (séries do NEWAVE, PLD gatilho por série e escolha de séries pela ENA), `backtest.py` (backtest sem vazamento com os decks), `models.py`. Fonte do DECOMP: `relato.rv0` (tudo) e `renovaveis.csv` (só para separar eólica e solar a partir de out/2025); `sumario.rv0` não é mais usado. Base histórica: `data/processed/base_mensal.parquet` (jan/2023–out/2026).
- `reports/figures/` — gráficos em PNG.
- `docs/metodologia.md` — raciocínio, registro de decisões e questões em aberto.

## Convenções
- Funções reutilizáveis ficam em `src/forecast_bandeiras/`; os notebooks apenas orquestram (importam e chamam).
- Gráficos relevantes são salvos em `reports/figures/` (PNG).
- Código e comentários em português.
- Responder sempre em português do Brasil.
- Lint/format com `uv run ruff check` e `uv run ruff format`.

## Boas práticas de modelagem
- Começar sempre por um baseline simples antes de modelos mais complexos.
- Se os dados forem temporais, separar treino/teste por data (`TimeSeriesSplit`), **nunca aleatoriamente**.
- Cuidado com vazamento de dados (data leakage): nenhuma feature pode usar informação indisponível no momento da previsão; ajustar transformações (escalas, imputações) apenas no treino.

### ⚠️ Regra do backtest: só o que existia na data da previsão
Todo backtest simula alguém **sentado na data do deck** (ex.: início de jan/2026 com o deck de jan) prevendo os meses seguintes. **Qualquer número usado numa previsão tem que estar disponível nessa data.** Antes de rodar ou reportar um resultado, conferir item a item:
- **Erros, desvios, viés, calibração (σ, correções, pesos):** só com previsões cujo mês-alvo **já tinha terminado** na data do deck. Deck de jan/2026 → erros até dez/2025; deck de fev/2026 → até jan/2026. Nunca usar erros de meses do mesmo ano posteriores à data, nem "deixar só o próprio mês de fora" (leave-one-out não basta). Sem histórico suficiente, o método fica suspenso, não se improvisa com dados do futuro.
- **Insumos do mês-alvo** (ANDE, PCH, carga/pesos de submercado, GF_band, PLD mín/máx): vêm do deck ou de publicações da data, não do PMO/boletim do próprio mês-alvo.
- **Escolha de parâmetros** (k, meia-vida, pesos, critério de seleção): escolhidos em um período e avaliados em outro; resultado escolhido e avaliado na mesma amostra é "dentro da amostra" e deve ser rotulado assim.
- **Oráculos** (ex.: ENA real no lugar da prevista): permitidos só para estudar limites, sempre identificados como "oráculo / limite superior", nunca como desempenho esperado.
- Ao apresentar qualquer resultado de backtest, dizer explicitamente o que é fora da amostra, o que é dentro da amostra e o que é oráculo.
