# Crypto AI Agent Interview Preparation

基于代码库整理：`/Users/kevinlee/Desktop/Crypto_AI_Agent/crypto_ai_agent`

说明：
- 本文档基于当前项目真实代码整理。
- 若涉及未来扩展或生产化方向，会明确写成“基于代码的推断”。
- 目标不是背稿，而是帮助你把回答讲得自然、清楚、有工程感。

## 1. Why keep both `/analyze-wallet` and `/agent/analyze-wallet`?

### 中文问题
为什么这个项目要同时保留 `/analyze-wallet` 和 `/agent/analyze-wallet` 两个接口？

### English Question
Why does the project keep both `/analyze-wallet` and `/agent/analyze-wallet` instead of using just one endpoint?

### 中文回答
我保留这两个接口，不是因为历史包袱，而是因为它们服务的是两类不同需求。

`/analyze-wallet` 是固定 pipeline，它的特点是确定性强、成本低、输出稳定，而且即使没有 OpenAI key 也可以通过规则分析正常返回结果。所以它更像系统的基础分析链路，适合做标准化风险输出、测试和后续生产化扩展。

`/agent/analyze-wallet` 则是自然语言交互层。它把取交易、特征提取、风险评估封装成工具，让模型根据用户问题决定调用哪些工具、按什么顺序调用。所以它更灵活，更适合问答式场景和展示 Agent 能力，但成本和不确定性也更高。

所以这两个接口分别代表两种能力：
- 固定 pipeline 负责稳定分析
- Agent 接口负责智能编排和自然语言交互

一句话总结就是：一个偏 production baseline，一个偏 AI interaction layer。

### English Answer
I keep both endpoints because they serve different goals.

`/analyze-wallet` is the deterministic pipeline. It is stable, lower-cost, easier to test, and it still works without an OpenAI key because it can fall back to rule-based analysis. So it acts as the system's baseline analysis path.

`/agent/analyze-wallet` is the natural-language interaction layer. It wraps transaction loading, feature extraction, and risk assessment as tools, and lets the model decide which tools to call and in what order based on the user's question. That makes it more flexible, but also more expensive and less predictable.

So the two endpoints represent two different capabilities:
- the fixed pipeline for stable analysis
- the agent endpoint for intelligent orchestration and question-driven interaction

In one sentence: one is the production-style baseline, and the other is the AI interaction layer.

## 2. What is the real core of the project?

### 中文问题
这个项目真正的核心模块是什么？为什么？

### English Question
What is the real core module of the project, and why?

### 中文回答
我认为这个项目真正的核心不是 OpenAI，也不是 LangChain，而是固定分析 pipeline，尤其是 feature extraction 这一层。

原因是这层定义了整个系统真正依赖的数据抽象。原始交易数据进入系统之后，并不会直接交给模型，而是先被转换成一组结构化特征，比如总交易数、流入流出、净流量、大额交易次数、独立对手方数量和高频行为标记。

后面的规则分析、LLM 分析，甚至 Agent tools，本质上都在复用这层产出的结果。也就是说，这一层才是整个系统的公共基础能力。

如果把 OpenAI 去掉，这个项目仍然能跑；如果把 Agent 去掉，这个项目仍然成立；但如果没有 feature extraction 和固定 pipeline，整个项目就只剩下一个很薄的 LLM demo。

### English Answer
The real core of the project is not OpenAI and not LangChain. It is the fixed analysis pipeline, especially the feature extraction layer.

That layer defines the actual data abstraction used by the whole system. Instead of feeding raw transactions directly into the model, the system first converts them into structured features such as total transactions, inflow/outflow, net flow, large transaction count, unique counterparties, and high-frequency flags.

The rule engine, the LLM-based analysis, and even the agent tools all depend on that same feature layer. So this is the shared foundation of the system.

If we remove OpenAI, the project still works. If we remove the agent, the project still works. But if we remove feature extraction and the fixed pipeline, the project becomes just a thin LLM demo.

## 3. Why not send raw transactions directly to the LLM?

### 中文问题
为什么不让大模型直接读取所有原始交易明细，而要先做 feature extraction？

### English Question
Why not let the LLM read all raw transaction records directly? Why add feature extraction first?

### 中文回答
我先做 feature extraction，核心是为了降噪、结构化和可控。

原始交易明细对 LLM 有几个问题。第一，噪声比较大，很多字段对当前风险判断并不直接有帮助。第二，原始数据量一大，token 成本会上升，响应速度也会变差。第三，模型直接读原始明细时，输出更容易不稳定，不利于回归测试和前端消费。

