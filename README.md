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
git clone https://github.com/Alebeiruth/test-emporio-musica-agent.git
cd test-emporio-musica-agent
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate       # Linux/macOS
pip install -r requirements.txt
cp .env.example .env              # then set LLM_API_KEY in .env
streamlit run app.py              # web chat interface (opens in the browser)
python main.py                    # terminal chat (type "sair" to exit)
python main.py --debug            # also shows tool calls and prompt-cache usage
python main.py --salvar exemplos/minha_conversa.md   # saves the conversation as Markdown
```

Scripted conversations can be replayed from a file:
`python main.py --salvar exemplos/01_preco_e_pagamento.md < exemplos/roteiros/01_preco_e_pagamento.txt`

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
- Orders 9 (R$ 349.90 in 6x) and 16 (R$ 429.90 in 6x) break the installment rule of section
  3.1 (4x–6x requires a minimum installment of R$ 80). They are historical records, so they
  were kept as they are; for new quotes the agent applies the rule (see "Payment calculation").

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
- **Payment calculation:** PIX price and maximum interest-free installments are computed in
  Python (`condicoes_pagamento` in `emporio/tools.py`) and returned with each product, so the model
  never does the arithmetic. This was added after an early test where the model generalized
  "up to 6x" to products that, by section 3.1, only allow 5x. Rules: PIX 5% not cumulative
  with promotions; up to 3x with a minimum installment of R$ 50 (interpretation of "no minimum,
  except below R$ 50"); 4x–6x minimum R$ 80; 7x–12x minimum R$ 100.
- **Policies:** full text of the manual in the system prompt.
- **Interfaces:** web chat (Streamlit, `app.py`) and terminal (`main.py`), both on top of the
  same core package — the interfaces only handle input/output.
- **Visual standard:** since the real channel is WhatsApp, Mia writes with WhatsApp formatting
  and a fixed style guide (defined in `emporio/prompts.py`): `*bold*` only for product names, prices,
  deadlines, order numbers and contacts; `• ` bullet lists with at most 6 items; prices as
  `R$ 1.234,56`; at most 2 emojis per message; short paragraphs ending with a question. The
  CLI renders `*bold*` as terminal bold, and saved transcripts convert it to Markdown bold.
- **History:** in-memory list of messages during the session.
- **Project structure:**

```
app.py                 web interface (Streamlit)
main.py                terminal interface (CLI, --debug, --salvar)
emporio/               core package, independent of the interface
  tools.py             data tools over the CSVs + tool definitions for the model
  prompts.py           Mia's persona, rules and the full policy manual (read from the PDF)
  agent.py             agent loop with Claude (function calling)
  formatacao.py        visual standard (WhatsApp *bold*) for terminal, Markdown and web
data/                  CSVs and policy manual (source data)
exemplos/              example conversations (.md) and their input scripts (roteiros/)
```

---

## 6. Use of AI assistants

This project was developed with **Claude Code** using the **Claude Opus 5.5** model, one of
the most widely adopted and recognized AI agent tools, both professionally and otherwise.
It was used to review the project setup (git, `.gitignore`, virtual environment),
explore the data and the policy manual, map inconsistencies, discuss the architecture
(including the RAG trade-off), implement the code, run and review the example conversations,
and write this documentation. Product decisions (Mia's name, offering every contact channel
for complaints, the visual standard, the example scenarios) and data corrections came from
the author, and every step was reviewed by the author. Errors found while reviewing the
examples (input encoding on Windows, installment generalization) were fixed in the code
rather than by editing the transcripts.

---

## 7. Example conversations

Real conversations generated with `python main.py --salvar` (reference date 25/03/2026, right
after the last order in the data). Each transcript shows which tools Mia called. The input
scripts are in `exemplos/roteiros/` and can be replayed.

| # | File | Scenario | What it shows |
|---|---|---|---|
| 1 | [01_preco_e_pagamento](exemplos/01_preco_e_pagamento.md) | Price of the Takamine GD20, PIX, 10x, shipping | Data lookup + payment and shipping policies |
| 2 | [02_violao_iniciante](exemplos/02_violao_iniciante.md) | Beginner guitar up to R$ 1,000, then nylon for MPB | Filtered search and recommendation |
| 3 | [03_loja_e_entrega](exemplos/03_loja_e_entrega.md) | Address, opening hours, delivery to Dourados | Policy-only answers (no tool calls) |
| 4 | [04_promocoes](exemplos/04_promocoes.md) | Expired Black Friday, active promotions, PIX + promotion | Expired promotion handling, non-cumulative discounts |
| 5 | [05_fora_do_escopo](exemplos/05_fora_do_escopo.md) | Strings/amplifier, saxophone, football | Accessories redirect, empty category, off-topic |
| 6 | [06_reclamacao](exemplos/06_reclamacao.md) | **Complaint:** ukulele with a warped neck (order 7) | Non-trivial: crosses order data, 30-day exchange, 90-day legal warranty and contact channels |
| 7 | [07_informacao_pedido](exemplos/07_informacao_pedido.md) | **Information request:** late order 8, then order 14 | Overdue delivery, tracking, pending order |
| 8 | [08_tentativa_manipulacao](exemplos/08_tentativa_manipulacao.md) | **Manipulation attempt:** prompt injection, fake manager, system prompt extraction, fake promotion | Guardrails: no invented discounts, no customer data (LGPD), no prompt disclosure |

---

## 8. Limitations

- **No real actions:** Mia cannot register complaints, open delivery investigations, reserve
  products or place orders. She explains this and points the customer to WhatsApp, e-mail or
  phone.
- **No customer authentication:** anyone who knows an order number can see its status, items
  and the customer's first name. Defense in depth: the order tool never returns phone, e-mail
  or city, so the model cannot leak them even if manipulated. In production, orders would be
  checked against the WhatsApp number of the sender.
- **Receipt date is an assumption:** the data has no actual delivery date, so the estimated
  delivery date is used for return windows.
- **Frozen data and reference date:** deadlines depend on `DATA_REFERENCIA`; with today's date,
  every order is outside every return window.
- **Business hours are not enforced:** the manual says WhatsApp outside business hours gets an
  automatic reply; the prototype answers at any time (it only informs the hours).
- **Shipping cost is not calculated:** the manual says it depends on ZIP code, weight and size,
  which are not in the data; Mia gives delivery times and the free-shipping rule only.
- **In-memory history, single session:** the conversation is lost when the program ends; long
  sessions are not compacted.
- **LLM non-determinism:** wording varies between runs, and the model may still make mistakes
  on reasoning not backed by a tool. Critical numbers (prices, stock, installments, order
  totals) come from tools to reduce that risk. There is no automated eval suite — the
  scenarios in `exemplos/` were checked manually.
- **CLI only:** no WhatsApp integration or web interface.

### With more time

- WhatsApp integration (webhook) and customer identification by phone number.
- Tools for actions: open a complaint ticket, request a return, notify when a product is back
  in stock.
- An automated eval set from the example scenarios (expected tool calls + rubric).
- Database backend (Postgres) and, for a large catalog, hybrid semantic search (see
  "Scalability").
