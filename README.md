# emporio-musica-agent

Prototype of a text-message customer service agent for **Empório da Música**, a fictional
musical instrument store in Campo Grande/MS (Brazil). Built in Python for the Artefact
AI Engineer technical challenge.

The agent must:

- take on a persona aligned with the store's tone of voice;
- answer based on the provided context (CSV files + store policy manual in PDF);
- know when to **query data** (price, stock, orders) and when to **apply policies**
  (returns, opening hours, payment);
- handle out-of-scope questions appropriately.

The agent is **Mia**, Empório da Música's virtual assistant.

## How to run

Requirements: Python 3.11+ (developed on 3.13) and an Anthropic API key.

```bash
git clone https://github.com/Alebeiruth/emporio-musica-agent.git
cd emporio-musica-agent
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate       # Linux/macOS
pip install -r requirements.txt
cp .env.example .env              # then set LLM_API_KEY in .env
python main.py                    # chat with Mia (type "sair" to exit)
python main.py --debug            # also shows tool calls and prompt-cache usage
```

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `LLM_API_KEY` | yes | — | Anthropic API key |
| `LLM_MODEL` | no | `claude-opus-5-5` | Claude model |
| `LLM_EFFORT` | no | `medium` | Reasoning effort (`low` … `max`) |
| `DATA_REFERENCIA` | no | today | "Today" for deadline calculations (`YYYY-MM-DD`). The data is frozen in 2025–2026, so e.g. `2025-12-08` makes return windows realistic. |

---

## 1. Workflow

1. **Read the e-mail** with the challenge invitation.
2. **Read the challenge instructions** (goals, deliverables and evaluation criteria:
   logic, clarity and initiative).
3. **Read the data, one file at a time**: first the policy manual (PDF), then each CSV.
4. **Renamed only the CSV files** (removed spaces from the file names). Their content —
   191 rows in total across the 6 files — was reviewed but not renamed.
5. **Created a public GitHub repository** dedicated to the project (own `git init`,
   `.gitignore`, `.env.example`, `requirements.txt`, Python virtual environment).
6. **Mapped data inconsistencies** and applied a small set of documented corrections
   (section 3).
7. **Defined the architecture** (section 5) before writing code.

### Store service guidelines (policy manual, pages 6–7)

Pages 6 and 7 of the policy manual (section 7, *Atendimento via WhatsApp*) define the
customer-service guidelines the agent follows:

- **Tone of voice:** informal but professional — "like talking to a friend who knows music".
- **Accurate information:** never state price, stock or delivery time without querying the system.
- **Scope:** the store sells **instruments only**; requests for accessories (strings, cables,
  picks, pedals, amplifiers, cases) must be politely redirected.
- **Standard flow:** greeting → understanding → system lookup → answer → closing.
- **Special situations:** out-of-stock product (suggest alternatives), discontinued product
  (offer equivalents), expired promotion (be transparent, show current price),
  complaint (empathy, register, 24 business-hour follow-up).

---

## 2. Data overview

| File | Rows | Content |
|---|---|---|
| `products.csv` | 65 | Price, stock, status, specs (JSON) |
| `categories.csv` | 9 | Instrument categories |
| `customers.csv` | 49 (originally 50) | Name, phone, e-mail, city |
| `orders.csv` | 20 | Status, total, payment, tracking |
| `order_items.csv` | 22 | Order × product × quantity (no unit price) |
| `promotions.csv` | 25 | Discount % per product (only 4 active) |
| `políticas_da_loja.pdf` | 8 pages | Store policy manual |

---

## 3. Data corrections and inconsistencies

### 3.1 Corrections applied to the data

| File | Issue found | Correction |
|---|---|---|
| `customers.csv` | Duplicate e-mail: customers 11 and 43 both used `bruno.martins@jmail.com` (same name). | Removed the duplicate record (43); customers 44–50 were renumbered to 43–49. No order references customer IDs ≥ 43, so referential integrity is preserved. |
| `products.csv` | Product 96 (Giannini GF-3D) had `status = active` with **0 units in stock**. | Status changed to `discontinued`. |
| `products.csv` | Descriptions of products 93 and 108 (Martin D-28 / D-28E) started with "O lendário…" without naming the instrument type; descriptions of 142 and 143 (keyboards) did not start with the product type either. | Descriptions now start with the instrument type ("Violão…", "Teclado…"), so name/description searches by type are consistent. |

