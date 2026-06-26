"use client";

import { FileImage, FileText, Folder, Globe2, Loader2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  fetchBrandAssetsPageWithFilters,
  type BrandAssetsPageResponse,
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
  const [message, setMessage] = useState<string | null>(null);
  const searchTimer = useRef<number | null>(null);

  useEffect(() => {
    setUpload((current) => ({
      ...current,
      folder:
        data.folders.find((item) => item.name === current.folder)?.name ?? data.uploadForm.folder,
    }));
  }, [data.folders, data.uploadForm.folder]);

  const loadData = async (nextFilters: FiltersState) => {
    setLoading(true);
    setMessage(null);
    try {
      const next = await fetchBrandAssetsPageWithFilters(nextFilters);
      setData(next);
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
      setMessage(`上传成功，已写入 ${result.count} 条资产记录。`);
      await loadData(filters);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setUploading(false);
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
          <div className="assets-brand-list">
            {data.brands.map((brand) => (
              <button
                className={`assets-brand-item ${filters.brandId === brand.id ? "active" : ""}`}
                key={brand.id}
                type="button"
                onClick={() => updateFilters({ brandId: brand.id })}
              >
                <span>
                  <strong>{brand.name}</strong>
                  <small>{brand.status}</small>
                </span>
                <em>{brand.assets}</em>
              </button>
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
                  </tr>
                </thead>
                <tbody>
                  {data.assets.length ? (
                    data.assets.map((asset) => (
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
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="table-empty" colSpan={5}>
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
    </div>
  );
}