所以我先把交易压缩成结构化统计特征，让模型看到的是一个更精炼、更可解释的输入空间。这样做有三个好处：
- 降低 token 成本
- 提高分析输入的一致性
- 让规则引擎和 LLM 可以共用同一套输入契约

所以这不是单纯为了“省钱”，更重要的是把系统做成工程上更稳定、可替换、可测试的结构。

### English Answer
I add feature extraction first for three reasons: denoising, structuring, and control.

Raw transaction records create several problems for an LLM. They contain a lot of noise, they increase token cost and latency as data grows, and they make the model output less stable and harder to test.

By converting transactions into structured statistics first, I give the model a cleaner and more explainable input space. That brings three benefits:
- lower token cost
- more consistent analysis input
- a shared input contract for both the rule engine and the LLM

So the goal is not just saving money. It is making the system more stable, replaceable, and testable from an engineering perspective.

## 4. How does the fixed pipeline work end to end?

### 中文问题
固定 pipeline 从收到请求到返回结果，中间按顺序经过哪些步骤？

### English Question
How does the fixed pipeline work step by step from request to response?

### 中文回答
固定 pipeline 是一个确定性分析链路，我是故意把它设计成明确顺序的。

第一步，请求进入 FastAPI 路由层，先通过 Pydantic 做参数校验，保证输入格式合法。

第二步，路由层决定数据来源。如果用户传了 `mock_transactions`，系统就直接使用这些交易；如果没有传，就根据 `wallet_address` 调用 mock data 层生成一份可复现的交易样本。

第三步，系统确定本次分析的主体钱包。如果请求里已经显式给了 `wallet_address`，就优先使用它；如果没有，就从交易列表里用启发式方法推断一个主要地址。

第四步，交易列表进入 feature extraction 层，被转换成结构化特征，包括总交易数、流入流出、净流量、独立对手方数量、大额交易统计、活跃天数和高频行为标记等。

第五步，这些特征进入 risk analysis 层。如果环境里没有 OpenAI key，就走规则分析；如果有 key，就调用 LLM 生成结构化风险结果；但如果模型调用失败或返回不合法 JSON，又会自动回退到规则分析。

第六步，系统把钱包地址、提取到的特征、风险等级、风险原因和后续建议封装成统一的响应 schema 返回。

一句话压缩版：输入规范化 -> 数据准备 -> 确定分析对象 -> 特征提取 -> 风险分析 -> 统一结构返回。

### English Answer
The fixed pipeline is intentionally designed as a deterministic sequence.

First, the request enters the FastAPI route layer, where Pydantic validates the input format.

Second, the route decides where the transaction data comes from. If the user provides `mock_transactions`, the system uses them directly. Otherwise, it generates a deterministic mock transaction sample from the wallet address.

Third, the system determines the target wallet for analysis. If `wallet_address` is explicitly provided, it uses that value. Otherwise, it infers the main wallet heuristically from the transactions.

Fourth, the transaction list goes into the feature extraction layer, which converts it into structured features such as total transactions, inflow/outflow, net flow, unique counterparties, large transaction statistics, active days, and high-frequency flags.

Fifth, those features enter the risk analysis layer. If there is no OpenAI key, the system uses rule-based analysis. If there is a key, it calls the LLM to generate structured risk output. If the model call fails or returns invalid JSON, it falls back to the rule-based path.

Sixth, the system wraps the wallet address, extracted features, risk level, risk reasons, and follow-up suggestions into a unified response schema and returns it.

Short version: input normalization -> data preparation -> target wallet resolution -> feature extraction -> risk analysis -> unified response.

## 5. Why unify `AIAnalysis` into one schema?

### 中文问题
为什么 `AIAnalysis` 要设计成统一 schema，而不是让规则和 LLM 各自返回不同格式？

### English Question
Why is `AIAnalysis` designed as a unified schema instead of letting the rule engine and the LLM return different formats?

### 中文回答
我把 `AIAnalysis` 设计成统一 schema，核心目的是让“分析来源可替换，但系统接口不变”。

这个项目里有两种分析来源：规则分析和 LLM 分析。如果它们各自返回不同格式，那上层 API、前端、测试代码、Agent 工具都要分别适配两套结构，复杂度会明显上升。

统一 schema 的价值主要有三个：
- 上层调用简单。无论底层是规则还是 LLM，调用方都只处理一种结构。
- 容错和回退简单。模型失败时可以直接切回规则分析，不需要改后续逻辑。
- 测试和维护更轻。只需要围绕一个稳定输出契约做校验。

