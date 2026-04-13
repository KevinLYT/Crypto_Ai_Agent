# Blockchain Wallet Security Analysis — Backend & AI Agent (MVP)

**One-liner (English):** A **FastAPI** backend that analyzes **blockchain-style wallet activity** using deterministic feature engineering, optional **OpenAI** reasoning, and a **LangChain tool-calling agent** endpoint for question-driven analysis — all returning **typed JSON** (no bundled frontend).

**一句话（中文）：** 面向实习/作品展示的 **Python 后端项目**：**FastAPI** 提供钱包行为与风险分析；既有 **固定 Pipeline**，也有 **LangChain 工具调用型 Agent**；数据当前为 **mock 交易**（可替换为真实链上数据源），输出 **结构化 JSON**，便于接前端或自动化测试。

**Stack highlights:** `FastAPI` · `Pydantic` · `pytest` · rules + optional `OpenAI` · `LangChain` + `langchain-openai` (single-turn agent, **no LangGraph**)

---

## At a glance / 当前能力一览

| Capability | English | 中文 |
|------------|---------|------|
| **REST API** | `GET /health`, OpenAPI at `/docs` | 健康检查、Swagger UI |
| **Fixed pipeline** | `POST /analyze-wallet` — deterministic steps, **works without OpenAI key** (rules) | 固定流程分析；**无 Key 可走规则** |
| **AI agent** | `POST /agent/analyze-wallet` — LLM chooses tools from a question; **requires valid `OPENAI_API_KEY`** | 单轮工具型 Agent；**必须可用 OpenAI Key** |
| **Data** | Mock ledger from address, or user-provided `mock_transactions` | Mock 或自定义交易列表 |
| **Output** | Pydantic-validated JSON; agent path adds `agent_answer`, `risk_assessment`, `tool_trace` | 强类型 JSON；Agent 路径含自然语言与可观测摘要 |
| **Tests** | `pytest` including agent + formatting stubs (no real LLM required for most tests) | 含 Agent 与格式化单测 |

---

## 1. Overview / 概述

### English

This project analyzes **wallet-style activity** from:

- a **wallet address** (deterministic mock transactions for local demos), or  
- a **custom transaction list** (`mock_transactions`).

It then computes **structured features** and produces **risk-oriented explanations** (rule template and/or OpenAI). A second endpoint exposes a **minimal LangChain agent** that wraps the same primitives as **tools**, so the model can decide **which tools to call** based on a natural-language **question**.

This is an **internship/portfolio-friendly** backend: clear layers, runnable locally, easy to extend toward real chain APIs and richer agents.

### 中文

项目分析 **类链上钱包行为**，输入可以是：

- **钱包地址**（本地自动生成可复现的 mock 交易），或  
- **交易列表** `mock_transactions`。

随后进行 **特征提取** 与 **风险向说明**（规则模板与/或 OpenAI）。另一条路由提供 **LangChain 单轮工具 Agent**：把同一套能力封装为 **tools**，由模型根据用户 **问题** 决定如何调用。  
定位为 **可演示的后端系统**：分层清晰、本地可跑、易扩展到真实链数据与更复杂 Agent。

---

## 2. Project Architecture / 项目架构

### English

**Project overview**  
The service is a **thin API layer** over three concerns: **data access** (mock today), **feature engineering** (pure Python), and **reasoning** (rules + optional LLM, or LangChain agent orchestration). Shared logic lives in `app/services/`; HTTP contracts in `app/models/`.

**Current system architecture (high level)**

```
                    ┌─────────────────────────────────────┐
                    │           FastAPI (app/)            │
                    │  routes.py → services + models      │
                    └─────────────────────────────────────┘
                                         │
           ┌─────────────────────────────┴─────────────────────────────┐
           ▼                                                             ▼
 POST /analyze-wallet                                    POST /agent/analyze-wallet
 (fixed pipeline in Python)                             (LangChain AgentExecutor)
           │                                                             │
           ▼                                                             ▼
 mock_data / wallet_resolve                              agent_tools (3 StructuredTools)
           │                                                             │
           ├──────────────────────────┬─────────────────────────────────┤
           ▼                          ▼                                 ▼
   feature_extraction            ai_analysis                    agent_formatting
   (deterministic stats)    (rules OR OpenAI httpx)         (risk parse, NL answer, summaries)
```

