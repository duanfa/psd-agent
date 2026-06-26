import type { StageMeta } from "@/lib/api";

export const FALLBACK_STAGES: StageMeta[] = [
  { id: "product_understanding", title: "商品理解 Agent", icon: "eye" },
  { id: "product_brief", title: "Product Brief", icon: "layers" },
  { id: "brand_knowledge", title: "品牌知识库 / 规则版本", icon: "library" },
  { id: "page_planner", title: "页面规划 Agent", icon: "palette" },
  { id: "layout_engine", title: "Layout Engine", icon: "grid" },
  { id: "copy", title: "文案 Agent", icon: "type" },
  { id: "figma_psd", title: "Figma / PSD 生成 Agent", icon: "file-image" },
  { id: "design_score", title: "Design Score", icon: "check-circle" },
  { id: "output_review", title: "输出、审核与反馈", icon: "check-circle" },
];
