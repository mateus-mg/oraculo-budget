# Oraculo Budget

Monitoramento de custos de LLM para Hermes Agent.

## Providers Monitorados

- **OpenCode Zen** - `provider=opencode-zen`
- **OpenCode Go** - `provider=opencode` (mapeado para `opencode-go`)
- **GitHub Copilot** - `provider=copilot` (mostrado como GRÁTIS)

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

O script usa as variáveis de ambiente já configuradas em `~/.hermes/.env`:

```
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_HOME_CHANNEL=998060657
```

## Uso

```bash
# Relatório diário
python main.py daily

# Relatório semanal
python main.py weekly

# Atualizar preços
python main.py update-prices

# Testar configuração
python main.py test

# Preview (sem enviar)
python main.py preview
```

## Cron Jobs

```bash
# Relatório diário às 20:00
0 20 * * * /media/mateus/Servidor/scripts/worktrees/oraculo-budget/kratos/main.py daily

# Relatório semanal segunda-feira às 20:00
0 20 * * 1 /media/mateus/Servidor/scripts/worktrees/oraculo-budget/kratos/main.py weekly

# Atualizar tabela de preços diariamente (00:00)
0 0 * * * /media/mateus/Servidor/scripts/worktrees/oraculo-budget/kratos/main.py update-prices
```

## Estrutura

```
oraculo-budget/
├── src/
│   ├── parser.py      # Parseia agent.log
│   ├── prices.py      # Scraping tabela OpenCode
│   ├── calculator.py  # Calcula custos
│   ├── report.py      # Gera relatórios
│   └── telegram.py     # Envio Telegram
├── data/
│   └── prices.json    # Cache de preços
├── output/
│   └── cost_report_*.json
└── main.py
```

## Cálculo de Custos

```python
input_cost  = (uncached_tokens / 1_000_000) * price_input
output_cost = (output_tokens / 1_000_000) * price_output
cache_benefit = cached_tokens * (price_input - cache_read) / 1_000_000

custo_final = input_cost + output_cost - cache_benefit
```

## Preços OpenCode (por 1M tokens)

| Modelo | Input | Output | Cache Read |
|--------|-------|--------|------------|
| minimax-m2.7 | $0.30 | $1.20 | $0.06 |
| minimax-m2.5 | $0.30 | $1.20 | $0.06 |
| kimi-k2.5 | $0.60 | $3.00 | $0.10 |
| kimi-k2.6 | $0.95 | $4.00 | $0.16 |
| qwen3.5-plus | $0.20 | $1.20 | $0.02 |
| qwen3.6-plus | $0.50 | $3.00 | $0.05 |