#!/usr/bin/env python3
"""
Oraculo Budget - Monitoramento de custos de LLM
Entry point principal (main.py)

Uso:
    python main.py daily          # Relatório diário
    python main.py weekly         # Relatório semanal
    python main.py update-prices  # Atualiza tabela de preços
    python main.py test           # Testa configuração
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.parser import AgentLogParser
from src.calculator import CostCalculator
from src.report import ReportGenerator
from src.prices import PriceScraper
from src.telegram import TelegramReporter, send_report


def cmd_daily():
    """Gera e envia relatório diário."""
    print(f"[{datetime.now():%H:%M:%S}] Gerando relatório diário...")
    
    generator = ReportGenerator()
    report, summary = generator.generate_daily_report()
    
    # Salva JSON
    json_path = generator.save_report_json(report, summary, 'daily')
    print(f"  ✓ Relatório salvo em {json_path}")
    
    # Envia via Telegram
    if send_report(report, 'daily'):
        print("  ✓ Enviado via Telegram")
    else:
        print("  ✗ Falha ao enviar via Telegram")
        # Ainda assim mostra o relatório no console
        print("\n" + "="*50)
        print(report)
    
    return 0


def cmd_weekly():
    """Gera e envia relatório semanal."""
    print(f"[{datetime.now():%H:%M:%S}] Gerando relatório semanal...")
    
    generator = ReportGenerator()
    report, summary = generator.generate_weekly_report()
    
    # Salva JSON
    json_path = generator.save_report_json(report, summary, 'weekly')
    print(f"  ✓ Relatório salvo em {json_path}")
    
    # Envia via Telegram
    if send_report(report, 'weekly'):
        print("  ✓ Enviado via Telegram")
    else:
        print("  ✗ Falha ao enviar via Telegram")
        print("\n" + "="*50)
        print(report)
    
    return 0


def cmd_update_prices():
    """Atualiza tabela de preços do OpenCode."""
    print(f"[{datetime.now():%H:%M:%S}] Atualizando preços...")
    
    scraper = PriceScraper()
    prices = scraper.fetch_prices()
    
    print(f"  ✓ {len(prices)} modelos com preço:")
    for model, data in sorted(prices.items()):
        print(f"    - {model}: ${data['input']}/1M in, ${data['output']}/1M out")
    
    return 0


def cmd_test():
    """Testa configuração e conexão."""
    print("=== Teste de configuração do Oraculo Budget ===\n")
    
    # Testa parser
    print("[1] Parser do agent.log")
    parser = AgentLogParser()
    requests = parser.parse_file()
    print(f"    ✓ Encontradas {len(requests)} requisições no log")
    
    # Testa calculadora
    print("\n[2] Calculadora de custos")
    calc = CostCalculator()
    if requests:
        last_5 = requests[-5:]
        costs = calc.calculate_batch(last_5)
        total = calc.total_cost(costs)
        saved = calc.total_saved(costs)
        print(f"    ✓ últimas 5 requisições: ${total:.4f} custo, ${saved:.4f} economizado")
    
    # Testa relatório
    print("\n[3] Gerador de relatórios")
    gen = ReportGenerator()
    report, summary = gen.generate_daily_report()
    print(f"    ✓ Relatório diário gerado: ${summary.total_cost:.2f}")
    
    # Testa Telegram
    print("\n[4] Conexão Telegram")
    try:
        reporter = TelegramReporter()
        if reporter.test_connection():
            print("    ✓ Telegram conectado")
            
            # Envia relatório de teste
            test_msg = "🧪 *Teste Oraculo Budget*\n\nConfiguração OK! Relatórios diários funcionando."
            if reporter.send_message(test_msg):
                print("    ✓ Mensagem de teste enviada")
        else:
            print("    ✗ Falha na conexão Telegram")
    except ValueError as e:
        print(f"    ⚠ Telegram não configurado: {e}")
    except Exception as e:
        print(f"    ✗ Erro: {e}")
    
    print("\n=== Teste completo ===")
    return 0


def cmd_preview():
    """Mostra preview do relatório sem enviar."""
    print("=== Preview do Relatório Diário ===\n")
    
    generator = ReportGenerator()
    report, summary = generator.generate_daily_report()
    print(report)
    
    return 0


def main():
    """Entry point principal."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nComandos disponíveis:")
        print("  daily          - Gera e envia relatório diário")
        print("  weekly         - Gera e envia relatório semanal")
        print("  update-prices  - Atualiza tabela de preços")
        print("  test           - Testa configuração")
        print("  preview        - Mostra preview do relatório (sem enviar)")
        return 1
    
    cmd = sys.argv[1].lower()
    
    commands = {
        'daily': cmd_daily,
        'weekly': cmd_weekly,
        'update-prices': cmd_update_prices,
        'test': cmd_test,
        'preview': cmd_preview,
    }
    
    if cmd not in commands:
        print(f"Comando desconhecido: {cmd}")
        print("Use: daily | weekly | update-prices | test | preview")
        return 1
    
    return commands[cmd]()


if __name__ == '__main__':
    sys.exit(main())