从架构角度讲，这其实是在做“稳定输出契约”。规则和 LLM 是不同实现，但对外暴露的是同一个分析对象。

### English Answer
I designed `AIAnalysis` as a unified schema so that the analysis source can change while the system interface stays the same.

This project has two analysis sources: rule-based logic and LLM-based analysis. If they returned different formats, then the API layer, frontend, tests, and agent tools would all need separate handling logic for each mode. That would increase complexity a lot.

The unified schema brings three main benefits:
- simpler upstream integration, because callers only handle one format
- easier fallback behavior, because the system can switch from the LLM to rules without changing later stages
- easier testing and maintenance, because validation is centered on one stable output contract

Architecturally, this is about creating a stable output contract. The rule engine and the LLM are different implementations, but they expose the same analysis object to the rest of the system.

## 6. Why is `agent_formatting` necessary?

### 中文问题
为什么 `agent_formatting` 这一层是必要的？如果没有它会怎样？

### English Question
Why is the `agent_formatting` layer necessary, and what would happen without it?

### 中文回答
`agent_formatting` 必要的原因是：Agent 的原始输出天然不稳定，不适合直接交给前端或上层业务使用。

如果没有这一层，会有三个明显问题。

第一，最终输出不稳定。Agent 的最终回答是自然语言，它可能这次详细、下次简略，甚至格式变化都很大。这样的输出不适合前端做稳定绑定，也不利于自动化测试。

第二，结构化信息可能丢失。这个项目真正有价值的，不只是最后一句自然语言判断，还包括风险等级、风险原因、建议、提取出的特征以及工具调用过程。如果只返回模型原话，很多中间价值会被丢掉。

第三，可观测性会变差。加了 formatting layer 之后，我可以从 `intermediate_steps` 和 `run_state` 里恢复结构化风险、整理 `tool_trace`，更容易调试，也更适合演示 Agent 实际做了什么。

所以这层的本质不是“美化输出”，而是把 Agent 不稳定的推理结果，转换成稳定的产品输出：结构化风险对象、自然语言答案和工具轨迹分别服务不同场景。

### English Answer
The `agent_formatting` layer is necessary because raw agent output is naturally unstable and should not be exposed directly to the frontend or upper business layers.

Without it, there would be three main problems.

First, the final output would be unstable. The agent's answer is natural language, so it may be detailed in one run, short in another, and vary in structure. That is bad for frontend binding and automated tests.

Second, structured information could be lost. The valuable output of this project is not just one sentence like "this wallet looks suspicious." It also includes risk level, reasons, follow-up suggestions, extracted features, and the tool execution path. If we only return the model's final text, a lot of that value disappears.

Third, observability would be weaker. With the formatting layer, I can recover structured risk results from `run_state` and `intermediate_steps`, and I can also build `tool_trace` summaries for debugging and demos.

So this layer is not just about polishing text. It converts unstable reasoning output into stable product output: structured risk data, natural-language answer, and tool trace for different consumers.

## 7. Why is `wallet_resolve` not a very advanced design, but still worth keeping?

### 中文问题
`wallet_resolve` 为什么不是一个很高级的设计，但又仍然值得保留？

### English Question
Why is `wallet_resolve` not a very advanced design, but still still worth keeping?

### 中文回答
`wallet_resolve` 不是一个很高级的设计，因为它本质上只是一个 MVP 级启发式。

当请求里没有明确给出 `wallet_address` 时，它只是简单统计交易中地址出现的次数，然后把出现最多的地址当成分析主体。这个方法实现很轻，也很容易理解，但它并不严谨。在真实链上环境里，如果遇到中转地址、多签钱包、合约地址或者复杂资金流，这种方法可能会误判。

但它依然值得保留，因为它解决了一个很实际的问题：在“只传交易列表、不传主体地址”的场景下，系统至少还能继续工作，而不是直接中断。

所以我会把它定义成一个兼容性补丁，而不是核心智能能力。它的价值不在于先进，而在于：
- 降低调用门槛
- 支持 demo 场景
- 把系统做成“有默认行为”的产品

面试时可以补一句：代码里其实也已经明确承认这是 MVP 启发式，生产环境更合理的做法是显式传入 `wallet_address`。

### English Answer
`wallet_resolve` is not an advanced design because it is basically an MVP-level heuristic.

When the request does not provide `wallet_address`, it simply counts how often each address appears in the transactions and treats the most frequent one as the subject wallet. This approach is lightweight and easy to understand, but it is not rigorous. In a real on-chain environment, it could misidentify relayers, multisig wallets, contracts, or intermediate addresses.

But it is still worth keeping because it solves a practical problem: in the "transactions only" scenario, the system can still proceed instead of failing immediately.

