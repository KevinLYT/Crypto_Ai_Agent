# Blockchain Wallet Security Analysis AI Agent (MVP)

**English:** A local, runnable backend-first prototype for wallet behavior and risk-oriented analysis. It returns structured JSON only (no frontend).  
**中文：** 本地可运行的钱包行为分析 MVP，定位为 **后端优先的 AI 应用原型**，非生产级完整产品。输入地址（自动 mock）或自定义交易列表，输出结构化 JSON；无 OpenAI Key 时用规则模板，有 Key 时走 HTTP 调用并可失败回退。

---

## 1. Overview / 概述

### English

This project analyzes blockchain-style **wallet activity** from either:

- a **wallet address** (internally uses generated mock transactions), or  
- a **custom list of transactions** (`mock_transactions`).

It then:

1. extracts structured behavioral features  
2. produces a risk-oriented narrative (rule-based or OpenAI)  
3. returns a **typed JSON** response  

External dependencies such as real chain APIs or vector databases are **not required** in this phase, so the repo stays simple, testable, and easy to extend toward RAG, retrieval, and agent-style toolchains.

### 中文

系统支持两种输入：

- **钱包地址**：不查真实链，自动使用内置 mock 交易。  
- **交易列表**：直接传入 `mock_transactions`（可同时传 `wallet_address` 指定分析主体）。

整体流程：

1. 提取结构化行为特征  
2. 生成风险向的分析说明（规则或 OpenAI）  
3. 返回标准 **JSON**（Pydantic 校验）

当前版本**不接真实链**，目的是架构清晰、易于调试与扩展（后续可接链上 API、向量库、Agent）。

---

## 2. System Flow / 系统流程

```
Client Request
    → FastAPI  POST /analyze-wallet
    → Data source (user mock_transactions OR default mock from address)
    → Feature extraction  (feature_extraction.py)
    → AI analysis         (ai_analysis.py: rules OR OpenAI)
    → JSON response     (wallet_address + extracted_features + ai_analysis)
```

**中文对照：** 客户端请求 → 路由 → 选数据源 → 特征计算 → AI 分析 → 结构化 JSON。

---

## 3. Directory Structure / 目录结构

```
crypto_ai_agent/
  app/
    main.py                 # FastAPI entry
    api/
      routes.py             # POST /analyze-wallet, GET /health
    services/
      mock_data.py          # Default mock ledger (replace with chain client later)
      feature_extraction.py # Transactions → numeric / behavioral features
      wallet_resolve.py     # Infer focal address when only mocks are sent
      ai_analysis.py        # Rules + OpenAI (httpx), fallback on errors
    models/
      schemas.py            # Pydantic: Transaction, request/response models
  utils/
    config.py               # Env-based settings (thresholds, OpenAI)
  data/
    sample_mock_transactions.json   # Field reference
    analyze_wallet_request.example.json  # Full request body example
  tests/
    ...
  requirements.txt
  .env.example
```

---

## 4. Module Breakdown / 模块拆解

| Module | English | 中文 |
|--------|---------|------|
| **`app/api/routes.py`** | HTTP entry: validate body, orchestrate services, map errors to HTTP. | **控制器**：接请求、走业务流程、返回响应。 |
| **`app/services/feature_extraction.py`** | Computes totals, in/out flows, large-tx counts, counterparties, high-frequency heuristics. | **数据 → 特征**：统计 + 简单行为启发式。 |
| **`app/services/ai_analysis.py`** | No `OPENAI_API_KEY` → rule template; with key → Chat Completions + JSON parse; failures fall back to rules. | **特征 → 解释**：规则兜底 + 可选 LLM。 |
| **`app/services/mock_data.py`** | Builds a small deterministic mock history for demos. | **替代链上数据**，便于本地与 CI。 |
| **`app/services/wallet_resolve.py`** | If only mocks: infer “main” address by frequency; explicit `wallet_address` wins. | **解析分析主体**（MVP 启发式）。 |
| **`app/models/schemas.py`** | Request/response and `Transaction` shapes for OpenAPI + validation. | **接口契约 / Schema**。 |
| **`utils/config.py`** | Loads `.env` (OpenAI, thresholds). | **环境变量与可调参数**。 |

---

## 5. Why This Architecture / 为什么这样设计

### English

Layers separate **data ingestion**, **feature engineering**, and **reasoning**. You can later swap mock ingestion for a chain adapter, add embeddings and retrieval before the LLM step, or wrap chain/tag lookups as **tools** in an agent workflow—without rewriting the whole API surface.

