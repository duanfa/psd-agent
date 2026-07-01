import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  FolderKanban,
  Images,
  LayoutTemplate,
  LibraryBig,
  Palette,
  Sparkles,
  WandSparkles,
} from "lucide-react";

const STEP_ITEMS = [
  {
    step: "01",
    title: "上传品牌资产",
    description: "把品牌过往优秀案例、官网地址、首页、二级页、商品详情页等资料传入系统。",
    details: ["官网地址", "首页设计图", "二级页设计图", "商品详情页设计图", "过往优秀案例"],
    icon: <FolderKanban size={18} />,
  },
  {
    step: "02",
    title: "沉淀品牌规则",
    description: "系统自动提取品牌设计规范和页面布局规范，并支持后续版本迭代。",
    details: ["品牌设计规范", "首页布局规范", "二级页布局规范", "商品详情页规范"],
    icon: <LibraryBig size={18} />,
  },
  {
    step: "03",
    title: "创建设计任务",
    description: "为本次需求选择规范，并上传 brief 线框、参考图和素材图。",
    details: ["选择品牌规范和页面规范", "上传 brief 线框 Excel", "上传参考图", "上传素材图"],
    icon: <LayoutTemplate size={18} />,
  },
  {
    step: "04",
    title: "开始生成设计",
    description: "系统综合本次任务资料和品牌规则，生成符合品牌要求的页面设计。",
    details: ["按 brief 确定布局", "按品牌规范统一风格", "参考参考图的视觉表达"],
    icon: <WandSparkles size={18} />,
  },
];

const TASK_INPUTS = [
  {
    title: "选择规范",
    desc: "可选择品牌设计规范和页面布局规范，也可以本次不套用。",
    icon: <Palette size={18} />,
  },
  {
    title: "上传 brief 线框 Excel",
    desc: "系统解析页面内容、模块顺序和布局要求，这是本次任务的核心依据。",
    icon: <FileSpreadsheet size={18} />,
  },
  {
    title: "上传相近参考图",
    desc: "只用于参考风格、氛围和表达方式，不直接决定最终布局。",
    icon: <Images size={18} />,
  },
  {
    title: "上传素材图",
    desc: "支持多张上传，作为本次设计生成所需的实际视觉素材。",
    icon: <Sparkles size={18} />,
  },
];

const PRIORITIES = [
  {
    title: "第一优先级：brief 线框 Excel",
    desc: "决定本次页面的真实布局和模块顺序。",
  },
  {
    title: "第二优先级：品牌规范 / 页面规范",
    desc: "保证品牌一致性，约束字体、色彩、结构和页面表达。",
  },
  {
    title: "第三优先级：参考图",
    desc: "仅参考风格和表现感觉，不覆盖 brief 的实际布局要求。",
  },
];

