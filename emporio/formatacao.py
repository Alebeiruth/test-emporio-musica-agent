"""Converte o padrão visual da Mia (formatação do WhatsApp) para cada interface."""

from __future__ import annotations

import re

NEGRITO_WHATSAPP = re.compile(r"\*([^*\n]+)\*")


def para_terminal(texto: str, cores: bool = True) -> str:
    """*negrito* vira negrito ANSI no terminal (ou texto simples, sem cores)."""
    substituto = "\033[1m" + r"\1" + "\033[0m" if cores else r"\1"
    return NEGRITO_WHATSAPP.sub(substituto, texto)


def para_markdown(texto: str) -> str:
    """*negrito* vira **negrito** do Markdown, com quebras de linha preservadas."""
    texto = NEGRITO_WHATSAPP.sub(r"**\1**", texto)
    return "\n".join(linha + "  " if linha.strip() else "" for linha in texto.splitlines())
