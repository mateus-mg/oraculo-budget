#!/usr/bin/env python3
"""
Gerador de relatórios de custos (diário e semanal).
Formata dados para envio via Telegram.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .parser import AgentLogParser, APIRequest
from .calculator import CostCalculator, CostResult
from .prices import PriceScraper


@dataclass
class DailySummary:
    """Sumário de um dia."""
    date: datetime
    total_cost: float
    request_count: int
    by_provider: dict
    by_model: dict
    avg_latency_ms: float
    avg_cache_hit: float
    vs_yesterday: Optional[float] = None  # % change


@dataclass
class WeeklySummary:
    """Sumário semanal."""
    start_date: datetime
    end_date: datetime
    total_cost: float
    daily_avg: float
    by_provider: dict
    by_model: dict
    by_day: dict  # date -> cost
    vs_last_week: Optional[float] = None


class ReportGenerator:
    """Gera relatórios formatados."""
    
    MONTHLY_BUDGET = 60.00  # Limite mensal em $
    
    def __init__(self):
        self.parser = AgentLogParser()
        self.calculator = CostCalculator()
        self.prices = PriceScraper()
    
    def generate_daily_report(self, date: Optional[datetime] = None) -> tuple[str, DailySummary]:
        """Gera relatório diário."""
        if date is None:
            date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Coleta requisições do dia
        requests = self.parser.get_requests_for_day(date)
        
        if not requests:
            return self._empty_report(date), self._empty_daily_summary(date)
        
        # Calcula custos
        costs = self.calculator.calculate_batch(requests)
        by_provider = self.calculator.aggregate_by_provider(costs)
        by_model = self.calculator.aggregate_by_model(costs)
        
        total_cost = self.calculator.total_cost(costs)
        total_saved = self.calculator.total_saved(costs)
        
        # Calcula métricas
        avg_latency = sum(c.latency_ms for c in costs) / len(costs)
        total_cached = sum(c.cached_tokens for c in costs)
        total_input = sum(c.input_tokens for c in costs)
        avg_cache_hit = total_cached / total_input if total_input else 0
        
        # Compara com ontem
        yesterday = date - timedelta(days=1)
        yesterday_req = self.parser.get_requests_for_day(yesterday)
        vs_yesterday = None
        if yesterday_req:
            yesterday_costs = self.calculator.calculate_batch(yesterday_req)
            yesterday_total = self.calculator.total_cost(yesterday_costs)
            if yesterday_total > 0:
                vs_yesterday = ((total_cost - yesterday_total) / yesterday_total) * 100
        
        # Acumulado mensal
        month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_requests = self.parser.parse_file(start_date=month_start, end_date=date + timedelta(days=1))
        month_costs = self.calculator.calculate_batch(month_requests)
        month_total = self.calculator.total_cost(month_costs)
        
        summary = DailySummary(
            date=date,
            total_cost=total_cost,
            request_count=len(requests),
            by_provider=by_provider,
            by_model=by_model,
            avg_latency_ms=avg_latency,
            avg_cache_hit=avg_cache_hit,
            vs_yesterday=vs_yesterday,
        )
        
        # Formata relatório
        report = self._format_daily_report(date, summary, month_total, vs_yesterday, total_saved, by_model, by_provider, avg_latency, avg_cache_hit)
        
        return report, summary
    
    def _format_daily_report(self, date: datetime, summary: DailySummary,
                            month_total: float, vs_yesterday: Optional[float],
                            total_saved: float, by_model: dict, 
                            by_provider: dict, avg_latency: float,
                            avg_cache_hit: float) -> str:
        """Formata relatório diário em texto Telegram."""
        date_str = date.strftime('%d/%m/%Y')
        
        # Header
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"💰 CUSTOS DO DIA — {date_str}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "📈 RESUMO GERAL",
            f"├─ Total hoje:        ${summary.total_cost:.2f}",
        ]
        
        if vs_yesterday is not None:
            arrow = "↑" if vs_yesterday > 0 else "↓"
            sign = "+" if vs_yesterday > 0 else ""
            lines.append(f"├─ vs ontem:           {sign}${abs(summary.total_cost - (summary.total_cost / (1 + vs_yesterday/100))):.2f} ({arrow}{abs(vs_yesterday):.0f}%)")
        
        lines.append(f"└─ Acumulado no mês:   ${month_total:.2f} / ${self.MONTHLY_BUDGET:.2f}")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🏢 POR PROVIDER")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Provider summaries
        sorted_providers = sorted(by_provider.items(), 
                                 key=lambda x: x[1]['total_cost'], 
                                 reverse=True)
        
        for i, (provider, data) in enumerate(sorted_providers, 1):
            is_copilot = provider == 'github-copilot'
            
            if is_copilot:
                lines.append(f"\n[{i}] {self._provider_name(provider)} ───────────── GRÁTIS 🎉")
                lines.append(f"   └─ {data['requests']} requisições")
                lines.append(f"   💰 Economizados: ${total_saved:.2f}")
            else:
                lines.append(f"\n[{i}] {self._provider_name(provider)} ───────────── ${data['total_cost']:.2f}")
                
                # Model breakdown
                sorted_models = sorted(data['models'].items(),
                                     key=lambda x: x[1]['total_cost'],
                                     reverse=True)
                
                for j, (model, mdata) in enumerate(sorted_models[:5], 1):
                    prefix = "├─" if j < len(sorted_models) else "└─"
                    lines.append(f"   {prefix} {model:15} ${mdata['total_cost']:.2f}  ({mdata['requests']} req)")
        
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("📉 CACHE HIT RATE (média hoje)")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Cache rates by model
        for model, data in sorted(by_model.items(), key=lambda x: x[1]['avg_cache_hit'], reverse=True)[:5]:
            rate = data['avg_cache_hit']
            bar_len = int(rate * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"{model:15} {bar}  {rate*100:.0f}%")
        
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⏱️ LATÊNCIA MÉDIA (ms)")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        for model, data in sorted(by_model.items(), key=lambda x: x[1]['avg_latency_ms'])[:5]:
            latency = data['avg_latency_ms']
            lines.append(f"{model:15} {latency:,.0f}ms")
        
        return "\n".join(lines)
    
    def _provider_name(self, provider: str) -> str:
        """Converte provider slug para nome legível."""
        names = {
            'opencode-zen': 'OpenCode Zen',
            'opencode-go': 'OpenCode Go',
            'github-copilot': 'GitHub Copilot',
        }
        return names.get(provider, provider.replace('-', ' ').title())
    
    def generate_weekly_report(self, end_date: Optional[datetime] = None) -> tuple[str, WeeklySummary]:
        """Gera relatório semanal."""
        if end_date is None:
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        start_date = end_date - timedelta(days=6)
        
        # Coleta requisições da semana
        requests = self.parser.parse_file(
            start_date=start_date.replace(hour=0, minute=0, second=0),
            end_date=end_date + timedelta(days=1)
        )
        
        if not requests:
            return self._empty_weekly_report(start_date, end_date), self._empty_weekly_summary(start_date, end_date)
        
        costs = self.calculator.calculate_batch(requests)
        by_provider = self.calculator.aggregate_by_provider(costs)
        by_model = self.calculator.aggregate_by_model(costs)
        
        total_cost = self.calculator.total_cost(costs)
        daily_avg = total_cost / 7
        total_saved = self.calculator.total_saved(costs)
        
        # Custo por dia
        by_day = {}
        for i in range(7):
            day = start_date + timedelta(days=i)
            day_requests = [r for r in requests if r.timestamp.date() == day.date()]
            if day_requests:
                day_costs = self.calculator.calculate_batch(day_requests)
                by_day[day] = self.calculator.total_cost(day_costs)
            else:
                by_day[day] = 0.0
        
        # Compara com semana anterior
        prev_start = start_date - timedelta(days=7)
        prev_end = start_date - timedelta(days=1)
        prev_requests = self.parser.parse_file(
            start_date=prev_start,
            end_date=prev_end + timedelta(days=1)
        )
        
        vs_last_week = None
        if prev_requests:
            prev_costs = self.calculator.calculate_batch(prev_requests)
            prev_total = self.calculator.total_cost(prev_costs)
            if prev_total > 0:
                vs_last_week = ((total_cost - prev_total) / prev_total) * 100
        
        remaining = self.MONTHLY_BUDGET - total_cost
        
        summary = WeeklySummary(
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            daily_avg=daily_avg,
            by_provider=by_provider,
            by_model=by_model,
            by_day=by_day,
            vs_last_week=vs_last_week,
        )
        
        report = self._format_weekly_report(start_date, end_date, summary, remaining, total_saved, by_day, by_provider, by_model)
        
        return report, summary
    
    def _format_weekly_report(self, start_date: datetime, end_date: datetime,
                             summary: WeeklySummary, remaining: float,
                             total_saved: float, by_day: dict,
                             by_provider: dict, by_model: dict) -> str:
        """Formata relatório semanal."""
        date_range = f"{start_date.strftime('%d')} a {end_date.strftime('%d/%m/%Y')}"
        
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"💰 CUSTOS SEMANAIS — {date_range}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "📈 RESUMO DA SEMANA",
            f"├─ Total semana:      ${summary.total_cost:.2f}",
            f"├─ Daily avg:          ${summary.daily_avg:.2f}",
        ]
        
        if summary.vs_last_week is not None:
            arrow = "↑" if summary.vs_last_week > 0 else "↓"
            sign = "+" if summary.vs_last_week > 0 else ""
            lines.append(f"├─ vs semana anterior: {sign}{abs(summary.vs_last_week):.1f}% {arrow}")
        
        lines.append(f"└─ Saldo restante:     ${remaining:.2f} / ${self.MONTHLY_BUDGET:.2f}")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("📅 EVOLUÇÃO DIÁRIA")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Bar chart dos dias
        max_cost = max(by_day.values()) if by_day else 1
        day_names = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']
        
        for i, (day, cost) in enumerate(sorted(by_day.items())):
            bar_len = int((cost / max_cost) * 30) if max_cost > 0 else 0
            bar = "█" * bar_len
            day_label = day_names[day.weekday()]
            lines.append(f"{day_label} {day.strftime('%d')}  {bar:<30}  ${cost:.2f}")
        
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🏢 POR PROVIDER (semana)")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        total_provider_cost = sum(p['total_cost'] for p in by_provider.values())
        
        for provider, data in sorted(by_provider.items(), key=lambda x: x[1]['total_cost'], reverse=True):
            is_copilot = provider == 'github-copilot'
            
            if is_copilot:
                req_count = data['requests']
                pct = 0
                lines.append(f"GitHub Copilot   GRÁTIS 🎉              —")
                lines.append(f"                  💰 Economizados: ${total_saved:.2f}")
                lines.append(f"                  📦 Requisições: {req_count}/300")
                remaining_req = 300 - req_count
                lines.append(f"                  ⏳ Restantes: {remaining_req}")
            else:
                pct = (data['total_cost'] / total_provider_cost * 100) if total_provider_cost > 0 else 0
                bar_len = int(pct / 5)
                bar = "█" * bar_len
                name = self._provider_name(provider)
                lines.append(f"{name:15} ${data['total_cost']:.2f}  {bar}  {pct:.0f}%")
        
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🤖 POR MODELO (TOP 5)")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        sorted_models = sorted(by_model.items(), 
                              key=lambda x: x[1]['total_cost'] if not x[1]['is_free'] else 0,
                              reverse=True)[:5]
        
        for i, (model, data) in enumerate(sorted_models, 1):
            is_free = data['is_free']
            cost = data['total_cost']
            pct = (cost / summary.total_cost * 100) if summary.total_cost > 0 else 0
            
            if is_free:
                lines.append(f"[{i}] {model:15} GRÁTIS")
            else:
                lines.append(f"[{i}] {model:15} ${cost:.2f}  ({pct:.0f}%)")
        
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 INSIGHTS")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Calcula projeção
        if summary.daily_avg > 0:
            days_remaining = 30 - end_date.day
            projected_total = month_cost = sum(by_day.values())
            if days_remaining > 0:
                projected = summary.daily_avg * days_remaining
                days_can_last = remaining / summary.daily_avg if summary.daily_avg > 0 else 0
                lines.append(f"💡 Se manter o ritmo atual:")
                lines.append(f"    → Crédito de ${self.MONTHLY_BUDGET:.0f} vai durar ~{days_can_last:.0f} dias")
        
        return "\n".join(lines)
    
    def _empty_report(self, date: datetime) -> str:
        """Relatório para dia sem dados."""
        return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 CUSTOS DO DIA — {date.strftime('%d/%m/%Y')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 RESUMO GERAL
├─ Total hoje:        $0.00
└─ Sem requisições registradas

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📭 Nenhuma atividade de API hoje.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    
    def _empty_weekly_report(self, start: datetime, end: datetime) -> str:
        """Relatório para semana sem dados."""
        return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 CUSTOS SEMANAIS — {start.strftime('%d')} a {end.strftime('%d/%m/%Y')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 RESUMO DA SEMANA
├─ Total semana:      $0.00
└─ Sem requisições registradas

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    
    def _empty_daily_summary(self, date: datetime) -> DailySummary:
        """Summary vazio para dia sem dados."""
        return DailySummary(
            date=date,
            total_cost=0.0,
            request_count=0,
            by_provider={},
            by_model={},
            avg_latency_ms=0.0,
            avg_cache_hit=0.0,
        )
    
    def _empty_weekly_summary(self, start: datetime, end: datetime) -> WeeklySummary:
        """Summary vazio para semana sem dados."""
        return WeeklySummary(
            start_date=start,
            end_date=end,
            total_cost=0.0,
            daily_avg=0.0,
            by_provider={},
            by_model={},
            by_day={},
        )
    
    def save_report_json(self, report: str, summary: DailySummary | WeeklySummary, report_type: str):
        """Salva relatório e summary em JSON."""
        from datetime import date
        
        date_str = summary.date.strftime('%Y-%m-%d') if hasattr(summary, 'date') else summary.end_date.strftime('%Y-%m-%d')
        
        output_dir = Path(__file__).parent.parent / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = output_dir / f'cost_report_{report_type}_{date_str}.json'
        
        import json
        
        data = {
            'type': report_type,
            'generated_at': datetime.now().isoformat(),
            'report_text': report,
            'summary': {
                'date': summary.date.isoformat() if hasattr(summary, 'date') else summary.end_date.isoformat(),
                'total_cost': summary.total_cost,
                'request_count': getattr(summary, 'request_count', 0),
                'daily_avg': getattr(summary, 'daily_avg', 0),
                'by_provider': summary.by_provider,
                'by_model': {k: {kk: vv for kk, vv in v.items()} for k, v in summary.by_model.items()},
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        return filename


def test_report():
    """Teste do gerador de relatórios."""
    gen = ReportGenerator()
    
    print("Gerando relatório diário...")
    report, summary = gen.generate_daily_report()
    print(report)
    print("\n" + "="*50 + "\n")
    
    print("Gerando relatório semanal...")
    report, summary = gen.generate_weekly_report()
    print(report)


if __name__ == '__main__':
    test_report()