# BrandOS AI 电商设计平台 MVP

当前仓库已从“单次详情页生成 Demo”补强为一个可运行的 BrandOS MVP 平台骨架，核心链路为：

```text
品牌管理 → 品牌资产池 → 规则版本 → 商品生成任务 → 历史任务追溯
         ↘ 资产训练候选池 ↗
```

它对应 BrandOS 的第一阶段目标：不是直接把 AI 当作出图工具，而是让系统持续沉淀品牌规则、版本和任务记录，并在生成时消费已发布的品牌规则版本。

## 当前能力

### 平台层

- 品牌管理：支持品牌列表、品牌详情、品牌创建。
- 品牌资产池：支持上传资产、标记资产角色、切换训练状态、启停资产。
- 规则版本：支持从已批准资产生成候选规则版本，并支持 Diff、发布、回滚。
- 历史任务：保存任务状态、阶段结果、日志和产物引用，支持任务追溯。
- 审计记录：品牌、资产、规则版本的关键动作会写入本地审计事件。

### 生成层

- 工作流请求支持 `brand_id`、`rule_version_id`。
- 若未指定 `rule_version_id`，会优先消费当前品牌已发布规则版本。
- 品牌知识阶段会以已发布规则为主，再融合本次任务的补充输入。
- 新上传素材不会直接改写品牌主规则，只会进入资产池与任务记录。

### 产物层

每次生成会写入 `backend/runs/<run_id>/outputs`：

- `design_spec.json`：完整结构化结果，包含品牌规则来源、页面结构、模块文案、图层树、评分和审核信息。
- `preview.svg`：低保真详情页预览图。
- `create_detail_page.jsx`：PSD 兼容脚本。
- `README.md`：导出包说明。

## 技术结构

- 前端：`Next.js 16 + React 19 + TypeScript`
- 后端：`FastAPI + Pydantic`
- 模型调用：`langchain init_chat_model`
- 存储方式：本地 JSON 文件持久化

本地数据目录：

- `backend/data/brands/`
- `backend/data/assets/`
- `backend/data/rule_versions/`
- `backend/data/runs/`
- `backend/data/audit_events/`

## 主要接口

### 平台接口

- `GET /api/brands`
- `POST /api/brands`
- `GET /api/brands/{brand_id}`
- `PATCH /api/brands/{brand_id}`
- `POST /api/brands/{brand_id}/train`
- `GET /api/brands/{brand_id}/audit-events`

- `GET /api/assets`
- `POST /api/assets`
- `PATCH /api/assets/{asset_id}`

- `GET /api/rule-versions`
- `GET /api/rule-versions/{version_id}`
- `GET /api/rule-versions/{version_id}/diff`
- `POST /api/rule-versions/{version_id}/publish`
- `POST /api/rule-versions/{version_id}/rollback`

- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/logs`
- `GET /api/runs/{run_id}/artifacts/{name}`

### 工作流接口

- `GET /api/config/defaults`
- `POST /api/workflows/generate`
- `POST /api/workflows/{run_id}/cancel`
- `GET /api/workflows/{run_id}/logs`
- `GET /api/workflows/{run_id}/artifacts/{name}`

## 工作流阶段

| 阶段 | 作用 | 产物 |
|---|---|---|
| 商品理解 Agent | 多模态模型读取上传图片并结合 brief 理解商品 | `product_info` |
| Product Brief | 合并视觉信息与商品资料 | `structured_info` |
| 品牌知识库 / 规则版本 | 消费品牌规则版本并融合任务级补充输入 | `brand_profile` |
| 页面规划 Agent | 生成页面结构与信息架构 | `design_direction` |
| Layout Engine | 输出模块布局与图层结构 | `modules` |
| 文案 Agent | 逐模块生成文案 | `copy` |
| Figma / PSD 生成 Agent | 输出图层树与命名说明 | `psd_layers` |
| Design Score | 输出品牌匹配与版式评分 | `design_score` |
| 输出、审核与反馈 | 汇总审核清单与反馈记录策略 | `outputs` |

## 配置文件

- `config/workflow-defaults.json`：项目默认参数
- `config/workflow-defaults.local.json`：本地覆盖参数

合并顺序：

```text
内置默认 → workflow-defaults.json → workflow-defaults.local.json → 请求体
```

默认会绑定：

- `brand_id = brand_default`
- `rule_version_id = rule_default_v1`

## 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

如需模型能力，可配置：

```bash
set DASHSCOPE_API_KEY=你的Key
```

或：

```bash
set OPENAI_API_KEY=你的Key
```

默认文本模型为 `qwen-plus`，默认视觉模型为 `qwen-vl-max`。

## 启动前端

```bash
cd frontend
pnpm install
set NEXT_PUBLIC_PSD_AGENT_API_BASE=http://localhost:8000
pnpm dev
```

## 本轮平台化补强结果

- 增加品牌、资产、规则版本、任务记录、审计事件的数据模型
- 增加本地 JSON 持久化存储
- 增加品牌、资产、规则版本、历史任务 API
- 生成链路接入品牌规则版本
- 前端扩展为平台化控制台，支持品牌空间、资产池、规则版本和历史任务视图
- 保留原有预览 SVG、设计 JSON、PSD JSX 导出能力

## 当前边界

本版本仍属于 MVP，以下能力未在本轮实现：

- 真实 Figma API 写入
- 图片生成 Agent 完整生产能力
- 多页面类型全量开放
- 团队权限与审批流细化
- 基于设计反馈的自动学习