So I would describe it as a compatibility helper rather than a core intelligence module. Its value is not sophistication. Its value is:
- lowering the input barrier
- supporting demo scenarios
- giving the system a sensible default behavior

In interviews, I would also add that the code already acknowledges this is an MVP heuristic, and in production the better approach would be to require an explicit `wallet_address`.

## 8. What feels most production-like and least production-like?

### 中文问题
你这个项目最像 production 的地方是什么，最不像 production 的地方又是什么？

### English Question
What is the most production-like part of this project, and what is the least production-like part?

### 中文回答
我觉得这个项目最像 production 的地方，不是它用了 OpenAI 或 LangChain，而是它的分层和输出契约设计。

比较像 production 的点有：
- 路由层、service 层、schema 层职责分离
- 固定 pipeline 和 Agent 共用底层能力，而不是重复造逻辑
- 输出统一为结构化 schema，便于前端接入和测试
- LLM 调用失败时有规则回退，不会让整个接口彻底不可用

这些点说明它至少有明确的工程边界和可维护性意识。

最不像 production 的地方，是数据和规则深度还远远不够。

当前项目没有真实链上数据源，交易主要来自 mock data；也没有地址标签系统、代币价值归一化、协议识别、持久化存储、缓存、异步任务和更完整的监控告警。严格说，它更像一个结构很清楚的 backend MVP，而不是完整的链上风控系统。

一句话可以总结成：架构思路比较像 production，但数据真实性和业务深度还明显停留在 MVP。

### English Answer
The most production-like part of this project is not that it uses OpenAI or LangChain. It is the way the system is layered and how the output contract is designed.

The parts that feel production-like are:
- clear separation between route layer, service layer, and schema layer
- shared lower-level business logic reused by both the fixed pipeline and the agent path
- unified structured output for frontend integration and testing
- graceful fallback from LLM analysis to rule-based analysis instead of total failure

These choices show engineering boundaries and maintainability awareness.

The least production-like part is the depth of the data and domain logic.

Right now there is no real on-chain data source. The transactions mainly come from deterministic mock data. There is also no address labeling system, no token value normalization, no protocol classification, no persistent storage, no caching, no async job layer, and no strong observability stack. So in practice, this is a well-structured backend MVP, not a full production blockchain risk platform.

In one sentence: the architecture feels more production-like than the data realism and domain depth.

## 9. If the Agent is the orchestration layer, what is the boundary between orchestration and business logic?

### 中文问题
你说 Agent 是 orchestration layer，不是业务层。那这两者的边界该怎么定义？

### English Question
You said the Agent is the orchestration layer, not the business layer. How do you define the boundary between them?

### 中文回答
我会把边界定义成一句话：业务层负责“能力本身”，编排层负责“什么时候、按什么顺序调用这些能力”。

在这个项目里，业务层包括 mock data、wallet resolve、feature extraction 和 risk analysis。这些模块各自都有明确输入输出，就算没有 Agent，它们也能单独运行，也能被固定 pipeline 直接调用。

Agent 不负责重新实现这些逻辑。它只是把这些能力包装成 tools，然后根据用户问题选择要不要调用、先调用哪个、最后怎么组织回答。

所以业务层回答的是：
- 怎么生成交易数据
- 怎么抽取特征
- 怎么做风险分析

而 Agent 层回答的是：
- 针对当前问题，需要不要查交易
- 要不要抽特征
- 要不要做风险评估
- 最后结果怎么面向用户表达

这样分层的好处是，业务逻辑不会被 prompt 和 Agent 绑定死，后面就算不用 LangChain，或者改成别的 orchestration 方式，底层 service 也能继续复用。

### English Answer
I define the boundary like this: the business layer owns the capabilities themselves, while the orchestration layer decides when and in what order to use those capabilities.

In this project, the business layer includes mock data generation, wallet resolution, feature extraction, and risk analysis. Each of these modules has explicit inputs and outputs, and they can run without the agent. The fixed pipeline already proves that.

The agent does not re-implement those capabilities. It only wraps them as tools and decides, based on the user's question, whether to call them, which one to call first, and how to organize the final response.

So the business layer answers questions like:
- how transaction data is obtained
- how features are extracted
- how risk is assessed

The agent layer answers questions like:
- do we need transaction retrieval for this question
- do we need feature extraction
- do we need risk assessment
- how should the result be presented to the user

This separation is useful because it prevents the core business logic from being tightly coupled to prompts or one specific agent framework. Even if we replaced LangChain or removed the agent entirely, the underlying services would still be reusable.

