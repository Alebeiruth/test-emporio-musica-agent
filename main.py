"""Interface de linha de comando para conversar com a Mia.

Uso:
    python main.py                          # conversa normal
    python main.py --debug                  # mostra ferramentas chamadas e uso de cache
    python main.py --salvar exemplos/x.md   # salva a conversa em Markdown
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from emporio import AgenteEmporio
from emporio.formatacao import para_markdown, para_terminal
from emporio.tools import data_referencia

load_dotenv()

SAIR = {"sair", "exit", "quit"}


class Transcricao:
    """Registra a conversa (com as ferramentas chamadas) para os exemplos em exemplos/."""

    def __init__(self, caminho: Path, modelo: str):
        self.caminho = caminho
        self.partes = [
            "<!-- Conversa real gerada com `python main.py --salvar` -->",
            f"> Modelo: `{modelo}` · Data de referência: "
            f"{data_referencia().strftime('%d/%m/%Y')}\n",
        ]

    def adicionar(self, cliente: str, ferramentas: list, resposta: str) -> None:
        self.partes.append(f"**🧑 Cliente:** {cliente}\n")
        for f in ferramentas:
            args = json.dumps(f.argumentos, ensure_ascii=False)
            self.partes.append(f"> 🔧 `{f.nome}({args})`\n")
        self.partes.append(f"**🎵 Mia:**  \n{para_markdown(resposta)}\n")
        self.partes.append("---\n")

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text("\n".join(self.partes), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # acentos e emojis no terminal do Windows
    if not sys.stdin.isatty():
        sys.stdin.reconfigure(encoding="utf-8")  # roteiros lidos de arquivo (UTF-8)
    cores = sys.stdout.isatty()
    if cores and os.name == "nt":
        os.system("")  # habilita sequências ANSI no console do Windows

    parser = argparse.ArgumentParser(description="Mia, a assistente virtual da Empório da Música")
    parser.add_argument("--debug", action="store_true", help="mostra ferramentas e uso de cache")
    parser.add_argument("--salvar", type=Path, help="salva a conversa em Markdown neste arquivo")
    args = parser.parse_args()

    if not os.getenv("LLM_API_KEY"):
        sys.exit("Defina LLM_API_KEY no arquivo .env (veja .env.example).")

    agente = AgenteEmporio()
    transcricao = Transcricao(args.salvar, agente.modelo) if args.salvar else None
    print("🎵 Empório da Música — atendimento com a Mia (digite 'sair' para encerrar)\n")

    while True:
        try:
            texto = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not texto:
            continue
        if texto.lower() in SAIR:
            break
        if not sys.stdin.isatty():
            print(texto)  # entrada via arquivo/pipe: ecoa a pergunta para a saída ficar legível

        try:
            resposta = agente.responder(texto)
        except anthropic.AuthenticationError:
            sys.exit("Chave de API inválida. Confira LLM_API_KEY no .env.")
        except anthropic.RateLimitError:
            print("Mia: Estou recebendo muitas mensagens agora, tente de novo em instantes.\n")
            continue
        except anthropic.APIStatusError as e:
            print(f"Mia: Tive um problema técnico ({e.status_code}). Tente novamente.\n")
            continue
        except anthropic.APIConnectionError:
            print("Mia: Sem conexão com o serviço no momento. Verifique sua internet.\n")
            continue

        if args.debug:
            for chamada in agente.ultimas_ferramentas:
                print(f"  [ferramenta] {chamada.nome}({chamada.argumentos})")
            uso = agente.ultimo_uso
            if uso is not None:
                print(
                    f"  [tokens] entrada={uso.input_tokens} "
                    f"cache_lido={uso.cache_read_input_tokens} "
                    f"cache_criado={uso.cache_creation_input_tokens} saída={uso.output_tokens}"
                )
        print(f"Mia: {para_terminal(resposta, cores)}\n")
        if transcricao:
            transcricao.adicionar(texto, agente.ultimas_ferramentas, resposta)

    if transcricao:
        transcricao.salvar()
        print(f"(conversa salva em {args.salvar})")
    print("Mia: Valeu pela conversa! Qualquer coisa, é só chamar. 🎶")


if __name__ == "__main__":
    main()
