"use client";

import { FileImage, FileText, Folder, Globe2, Loader2, Plus, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  brandAssetFileUrl,
  createBrand,
  deleteBrand,
  deleteBrandAsset,
  fetchBrandAssetPreview,
  fetchBrandAssetsPageWithFilters,
  type BrandAssetPreviewResponse,
  type BrandAssetsPageResponse,
  updateBrandAssetTrainingMeta,
  updateBrand,
  uploadBrandAssets,
} from "@/lib/api";

const ICONS = {
  FileText,
  FileImage,
  Globe2,
  Folder,
};

interface FiltersState {
  brandId: number;
  folder: string;
  status: string;
  search: string;
}

interface UploadState {
  name: string;
  folder: string;
  source: string;
  files: File[];
}

interface BrandFormState {
  id?: number;
  name: string;
  status: string;
}

interface AssetTrainingDraft {
  trainingRole: string;
  includeInTraining: boolean;
  qualityLevel: string;
}

export function BrandAssetsPageClient({ initialData }: { initialData: BrandAssetsPageResponse }) {
  const [data, setData] = useState(initialData);
  const [filters, setFilters] = useState<FiltersState>({
    brandId: initialData.filters.brandId,
    folder: initialData.filters.folder,
    status: initialData.filters.status,
    search: initialData.filters.search,
  });
  const [upload, setUpload] = useState<UploadState>({
    name: initialData.uploadForm.name,
    folder: initialData.uploadForm.folder,
    source: initialData.uploadForm.source,
    files: [],
  });
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [savingBrand, setSavingBrand] = useState(false);
  const [deletingAssetId, setDeletingAssetId] = useState<number | null>(null);
  const [savingAssetId, setSavingAssetId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<BrandAssetPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [brandForm, setBrandForm] = useState<BrandFormState>({
    name: "",
    status: "active",
  });
  const searchTimer = useRef<number | null>(null);
  const [assetDrafts, setAssetDrafts] = useState<Record<number, AssetTrainingDraft>>({});

  useEffect(() => {
    setUpload((current) => ({
      ...current,
      folder:
        data.folders.find((item) => item.name === current.folder)?.name ?? data.uploadForm.folder,
    }));
  }, [data.folders, data.uploadForm.folder]);

  const loadData = async (nextFilters: Partial<FiltersState> = filters) => {
    setLoading(true);
    setMessage(null);
    try {
      const next = await fetchBrandAssetsPageWithFilters(nextFilters);
      setData(next);
      setFilters(next.filters);
      setAssetDrafts(
        Object.fromEntries(
          next.assets.map((asset) => [
            asset.id,
            {
              trainingRole: asset.trainingRole,
              includeInTraining: asset.includeInTraining,
              qualityLevel: asset.qualityLevel,
            },
          ]),
        ),
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const updateFilters = (patch: Partial<FiltersState>) => {
    const next = { ...filters, ...patch };
    setFilters(next);
    if ("search" in patch) {
      if (searchTimer.current) window.clearTimeout(searchTimer.current);
      searchTimer.current = window.setTimeout(() => {
        void loadData(next);
      }, 250);
      return;
    }
    void loadData(next);
  };

  const resetBrandForm = () => setBrandForm({ name: "", status: "active" });

  const editBrand = (brand: BrandAssetsPageResponse["brands"][number]) => {
    setBrandForm({ id: brand.id, name: brand.name, status: brand.status });
  };

  const saveBrand = async () => {
    if (!brandForm.name.trim()) {
      setMessage("请输入品牌名称。");
      return;
    }
    setSavingBrand(true);
    setMessage(null);
    try {
      const saved = brandForm.id
        ? await updateBrand({
            id: brandForm.id,
            name: brandForm.name,
            status: brandForm.status,
          })
        : await createBrand({ name: brandForm.name, status: brandForm.status });
      const successMessage = brandForm.id ? "品牌已更新。" : "品牌已创建。";
      resetBrandForm();
      await loadData({ ...filters, brandId: saved.id });
      setMessage(successMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSavingBrand(false);
    }
  };

  const handleDeleteBrand = async (brandId: number) => {
    const brand = data.brands.find((item) => item.id === brandId);
    if (!brand) return;
    if (!window.confirm(`确定删除品牌「${brand.name}」及其资产、规则和训练记录吗？`)) return;
    setSavingBrand(true);
    setMessage(null);
    try {
      await deleteBrand(brandId);
      if (brandForm.id === brandId) resetBrandForm();
      await loadData({ folder: "", status: "", search: "" });
      setMessage("品牌已删除。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSavingBrand(false);
    }
  };

  const handleDeleteAsset = async (assetId: number) => {
    const asset = data.assets.find((item) => item.id === assetId);
    if (!asset) return;
    if (!window.confirm(`确定删除资产「${asset.name}」吗？`)) return;
    setDeletingAssetId(assetId);
    setMessage(null);
    try {
      await deleteBrandAsset(assetId);
      if (preview?.id === assetId) setPreview(null);
      await loadData(filters);
      setMessage("资产已删除。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setDeletingAssetId(null);
    }
  };

  const handleUpload = async () => {
    if (!upload.files.length) {
      setMessage("请先选择至少一个文件。");
      return;
    }
    setUploading(true);
    setMessage(null);
    try {
      const result = await uploadBrandAssets({
        brandId: filters.brandId,
        name: upload.name,
        folder: upload.folder,
        source: upload.source,
        files: upload.files,
      });
      setUpload((current) => ({ ...current, files: [] }));
      await loadData(filters);
      setMessage(`上传成功，已写入 ${result.count} 条资产记录。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setUploading(false);
    }
  };

  const handlePreview = async (assetId: number) => {
    setPreviewLoading(true);
    setMessage(null);
    try {
      const result = await fetchBrandAssetPreview(assetId);
      setPreview(result);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setPreviewLoading(false);
    }
  };

  const updateAssetDraft = (assetId: number, patch: Partial<AssetTrainingDraft>) => {
    setAssetDrafts((current) => ({
      ...current,
      [assetId]: {
        trainingRole: current[assetId]?.trainingRole ?? "reference",
        includeInTraining: current[assetId]?.includeInTraining ?? false,
        qualityLevel: current[assetId]?.qualityLevel ?? "normal",
        ...patch,
      },
    }));
  };

  const handleSaveAssetTrainingMeta = async (assetId: number) => {
    const draft = assetDrafts[assetId];
    if (!draft) return;
    setSavingAssetId(assetId);
    setMessage(null);
    try {
      await updateBrandAssetTrainingMeta({
        assetId,
        trainingRole: draft.trainingRole,
        includeInTraining: draft.includeInTraining,
        qualityLevel: draft.qualityLevel,
      });
      await loadData(filters);
      setMessage("资产训练治理信息已更新。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSavingAssetId(null);
    }
  };

  return (
    <div className="assets-page">
      <div className="topbar">
        <div className="topbar-left">
          <h1>{data.page.title}</h1>
          <div className="subtitle">{data.page.subtitle}</div>
        </div>
        <div className="topbar-right">
          <button className="btn ghost" type="button">
            批量导入
          </button>
          <button className="btn primary" type="button" onClick={handleUpload}>
            {uploading ? <Loader2 className="spin" size={16} /> : <Upload size={16} />} 上传资产
          </button>
        </div>
      </div>

      <div className="assets-layout">
        <aside className="assets-brand-panel">
          <div className="assets-panel-title">品牌空间</div>
          <div className="brand-manage-form">
            <input
              placeholder="品牌名称"
              value={brandForm.name}
              onChange={(e) => setBrandForm((current) => ({ ...current, name: e.target.value }))}
            />
            <select
              value={brandForm.status}
              onChange={(e) => setBrandForm((current) => ({ ...current, status: e.target.value }))}
            >
              <option value="active">active</option>
              <option value="draft">draft</option>
              <option value="paused">paused</option>
            </select>
            <div className="brand-manage-actions">
              <button className="btn primary" disabled={savingBrand} type="button" onClick={saveBrand}>
                {savingBrand ? <Loader2 className="spin" size={14} /> : <Plus size={14} />}
                {brandForm.id ? "保存品牌" : "新增品牌"}
              </button>
              {brandForm.id ? (
                <button className="btn ghost" type="button" onClick={resetBrandForm}>
                  取消
                </button>
              ) : null}
            </div>
          </div>
          <div className="assets-brand-list">
            {data.brands.map((brand) => (
              <div
                className={`assets-brand-item ${filters.brandId === brand.id ? "active" : ""}`}
                key={brand.id}
              >
                <button
                  className="assets-brand-select"
                  type="button"
                  onClick={() => updateFilters({ brandId: brand.id })}
                >
                  <span>
                    <strong>{brand.name}</strong>
                    <small>{brand.status}</small>
                  </span>
                  <em>{brand.assets}</em>
                </button>
                <div className="assets-brand-actions">
                  <button type="button" onClick={() => editBrand(brand)}>
                    编辑
                  </button>
                  <button
                    className="danger-link"
                    disabled={savingBrand || data.brands.length <= 1}
                    type="button"
                    onClick={() => handleDeleteBrand(brand.id)}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <section className="assets-main-panel">
          <div className="assets-toolbar">
            <select
              aria-label="资产分类"
              value={filters.folder}
              onChange={(e) => updateFilters({ folder: e.target.value })}
            >
              <option value="">全部文件夹</option>
              {data.folders.map((folder) => (
                <option key={folder.name} value={folder.name}>
                  {folder.name}
                </option>
              ))}
            </select>
            <select
              aria-label="资产状态"
              value={filters.status}
              onChange={(e) => updateFilters({ status: e.target.value })}
            >
              <option value="">全部状态</option>
              {data.statuses.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <input
              placeholder="搜索资产名称或来源"
              value={filters.search}
              onChange={(e) => updateFilters({ search: e.target.value })}
            />
          </div>

          <div className="assets-folder-grid">
            {data.folders.map((folder) => {
              const Icon = ICONS[folder.icon as keyof typeof ICONS] ?? Folder;
              return (
                <button
                  className={`assets-folder-card assets-folder-button ${
                    filters.folder === folder.name ? "active" : ""
                  }`}
                  key={folder.name}
                  type="button"
                  onClick={() =>
                    updateFilters({ folder: filters.folder === folder.name ? "" : folder.name })
                  }
                >
                  <div className="assets-folder-icon">
                    <Icon size={20} />
                  </div>
                  <div>
                    <h2>{folder.name}</h2>
                    <p>{folder.description}</p>
                    <span>{folder.count} 项资产</span>
                  </div>
                </button>
              );
            })}
          </div>

          <section className="assets-table-card">
            <div className="assets-card-head">
              <h2>最近资产</h2>
              <span>
                当前品牌：{data.selectedBrand.name}
                {loading ? " · 刷新中..." : ""}
              </span>
            </div>
            <div className="assets-table-wrap">
              <table className="assets-table">
                <thead>
                  <tr>
                    <th>资产名称</th>
                    <th>文件夹</th>
                    <th>类型</th>
                    <th>来源</th>
                    <th>状态</th>
                    <th>训练角色</th>
                    <th>训练池</th>
                    <th>质量等级</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {data.assets.length ? (
                    data.assets.map((asset) => {
                      const draft = assetDrafts[asset.id] ?? {
                        trainingRole: asset.trainingRole,
                        includeInTraining: asset.includeInTraining,
                        qualityLevel: asset.qualityLevel,
                      };
                      return (
                        <tr key={asset.id}>
                          <td>{asset.name}</td>
                          <td>{asset.folder}</td>
                          <td>{asset.type}</td>
                          <td>{asset.source}</td>
                          <td>
                            <span
                              className={`asset-status ${
                                asset.status === "待校验" ? "warning" : "success"
                              }`}
                            >
                              {asset.status}
                            </span>
                          </td>
                          <td>
                            <select
                              value={draft.trainingRole}
                              onChange={(e) =>
                                updateAssetDraft(asset.id, { trainingRole: e.target.value })
                              }
                            >
                              <option value="core">核心规范</option>
                              <option value="high_quality">高质量案例</option>
                              <option value="reference">普通参考</option>
                              <option value="excluded">排除样本</option>
                            </select>
                          </td>
                          <td>
                            <label className="switch compact-switch">
                              <input
                                checked={draft.includeInTraining}
                                type="checkbox"
                                onChange={(e) =>
                                  updateAssetDraft(asset.id, {
                                    includeInTraining: e.target.checked,
                                  })
                                }
                              />
                              <span className="switch-track" />
                            </label>
                          </td>
                          <td>
                            <select
                              value={draft.qualityLevel}
                              onChange={(e) =>
                                updateAssetDraft(asset.id, { qualityLevel: e.target.value })
                              }
                            >
                              <option value="high">high</option>
                              <option value="normal">normal</option>
                              <option value="low">low</option>
                            </select>
                          </td>
                          <td>
                            <div className="table-actions">
                              <button
                                className="table-action"
                                disabled={previewLoading}
                                type="button"
                                onClick={() => handlePreview(asset.id)}
                              >
                                预览
                              </button>
                              <button
                                className="table-action"
                                disabled={savingAssetId === asset.id}
                                type="button"
                                onClick={() => handleSaveAssetTrainingMeta(asset.id)}
                              >
                                {savingAssetId === asset.id ? (
                                  <Loader2 className="spin" size={12} />
                                ) : null}
                                保存治理
                              </button>
                              <button
                                className="table-action danger"
                                disabled={deletingAssetId === asset.id}
                                type="button"
                                onClick={() => handleDeleteAsset(asset.id)}
                              >
                                {deletingAssetId === asset.id ? (
                                  <Loader2 className="spin" size={12} />
                                ) : (
                                  <Trash2 size={12} />
                                )}
                                删除
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td className="table-empty" colSpan={9}>
                        没有匹配的资产记录。
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </section>

        <aside className="assets-upload-panel">
          <div className="assets-panel-title">上传品牌资产</div>
          <label className="field">
            <span className="field-label">资产名称</span>
            <input
              value={upload.name}
              onChange={(e) => setUpload((current) => ({ ...current, name: e.target.value }))}
            />
          </label>
          <label className="field">
            <span className="field-label">归属文件夹</span>
            <select
              value={upload.folder}
              onChange={(e) => setUpload((current) => ({ ...current, folder: e.target.value }))}
            >
              {data.folders.map((folder) => (
                <option key={folder.name} value={folder.name}>
                  {folder.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">资产来源</span>
            <input
              value={upload.source}
              onChange={(e) => setUpload((current) => ({ ...current, source: e.target.value }))}
            />
          </label>
          <label className="assets-dropzone assets-dropzone-label">
            <input
              className="assets-file-input"
              multiple
              type="file"
              onChange={(e) =>
                setUpload((current) => ({ ...current, files: Array.from(e.target.files ?? []) }))
              }
            />
            <Upload size={20} />
            <strong>拖拽或点击上传</strong>
            <span>支持图片、PDF、HTML、PSD、Markdown、Word 等格式</span>
          </label>
          {upload.files.length ? (
            <div className="chips">
              {upload.files.map((file) => (
                <span className="chip-static" key={`${file.name}-${file.size}`}>
                  {file.name}
                </span>
              ))}
            </div>
          ) : null}
          {message ? <div className="hint">{message}</div> : null}
          <p className="hint">训练前会自动进行格式识别、文件夹校验和可解析性检查。</p>
          <button className="btn primary assets-submit" disabled={uploading} type="button" onClick={handleUpload}>
            {uploading ? <Loader2 className="spin" size={16} /> : null}
            开始上传
          </button>
        </aside>
      </div>

      {preview ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="asset-preview-modal">
            <div className="split-line">
              <div>
                <h2 className="section-title">{preview.name}</h2>
                <div className="subtitle">
                  {preview.brandName} / {preview.folder} / {preview.contentType || "未知类型"}
                </div>
              </div>
              <button className="btn ghost" type="button" onClick={() => setPreview(null)}>
                关闭
              </button>
            </div>

            <div className="asset-preview-meta">
              <span>来源：{preview.source || "未知来源"}</span>
              <span>状态：{preview.status}</span>
              <span>训练角色：{preview.trainingRole}</span>
              <span>纳入训练：{preview.includeInTraining ? "是" : "否"}</span>
              <span>质量：{preview.qualityLevel}</span>
              <span>大小：{preview.size ? `${(preview.size / 1024).toFixed(1)} KB` : "未知"}</span>
            </div>

            <div className="asset-preview-body">
              {preview.previewType === "image" && preview.fileUrl ? (
                <img alt={preview.name} className="asset-preview-image" src={brandAssetFileUrl(preview.fileUrl)} />
              ) : null}
              {preview.previewType === "pdf" && preview.fileUrl ? (
                <iframe
                  className="asset-preview-frame"
                  src={brandAssetFileUrl(preview.fileUrl)}
                  title={preview.name}
                />
              ) : null}
              {preview.previewType === "text" ? (
                <pre className="asset-preview-text">
                  {preview.textPreview || "文件暂无可读取文本内容。"}
                </pre>
              ) : null}
              {["metadata", "unknown"].includes(preview.previewType) ? (
                <div className="asset-preview-empty">
                  <p>
                    {preview.fileExists
                      ? "该文件类型暂不支持内嵌预览，可以下载后查看。"
                      : "当前记录没有可访问的本地文件，展示资产元信息。"}
                  </p>
                  {preview.fileUrl ? (
                    <a className="download" href={brandAssetFileUrl(preview.fileUrl)} rel="noreferrer" target="_blank">
                      下载文件
                    </a>
                  ) : null}
                  <pre>{JSON.stringify(preview.metadata ?? {}, null, 2)}</pre>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
