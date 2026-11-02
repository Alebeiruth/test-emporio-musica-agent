"""Ferramentas de consulta ao "sistema" da loja (CSVs carregados em memória com pandas).

Cada função pública devolve dados simples (dict/list) prontos para virar JSON e voltar
ao modelo como resultado de uma chamada de ferramenta (function calling).
"""

from __future__ import annotations

import json
import os
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

STATUS_PRODUTO = {
    "active": "ativo",
    "discontinued": "descontinuado",
    "coming_soon": "em breve (aguardando chegada)",
}
STATUS_PEDIDO = {
    "pending": "pendente (aguardando pagamento/confirmação)",
    "confirmed": "confirmado (em separação, ainda não enviado)",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}


def _normalizar(texto: object) -> str:
    """Minúsculas e sem acentos, para busca tolerante ("violao" encontra "Violão")."""
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def data_referencia() -> date:
    """Data "de hoje" usada nos cálculos de prazo.

    Os dados estão congelados em março/2026; DATA_REFERENCIA (AAAA-MM-DD) no .env
    permite simular outra data. Sem ela, usa a data atual.
    """
    valor = os.getenv("DATA_REFERENCIA")
    return date.fromisoformat(valor) if valor else date.today()


# --- Carga dos dados ------------------------------------------------------------------

_categorias = pd.read_csv(DATA_DIR / "categories.csv")
_produtos = pd.read_csv(DATA_DIR / "products.csv").merge(
    _categorias[["category_id", "name"]].rename(columns={"name": "categoria"}),
    on="category_id",
    how="left",
)
_clientes = pd.read_csv(DATA_DIR / "customers.csv")
_pedidos = pd.read_csv(DATA_DIR / "orders.csv")
_itens = pd.read_csv(DATA_DIR / "order_items.csv")
_promocoes = pd.read_csv(DATA_DIR / "promotions.csv")
_promocoes_ativas = _promocoes[_promocoes["is_active"] == 1]

# Texto pesquisável de cada produto: nome + categoria + descrição, normalizado.
_produtos["_busca"] = (
    _produtos["name"] + " " + _produtos["categoria"] + " " + _produtos["description"]
).map(_normalizar)


def _valor(v):
    """Converte NaN do pandas em None (JSON null)."""
    return None if pd.isna(v) else v


def _promocao_ativa(product_id: int) -> dict | None:
    promo = _promocoes_ativas[_promocoes_ativas["product_id"] == product_id]
    if promo.empty:
        return None
    p = promo.iloc[0]
    preco = float(_produtos.loc[_produtos["product_id"] == product_id, "price_brl"].iloc[0])
    desconto = int(p["discount_percent"])
    return {
        "campanha": p["description"],
        "desconto_percentual": desconto,
        "preco_promocional_brl": round(preco * (1 - desconto / 100), 2),
    }


def _max_parcelas(valor: float) -> int:
    """Maior número de parcelas sem juros pela seção 3.1 do manual.

    Até 3x: parcela mínima de R$ 50 (interpretação de "sem valor mínimo, exceto abaixo de
    R$ 50"); 4x–6x: mínimo R$ 80; 7x–12x: mínimo R$ 100.
    """
    def minimo(n: int) -> float:
        return 50 if n <= 3 else 80 if n <= 6 else 100

    return max((n for n in range(1, 13) if n == 1 or valor / n >= minimo(n)), default=1)


def condicoes_pagamento(preco: float, promocao: dict | None) -> dict:
    """Calcula PIX e parcelamento de forma determinística (o modelo não faz contas)."""
    valor = promocao["preco_promocional_brl"] if promocao else preco
    parcelas = _max_parcelas(valor)
    return {
        "valor_base_brl": round(valor, 2),
        # PIX não é cumulativo com promoção (seção 6.2).
        "preco_pix_brl": round(valor, 2) if promocao else round(preco * 0.95, 2),
        "pix_tem_desconto_adicional": promocao is None,
        "max_parcelas_sem_juros": parcelas,
        "valor_parcela_no_maximo_brl": round(valor / parcelas, 2),
        "permite_combinar_pix_e_cartao": valor > 2000,
    }


