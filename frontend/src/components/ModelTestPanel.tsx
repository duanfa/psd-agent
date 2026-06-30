"use client";

import { Bot, Cpu, FileText, Loader2, RotateCcw, Send, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  fetchModelTestConfig,
  testModel,
  type ChatMessage,
  type ModelTestConfigResponse,
  type ModelTestResponse,
} from "@/lib/api";
import { Section } from "./Section";

const STARTER_PROMPTS = [
  "请简单自我介绍，并告诉我你现在能正常回复。",
  "用 3 条 bullet 总结一下当前模型是否可用的判断方式。",
  "请写一句适合电商详情页首屏的中文标题文案。",
];

export function ModelTestPanel() {
  const [systemPrompt, setSystemPrompt] = useState(
    "你是 BrandOS 的模型联调助手。请直接回答用户问题，并尽量简洁。",
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultMeta, setResultMeta] = useState<ModelTestResponse | null>(null);
  const [config, setConfig] = useState<ModelTestConfigResponse | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchModelTestConfig()
      .then((data) => {
        setConfig(data);
        setConfigError(null);
      })
      .catch((err) => setConfigError(err instanceof Error ? err.message : String(err)))
      .finally(() => setConfigLoading(false));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  const handleSend = async (text?: string) => {
    const content = (text ?? draft).trim();
    if (!content || loading || configLoading || !!configError) return;

    const nextMessages: ChatMessage[] = [...messages, { role: "user", content }];
    setMessages(nextMessages);
    setDraft("");
    setError(null);
    setLoading(true);

    try {
      const response = await testModel({
        messages: systemPrompt.trim()
          ? [{ role: "system", content: systemPrompt.trim() }, ...nextMessages]
          : nextMessages,
      });
      setResultMeta(response);
      setMessages([...nextMessages, { role: "assistant", content: response.reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="shell">
      <section className="panel config-panel">
        <div className="panel-header">
          <div className="panel-title">
            <Cpu size={18} /> 测试参数
          </div>
        </div>

        <div className="panel-scroll">
          <Section
            title="文本模型配置"
            description="直接读取后端当前生效的 model_config"
            icon={<Cpu size={16} />}
            defaultOpen
          >
            {configLoading ? (
              <div className="placeholder model-test-empty">
                <Loader2 className="spin" size={20} />
                <p>正在读取模型测试配置...</p>
              </div>
            ) : configError ? (
              <div className="error">{configError}</div>
            ) : config ? (
              <>
                <div className="model-config-grid">
                  <Field label="配置来源">
                    <div className="readonly-field">
                      <FileText size={14} />
                      {config.source_path}
                    </div>
                  </Field>
                  <Field label="Provider">
                    <div className="readonly-field">{config.provider}</div>
                  </Field>
                  <Field label="文本模型">
                    <div className="readonly-field">{config.model}</div>
                  </Field>
                  <Field label="视觉模型">
                    <div className="readonly-field">{config.vision_model}</div>
                  </Field>
                  <Field label="Base URL">
                    <div className="readonly-field readonly-field-multiline">
                      {config.base_url || "默认 Base URL"}
                    </div>
                  </Field>
                  <Field label="API Key">
                    <div className="readonly-field">{config.has_api_key ? "已配置" : "未配置"}</div>
                  </Field>
                  <Field label="Temperature">
                    <div className="readonly-field">{config.temperature}</div>
                  </Field>
                  <Field label="Max Tokens">
                    <div className="readonly-field">{config.max_tokens}</div>
                  </Field>
                </div>
                <p className="hint">
                  模型测试不会读取页面填写值，发送请求时后端会直接使用
                  当前生效配置来源（`workflow-defaults*.json`，以及可选的 `workflow-gpt.json` 覆盖层）。
                </p>
              </>
            ) : null}
          </Section>

          <Section
            title="System Prompt"
            description="可选，用来定义测试对话的角色和回答风格"
            icon={<Bot size={16} />}
            defaultOpen
          >
            <textarea
              className="model-test-system"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
            />
          </Section>

          <Section
            title="快速测试语句"
            description="一键发送常见联调问题"
            icon={<Send size={16} />}
            defaultOpen
          >
            <div className="model-test-starters">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  className="starter-chip"
                  disabled={loading}
                  key={prompt}
                  type="button"
                  onClick={() => handleSend(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </Section>
        </div>
      </section>

      <aside className="panel result-panel">
        <div className="panel-header">
          <div className="panel-title">
            <Bot size={18} /> 模型对话测试
          </div>
          <button
            className="btn ghost"
            disabled={loading && messages.length === 0}
            type="button"
            onClick={() => {
              setMessages([]);
              setError(null);
              setResultMeta(null);
            }}
          >
            <RotateCcw size={15} /> 清空会话
          </button>
        </div>

        <div className="panel-scroll model-test-scroll">
          <div className="model-test-meta">
            <span className="pill pill-ghost">{config?.provider ?? "读取中"}</span>
            <span className="pill pill-ghost">{config?.model ?? "读取中"}</span>
            <span className="pill pill-ghost">{config?.base_url || "默认 Base URL"}</span>
            {resultMeta ? <span className="pill pill-on">最近一次请求成功</span> : null}
          </div>

          {configError ? <div className="error">{configError}</div> : null}
          {error ? <div className="error">{error}</div> : null}

          <div className="chat-thread">
            {!messages.length ? (
              <div className="placeholder model-test-empty">
                <Bot size={28} />
                <p>输入一段文本并发送，确认当前模型配置是否能正常返回结果。</p>
              </div>
            ) : (
              messages.map((message, index) => (
                <article
                  className={`chat-bubble ${
                    message.role === "assistant" ? "chat-bubble-assistant" : "chat-bubble-user"
                  }`}
                  key={`${message.role}-${index}-${message.content.slice(0, 24)}`}
                >
                  <div className="chat-bubble-head">
                    <span className="chat-role-icon">
                      {message.role === "assistant" ? <Bot size={14} /> : <User size={14} />}
                    </span>
                    <strong>{message.role === "assistant" ? "模型回复" : "你"}</strong>
                  </div>
                  <div className="chat-bubble-body">{message.content}</div>
                </article>
              ))
            )}

            {loading ? (
              <article className="chat-bubble chat-bubble-assistant">
                <div className="chat-bubble-head">
                  <span className="chat-role-icon">
                    <Bot size={14} />
                  </span>
                  <strong>模型回复</strong>
                </div>
                <div className="chat-bubble-body chat-bubble-loading">
                  <Loader2 className="spin" size={16} /> 正在请求模型...
                </div>
              </article>
            ) : null}
            <div ref={chatEndRef} />
          </div>

          <div className="model-test-composer">
            <textarea
              placeholder="输入测试问题，例如：请回复“连接成功”，并附上当前模型名称。"
              value={draft}
              disabled={configLoading || !!configError}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
            />
            <button
              className="btn primary"
              disabled={loading || !draft.trim() || configLoading || !!configError}
              type="button"
              onClick={() => handleSend()}
            >
              {loading ? <Loader2 className="spin" size={16} /> : <Send size={16} />}
              发送测试
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      {children}
    </div>
  );
}