### 3.2 Inconsistencies documented (data not changed)

**Catalog size vs. manual.** The manual says the store has "more than 300 instruments",
but the catalog has 65 products: 35 acoustic guitars (violões), 15 ukuleles, 5 electric
guitars, 4 basses, 3 drums/percussion and 3 keyboards — 62 of them were originally active
(61 after the product 96 change). Three categories (woodwinds, brass, orchestral strings)
have **no products**.
→ The agent only answers from the catalog. "Do you have a saxophone?" must be answered
with "not available at the moment" — never invented.

**Order 3 vs. product 130.** Order 3 is `delivered` and contains product 130
(Kala baritone ukulele), which is currently `coming_soon`.
→ Assumption: order 3 took the last units in stock and the product is now awaiting
restock. Reasonable, since the order was delivered in Dec/2025.

**Order totals differ from the sum of the items.** `order_items.csv` has no unit price,
so the expected total was computed with the current catalog price:

| Order | Items | Sum at catalog price | `total_brl` | Difference |
|---|---|---|---|---|
| 3 | 2 × product 130 (R$ 1,749) | R$ 3,498 | R$ 3,450 | −R$ 48 |
| 20 | 1 × product 107 (R$ 799) + 1 × product 84 (R$ 689) | R$ 1,488 | R$ 1,400 | −R$ 88 |

There is no promotion for these products in `promotions.csv` and the payment methods
(credit card, 12x and 3x) carry no discount per the manual. Possible causes: a price
change after the purchase, an unrecorded discount, or a data error.
→ The agent **always reports the order's `total_brl`** and never recalculates it.
(Order 20 is also `cancelled`.)

**Other points**

- Only 4 of 25 promotions are active (products 127, 121, 90, 94); the agent must never
  promise an expired promotion (policy 7.3).
- The data is frozen in time: the latest order is from 22/03/2026. The reference date for
  deadline calculations (e.g. the 7-day withdrawal right) is configurable.
- 12 orders have no tracking code / estimated delivery — expected, as they were not shipped.
- Product names contain typos (e.g. "Cedr"), so product search is partial and case-insensitive.

### 3.3 Contradictions in the policy manual

| Topic | Contradiction | Assumption |
|---|---|---|
| WhatsApp | (67) 3341-4444 (section 1.2) × (67) 3321-4500 (section 7) | Section 7 is specific to WhatsApp, so (67) 3321-4500 is used for WhatsApp and (67) 3341-4444 as the store phone. |
| E-mail | `contato@emporiodamusica.com.br` (cover) × `contato@empóriodamusica.com.br` (section 1.2) | Use the version without the accent (accented domains are unusual and likely a typo). |
| Installments | Table: minimum installment R$ 100 × section 3.1: tiered (up to 3x free; 4–6x min. R$ 80; 7–12x min. R$ 100) | Follow the detailed rule in section 3.1. |
| Withdrawal right | Applies only to online purchases, but orders do not record the sales channel | Orders in the system are assumed to be online purchases. |

---

## 4. Technical decisions

### RAG or not?

| Source | Decision | Rationale |
|---|---|---|
| Policy manual (PDF, ~4k tokens) | **No RAG** — full text in the system prompt | It fits comfortably in the context window. Many answers combine several sections (returns = 4.1 + 4.2 + 8.1; price = PIX + non-cumulative promotions); retrieving a single chunk could produce a wrong answer. Fewer moving parts; cost mitigated with prompt caching. |
| Data (CSVs) | **Function calling** (Python tools over pandas) | Structured data needs exact filters (price ≤ 1000, category, stock > 0); vector search is approximate. Policy 7.1 requires querying the system before stating price/stock — the tool *is* that query. |

RAG would make sense with a manual of hundreds of pages, or a catalog of thousands of
products requiring semantic search over descriptions ("a good guitar for MPB").

