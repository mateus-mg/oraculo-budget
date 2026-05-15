#!/usr/bin/env python3
"""
Parser para agent.log do Hermes.
Extrai requisições de API com formato:
API call #N: model=X provider=Y in=N out=N total=N latency=Ns cache=X/Y (Z%)
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class APIRequest:
    """Representa uma requisição de API parseada do log."""
    timestamp: datetime
    call_number: int
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cached_tokens: int
    total_cache_tokens: int
    cache_hit_rate: float  # 0.0 a 1.0
    
    @property
    def uncached_tokens(self) -> int:
        """Tokens que não vieram do cache (input apenas)."""
        return self.input_tokens - self.cached_tokens


class AgentLogParser:
    """Parser para arquivos de log do Hermes."""
    
    # Regex para linha de API call
    API_CALL_PATTERN = re.compile(
        r'^(?P<date>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}),\d+\s+INFO\s+'
        r'(?:\[.*?\]\s+)?run_agent:\s+API call #(?P<call_num>\d+):\s+'
        r'model=(?P<model>\S+)\s+'
        r'provider=(?P<provider>\S+)\s+'
        r'in=(?P<input>\d+)\s+'
        r'out=(?P<output>\d+)\s+'
        r'total=(?P<total>\d+)\s+'
        r'latency=(?P<latency>\d+\.?\d*)s\s+'
        r'cache=(?P<cached>\d+)/(?P<total_cache>\d+)\s+\((?P<cache_rate>\d+)%\)'
    )
    
    # Regex para provider normalization
    PROVIDER_MAP = {
        'opencode': 'opencode-go',
        'opencode-zen': 'opencode-zen',
        'opencode-go': 'opencode-go',
        'copilot': 'github-copilot',
        'github-copilot': 'github-copilot',
    }
    
    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or Path('/home/mateus/.hermes/logs/agent.log')
    
    def parse_line(self, line: str) -> Optional[APIRequest]:
        """Parseia uma linha individual do log."""
        match = self.API_CALL_PATTERN.search(line)
        if not match:
            return None
        
        date_str = match.group('date')
        timestamp = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        
        provider_raw = match.group('provider')
        provider = self.PROVIDER_MAP.get(provider_raw, provider_raw)
        
        cache_rate = int(match.group('cache_rate')) / 100.0
        cached = int(match.group('cached'))
        total_cache = int(match.group('total_cache'))
        
        return APIRequest(
            timestamp=timestamp,
            call_number=int(match.group('call_num')),
            model=match.group('model'),
            provider=provider,
            input_tokens=int(match.group('input')),
            output_tokens=int(match.group('output')),
            total_tokens=int(match.group('total')),
            latency_ms=float(match.group('latency')) * 1000,
            cached_tokens=cached,
            total_cache_tokens=total_cache,
            cache_hit_rate=cache_rate,
        )
    
    def parse_file(self, start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> list[APIRequest]:
        """Parseia o arquivo de log completo ou um período."""
        requests = []
        
        if not self.log_path.exists():
            return requests
        
        with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                req = self.parse_line(line)
                if req:
                    if start_date and req.timestamp < start_date:
                        continue
                    if end_date and req.timestamp > end_date:
                        continue
                    requests.append(req)
        
        return requests
    
    def get_requests_for_day(self, date: datetime) -> list[APIRequest]:
        """Retorna todas requisições de um dia específico."""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.parse_file(start_date=start, end_date=end)
    
    def get_requests_for_week(self, end_date: datetime) -> list[APIRequest]:
        """Retorna requisições da semana (últimos 7 dias)."""
        start = (end_date - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        return self.parse_file(start_date=start, end_date=end_date)


def test_parser():
    """Teste rápido do parser."""
    parser = AgentLogParser()
    
    # Teste com linha de exemplo
    test_line = "2026-05-15 00:24:50,955 INFO [20260515_000911_29214d] run_agent: API call #26: model=minimax-m2.7 provider=opencode in=44054 out=125 total=44179 latency=2.5s cache=43648/44054 (99%)"
    
    req = parser.parse_line(test_line)
    if req:
        print(f"✓ Parser funcionou!")
        print(f"  Model: {req.model}")
        print(f"  Provider: {req.provider}")
        print(f"  Input: {req.input_tokens}, Output: {req.output_tokens}")
        print(f"  Cache hit: {req.cache_hit_rate:.0%}")
    else:
        print("✗ Parser falhou")


if __name__ == '__main__':
    test_parser()