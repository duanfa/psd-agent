# BrandOS AI 电商设计平台 MVP

基于新版 BrandOS PRD、战略原则和 HTML 原型升级的可运行 MVP。产品定位从单纯 PSD 详情页生成，调整为：

```
品牌资产 → 品牌知识库 → 规则版本 → Product Brief → 页面规划
      → 图片生成 → Layout Engine → Figma / PSD → Design Score → 人工反馈
```

- 前端：Next.js 单页 BrandOS 控制台，顶部为工作流节点和 BrandOS 核心概览，左侧分组配置，右侧阶段时间线 + 预览 + 下载。
- 接口：前后端通过 HTTP multipart 调用。
- 后端：Python FastAPI，把工作流拆成品牌知识库、页面规划、设计稿输出、评分反馈等阶段依次执行。
- Agent：每个阶段优先用模型（langchain `init_chat_model` / DeepAgents 同源）生成结构化结果；
  缺 Key 或依赖不可用时，逐阶段降级为规则生成，保证流程始终可跑通。
- 可调参数：模型、温度、token、输出类型、品牌字体、字号、行距、配色、画布、标准模块数量，
  以及每个阶段的提示词，全部可在 Web 界面实时调整。

## 流水线阶段

| 阶段 | 作用 | 产物 |
|---|---|---|
| 商品理解 Agent | 多模态模型读取上传图片并结合 brief 理解商品 | product_info |
| Product Brief | 合并视觉信息与商品资料 | structured_info |
| 品牌知识库 / 规则版本 | 输出 Core Rule / Derived Rule / Asset Memory、权重、版本状态和漂移风险 | brand_profile |
| 页面规划 Agent | 在标准模块模板内生成页面信息架构与图片策略 | design_direction |
| 图片生成 Agent | 为模块规划配图，优先输出真实 Figma 交付所需图片资产，缺省时回退生成占位图 | generated_images |
| Layout Engine | 拆分模块、定义布局与图层结构 | modules |
| 文案 Agent | 逐模块生成标题/副标题/说明/要点 | copy |
| Figma / PSD 生成 Agent | 输出 Figma Frame / PSD 图层树与命名规范 | psd_layers |
| Design Score | 输出品牌匹配、版式质量、可读性、转化等评分 | design_score |
| 输出、审核与反馈 | 汇总产物、审核清单和设计师反馈记录策略 | outputs |

## 配置文件

- `config/workflow-defaults.json`：项目默认参数（默认输出详情页结构化方案、真实 Figma 交付入口或 Figma 脚本 fallback，以及 PSD 兼容文件）。
- `config/workflow-defaults.local.json`：本地覆盖（可选，放私有 key、自定义模型）。

合并顺序：内置默认 → `workflow-defaults.json` → `workflow-defaults.local.json` → 请求体。

## 路线图

- `docs/system-optimization-roadmap.md`：基于 VEJA 详情页日志复盘整理的系统层优化方案，包含 `layout_schema`、`image_slots`、阶段校验、Layout Guard、素材匹配和前端结果态升级等改造方向。
- `docs/system-optimization-tasks.md`：将系统优化路线图进一步拆成 `Epic / Issue / 验收标准` 的可执行任务清单，适合直接排期或建 issue。

## 启动后端

```bash
cd psd-agent/backend
pip install -r requirements.txt
export DATABASE_URL="mysql://mysql:mysql@127.0.0.1:3306/myprismadb?schema=public"
export DASHSCOPE_API_KEY=你的Key   # 或 OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

默认文本模型为 `qwen-plus`、视觉模型为 `qwen-vl-max`（DashScope OpenAI 兼容），可在界面或配置文件改成任意 provider。

也可以复制 `backend/.env.example` 为 `backend/.env`，后端会自动读取。后端启动时会根据 `DATABASE_URL` 自动创建 MySQL 表，用于持久化工作流任务、上传资产、阶段结果、运行日志、输出产物索引、品牌和品牌资产。产物文件仍写入 `backend/runs/<run_id>/outputs`，数据库保存可检索的结构化索引和完整设计规格。

视觉理解阶段会把上传的商品图压缩后送入多模态模型（`enable_vision` 控制开关，`max_vision_images` 控制读图数量）。
图片压缩依赖 Pillow，已包含在 `requirements.txt`；若未安装则自动回退为文本推断。

## 启动前端

```bash
cd psd-agent/frontend
pnpm install
NEXT_PUBLIC_PSD_AGENT_API_BASE=http://localhost:8000 pnpm dev
```

## 生成产物

每次生成写入 `backend/runs/<run_id>/outputs`：

- `design_spec.json`：完整结构（品牌规则分层 + 页面结构 + 模块文案 + 模块配图 + Figma/PSD 图层树 + 设计评分 + 审核清单）。
- `preview.svg`：由真实文案/版式驱动的详情页预览图。
- `assets/`：原始上传图片与图片生成阶段输出的占位图/派生图，供预览与导出消费。
- `create_detail_page.jsx`：PSD 兼容脚本，生成可编辑文字层与图层分组初稿。
- `create_figma_page.ts`：Figma 插件脚本 fallback；若配置真实 Figma 导出适配器，则前端优先展示真实 Figma 页面入口。
- `editable_detail_page.html`：浏览器可编辑审稿稿，适合设计师初审与反馈记录。
- `README.md`：导出包说明。

当前为 BrandOS MVP 初稿链路：AI 负责品牌规则消费、页面结构、模块配图规划、文案、版式和设计稿结构规划。
当前版本中的 Figma 交付支持两种模式：优先展示真实 Figma 页面入口；若未配置真实导出适配器，则自动回退为 Figma 插件脚本。
高清素材替换、抠图调色与最终审稿仍由设计师完成。设计师修改会作为反馈数据记录，不会自动覆盖品牌核心规则。