### Token usage: full manual in the prompt vs. RAG

Per call, RAG sends fewer tokens (only the retrieved chunks, ~500–1,000 tokens, versus
~4,000 for the full manual). Over a conversation, however, **prompt caching** changes the
math: the manual is a static prefix, so after the first call it is read from the cache at
~10% of the normal input price. RAG chunks change on every question and barely benefit
from caching.

Rough estimate for a 10-message conversation (~20 model calls, since tool use adds calls):

| Strategy | Policy tokens (input-price equivalent) |
|---|---|
| Full manual, no cache | 20 × 4k = ~80k |
| Full manual, with cache | 1 write (~1.25×) + 19 reads (~0.1×) = **~12–13k** |
| RAG | 20 × ~800 = ~16k + embedding/vector search cost |

With caching, the full-manual approach costs about the same as RAG (or less) and avoids
RAG's main risk here: retrieving an incomplete chunk for questions that span several
sections.

### Scalability: what changes as the store grows

RAG solves **unstructured text**, not structured data, so growth affects each source
differently:

| Source | Today | At scale |
|---|---|---|
| Policy manual | Full text in the system prompt, cached | RAG once it reaches tens of thousands of tokens or many documents (manufacturer manuals, FAQ, support history) |
| Products (filters) | Tool + pandas | Same tool backed by a database (SQL) |
| Products (meaning-based search, e.g. "a good guitar for MPB") | Not needed | **Hybrid**: a new vector-search tool (e.g. pgvector) combined with exact SQL filters (price, stock, status) |
| Customers and orders | Tool + pandas | Tool + database; never RAG (lookups by ID) |

- The catalog never enters the prompt: tools return at most 15 filtered products, so
  token usage per query is the same with 65 or 50,000 products. Only the data backend
  changes (CSV → Postgres), without touching the agent.
- Vector search would be **worse** for structured queries: "guitars under R$ 1,000 in
  stock" needs exact filters, and order lookups are by ID.
- When RAG becomes useful, it is added as **one more tool** the model can choose, not a
  replacement for the existing ones — the architecture stays the same.

### Orders and order items kept as separate files

`orders.csv` and `order_items.csv` are **not merged on disk**. An order has 1..N items,
so a merged file would repeat order-level fields (`total_brl`, status, tracking) on every
item row, which invites double counting and breaks the normalized structure of the source
data. Instead, the two tables are **joined in memory at load time** (pandas `merge`), and
the order lookup tool returns a single object: the order header plus its list of items
with product names.

### No database

With 65 products and 20 orders, pandas in memory is enough, and the evaluator can run the
project with just `pip install` + `python main.py`. In production the data would come from
the store's database.

---

## 5. Architecture

- **Approach:** agent with function calling (the model decides when to call each tool),
  implemented as a manual tool-use loop with the Anthropic Python SDK.
- **Model:** Claude Opus 5.5 (configurable). Server-side refusal fallback enabled
  (`fallbacks: "default"`); prompt caching on the static prefix (tools + instructions + manual).
- **Tools:** `buscar_produtos(nome, categoria, preco_max, apenas_disponiveis)`,
  `consultar_pedido(id_pedido)`, `listar_promocoes(incluir_inativas)`, `listar_categorias()`.
- **Complaints:** there is no complaint-registration system, so Mia does not claim to register
  them; she summarizes the issue and offers every channel (WhatsApp, e-mail, store phone).
- **Policies:** full text of the manual in the system prompt.
- **Interface:** CLI.
- **History:** in-memory list of messages during the session.
- **Files:** `tools.py`, `prompts.py`, `agent.py`, `main.py`, `exemplos/*.md`.

---

## 6. Use of AI assistants

This project was developed with **Claude Code** using the **Claude Opus 5.5** model, one of
the most widely adopted and recognized AI agent tools, both professionally and otherwise.
It was used to review the project setup (git, `.gitignore`, virtual environment),
explore the data and the policy manual, map inconsistencies, discuss the architecture and
write this documentation. All decisions and data corrections were reviewed by the author.

---

## 7. Limitations

_To be completed._
