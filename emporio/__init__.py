"""Núcleo da Mia, a assistente virtual da Empório da Música.

- tools.py      ferramentas de consulta aos dados (CSVs) + definições para o modelo
- prompts.py    persona, regras e manual de políticas (PDF) no system prompt
- agent.py      loop do agente com o Claude (function calling)
- formatacao.py padrão visual (*negrito* do WhatsApp) para terminal, Markdown e web
"""

from .agent import AgenteEmporio

__all__ = ["AgenteEmporio"]