**Data flow — `POST /analyze-wallet` (fixed pipeline)**  
The server **always** runs the same sequence:

1. Resolve data: `mock_transactions` from the client **or** `build_default_mock_transactions(wallet_address)`.  
2. Resolve focal wallet: `resolve_wallet_address` / `infer_wallet_from_transactions`.  
3. `extract_features(wallet, txs)` → `ExtractedFeatures`.  
4. `analyze_wallet_ai(wallet, features)` → `AIAnalysis` (rules if no key; OpenAI with JSON parse + fallback).  
5. Return `AnalyzeWalletResponse`.

There is **no LLM “decision” step** for ordering: the workflow is **explicitly coded**. That makes behavior **predictable**, easy to test, and usable **without** an OpenAI key.

**Data flow — `POST /agent/analyze-wallet` (LangChain agent)**  
1. Client sends `wallet_address` + `question`.  
2. `ChatOpenAI` + `create_tool_calling_agent` + `AgentExecutor` runs **one conversational turn** with tools:  
   - `get_wallet_transactions`  
   - `extract_wallet_features`  
   - `assess_wallet_risk`  
3. The **model** chooses whether/when to call tools (within iteration limits).  
4. Post-processing (`agent_formatting.py`) extracts structured **`risk_assessment`**, builds **`agent_answer`** (natural language), and **`tool_trace`** (short `{tool, summary}` rows).

This is **closer to a real “AI agent”** because **control flow is partly delegated to the LLM** (tool selection / ordering), not fully hard-coded — while still being **single-turn** and **without** LangGraph, RAG, or long-term memory.

### 中文

**项目概述**  
服务在 **数据获取（当前为 mock）**、**特征工程（纯代码）**、**推理（规则 / OpenAI / LangChain 编排）** 三层上组织代码；共享能力在 `app/services/`，接口契约在 `app/models/`。

**当前系统架构（高层）**  
见上文 ASCII 图：左侧为 **固定 Pipeline 路由**，右侧为 **LangChain Agent + 工具 + 后处理**。

**数据流 — `POST /analyze-wallet`（固定 workflow）**  
后端 **写死顺序**：选数据 → 解析主体钱包 → `extract_features` → `analyze_wallet_ai` → 返回 `AnalyzeWalletResponse`。  
**没有**由大模型决定「下一步调用谁」的环节，因此行为 **稳定、可测**；**无 OpenAI Key** 时仍可通过 **规则模板** 返回完整 JSON。

**数据流 — `POST /agent/analyze-wallet`（LangChain agent）**  
客户端提交 **地址 + 自然语言问题**；`AgentExecutor` 在单轮内让模型 **按需调用工具**，再经 **后处理** 输出 **`agent_answer`（可读总结）**、**`risk_assessment`（结构化风险）**、**`tool_trace`（步骤摘要）**。  
这 **更接近真正的 AI Agent**：**工具是否调用、调用顺序** 由 **模型在运行时** 参与决策（在迭代上限内）；但仍为 **单轮** MVP，无 LangGraph / 向量库 / 会话记忆。

---

## 3. API Endpoints / 接口说明

### `POST /analyze-wallet` — fixed pipeline

| Aspect | English | 中文 |
|--------|---------|------|
| **Orchestration** | Fully **deterministic** in Python (`routes.py` → services). | **固定编排**，不依赖 Agent 决策。 |
| **OpenAI** | Optional: with key → OpenAI JSON analysis; without key → **rules only**; failures fall back to rules. | **无 Key 可走规则**；有 Key 可走模型并可回退规则。 |
| **Best for** | Baselines, CI, demos without LLM spend, predictable JSON. | 基线、CI、不想消耗 Token 的演示。 |
| **Response** | `wallet_address`, `extracted_features`, `ai_analysis` | 特征 + `ai_analysis` 结构化风险 |

