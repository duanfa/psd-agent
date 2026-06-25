# PSD 详情页自动生成 Agent

基于 `详情页自动生成工作流说明文档.md` 落地的工作流原型，严格对齐流程图：

```
商品图 → 视觉理解模型 → 商品结构化信息 → 品牌 RAG → 设计 Agent
      → 版式规划 Agent → 文案 Agent → PSD 生成 Agent
      → 主图 PSD / 详情页 PSD / 广告 Banner → 人工审核
```

- 前端：Next.js 单页调试台，顶部为流水线节点可视化，左侧分组配置，右侧阶段时间线 + 预览 + 下载。
- 接口：前后端通过 HTTP multipart 调用。
- 后端：Python FastAPI，把工作流拆成 8 个阶段依次执行。
- Agent：每个阶段优先用模型（langchain `init_chat_model` / DeepAgents 同源）生成结构化结果；
  缺 Key 或依赖不可用时，逐阶段降级为规则生成，保证流程始终可跑通。
- 可调参数：模型、温度、token、输出类型、字体、字号、行距、配色、画布、模块数量，
  以及每个阶段的提示词，全部可在 Web 界面实时调整。

## 流水线阶段

| 阶段 | 作用 | 产物 |
|---|---|---|
| 视觉理解模型 | 多模态模型真正读取上传图片识别商品（缺图/缺 Pillow 时回退文本推断） | product_info |
| 商品结构化信息 | 合并视觉信息与 brief | structured_info |
| 品牌 RAG | 提取品牌风格、配色、字体、模块顺序 | brand_profile |
| 设计 Agent | 整体视觉方向、色调、图片策略、约束 | design_direction |
| 版式规划 Agent | 拆分模块、定义布局与图层结构 | modules |
| 文案 Agent | 逐模块生成标题/副标题/说明/要点 | copy |
| PSD 生成 Agent | 输出 PSD 图层树与命名规范 | psd_layers |
| 输出与人工审核 | 汇总产物 + 审核清单 | outputs |

## 配置文件

- `config/workflow-defaults.json`：项目默认参数（已对齐 brief：790px 宽、方正兰亭特黑/黑、AKR Sans）。
- `config/workflow-defaults.local.json`：本地覆盖（可选，放私有 key、自定义模型）。

合并顺序：内置默认 → `workflow-defaults.json` → `workflow-defaults.local.json` → 请求体。

## 启动后端

```bash
cd psd-agent/backend
pip install -r requirements.txt
export DASHSCOPE_API_KEY=你的Key   # 或 OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

默认文本模型为 `qwen-plus`、视觉模型为 `qwen-vl-max`（DashScope OpenAI 兼容），可在界面或配置文件改成任意 provider。

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

- `design_spec.json`：完整结构（各阶段产物 + 模块文案 + PSD 图层树 + 审核清单）。
- `preview.svg`：由真实文案/版式驱动的详情页预览图。
- `create_detail_page.jsx`：Photoshop 脚本，生成可编辑文字层与图层分组初稿。
- `README.md`：导出包说明。

当前为半自动初稿链路：AI 负责风格、文案、版式和 PSD 图层规划；
高清素材替换、抠图调色与最终审稿仍由设计师在 Photoshop 完成。
