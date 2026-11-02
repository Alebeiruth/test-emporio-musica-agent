"""Interface web (Streamlit) para conversar com a Mia.

Uso:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
from datetime import date

import anthropic
import streamlit as st
from dotenv import load_dotenv

from emporio import AgenteEmporio
from emporio.formatacao import para_markdown

load_dotenv()

EXEMPLOS = [
    "Quanto custa o Takamine GD20?",
    "Quais violões vocês têm até R$ 1000?",
    "A promoção da Black Friday ainda vale?",
    "Quero saber do meu pedido 8",
    "Vocês vendem cordas?",
]
DATA_PADRAO = date(2026, 3, 25)  # logo após o último pedido dos dados (ver README)

st.set_page_config(page_title="Mia · Empório da Música", page_icon="🎵")


def nova_conversa(data_ref: date) -> None:
    # A data de referência entra no system prompt e nos cálculos de prazo das ferramentas.
    os.environ["DATA_REFERENCIA"] = data_ref.isoformat()
    st.session_state.agente = AgenteEmporio()
    st.session_state.historico = []  # (papel, texto, ferramentas)
    st.session_state.data_ref = data_ref


# --- Barra lateral -------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configurações")
    data_ref = st.date_input(
        "Data de referência (\"hoje\")",
        value=st.session_state.get("data_ref", DATA_PADRAO),
        format="DD/MM/YYYY",
        help="Os dados estão congelados em 2025–2026; a data define os prazos de troca.",
    )
    mostrar_ferramentas = st.toggle("Mostrar ferramentas chamadas", value=True)
    if st.button("🔄 Nova conversa", use_container_width=True):
        nova_conversa(data_ref)

    st.divider()
    st.caption("Experimente:")
    for exemplo in EXEMPLOS:
        if st.button(exemplo, use_container_width=True):
            st.session_state.pergunta_exemplo = exemplo

if not os.getenv("LLM_API_KEY"):
    st.error("Defina LLM_API_KEY no arquivo .env (veja .env.example) e reinicie o app.")
    st.stop()

if "agente" not in st.session_state or st.session_state.data_ref != data_ref:
    nova_conversa(data_ref)

# --- Conversa ------------------------------------------------------------------------
st.title("🎵 Empório da Música")
st.caption(f"Atendimento com a Mia, assistente virtual · Modelo `{st.session_state.agente.modelo}`")


def mostrar_mensagem(papel: str, texto: str, ferramentas: list) -> None:
    with st.chat_message(papel, avatar="🧑" if papel == "user" else "🎵"):
        if ferramentas and mostrar_ferramentas:
            with st.expander(f"🔧 {len(ferramentas)} consulta(s) ao sistema"):
                for f in ferramentas:
                    st.code(f"{f.nome}({json.dumps(f.argumentos, ensure_ascii=False)})")
        st.markdown(para_markdown(texto) if papel == "assistant" else texto)


for papel, texto, ferramentas in st.session_state.historico:
    mostrar_mensagem(papel, texto, ferramentas)

pergunta = st.chat_input("Digite sua mensagem...") or st.session_state.pop("pergunta_exemplo", None)
if pergunta:
    st.session_state.historico.append(("user", pergunta, []))
    mostrar_mensagem("user", pergunta, [])

    agente: AgenteEmporio = st.session_state.agente
    try:
        with st.spinner("A Mia está digitando..."):
            resposta = agente.responder(pergunta)
    except anthropic.AuthenticationError:
        st.error("Chave de API inválida. Confira LLM_API_KEY no .env.")
        st.stop()
    except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        st.error(f"Problema ao falar com o modelo: {type(e).__name__}. Tente novamente.")
        st.stop()

    st.session_state.historico.append(("assistant", resposta, agente.ultimas_ferramentas))
    mostrar_mensagem("assistant", resposta, agente.ultimas_ferramentas)