### `POST /agent/analyze-wallet` — LangChain tool-calling agent

| Aspect | English | 中文 |
|--------|---------|------|
| **Orchestration** | **LLM-driven tool use** inside `AgentExecutor` (single turn). | **模型驱动**工具调用（单轮）。 |
| **OpenAI** | **Required:** valid `OPENAI_API_KEY` for tool-calling + final message. Missing key → **HTTP 503** with clear `detail`. | **必须可用 Key**；缺失则 **503** 说明原因。 |
| **Best for** | Natural-language Q&A (“Is this suspicious?”), portfolio “agent” story. | 自然语言问答、作品里体现 Agent。 |
| **Response** | `wallet_address`, `question`, **`agent_answer`**, **`risk_assessment`**, `extracted_features` (nullable), **`tool_trace`**, `error` (optional) | 见下一节字段语义 |

---

## 4. Response fields / 响应字段（展示 vs 绑定 vs 可观测）

### `POST /analyze-wallet`

| Field | Use case | 说明 |
|-------|----------|------|
| **`extracted_features`** | Frontend charts / tables; deterministic | 纯代码计算，适合 **图表与表格** |
| **`ai_analysis`** | Badges, bullet lists, drill-down | 与 Agent 的 `risk_assessment` **同构**（结构化风险） |

### `POST /agent/analyze-wallet`

| Field | English | 中文 | Typical use |
|-------|---------|------|---------------|
| **`agent_answer`** | Short **natural-language** answer for chat UI / report intro. | **用户可读**的一段话 | **User-facing display** |
| **`risk_assessment`** | Same shape as `ai_analysis`: `wallet_summary`, `risk_level`, `risk_reasons`, `unusual_patterns`, `suggested_followup`. | **结构化风险对象**（便于组件绑定） | **Frontend components**, tests, analytics |
| **`extracted_features`** | Present when the extraction tool ran; else `null`. | 提特征工具执行过则有值 | **Metrics widgets** |
| **`tool_trace`** | List of `{ "tool", "summary" }` — concise, no huge raw JSON. | **步骤摘要**，便于演示/排错 | **Debug / observability**, “advanced” panel |

**Why separate `agent_answer` and `risk_assessment`?**  
Structured data is stable for **UI binding and regression tests**; natural language is optimized for **humans** and avoids showing escaped JSON when the model echoes tool output.

---

## 5. Directory Structure / 目录结构

```
crypto_ai_agent/
  app/
    main.py                 # FastAPI entry
    api/
      routes.py             # POST /analyze-wallet, POST /agent/analyze-wallet, GET /health
    services/
      mock_data.py          # Default mock ledger (replace with chain client later)
      feature_extraction.py # Transactions → numeric / behavioral features
      wallet_resolve.py     # Infer focal address when only mocks are sent
      ai_analysis.py        # Rules + OpenAI (httpx), fallback on errors
      agent_tools.py        # LangChain tools wrapping mock/features/risk services
      agent_runner.py       # Minimal tool-calling agent runner (LangChain)
      agent_formatting.py   # Post-process: risk parsing, tool summaries, NL answer
    models/
      schemas.py            # Pydantic: Transaction, request/response models
      agent_schemas.py      # Agent API request/response models
  utils/
    config.py               # Env-based settings (thresholds, OpenAI)
  data/
    sample_mock_transactions.json   # Field reference
    analyze_wallet_request.example.json  # Full request body example
  tests/
    test_api.py
    test_feature_extraction.py
    test_agent_api.py
    test_agent_formatting.py
    conftest.py
  requirements.txt
  .env.example
```

---

## 6. Module Breakdown / 模块拆解

