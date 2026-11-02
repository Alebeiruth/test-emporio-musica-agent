"""Loop do agente: conversa com o Claude e executa as ferramentas que ele pedir.

O modelo decide, a cada mensagem, se responde direto (políticas no system prompt) ou se
chama uma ferramenta de dados (tools.py). O histórico fica em memória durante a sessão.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic

from prompts import montar_system
from tools import TOOLS, data_referencia, executar_ferramenta

MODELO_PADRAO = "claude-opus-5-5"
ESFORCO_PADRAO = "medium"
MAX_ITERACOES = 8  # limite de chamadas ao modelo por mensagem do cliente (evita loop infinito)

# Fallback no servidor: se o classificador de segurança recusar, a API refaz a chamada no
# modelo recomendado para a categoria, em vez de devolver a recusa.
BETA_FALLBACK = "server-side-fallback-2026-07-01"

MSG_RECUSA = (
    "Desculpe, não consigo ajudar com isso por aqui. Posso te ajudar com instrumentos, "
    "pedidos ou dúvidas sobre a loja? 🎸"
)
MSG_LIMITE = (
    "Opa, não consegui concluir sua solicitação agora. Pode reformular a pergunta? Se "
    "preferir, fale com a equipe pelo WhatsApp (67) 3321-4500."
)


@dataclass
class ChamadaFerramenta:
    nome: str
    argumentos: dict
    resultado: str


@dataclass
class AgenteEmporio:
    client: anthropic.Anthropic | None = None
    modelo: str = field(default_factory=lambda: os.getenv("LLM_MODEL", MODELO_PADRAO))
    esforco: str = field(default_factory=lambda: os.getenv("LLM_EFFORT", ESFORCO_PADRAO))
    mensagens: list = field(default_factory=list)
    # Ferramentas chamadas na última resposta (para o modo --debug e para os exemplos).
    ultimas_ferramentas: list[ChamadaFerramenta] = field(default_factory=list)
    # Uso de tokens da última chamada (para verificar o prompt caching).
    ultimo_uso: object = None

    def __post_init__(self):
        if self.client is None:
            self.client = anthropic.Anthropic(api_key=os.getenv("LLM_API_KEY"))
        # Montado uma vez por sessão: o prefixo fica idêntico entre chamadas (cache).
        self.system = montar_system(data_referencia())

    def _chamar_modelo(self):
        return self.client.beta.messages.create(
            model=self.modelo,
            max_tokens=16000,
            system=self.system,
            tools=TOOLS,
            messages=self.mensagens,
            output_config={"effort": self.esforco},
            betas=[BETA_FALLBACK],
            fallbacks="default",
        )

    def responder(self, texto_cliente: str) -> str:
        self.mensagens.append({"role": "user", "content": texto_cliente})
        self.ultimas_ferramentas = []

        for _ in range(MAX_ITERACOES):
            resposta = self._chamar_modelo()
            self.ultimo_uso = resposta.usage

            if resposta.stop_reason == "refusal":
                # Mantém o histórico só com acréscimos (nunca editar mensagens anteriores).
                self.mensagens.append({"role": "assistant", "content": MSG_RECUSA})
                return MSG_RECUSA

            # Devolve o conteúdo completo (inclui blocos de thinking e de tool_use).
            self.mensagens.append({"role": "assistant", "content": resposta.content})

            if resposta.stop_reason == "pause_turn":
                continue

            if resposta.stop_reason == "tool_use":
                resultados = []
                for bloco in resposta.content:
                    if bloco.type != "tool_use":
                        continue
                    resultado = executar_ferramenta(bloco.name, dict(bloco.input))
                    self.ultimas_ferramentas.append(
                        ChamadaFerramenta(bloco.name, dict(bloco.input), resultado)
                    )
                    resultados.append(
                        {"type": "tool_result", "tool_use_id": bloco.id, "content": resultado}
                    )
                # Todos os resultados numa única mensagem (permite chamadas em paralelo).
                self.mensagens.append({"role": "user", "content": resultados})
                continue

            texto = "\n".join(b.text for b in resposta.content if b.type == "text").strip()
            if resposta.stop_reason == "max_tokens":
                texto += "\n\n(resposta interrompida por tamanho)"
            return texto or MSG_LIMITE

        # Estourou o limite de iterações: fecha o turno com uma resposta segura.
        self.mensagens.append({"role": "assistant", "content": MSG_LIMITE})
        return MSG_LIMITE