export function HowItWorksPage() {
  return (
    <main className="data-page how-page">
      <header className="hero how-hero">
        <div className="hero-text">
          <div className="eyebrow">
            <Sparkles size={14} /> Explain BrandOS AI
          </div>
          <h1>3 分钟看懂 BrandOS AI 怎么工作</h1>
          <p>
            这是一个“先沉淀品牌规则，再按任务生成页面设计”的系统。页面重点不是解释技术细节，而是回答三个问题：
            先上传什么、系统会做什么、最后怎么生成。
          </p>
          <div className="how-hero-actions">
            <Link className="btn primary" href="/brand-assets">
              从品牌资产开始 <ArrowRight size={16} />
            </Link>
            <Link className="btn ghost" href="/create-task">
              直接创建设计任务
            </Link>
          </div>
        </div>
        <div className="how-hero-side">
          <article className="info-card">
            <div className="eyebrow">一句话版本</div>
            <h3>先沉淀规则，再生成设计</h3>
            <p>
              品牌历史资产用于沉淀长期规范，本次任务的 `brief 线框 Excel`
              决定实际布局，参考图只参考风格。
            </p>
          </article>
        </div>
      </header>

      <section className="summary-grid">
        <article className="info-card">
          <div className="eyebrow">你要做什么</div>
          <div className="big-metric">4 步</div>
          <div className="muted-text">上传资产、沉淀规则、创建任务、开始生成。</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">系统会做什么</div>
          <div className="big-metric">提取 + 应用</div>
          <div className="muted-text">提取品牌规范、页面规范，并在任务中组合应用。</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">布局依据</div>
          <div className="big-metric">Brief</div>
          <div className="muted-text">最终布局以上传的 brief 线框 Excel 为准。</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">最终产出</div>
          <div className="big-metric">页面设计</div>
          <div className="muted-text">生成符合品牌要求、符合本次 brief 的页面方案。</div>
        </article>
      </section>

      <section className="panel content-panel how-section">
        <div className="split-line">
          <div>
            <h2 className="section-title">整体流程</h2>
            <div className="subtitle">按“先长期沉淀，再处理单次任务”的顺序理解最清楚。</div>
          </div>
          <span className="tag">品牌层 + 任务层</span>
        </div>
        <div className="how-step-grid">
          {STEP_ITEMS.map((item) => (
            <article className="how-step-card" key={item.step}>
              <div className="how-step-head">
                <span className="how-step-badge">{item.step}</span>
                <div className="how-step-icon">{item.icon}</div>
              </div>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
              <ul className="how-list">
                {item.details.map((detail) => (
                  <li key={detail}>
                    <CheckCircle2 size={14} />
                    <span>{detail}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <div className="content-grid-2">
        <section className="panel content-panel how-section">
          <div className="split-line">
            <div>
              <h2 className="section-title">品牌资产能沉淀出什么</h2>
              <div className="subtitle">品牌资产不是为了某一次任务，而是为了形成长期可复用的规则。</div>
            </div>
          </div>
          <div className="record-list">
            <div className="record-item">
              <strong>品牌设计规范</strong>
              <div className="subtitle">沉淀品牌调性、字体、色彩、视觉语言和禁用项。</div>
            </div>
            <div className="record-item">
              <strong>首页布局规范</strong>
              <div className="subtitle">沉淀首页常见模块顺序、信息结构和视觉组织方式。</div>
            </div>
            <div className="record-item">
              <strong>二级页布局规范</strong>
              <div className="subtitle">沉淀分类页、活动页或频道页的布局组织规则。</div>
            </div>
            <div className="record-item">
              <strong>商品详情页规范</strong>
              <div className="subtitle">沉淀详情页的模块节奏、卖点呈现和素材排布逻辑。</div>
            </div>
          </div>
        </section>

        <section className="panel content-panel how-section">
          <div className="split-line">
            <div>
              <h2 className="section-title">创建设计任务时要上传什么</h2>
              <div className="subtitle">这里讲本次任务的输入，不讲系统实现，让业务和设计都能直接看懂。</div>
            </div>
          </div>
          <div className="record-list">
            {TASK_INPUTS.map((item) => (
              <div className="record-item how-input-card" key={item.title}>
                <div className="how-input-icon">{item.icon}</div>
                <div>
                  <strong>{item.title}</strong>
                  <div className="subtitle">{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="panel content-panel how-section">
        <div className="split-line">
          <div>
            <h2 className="section-title">生成优先级</h2>
            <div className="subtitle">这一部分最关键，用来防止大家误解“参考图会不会覆盖 brief”。</div>
          </div>
          <span className="tag">必须讲清楚</span>
        </div>
        <div className="how-priority-grid">
          {PRIORITIES.map((item, index) => (
            <article className={`how-priority-card how-priority-${index + 1}`} key={item.title}>
              <div className="eyebrow">优先级 {index + 1}</div>
              <h3>{item.title}</h3>
              <p>{item.desc}</p>
            </article>
          ))}
        </div>
        <div className="how-highlight">
          <strong>结论：</strong>
          最终页面布局，以本次上传的 `brief 线框 Excel` 为准；参考图只参考风格，不决定最终布局。
        </div>
      </section>

      <section className="panel content-panel how-section">
        <div className="split-line">
          <div>
            <h2 className="section-title">给不喜欢看文档的人怎么讲</h2>
            <div className="subtitle">照着下面三句话讲，通常比讲功能定义更容易理解。</div>
          </div>
        </div>
        <div className="how-script-grid">
          <article className="info-card">
            <div className="eyebrow">第一句</div>
            <p>先把品牌过去做得好的资产传进来，系统会自动沉淀出品牌规范和页面规范。</p>
          </article>
          <article className="info-card">
            <div className="eyebrow">第二句</div>
            <p>做具体任务时，上传本次的 brief 线框 Excel、参考图和素材图，再选择要不要套用已有规范。</p>
          </article>
          <article className="info-card">
            <div className="eyebrow">第三句</div>
            <p>系统生成时，实际布局以 brief 为准，品牌规范保证统一性，参考图只参考风格。</p>
          </article>
        </div>
      </section>
    </main>
  );
}
