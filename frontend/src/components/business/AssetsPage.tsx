"use client";

import { useEffect, useMemo, useState } from "react";
import { Play, Search, Upload } from "lucide-react";
import { fetchAssets, trainRuleVersion, updateAsset, uploadAsset, type BrandAssetRecord } from "@/lib/api";
import { AppShell } from "./AppShell";
import { useBrandSelection } from "./useBrandSelection";
import { EmptyState, PageSection, StatusBadge } from "./ui";

const CATEGORY_LABEL: Record<BrandAssetRecord["role"], string> = {
  core_spec: "核心规范",
  high_quality_case: "高质量案例",
  reference: "普通参考",
  excluded: "排除样本",
};

export function AssetsPage() {
  const {
    brands,
    selectedBrand,
    selectedBrandId,
    loading,
    error,
    setSelectedBrandId,
    buildHref,
  } = useBrandSelection();
  const [assets, setAssets] = useState<BrandAssetRecord[]>([]);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [uploading, setUploading] = useState(false);
  const [training, setTraining] = useState(false);

  const loadAssets = async (brandId: string) => {
    setPageLoading(true);
    setPageError(null);
    try {
      setAssets(await fetchAssets(brandId));
    } catch (err) {
      setPageError(err instanceof Error ? err.message : String(err));
    } finally {
      setPageLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedBrandId) {
      setAssets([]);
      setPageLoading(false);
      return;
    }
    void loadAssets(selectedBrandId);
  }, [selectedBrandId]);

  const filteredAssets = useMemo(
    () =>
      assets.filter((asset) => {
        const hitKeyword =
          !keyword ||
          asset.name.toLowerCase().includes(keyword.toLowerCase()) ||
          asset.source.toLowerCase().includes(keyword.toLowerCase());
        const hitRole = roleFilter === "all" || asset.role === roleFilter;
        const hitStatus = statusFilter === "all" || asset.training_status === statusFilter;
        return hitKeyword && hitRole && hitStatus;
      }),
    [assets, keyword, roleFilter, statusFilter],
  );

  const handleUpload = async (file?: File) => {
    if (!file || !selectedBrandId) return;
    setUploading(true);
    setPageError(null);
    try {
      await uploadAsset({
        brandId: selectedBrandId,
        file,
        role: "reference",
        trainingStatus: "candidate",
      });
      await loadAssets(selectedBrandId);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  };

  const handleUpdate = async (
    assetId: string,
    patch: Partial<Pick<BrandAssetRecord, "role" | "training_status" | "enabled">>,
  ) => {
    try {
      await updateAsset(assetId, patch);
      if (selectedBrandId) await loadAssets(selectedBrandId);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleTrain = async () => {
    if (!selectedBrandId) return;
    setTraining(true);
    setPageError(null);
    try {
      await trainRuleVersion({
        brandId: selectedBrandId,
        summary: "基于已批准资产生成候选规则版本。",
        changeReason: "从品牌资产页发起训练。",
        assetIds: assets
          .filter((asset) => asset.training_status === "approved_for_training" && asset.enabled)
          .map((asset) => asset.id),
      });
    } catch (err) {
      setPageError(err instanceof Error ? err.message : String(err));
    } finally {
      setTraining(false);
    }
  };

  return (
    <AppShell
      title="品牌资产"
      subtitle="统一管理品牌官网、规范、历史案例和设计素材"
      brands={brands}
      selectedBrand={selectedBrand}
      selectedBrandId={selectedBrandId}
      loadingBrands={loading}
      onBrandChange={setSelectedBrandId}
      buildHref={buildHref}
      headerActions={
        <button className="btn ghost" type="button" onClick={() => void handleTrain()} disabled={!assets.length || training}>
          <Play size={14} /> {training ? "训练中..." : "发起训练"}
        </button>
      }
    >
      {error || pageError ? <div className="error">{error ?? pageError}</div> : null}

      <PageSection title="资产列表" subtitle="可按分类、状态和关键字快速筛选">
        <div className="biz-filter-row">
          <label className="biz-input-wrap">
            <Search size={14} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索资产名称或来源"
            />
          </label>
          <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
            <option value="all">全部分类</option>
            <option value="core_spec">核心规范</option>
            <option value="high_quality_case">高质量案例</option>
            <option value="reference">普通参考</option>
            <option value="excluded">排除样本</option>
          </select>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">全部状态</option>
            <option value="candidate">待纳入训练池</option>
            <option value="approved_for_training">已批准训练</option>
            <option value="excluded">排除</option>
          </select>
          <label className={`btn primary ${uploading ? "btn-disabled" : ""}`}>
            <Upload size={14} /> {uploading ? "上传中..." : "上传资产"}
            <input
              type="file"
              hidden
              disabled={!selectedBrandId || uploading}
              onChange={(event) => {
                void handleUpload(event.target.files?.[0]);
                event.currentTarget.value = "";
              }}
            />
          </label>
        </div>

        {pageLoading ? <div className="biz-loading">正在加载资产...</div> : null}
        {!pageLoading && !filteredAssets.length ? (
          <EmptyState
            title="当前分类下暂无资产"
            description="点击“上传资产”开始导入品牌资料。"
          />
        ) : null}

        <div className="biz-table-wrap">
          <table className="biz-table">
            <thead>
              <tr>
                <th>资产名称</th>
                <th>分类</th>
                <th>来源</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredAssets.map((asset) => (
                <tr key={asset.id}>
                  <td>
                    <div className="biz-table-title">{asset.name}</div>
                    <div className="biz-list-meta">{asset.bucket} · {(asset.size / 1024).toFixed(0)} KB</div>
                  </td>
                  <td>
                    <select
                      value={asset.role}
                      onChange={(event) =>
                        void handleUpdate(asset.id, {
                          role: event.target.value as BrandAssetRecord["role"],
                        })
                      }
                    >
                      {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>{asset.source}</td>
                  <td>
                    <StatusBadge value={asset.training_status} />
                  </td>
                  <td>
                    <div className="biz-inline-actions">
                      <select
                        value={asset.training_status}
                        onChange={(event) =>
                          void handleUpdate(asset.id, {
                            training_status: event.target.value as BrandAssetRecord["training_status"],
                          })
                        }
                      >
                        <option value="candidate">待纳入训练池</option>
                        <option value="approved_for_training">已批准训练</option>
                        <option value="excluded">排除</option>
                      </select>
                      <button
                        className="btn ghost btn-small"
                        type="button"
                        onClick={() => void handleUpdate(asset.id, { enabled: !asset.enabled })}
                      >
                        {asset.enabled ? "停用资产" : "启用资产"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageSection>

      <div className="biz-two-column">
        <PageSection title="上传记录" subtitle="当前品牌最近导入的资产">
          <div className="biz-list">
            {assets.slice(0, 5).map((asset) => (
              <article className="biz-list-card" key={asset.id}>
                <div className="biz-list-card-head">
                  <div>
                    <div className="biz-list-title">{asset.name}</div>
                    <div className="biz-list-meta">{asset.source}</div>
                  </div>
                  <StatusBadge value={asset.training_status} />
                </div>
                <p className="biz-card-text">{CATEGORY_LABEL[asset.role]}</p>
              </article>
            ))}
          </div>
        </PageSection>

        <PageSection title="资产详情" subtitle="本轮先提供只读摘要与状态操作">
          {!filteredAssets[0] ? (
            <EmptyState title="暂无资产详情" description="选择或搜索资产后可在这里查看更多信息。" />
          ) : (
            <article className="biz-detail-card">
              <h3>{filteredAssets[0].name}</h3>
              <div className="biz-detail-list">
                <div>资产分类：{CATEGORY_LABEL[filteredAssets[0].role]}</div>
                <div>资产来源：{filteredAssets[0].source}</div>
                <div>上传路径：{filteredAssets[0].path}</div>
                <div>启用状态：{filteredAssets[0].enabled ? "启用" : "停用"}</div>
              </div>
            </article>
          )}
        </PageSection>
      </div>
    </AppShell>
  );
}