| Module | English | 中文 |
|--------|---------|------|
| **`app/api/routes.py`** | HTTP entry: validate body, orchestrate services, map errors to HTTP. | **控制器**：接请求、走业务流程、返回响应。 |
| **`app/services/feature_extraction.py`** | Computes totals, in/out flows, large-tx counts, counterparties, high-frequency heuristics. | **数据 → 特征**：统计 + 简单行为启发式。 |
| **`app/services/ai_analysis.py`** | No `OPENAI_API_KEY` → rule template; with key → Chat Completions + JSON parse; failures fall back to rules. | **特征 → 解释**：规则兜底 + 可选 LLM。 |
| **`app/services/mock_data.py`** | Builds a small deterministic mock history for demos. | **替代链上数据**，便于本地与 CI。 |
| **`app/services/wallet_resolve.py`** | If only mocks: infer “main” address by frequency; explicit `wallet_address` wins. | **解析分析主体**（MVP 启发式）。 |
| **`app/services/agent_tools.py`** | LangChain `StructuredTool` definitions wrapping existing services. | Agent **工具封装**，复用现有逻辑。 |
| **`app/services/agent_runner.py`** | `AgentExecutor`, prompts, calls formatting layer. | Agent **执行器**。 |
| **`app/services/agent_formatting.py`** | Parses `risk_assessment`, builds `agent_answer`, summarizes `tool_trace`. | **产品化后处理**。 |
| **`app/models/schemas.py`** | Core domain + `/analyze-wallet` contracts. | **核心 Schema**。 |
| **`app/models/agent_schemas.py`** | `/agent/analyze-wallet` request/response. | **Agent 接口契约**。 |
| **`utils/config.py`** | Loads `.env` (OpenAI, thresholds). | **环境变量与可调参数**。 |

---

## 7. Why This Architecture / 为什么这样设计

### English

Layers separate **data ingestion**, **feature engineering**, and **reasoning**. You can swap mock ingestion for a chain adapter, add retrieval before prompts, or add tools — **without** deleting the stable `/analyze-wallet` contract.

### 中文

把 **数据准备、特征、分析** 拆开：接真实链时主要换数据源；加 RAG 时在进模型前拼检索；Agent 路径独立演进，**不破坏**固定 Pipeline 的稳定性。

---

## 8. Environment & Config / 环境与配置

**Python:** 3.9+（推荐 3.11/3.12；已在 3.9 下跑通测试。）

### Install / 安装依赖

**pip**

```bash
cd crypto_ai_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**uv（可选）**

```bash
cd crypto_ai_agent
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

### Env file / 环境变量

```bash
cp .env.example .env
```

| Variable | English | 中文 |
|----------|---------|------|
| `OPENAI_API_KEY` | **Empty:** `/analyze-wallet` uses **rules** for `ai_analysis`; `/agent/analyze-wallet` returns **503** (agent requires a key). **Set:** enables OpenAI paths where configured. | 留空：固定接口走规则；**Agent 接口不可用**。填写：按模块启用模型调用。 |
| `OPENAI_BASE_URL` | OpenAI-compatible API base URL. | 默认 `https://api.openai.com/v1`。 |
| `OPENAI_MODEL` | e.g. `gpt-4o-mini`. | 模型名。 |
| `LARGE_TX_MULTIPLIER`, etc. | Tune heuristics (see `utils/config.py`). | 调节特征阈值。 |

After editing `.env`, **restart** uvicorn (`get_settings` uses `lru_cache`).

---

## 9. Run the Server / 启动服务

**Always run commands from the `crypto_ai_agent` directory** so imports like `app` and `utils` resolve correctly.

```bash
cd crypto_ai_agent
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive API docs (Swagger UI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
- **交互式文档：** 浏览器打开 `http://127.0.0.1:8000/docs` 即可在线试接口。

---

## 10. Quick Walkthrough / 手把手演示

### English

1. **Start the server** (see **Section 9**). Confirm `GET /health` returns `{"status":"ok"}` (optional sanity check).  
2. **Open Swagger:** go to `http://127.0.0.1:8000/docs`.  
3. **Test fixed pipeline — `POST /analyze-wallet`:**  
   - Click **POST `/analyze-wallet`** → **Try it out**.  
   - Use a minimal JSON body (address-only mock):

