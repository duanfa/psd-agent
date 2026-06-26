"use client";

import { Plus, RefreshCw } from "lucide-react";
import { useState } from "react";
import type { BrandRecord, BrandRuleVersionRecord } from "@/lib/api";

interface BrandSidebarProps {
  brands: BrandRecord[];
  selectedBrandId: string | null;
  currentRuleVersion?: BrandRuleVersionRecord | null;
  assetCount?: number;
  runCount?: number;
  loading?: boolean;
  onSelectBrand: (brandId: string) => void;
  onCreateBrand: (payload: { name: string; code?: string; description?: string }) => Promise<void>;
  onRefresh: () => Promise<void> | void;
}

export function BrandSidebar({
  brands,
  selectedBrandId,
  currentRuleVersion,
  assetCount = 0,
  runCount = 0,
  loading = false,
  onSelectBrand,
  onCreateBrand,
  onRefresh,
}: BrandSidebarProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const selectedBrand = brands.find((item) => item.id === selectedBrandId) ?? null;

  const submit = async () => {
    if (!name.trim()) return;
    await onCreateBrand({ name: name.trim(), code: code.trim() || undefined, description: description.trim() });
    setName("");
    setCode("");
    setDescription("");
  };

  return (
    <section className="panel platform-panel">
      <div className="panel-header">
        <div className="panel-title">品牌空间</div>
        <button className="btn ghost btn-small" type="button" onClick={() => void onRefresh()}>
          <RefreshCw size={14} /> 刷新
        </button>
      </div>
      <div className="panel-scroll">
        <div className="field">
          <span className="field-label">当前品牌</span>
          <select
            value={selectedBrandId ?? ""}
            onChange={(e) => e.target.value && onSelectBrand(e.target.value)}
            disabled={loading}
          >
            {brands.map((brand) => (
              <option key={brand.id} value={brand.id}>
                {brand.name}
              </option>
            ))}
          </select>
        </div>

        {selectedBrand ? (
          <div className="platform-card">
            <div className="card-label">品牌概览</div>
            <div className="kv-list">
              <div><strong>编码：</strong>{selectedBrand.code || "-"}</div>
              <div><strong>状态：</strong>{selectedBrand.status}</div>
              <div><strong>当前发布版本：</strong>{currentRuleVersion?.version_label ?? "未发布"}</div>
              <div><strong>资产数量：</strong>{assetCount}</div>
              <div><strong>历史任务：</strong>{runCount}</div>
              <div><strong>描述：</strong>{selectedBrand.description || "暂无描述"}</div>
            </div>
          </div>
        ) : null}

        <div className="platform-card">
          <div className="card-label">新建品牌</div>
          <div className="field">
            <span className="field-label">品牌名称</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如 ANKORAU" />
          </div>
          <div className="grid-2">
            <div className="field">
              <span className="field-label">品牌编码</span>
              <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="可选" />
            </div>
            <div className="field">
              <span className="field-label">品牌描述</span>
              <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="可选" />
            </div>
          </div>
          <button className="btn primary btn-small" type="button" onClick={() => void submit()}>
            <Plus size={14} /> 创建品牌
          </button>
        </div>
      </div>
    </section>
  );
}