def _formatar_produto(linha: pd.Series) -> dict:
    promocao = _promocao_ativa(int(linha["product_id"]))
    return {
        "id": int(linha["product_id"]),
        "nome": linha["name"],
        "categoria": linha["categoria"],
        "preco_brl": float(linha["price_brl"]),
        "estoque": int(linha["stock_quantity"]),
        "status": STATUS_PRODUTO.get(linha["status"], linha["status"]),
        "descricao": linha["description"],
        "especificacoes": json.loads(linha["specs"]),
        "promocao_ativa": promocao,
        "pagamento": condicoes_pagamento(float(linha["price_brl"]), promocao),
    }


# --- Ferramentas ----------------------------------------------------------------------


def buscar_produtos(
    nome: str | None = None,
    categoria: str | None = None,
    preco_max: float | None = None,
    apenas_disponiveis: bool = False,
    limite: int = 15,
) -> dict:
    """Busca produtos por termos (nome/descrição), categoria e preço máximo.

    A busca é parcial e ignora maiúsculas e acentos; todos os termos de `nome` precisam
    aparecer no produto. `apenas_disponiveis` filtra status ativo com estoque > 0.
    """
    df = _produtos
    if nome:
        for termo in _normalizar(nome).split():
            df = df[df["_busca"].str.contains(termo, regex=False)]
    if categoria:
        df = df[df["categoria"].map(_normalizar).str.contains(_normalizar(categoria), regex=False)]
    if preco_max is not None:
        df = df[df["price_brl"] <= float(preco_max)]
    if apenas_disponiveis:
        df = df[(df["status"] == "active") & (df["stock_quantity"] > 0)]

    df = df.sort_values("price_brl")
    return {
        "total_encontrado": len(df),
        "exibindo": min(len(df), limite),
        "produtos": [_formatar_produto(linha) for _, linha in df.head(limite).iterrows()],
    }


def consultar_pedido(id_pedido: int) -> dict:
    """Retorna o pedido com seus itens (join de orders + order_items + products)."""
    pedido = _pedidos[_pedidos["order_id"] == int(id_pedido)]
    if pedido.empty:
        return {"erro": f"Pedido {id_pedido} não encontrado."}
    p = pedido.iloc[0]

    itens = _itens[_itens["order_id"] == int(id_pedido)].merge(
        _produtos[["product_id", "name"]], on="product_id", how="left"
    )
    cliente = _clientes[_clientes["customer_id"] == p["customer_id"]]
    primeiro_nome = cliente.iloc[0]["name"].split()[0] if not cliente.empty else None

    resultado = {
        "id_pedido": int(p["order_id"]),
        "cliente_primeiro_nome": primeiro_nome,
        "data_pedido": p["order_date"],
        "status": STATUS_PEDIDO.get(p["status"], p["status"]),
        # Sempre o total registrado no pedido; não recalcular pelos itens (ver README).
        "total_brl": float(p["total_brl"]),
        "forma_pagamento": p["payment_method"],
        "codigo_rastreio": _valor(p["tracking_code"]),
        "previsao_entrega": _valor(p["estimated_delivery"]),
        "observacoes": _valor(p["notes"]),
        "itens": [
            {"id_produto": int(i["product_id"]), "nome": i["name"], "quantidade": int(i["quantity"])}
            for _, i in itens.iterrows()
        ],
        "data_referencia_hoje": data_referencia().isoformat(),
    }

    # Para prazos de troca/arrependimento: a data de recebimento não existe nos dados;
    # assume-se a previsão de entrega como data de recebimento (suposição do README).
    if p["status"] == "delivered" and not pd.isna(p["estimated_delivery"]):
        dias = (data_referencia() - date.fromisoformat(p["estimated_delivery"])).days
        resultado["dias_desde_entrega"] = dias
    return resultado