### 中文

把 **数据准备、特征、分析** 拆开：接真实链时主要换数据源模块；加 RAG 时在进 LLM 前拼检索片段；升级 Agent 时把「查链 / 查标签」做成 tools，路由层仍可保持 `/analyze-wallet` 或并行新端点。

---

## 6. Environment & Config / 环境与配置

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
| `OPENAI_API_KEY` | Empty → rules only. Set → OpenAI call. | 留空走规则；填写则调用模型。 |
| `OPENAI_BASE_URL` | Default OpenAI-compatible base URL. | 默认 `https://api.openai.com/v1`。 |
| `OPENAI_MODEL` | e.g. `gpt-4o-mini`. | 模型名。 |
| `LARGE_TX_MULTIPLIER`, etc. | Tune heuristics (see `utils/config.py`). | 调节特征阈值。 |

After editing `.env`, **restart** uvicorn (`get_settings` uses `lru_cache`).

---

## 7. Run the Server / 启动服务

**Run from the `crypto_ai_agent` directory** so `app` and `utils` import correctly.

```bash
cd crypto_ai_agent
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 8. Quick Walkthrough (Swagger) / 手把手（文档 UI）

1. In `/docs`, open **POST `/analyze-wallet`** → **Try it out**.  
2. Request body example (address only → internal mock):

```json
{
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
}
```

3. Click **Execute**.  
4. **English:** The route loads mock txs, runs feature extraction, then rule-based or OpenAI analysis.  
   **中文：** 后端生成 mock → 算特征 → 生成分析 → 返回 JSON。

**What you get / 返回结构**

- **`extracted_features`** — numeric features computed by code.  
- **`ai_analysis`** — structured explanation (`wallet_summary`, `risk_level`, `risk_reasons`, `unusual_patterns`, `suggested_followup`).

---

## 9. API (curl) / 命令行调用

**Address only / 仅地址**

```bash
curl -s http://127.0.0.1:8000/analyze-wallet \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"}' | python3 -m json.tool
```

**Custom mocks / 自定义 mock**

```bash
curl -s http://127.0.0.1:8000/analyze-wallet \
  -H "Content-Type: application/json" \
  -d @data/analyze_wallet_request.example.json | python3 -m json.tool
```

`data/sample_mock_transactions.json` is a minimal field sample; use `analyze_wallet_request.example.json` for a full valid body.

---

## 10. Switch Rules → OpenAI / 切换到 OpenAI

1. Set `OPENAI_API_KEY` in `.env`.  
2. Restart uvicorn.  
3. No code change: `app/services/ai_analysis.py` → `analyze_wallet_ai` selects the path automatically.  
For OpenAI-compatible gateways, adjust `OPENAI_BASE_URL` and `OPENAI_MODEL` per provider docs.

---

## 11. Tests / 测试

```bash
cd crypto_ai_agent
source .venv/bin/activate
pytest -q
```

---

## 12. Implementation Data Flow / 实现级数据流

1. `routes.analyze_wallet` receives the body.  
2. Data source: user `mock_transactions` **or** `build_default_mock_transactions(address)`.  
3. `extract_features(wallet, txs)`.  
4. `analyze_wallet_ai`: no key → rules; with key → OpenAI JSON → on failure → rules.  
5. Return `AnalyzeWalletResponse`.

---

## 13. Current Status / 当前状态

### English

- Runnable FastAPI backend  
- Clear module boundaries for portfolio / internship demos  
- Ready for: real chain adapters, embeddings, agent tools  

### 中文

- 可运行后端 + OpenAPI 文档  
- 分层清晰，适合作为作品/实习展示原型  
- 已预留扩展点（链上客户端、RAG、Agent）

---

## 14. Roadmap / 下一步（优先级）

1. **Real blockchain API** — `services/chain/…`, caching, rate limits.  
2. **Embeddings / retrieval** — vector store + top-k context in prompt (light RAG).  
3. **Agent workflow** — explicit tools (chain, labels, graph, news); add orchestration when needed.

---

## 15. FAQ / 常见问题

**`ImportError: No module named 'utils'`**  
Work in `crypto_ai_agent` and run `uvicorn app.main:app`.

**OpenAI errors but you still get JSON**  
By design: errors fall back to the rule engine; check server logs.

**Wrong inferred wallet when only mocks are sent**  
MVP uses “most frequent address”; production clients should pass `wallet_address`.

---

## 16. License / 许可证

MIT（可按需修改；作品展示建议附上你自己的 LICENSE 说明。）
