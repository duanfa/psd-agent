"use client";

import { Upload } from "lucide-react";
import type { BrandAssetRecord } from "@/lib/api";

interface AssetManagerProps {
  assets: BrandAssetRecord[];
  selectedBrandId: string | null;
  uploading?: boolean;
  onUpload: (file: File) => Promise<void>;
  onUpdateAsset: (
    assetId: string,
    patch: Partial<Pick<BrandAssetRecord, "role" | "training_status" | "enabled">>,
  ) => Promise<void>;
}

export function AssetManager({
  assets,
  selectedBrandId,
  uploading = false,
  onUpload,
  onUpdateAsset,
}: AssetManagerProps) {
  const approvedCount = assets.filter(
    (asset) => asset.training_status === "approved_for_training" && asset.enabled,
  ).length;

  return (
    <section className="panel platform-panel">
      <div className="panel-header">
        <div className="panel-title">品牌资产池</div>
      </div>
      <div className="panel-scroll">
        <label className={`dropzone ${!selectedBrandId ? "disabled-zone" : ""}`}>
          <Upload size={18} />
          <span>{selectedBrandId ? "上传品牌资产" : "请先选择品牌"}</span>
          <input
            type="file"
            style={{ display: "none" }}
            disabled={!selectedBrandId || uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void onUpload(file);
              e.currentTarget.value = "";
            }}
          />
        </label>

        {assets.length ? (
          <div className="platform-inline-stats">
            <span className="mini-stat">总资产 {assets.length}</span>
            <span className="mini-stat">已批准训练 {approvedCount}</span>
          </div>
        ) : null}

        {!assets.length ? <p className="hint">当前品牌还没有资产，可先上传规范、案例图或商品素材。</p> : null}

        <div className="platform-list">
          {assets.map((asset) => (
            <div className="platform-card" key={asset.id}>
              <div className="platform-card-head">
                <div>
                  <div className="platform-card-title">{asset.name}</div>
                  <div className="platform-card-meta">
                    {asset.bucket} · {(asset.size / 1024).toFixed(0)} KB · {asset.source}
                  </div>
                </div>
                <span className={`pill ${asset.enabled ? "pill-on" : "pill-off"}`}>
                  {asset.enabled ? "启用" : "停用"}
                </span>
              </div>
              <div className="grid-2">
                <label className="field">
                  <span className="field-label">资产角色</span>
                  <select
                    value={asset.role}
                    onChange={(e) =>
                      void onUpdateAsset(asset.id, {
                        role: e.target.value as BrandAssetRecord["role"],
                      })
                    }
                  >
                    <option value="core_spec">核心规范</option>
                    <option value="high_quality_case">高质量案例</option>
                    <option value="reference">普通参考</option>
                    <option value="excluded">排除样本</option>
                  </select>
                </label>
                <label className="field">
                  <span className="field-label">训练状态</span>
                  <select
                    value={asset.training_status}
                    onChange={(e) =>
                      void onUpdateAsset(asset.id, {
                        training_status: e.target.value as BrandAssetRecord["training_status"],
                      })
                    }
                  >
                    <option value="candidate">待纳入训练池</option>
                    <option value="approved_for_training">已批准训练</option>
                    <option value="excluded">排除</option>
                  </select>
                </label>
              </div>
              <label className="switch">
                <input
                  checked={asset.enabled}
                  type="checkbox"
                  onChange={(e) => void onUpdateAsset(asset.id, { enabled: e.target.checked })}
                />
                <span className="switch-track" />
                资产可用
              </label>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
