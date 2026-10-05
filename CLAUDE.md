# forecast-bandeiras

## Objetivo do projeto
Prever a bandeira tarifária mensal (M+1 até no mínimo M+6), em cenários LI / esperado / LS.

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
- `data/processed/` — dados limpos, em parquet.
- `notebooks/` — `01_eda`, `02_features`, `03_modelagem`.
- `src/forecast_bandeiras/` — `load.py` (leitura de `sumario.rv0` e patamares), `regra.py` (GH_band, GSF e cor pelo ábaco), `features.py`, `models.py`.
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
