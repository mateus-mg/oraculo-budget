#!/usr/bin/env python3
"""
Calculadora de custos para requisições de LLM.
Baseado nos preços do OpenCode e nos dados do Hermes.
"""

from dataclasses import dataclass
from typing import Optional
from .parser import APIRequest
from .prices import PriceScraper, DEFAULT_PRICES


@dataclass
class CostResult:
    """Resultado do cálculo de custo."""
    model: str
    provider: str
    input_cost: float
    output_cost: float
    cache_benefit: float
    total_cost: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cache_hit_rate: float
    latency_ms: float
    is_free: bool = False  # Para Copilot


class CostCalculator:
    """Calcula custos baseado em preços e requisições."""
    
    def __init__(self, price_scraper: Optional[PriceScraper] = None):
        self.prices = price_scraper or PriceScraper()
    
    def calculate_request_cost(self, request: APIRequest) -> CostResult:
        """Calcula custo de uma única requisição."""
        model = request.model.lower()
        
        # Verifica se é provider gratuito (Copilot)
        is_copilot = request.provider in ('github-copilot', 'copilot')
        
        # Busca preço do modelo
        price_data = self.prices.get_price(model)
        
        if price_data is None:
            # Modelo não encontrado - usa placeholder
            price_data = {
                'input': 0.30,  # Fallback
                'output': 1.20,
                'cache_read': 0.06,
                'cache_write': None,
            }
            has_price = False
        else:
            has_price = True
        
        # Cálculo de custo correto com cache:
        # - Tokens não-cacheados: pagam input_price completo
        # - Tokens cacheados: pagam cache_read_price (mais barato)
        # - Output: sempre paga output_price
        cache_read_price = price_data.get('cache_read', 0) or 0
        uncached_input = request.input_tokens - request.cached_tokens
        
        input_cost = (uncached_input / 1_000_000) * price_data['input']
        cache_cost = (request.cached_tokens / 1_000_000) * cache_read_price
        output_cost = (request.output_tokens / 1_000_000) * price_data['output']
        
        # Cache benefit (economia vs pagar input_price por tudo)
        if cache_read_price < price_data['input'] and request.cached_tokens > 0:
            cache_benefit = request.cached_tokens * (price_data['input'] - cache_read_price) / 1_000_000
        else:
            cache_benefit = 0.0
        
        # Custo total = input (não-cacheado) + cache (lido do cache) + output
        # Fórmula correta: custo real considerando cache pricing
        if is_copilot:
            total_cost = 0.0
            is_free = True
        else:
            total_cost = input_cost + cache_cost + output_cost
            is_free = False
        
        return CostResult(
            model=request.model,
            provider=request.provider,
            input_cost=input_cost,
            output_cost=output_cost,
            cache_benefit=cache_benefit,
            total_cost=total_cost,
            input_tokens=request.input_tokens,
            output_tokens=request.output_tokens,
            cached_tokens=request.cached_tokens,
            cache_hit_rate=request.cache_hit_rate,
            latency_ms=request.latency_ms,
            is_free=is_free,
        )
    
    def calculate_batch(self, requests: list[APIRequest]) -> list[CostResult]:
        """Calcula custos de múltiplas requisições."""
        return [self.calculate_request_cost(req) for req in requests]
    
    def aggregate_by_model(self, costs: list[CostResult]) -> dict[str, dict]:
        """Agrega custos por modelo."""
        models = {}
        
        for cost in costs:
            key = cost.model
            if key not in models:
                models[key] = {
                    'total_cost': 0.0,
                    'requests': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cached_tokens': 0,
                    'latencies': [],
                    'provider': cost.provider,
                    'is_free': cost.is_free,
                }
            
            models[key]['total_cost'] += cost.total_cost
            models[key]['requests'] += 1
            models[key]['input_tokens'] += cost.input_tokens
            models[key]['output_tokens'] += cost.output_tokens
            models[key]['cached_tokens'] += cost.cached_tokens
            models[key]['latencies'].append(cost.latency_ms)
        
        # Calcula médias
        for model, data in models.items():
            if data['requests'] > 0:
                data['avg_latency_ms'] = sum(data['latencies']) / len(data['latencies'])
                data['avg_cache_hit'] = (data['cached_tokens'] / 
                                         (data['input_tokens'] or 1))
            else:
                data['avg_latency_ms'] = 0
                data['avg_cache_hit'] = 0
        
        return models
    
    def aggregate_by_provider(self, costs: list[CostResult]) -> dict[str, dict]:
        """Agrega custos por provider."""
        providers = {}
        
        for cost in costs:
            key = cost.provider
            if key not in providers:
                providers[key] = {
                    'total_cost': 0.0,
                    'requests': 0,
                    'models': {},
                }
            
            providers[key]['total_cost'] += cost.total_cost
            providers[key]['requests'] += 1
            
            # Adiciona ao modelo dentro do provider
            if cost.model not in providers[key]['models']:
                providers[key]['models'][cost.model] = {
                    'total_cost': 0.0,
                    'requests': 0,
                }
            
            providers[key]['models'][cost.model]['total_cost'] += cost.total_cost
            providers[key]['models'][cost.model]['requests'] += 1
        
        return providers
    
    def total_cost(self, costs: list[CostResult]) -> float:
        """Retorna custo total (ignorando gratuitos)."""
        return sum(c.total_cost for c in costs if not c.is_free)
    
    def total_saved(self, costs: list[CostResult]) -> float:
        """Retorna total economizado (principalmente Copilot)."""
        # Calcula quanto teria custado sem Copilot
        total = 0.0
        for cost in costs:
            if cost.is_free:
                # Simula custo como se fosse OpenCode
                price_data = self.prices.get_price(cost.model) or {
                    'input': 0.30,
                    'output': 1.20,
                }
                input_cost = (cost.input_tokens / 1_000_000) * price_data['input']
                output_cost = (cost.output_tokens / 1_000_000) * price_data['output']
                total += input_cost + output_cost
        return total


def test_calculator():
    """Teste rápido da calculadora."""
    from .parser import AgentLogParser
    
    parser = AgentLogParser()
    calc = CostCalculator()
    
    # Pega últimas requisições do log
    requests = parser.parse_file()
    if not requests:
        print("Nenhuma requisição encontrada no log")
        return
    
    # Calcula custo das últimas 10
    last_10 = requests[-10:]
    costs = calc.calculate_batch(last_10)
    
    print(f"Últimas {len(costs)} requisições:")
    for cost in costs:
        marker = " (GRÁTIS)" if cost.is_free else ""
        print(f"  {cost.model:20} {cost.provider:15} ${cost.total_cost:.4f}{marker}")
    
    print(f"\nTotal custos pagos: ${calc.total_cost(costs):.4f}")
    print(f"Total economizado:   ${calc.total_saved(costs):.4f}")


if __name__ == '__main__':
    test_calculator()