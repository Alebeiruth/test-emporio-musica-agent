"""Interface de linha de comando para conversar com a Mia.

Uso:
    python main.py            # conversa normal
    python main.py --debug    # mostra as ferramentas chamadas e o uso de cache
"""

from __future__ import annotations

import argparse
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

from agent import AgenteEmporio  # noqa: E402  (depois do load_dotenv: lê LLM_MODEL etc.)

SAIR = {"sair", "exit", "quit"}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # acentos e emojis no terminal do Windows

    parser = argparse.ArgumentParser(description="Mia, a assistente virtual da Empório da Música")
    parser.add_argument("--debug", action="store_true", help="mostra ferramentas e uso de cache")
    args = parser.parse_args()

    if not os.getenv("LLM_API_KEY"):
        sys.exit("Defina LLM_API_KEY no arquivo .env (veja .env.example).")

    agente = AgenteEmporio()
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
        print(f"Mia: {resposta}\n")

    print("Mia: Valeu pela conversa! Qualquer coisa, é só chamar. 🎶")


if __name__ == "__main__":
    main()
