#!/usr/bin/env python3
"""
Módulo de preços - Scraping da tabela OpenCode + cache local.
URL: https://opencode.ai/docs/zen
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import requests
from bs4 import BeautifulSoup


# Preços padrão (fallback) - baseado na tabela oficial do OpenCode Zen
DEFAULT_PRICES = {
    # Modelo: (input, output, cache_read, cache_write) por 1M tokens
    'minimax-m2.7': {
        'input': 0.30,
        'output': 1.20,
        'cache_read': 0.06,
        'cache_write': 0.375,
    },
    'minimax-m2.5': {
        'input': 0.30,
        'output': 1.20,
        'cache_read': 0.06,
        'cache_write': 0.375,
    },
    'kimi-k2.5': {
        'input': 0.60,
        'output': 3.00,
        'cache_read': 0.10,
        'cache_write': None,  # Não suporta cache write
    },
    'kimi-k2.6': {
        'input': 0.95,
        'output': 4.00,
        'cache_read': 0.16,
        'cache_write': None,
    },
    'qwen3.5-plus': {
        'input': 0.20,
        'output': 1.20,
        'cache_read': 0.02,
        'cache_write': 0.25,
    },
    'qwen3.6-plus': {
        'input': 0.50,
        'output': 3.00,
        'cache_read': 0.05,
        'cache_write': 0.625,
    },
    # Modelos Copilot (para cálculo de economia)
    'gpt-5.2-codex': {
        'input': 0.003,  # Preço estimado Copilot
        'output': 0.003,
        'cache_read': 0.0,
        'cache_write': None,
    },
    'gpt-5.1-codex': {
        'input': 0.003,
        'output': 0.003,
        'cache_read': 0.0,
        'cache_write': None,
    },
}


class PriceScraper:
    """Scraper para tabela de preços do OpenCode."""
    
    PRICES_URL = 'https://opencode.ai/docs/zen'
    CACHE_FILE = Path(__file__).parent.parent / 'data' / 'prices.json'
    CACHE_DURATION = timedelta(hours=24)
    
    def __init__(self):
        self.prices: dict = DEFAULT_PRICES.copy()
        self._load_cache()
    
    def _load_cache(self) -> bool:
        """Carrega preços do cache se válido."""
        if not self.CACHE_FILE.exists():
            return False
        
        try:
            with open(self.CACHE_FILE, 'r') as f:
                data = json.load(f)
            
            cached_at = datetime.fromisoformat(data['cached_at'])
            if datetime.now() - cached_at < self.CACHE_DURATION:
                self.prices.update(data['prices'])
                return True
        except (json.JSONDecodeError, KeyError, ValueError):
            return False
        
        return False
    
    def _save_cache(self):
        """Salva preços no cache."""
        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'cached_at': datetime.now().isoformat(),
            'prices': self.prices,
        }
        
        with open(self.CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def fetch_prices(self) -> dict:
        """Faz scraping dos preços do site OpenCode."""
        try:
            response = requests.get(self.PRICES_URL, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procura tabela de preços
            tables = soup.find_all('table')
            for table in tables:
                headers = [th.get_text().strip().lower() for th in table.find_all('th')]
                if any('input' in h for h in headers) or any('model' in h for h in headers):
                    self._parse_table(table)
                    break
            
            self._save_cache()
            
        except Exception as e:
            print(f"Aviso: Falha ao buscar preços online: {e}")
            print("  Usando preços em cache ou padrão.")
        
        return self.prices
    
    def _parse_table(self, table):
        """Parseia tabela de preços."""
        rows = table.find_all('tr')
        
        for row in rows:
            cells = [td.get_text().strip() for td in row.find_all(['td', 'th'])]
            if len(cells) < 3:
                continue
            
            # Tenta identificar modelo na primeira célula
            model = cells[0].lower().replace(' ', '-')
            
            # Extrai preços das células seguintes
            prices = {}
            for i, cell in enumerate(cells[1:], 1):
                # Remove $, /1M, etc
                value = re.sub(r'[^\d.]', '', cell)
                if value:
                    try:
                        prices[i] = float(value)
                    except ValueError:
                        pass
            
            if prices and self._is_valid_model(model):
                self._update_model_prices(model, prices)
    
    def _is_valid_model(self, model: str) -> bool:
        """Verifica se é um modelo válido (não é header)."""
        invalid = ['model', 'modelo', 'preço', 'price', 'cache', 'input', 'output']
        return not any(inv in model.lower() for inv in invalid)
    
    def _update_model_prices(self, model: str, prices: dict):
        """Atualiza preços de um modelo."""
        # Mapeamento genérico baseado no número de colunas
        if 1 in prices:
            self.prices.setdefault(model, {})['input'] = prices[1]
        if 2 in prices:
            self.prices.setdefault(model, {})['output'] = prices[2]
        if 3 in prices:
            self.prices.setdefault(model, {})['cache_read'] = prices[3]
        if 4 in prices:
            self.prices.setdefault(model, {})['cache_write'] = prices[4]
    
    def get_price(self, model: str) -> Optional[dict]:
        """Retorna preços de um modelo específico."""
        return self.prices.get(model.lower())
    
    def has_price(self, model: str) -> bool:
        """Verifica se temos preço para o modelo."""
        return model.lower() in self.prices
    
    def add_model_price(self, model: str, input_price: float, 
                        output_price: float, cache_read: float = 0,
                        cache_write: Optional[float] = None):
        """Adiciona/atualiza preço de um modelo."""
        self.prices[model.lower()] = {
            'input': input_price,
            'output': output_price,
            'cache_read': cache_read,
            'cache_write': cache_write,
        }
    
    def save_prices(self):
        """Salva preços no arquivo de cache."""
        self._save_cache()
    
    @property
    def all_models(self) -> list[str]:
        """Lista todos os modelos com preço conhecido."""
        return list(self.prices.keys())


def update_prices():
    """Função para atualizar preços via CLI."""
    scraper = PriceScraper()
    prices = scraper.fetch_prices()
    
    print("Preços atualizados:")
    for model, data in prices.items():
        print(f"  {model}: ${data['input']} / ${data['output']}")
    
    scraper.save_prices()


if __name__ == '__main__':
    update_prices()