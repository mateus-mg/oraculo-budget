#!/usr/bin/env python3
"""
Módulo de envio Telegram.
Usa variáveis de ambiente já configuradas em ~/.hermes/.env
"""

import os
import sys
from pathlib import Path
from typing import Optional
import requests

# Tenta carregar python-dotenv se disponível
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


class TelegramReporter:
    """Envia relatórios via Telegram."""
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        # Garante que .env está carregado antes de buscar variáveis
        self._ensure_env_loaded()
        
        # Carrega do .env se não especificado
        self.token = token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_HOME_CHANNEL')
        
        if not self.token or not self.chat_id:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN e TELEGRAM_HOME_CHANNEL devem estar configurados. "
                "Verifique ~/.hermes/.env"
            )
        
        self.api_url = f"https://api.telegram.org/bot{self.token}"
    
    def _ensure_env_loaded(self):
        """Garante que variáveis de ambiente estão carregadas do .env."""
        env_path = Path.home() / '.hermes' / '.env'
        
        if not env_path.exists():
            return
        
        # Se python-dotenv disponível, usa ele (melhor parsing)
        if DOTENV_AVAILABLE:
            load_dotenv(env_path, override=False)
        else:
            # Fallback: parsing manual simples
            if not os.getenv('TELEGRAM_BOT_TOKEN'):
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, val = line.split('=', 1)
                            key = key.strip()
                            val = val.strip()
                            # Define apenas se não existe (override=False)
                            if key == 'TELEGRAM_BOT_TOKEN' and not os.getenv(key):
                                os.environ[key] = val
                            elif key == 'TELEGRAM_HOME_CHANNEL' and not os.getenv(key):
                                os.environ[key] = val
    
    def _load_env(self):
        """Carrega variáveis do .env se não definidas."""
        env_path = Path.home() / '.hermes' / '.env'
        
        if not self.token:
            # Tenta carregar do .env
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            if '=' in line:
                                key, val = line.strip().split('=', 1)
                                if key == 'TELEGRAM_BOT_TOKEN':
                                    self.token = val
                                elif key == 'TELEGRAM_HOME_CHANNEL':
                                    self.chat_id = val
        
        if not self.token or not self.chat_id:
            raise ValueError(
                "Variáveis Telegram não encontradas. "
                f"Verifique {env_path}"
            )
    
    def send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """Envia mensagem de texto."""
        url = f"{self.api_url}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            if result.get('ok'):
                return True
            else:
                print(f"Erro Telegram: {result.get('description')}")
                return False
                
        except requests.RequestException as e:
            print(f"Falha ao enviar mensagem: {e}")
            return False
    
    def send_document(self, filepath: Path, caption: Optional[str] = None) -> bool:
        """Envia documento (arquivo JSON do relatório)."""
        url = f"{self.api_url}/sendDocument"
        
        if not filepath.exists():
            print(f"Arquivo não encontrado: {filepath}")
            return False
        
        with open(filepath, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': self.chat_id}
            if caption:
                data['caption'] = caption
            
            try:
                response = requests.post(url, files=files, data=data, timeout=60)
                result = response.json()
                
                if result.get('ok'):
                    return True
                else:
                    print(f"Erro Telegram: {result.get('description')}")
                    return False
                    
            except requests.RequestException as e:
                print(f"Falha ao enviar documento: {e}")
                return False
    
    def send_photo(self, filepath: Path, caption: Optional[str] = None) -> bool:
        """Envia foto."""
        url = f"{self.api_url}/sendPhoto"
        
        if not filepath.exists():
            print(f"Arquivo não encontrado: {filepath}")
            return False
        
        with open(filepath, 'rb') as f:
            files = {'photo': f}
            data = {'chat_id': self.chat_id}
            if caption:
                data['caption'] = caption
            
            try:
                response = requests.post(url, files=files, data=data, timeout=60)
                result = response.json()
                
                if result.get('ok'):
                    return True
                else:
                    print(f"Erro Telegram: {result.get('description')}")
                    return False
                    
            except requests.RequestException as e:
                print(f"Falha ao enviar foto: {e}")
                return False
    
    def test_connection(self) -> bool:
        """Testa conexão com Telegram."""
        url = f"{self.api_url}/getMe"
        
        try:
            response = requests.get(url, timeout=10)
            result = response.json()
            return result.get('ok', False)
        except:
            return False


def send_report(report_text: str, report_type: str = "daily") -> bool:
    """Função helper para enviar relatório."""
    try:
        reporter = TelegramReporter()
        
        if reporter.test_connection():
            print(f"✓ Conexão Telegram OK")
        else:
            print("✗ Falha na conexão Telegram")
            return False
        
        success = reporter.send_message(report_text)
        
        if success:
            print(f"✓ Relatório {report_type} enviado!")
        else:
            print(f"✗ Falha ao enviar relatório {report_type}")
        
        return success
        
    except Exception as e:
        print(f"✗ Erro: {e}")
        return False


def test_telegram():
    """Testa configuração do Telegram."""
    try:
        reporter = TelegramReporter()
        
        print(f"Token: {reporter.token[:10]}..." if reporter.token else "Token: não encontrado")
        print(f"Chat ID: {reporter.chat_id}")
        
        if reporter.test_connection():
            print("✓ Conexão OK!")
            
            # Envia mensagem de teste
            test_msg = "🧪 *Teste do Oraculo Budget*\n\nScript conectado e funcionando!"
            if reporter.send_message(test_msg):
                print("✓ Mensagem de teste enviada!")
            else:
                print("✗ Falha ao enviar mensagem de teste")
        else:
            print("✗ Falha na conexão")
            
    except ValueError as e:
        print(f"✗ Configuração: {e}")
    except Exception as e:
        print(f"✗ Erro: {e}")


if __name__ == '__main__':
    test_telegram()