def listar_promocoes(incluir_inativas: bool = False) -> dict:
    """Lista promoções (por padrão, só as ativas), com preço original e promocional."""
    df = _promocoes if incluir_inativas else _promocoes_ativas
    df = df.merge(_produtos[["product_id", "name", "price_brl"]], on="product_id", how="left")
    return {
        "promocoes": [
            {
                "campanha": r["description"],
                "ativa": bool(r["is_active"]),
                "id_produto": int(r["product_id"]),
                "produto": r["name"],
                "preco_original_brl": float(r["price_brl"]),
                "desconto_percentual": int(r["discount_percent"]),
                "preco_promocional_brl": round(r["price_brl"] * (1 - r["discount_percent"] / 100), 2),
            }
            for _, r in df.iterrows()
        ]
    }


def listar_categorias() -> dict:
    """Categorias da loja com a quantidade de produtos ativos e com estoque em cada uma."""
    disponiveis = _produtos[(_produtos["status"] == "active") & (_produtos["stock_quantity"] > 0)]
    contagem = disponiveis.groupby("category_id").size()
    return {
        "categorias": [
            {"categoria": c["name"], "produtos_disponiveis": int(contagem.get(c["category_id"], 0))}
            for _, c in _categorias.iterrows()
        ]
    }


# --- Definições para o modelo (formato de tools da API da Anthropic) ------------------

TOOLS = [
    {
        "name": "buscar_produtos",
        "description": (
            "Consulta o catálogo da loja: preço, estoque, status, especificações e promoção "
            "ativa de cada produto. Use SEMPRE antes de informar preço, estoque ou "
            "disponibilidade. Busca parcial, sem diferenciar maiúsculas/acentos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string",
                    "description": "Termos de busca: marca, modelo ou característica (ex.: 'Takamine GD20', 'nylon', '7 cordas').",
                },
                "categoria": {
                    "type": "string",
                    "description": "Categoria (ex.: 'Violões', 'Guitarras', 'Baixos', 'Ukuleles', 'Teclados', 'Baterias').",
                },
                "preco_max": {"type": "number", "description": "Preço máximo em reais."},
                "apenas_disponiveis": {
                    "type": "boolean",
                    "description": "Se true, retorna só produtos ativos com estoque.",
                },
            },
        },
    },
    {
        "name": "consultar_pedido",
        "description": (
            "Consulta um pedido pelo número: status, itens, total, pagamento, rastreio, "
            "previsão de entrega e dias desde a entrega (para prazos de troca)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"id_pedido": {"type": "integer", "description": "Número do pedido."}},
            "required": ["id_pedido"],
        },
    },
    {
        "name": "listar_promocoes",
        "description": (
            "Lista as promoções com preço original e promocional. Use para perguntas sobre "
            "promoções ou para verificar se uma campanha (ex.: Black Friday) ainda está ativa."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "incluir_inativas": {
                    "type": "boolean",
                    "description": "Se true, inclui promoções encerradas (para confirmar que expiraram).",
                }
            },
        },
    },
    {
        "name": "listar_categorias",
        "description": "Lista as categorias de instrumentos e quantos produtos disponíveis há em cada uma.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

_FUNCOES = {
    "buscar_produtos": buscar_produtos,
    "consultar_pedido": consultar_pedido,
    "listar_promocoes": listar_promocoes,
    "listar_categorias": listar_categorias,
}


def executar_ferramenta(nome: str, argumentos: dict) -> str:
    """Executa a ferramenta pedida pelo modelo e devolve o resultado como JSON."""
    funcao = _FUNCOES.get(nome)
    if funcao is None:
        return json.dumps({"erro": f"Ferramenta desconhecida: {nome}"}, ensure_ascii=False)
    try:
        resultado = funcao(**argumentos)
    except Exception as exc:  # erro vira resposta para o modelo, não derruba o agente
        resultado = {"erro": f"Falha ao executar {nome}: {exc}"}
    return json.dumps(resultado, ensure_ascii=False, default=str)