```json
{
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
}
```

   - Click **Execute**.  
   - **What to look at:** `extracted_features` (numbers from code), `ai_analysis.risk_level`, lists under `risk_reasons` / `suggested_followup`.  
4. **Test LangChain agent — `POST /agent/analyze-wallet`:**  
   - Ensure `.env` has a **valid** `OPENAI_API_KEY`, then restart uvicorn.  
   - Click **POST `/agent/analyze-wallet`** → **Try it out**.  
   - Example body:

```json
{
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "question": "Is this wallet suspicious?"
}
```

5. **Suggested example questions (copy/paste):**  
   - `Is this wallet suspicious?`  
   - `What are the main risks of this wallet?`  
   - `What should I investigate next?`  
6. **What to look at in the agent response:**  
   - **`agent_answer`** — should read like a short paragraph, not escaped JSON.  
   - **`risk_assessment`** — structured object (same idea as `ai_analysis`).  
   - **`tool_trace`** — a few `{tool, summary}` lines describing what happened.  
   - **`extracted_features`** — populated if the agent ran the feature tool.  
7. **If agent returns 503:** missing/empty `OPENAI_API_KEY` — fix `.env` and restart; `/analyze-wallet` should still work with rules.

### 中文

1. **启动服务**（见上文 **第 9 节**）。可选：访问 `GET /health` 确认 `{"status":"ok"}`。  
2. **打开文档：** 浏览器访问 `http://127.0.0.1:8000/docs`。  
3. **测试固定 Pipeline — `POST /analyze-wallet`：**  
   - 展开 **POST `/analyze-wallet`** → **Try it out**。  
   - 请求体示例（仅地址，后端自动生成 mock）：

```json
{
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
}
```

   - 点击 **Execute**。  
   - **重点看：** `extracted_features` 数值字段；`ai_analysis.risk_level`；`risk_reasons`、`suggested_followup` 列表。  
4. **测试 LangChain Agent — `POST /agent/analyze-wallet`：**  
   - `.env` 配置 **可用** 的 `OPENAI_API_KEY` 后 **重启** uvicorn。  
   - 展开 **POST `/agent/analyze-wallet`** → **Try it out**。  
   - 示例请求体：

```json
{
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "question": "这个钱包可疑吗？"
}
```

5. **建议尝试的问题（2～3 个）：**  
   - `Is this wallet suspicious?`  
   - `What are the main risks of this wallet?`  
   - `What should I investigate next?`（或中文等价问法）  
6. **Agent 返回里建议重点观察：**  
   - **`agent_answer`**：是否像 **自然段落**，而不是一整段转义 JSON。  
   - **`risk_assessment`**：是否为 **结构化对象**（风险等级、列表字段齐全）。  
   - **`tool_trace`**：是否每条只有 **`tool` + `summary`**，摘要是否可读。  
   - **`extracted_features`**：若 Agent 调用了提特征工具，应出现完整特征对象。  
7. **若返回 503：** 多为未配置或无效 `OPENAI_API_KEY`；可先使用 `/analyze-wallet` 验证规则路径仍正常。

---

## 11. API (curl) / 命令行调用

**Fixed pipeline — address only / 固定流程 — 仅地址**

```bash
curl -s http://127.0.0.1:8000/analyze-wallet \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"}' | python3 -m json.tool
```

**Fixed pipeline — custom mocks / 固定流程 — 自定义 mock**

```bash
curl -s http://127.0.0.1:8000/analyze-wallet \
  -H "Content-Type: application/json" \
  -d @data/analyze_wallet_request.example.json | python3 -m json.tool
```

`data/sample_mock_transactions.json` is a minimal field sample; use `analyze_wallet_request.example.json` for a full valid body.

**LangChain agent / LangChain 智能体（需要可用 `OPENAI_API_KEY`）**

```bash
curl -s http://127.0.0.1:8000/agent/analyze-wallet \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb","question":"Is this wallet suspicious?"}' \
  | python3 -m json.tool
```

---

## 12. Switch Rules → OpenAI / 切换到 OpenAI

