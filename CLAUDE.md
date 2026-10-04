# forecast-bandeiras

## Objetivo do projeto
Prever uma variável alvo a partir de variáveis de entrada.

- **Variável alvo:** TODO
- **Variáveis de entrada:** TODO

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
- `src/forecast_bandeiras/` — `load.py`, `features.py`, `models.py`.
- `reports/figures/` — gráficos em PNG.

## Convenções
- Funções reutilizáveis ficam em `src/forecast_bandeiras/`; os notebooks apenas orquestram (importam e chamam).
- Gráficos relevantes são salvos em `reports/figures/` (PNG).
- Código e comentários em português.
- Lint/format com `uv run ruff check` e `uv run ruff format`.

## Boas práticas de modelagem
- Começar sempre por um baseline simples antes de modelos mais complexos.
- Se os dados forem temporais, separar treino/teste por data (`TimeSeriesSplit`), **nunca aleatoriamente**.
- Cuidado com vazamento de dados (data leakage): nenhuma feature pode usar informação indisponível no momento da previsão; ajustar transformações (escalas, imputações) apenas no treino.