1. Set `OPENAI_API_KEY` in `.env`.  
2. Restart uvicorn.  
3. **`/analyze-wallet`:** `analyze_wallet_ai` automatically uses OpenAI when the key is set, with rule fallback on errors.  
4. **`/agent/analyze-wallet`:** requires the key for LangChain tool-calling; no key → **503**.  

For OpenAI-compatible gateways, adjust `OPENAI_BASE_URL` and `OPENAI_MODEL` per provider docs.

---

## 13. Tests / 测试

```bash
cd crypto_ai_agent
source .venv/bin/activate
pytest -q
```

**What the tests cover / 测试覆盖说明**

| File | English | 中文 |
|------|---------|------|
| `tests/test_api.py` | Health + `/analyze-wallet` smoke | 健康检查与固定接口冒烟 |
| `tests/test_feature_extraction.py` | Feature extraction correctness | 特征提取逻辑 |
| `tests/test_agent_api.py` | Agent validation (422), missing key (**503** + clear `detail`), stubbed **200** schema (`risk_assessment` object, `tool_trace` shape, `agent_answer` not JSON-shaped) | Agent 路由、无 Key、stub  schema |
| `tests/test_agent_formatting.py` | Parsing, tool summaries, NL answer **without** calling OpenAI | 格式化与后处理单测 |
| `tests/conftest.py` | Clears `get_settings` cache between tests | 避免环境变量缓存串味 |

Run from `crypto_ai_agent` so imports resolve the same way as uvicorn.

---

## 14. Implementation Data Flow (reference) / 实现级数据流（参考）

**`/analyze-wallet`**

1. `routes.analyze_wallet` validates the body.  
2. Data: `mock_transactions` **or** `build_default_mock_transactions(address)`.  
3. `extract_features(wallet, txs)`.  
4. `analyze_wallet_ai`: no key → rules; with key → OpenAI JSON → on failure → rules.  
5. Return `AnalyzeWalletResponse`.

**`/agent/analyze-wallet`**

1. `routes.agent_analyze_wallet` validates `AgentAnalyzeWalletRequest`.  
2. `run_wallet_agent` builds LangChain tools + executor, awaits `ainvoke`.  
3. `agent_formatting` derives `risk_assessment`, `agent_answer`, `tool_trace`; returns `AgentAnalyzeWalletResponse`.

---

## 15. Current Status / 当前状态

### English

- **Production-ready?** No — MVP / demo scope (mock data, simple heuristics).  
- **Demonstrable?** Yes — recruiters/engineers can run locally, hit `/docs`, and compare **pipeline vs agent** in minutes.  
- **Extension-ready:** swap mock ingestion, add chain/label tools, optional RAG — without throwing away the API shape.

### 中文

- **非生产级**：mock 数据 + 启发式规则，仅作原型。  
- **可展示性强**：本地可跑、Swagger 可点、**双模式（Pipeline / Agent）** 一条线讲清楚。  
- **可扩展**：替换数据源、加链上工具、加检索增强等，接口层可渐进演进。

---

## 16. Roadmap / 下一步（优先级）

1. **Real blockchain API** — `services/chain/…`, caching, rate limits.  
2. **Embeddings / retrieval** — vector store + top-k context in prompt (light RAG).  
3. **Richer agent tools** — labels, graph metrics, exchange heuristics; policies for multi-step (still **no LangGraph** unless you explicitly choose to add it later).

---

## 17. FAQ / 常见问题

**`ImportError: No module named 'utils'`**  
Work in `crypto_ai_agent` and run `uvicorn app.main:app`.

**OpenAI errors on `/analyze-wallet` but you still get JSON**  
By design: errors fall back to the rule engine; check server logs.

**`/agent/analyze-wallet` returns 503**  
Configure a valid `OPENAI_API_KEY` and restart. The message in `detail` explains this path.

**Wrong inferred wallet when only mocks are sent**  
MVP uses “most frequent address”; production clients should pass `wallet_address`.

---

## 18. License / 许可证

MIT（可按需修改；作品展示建议附上你自己的 LICENSE 说明。）
