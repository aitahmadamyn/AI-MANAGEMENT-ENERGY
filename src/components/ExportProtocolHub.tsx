import React, { useMemo, useState } from 'react';
import exportManifest from '../data/exportProtocolManifest.json';
import { downloadStagedAsset } from '../utils/downloadFile';

type PhaseFilter =
  | 'All'
  | 'Phase 1'
  | 'Phase 2'
  | 'Phase 3'
  | 'Phase 4'
  | 'Phase 5'
  | 'Phase 6'
  | 'Phase 7';

type ResourceTab = 'all' | 'datasets' | 'notebooks' | 'archives';

const PHASE_FILTERS: PhaseFilter[] = [
  'All',
  'Phase 1',
  'Phase 2',
  'Phase 3',
  'Phase 4',
  'Phase 5',
  'Phase 6',
  'Phase 7',
];

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

export const ExportProtocolHub: React.FC = () => {
  const [phaseFilter, setPhaseFilter] = useState<PhaseFilter>('All');
  const [resourceTab, setResourceTab] = useState<ResourceTab>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const { master_archive, phase_archives, notebooks, datasets, staged_downloads } = exportManifest;
  const numericAudit = (
    exportManifest as { numeric_type_audit?: { files_audited: number; numeric_columns_verified: number } }
  ).numeric_type_audit;

  const sizeLookup = useMemo(() => {
    const map = new Map<string, { size_bytes: number; sha256_short: string }>();
    for (const item of staged_downloads) {
      map.set(item.filename, { size_bytes: item.size_bytes, sha256_short: item.sha256_short });
    }
    return map;
  }, [staged_downloads]);

  const triggerDownload = async (href: string, filename: string) => {
    setDownloadError(null);
    setDownloadingFile(filename);
    try {
      await downloadStagedAsset(href, filename);
    } catch (err) {
      const msg = err instanceof Error ? err.message : `Failed to download ${filename}`;
      setDownloadError(msg);
    } finally {
      setDownloadingFile(null);
    }
  };

  const queryLower = searchQuery.trim().toLowerCase();

  const filteredArchives = useMemo(() => {
    return phase_archives.filter((pa) => {
      const phLabel = `Phase ${pa.phase}`;
      if (phaseFilter !== 'All' && phLabel !== phaseFilter) return false;
      if (!queryLower) return true;
      return (
        pa.filename.toLowerCase().includes(queryLower) ||
        pa.title.toLowerCase().includes(queryLower) ||
        phLabel.toLowerCase().includes(queryLower)
      );
    });
  }, [phase_archives, phaseFilter, queryLower]);

  const filteredNotebooks = useMemo(() => {
    return notebooks.filter((nb) => {
      if (phaseFilter !== 'All' && nb.phase !== phaseFilter) return false;
      if (!queryLower) return true;
      return (
        nb.filename.toLowerCase().includes(queryLower) ||
        nb.description.toLowerCase().includes(queryLower) ||
        nb.phase.toLowerCase().includes(queryLower)
      );
    });
  }, [notebooks, phaseFilter, queryLower]);

  const filteredDatasets = useMemo(() => {
    return datasets.filter((ds) => {
      if (phaseFilter !== 'All' && ds.phase_of_origin !== phaseFilter) return false;
      if (!queryLower) return true;
      return (
        ds.filename.toLowerCase().includes(queryLower) ||
        ds.relative_path.toLowerCase().includes(queryLower) ||
        ds.description.toLowerCase().includes(queryLower) ||
        ds.provenance_status.toLowerCase().includes(queryLower)
      );
    });
  }, [datasets, phaseFilter, queryLower]);

  const resetFilters = () => {
    setPhaseFilter('All');
    setResourceTab('all');
    setSearchQuery('');
  };

  return (
    <div className="space-y-6">
      {downloadError && (
        <div
          role="alert"
          className="bg-red-50 border border-red-300 text-red-900 rounded-lg px-4 py-3 text-xs flex items-center justify-between gap-4"
        >
          <span>
            <span className="font-semibold">Download error:</span> {downloadError}
          </span>
          <button
            type="button"
            onClick={() => setDownloadError(null)}
            className="px-2 py-1 border border-red-300 rounded hover:bg-red-100 cursor-pointer shrink-0"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* KPI & Master Bundle Strip */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="max-w-2xl">
            <div className="text-xs font-mono text-slate-500">
              Mandatory Data &amp; Code Export Protocol · Phases 1–7 · Typed Numbers (XLSX + CSV) &amp; Verified ZIPs
            </div>
            <h2 className="text-base font-semibold text-slate-900 mt-0.5 text-balance">
              Typed Excel (.xlsx) &amp; CSV Datasets, Colab Notebooks &amp; Verified Phase Archives
            </h2>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              Every dataset enforces strict numeric columns (1/0 flags instead of boolean strings, integer code columns for modes/scenarios/seasons/feedstocks) and exports both native typed <span className="font-mono">.xlsx</span> (for Excel/WPS FR) and UTF-8 <span className="font-mono">.csv</span>.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              disabled={downloadingFile !== null}
              onClick={() => triggerDownload('/downloads/DATA_DICTIONARY.xlsx', 'DATA_DICTIONARY.xlsx')}
              className="px-3 py-2 text-xs font-medium text-emerald-900 bg-emerald-50 border border-emerald-300 rounded hover:bg-emerald-100 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
            >
              {downloadingFile === 'DATA_DICTIONARY.xlsx' ? 'Downloading...' : 'DATA_DICTIONARY.xlsx'}
            </button>
            <button
              type="button"
              disabled={downloadingFile !== null}
              onClick={() => triggerDownload('/downloads/PROJECT_MANIFEST.xlsx', 'PROJECT_MANIFEST.xlsx')}
              className="px-3 py-2 text-xs font-medium text-emerald-900 bg-emerald-50 border border-emerald-300 rounded hover:bg-emerald-100 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
            >
              {downloadingFile === 'PROJECT_MANIFEST.xlsx' ? 'Downloading...' : 'PROJECT_MANIFEST.xlsx'}
            </button>
            <button
              type="button"
              disabled={downloadingFile !== null}
              onClick={() => triggerDownload('/downloads/DATA_DICTIONARY.csv', 'DATA_DICTIONARY.csv')}
              className="px-3 py-2 text-xs font-medium text-slate-800 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
            >
              {downloadingFile === 'DATA_DICTIONARY.csv' ? 'Downloading...' : 'Dictionary CSV'}
            </button>
            <button
              type="button"
              disabled={downloadingFile !== null}
              onClick={() => triggerDownload(`/downloads/${master_archive.filename}`, master_archive.filename)}
              className="px-4 py-2 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
            >
              {downloadingFile === master_archive.filename
                ? 'Downloading ZIP...'
                : `Master ZIP (${formatBytes(master_archive.size_bytes)})`}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
          <div>
            <div className="text-xs text-slate-500">Exported Datasets (CSV + XLSX)</div>
            <div className="text-xl font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
              {exportManifest.total_datasets_documented}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              {numericAudit
                ? `${numericAudit.numeric_columns_verified} typed numeric columns verified`
                : 'Strict int/float & 1/0 encodings'}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Colab Notebooks (.ipynb)</div>
            <div className="text-xl font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
              {exportManifest.total_notebooks}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">Phases 1–7 · AST verified</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Manifest Deliverables</div>
            <div className="text-xl font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
              {exportManifest.total_manifest_deliverables}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">XLSX · CSV · IPYNB · PY · PKL</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Complete Master Archive</div>
            <div className="text-xl font-mono font-semibold tabular-nums text-emerald-800 mt-0.5">
              {master_archive.file_count} files
            </div>
            <div className="text-xs font-mono text-slate-500 mt-0.5 truncate" title={master_archive.sha256}>
              SHA-256: {master_archive.sha256.slice(0, 14)}
            </div>
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col xl:flex-row xl:items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-100 rounded-md w-fit">
          {PHASE_FILTERS.map((ph) => (
            <button
              key={ph}
              type="button"
              onClick={() => setPhaseFilter(ph)}
              className={`px-2.5 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                phaseFilter === ph
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {ph}
            </button>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-md w-fit">
            {[
              { id: 'all' as ResourceTab, label: 'All Deliverables' },
              { id: 'datasets' as ResourceTab, label: `Datasets (${datasets.length})` },
              { id: 'notebooks' as ResourceTab, label: `Colab (${notebooks.length})` },
              { id: 'archives' as ResourceTab, label: `Phase ZIPs (${phase_archives.length})` },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setResourceTab(tab.id)}
                className={`px-2.5 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                  resourceTab === tab.id
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter filename or provenance..."
            aria-label="Filter downloadable deliverables"
            className="px-3 py-1.5 text-xs bg-white border border-slate-300 rounded w-full sm:w-64 focus:outline-none focus:border-sky-700"
          />
        </div>
      </div>

      {/* Section A: Per-Phase Verified ZIP Archives */}
      {(resourceTab === 'all' || resourceTab === 'archives') && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                01. Per-Phase Portable Archives (Windows &amp; Colab Verified ZIPs)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Self-contained ZIP packages using FAT/Windows-safe permissions, CSVs, typed XLSX workbooks, Colab notebooks, and reports.
              </p>
            </div>
            <span className="text-xs font-mono tabular-nums text-slate-500 shrink-0">
              {filteredArchives.length} shown
            </span>
          </div>
          {filteredArchives.length === 0 ? (
            <div className="px-5 py-6 text-xs text-slate-500 flex items-center justify-between">
              <span>No phase archives match the active filter.</span>
              <button
                type="button"
                onClick={resetFilters}
                className="px-3 py-1.5 text-xs font-medium text-slate-800 border border-slate-300 rounded hover:bg-slate-50 cursor-pointer"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                    <th className="py-2.5 px-4 font-semibold">Phase</th>
                    <th className="py-2.5 px-3 font-semibold">Archive File</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Files</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Size</th>
                    <th className="py-2.5 px-3 font-semibold">SHA-256 Prefix</th>
                    <th className="py-2.5 px-4 font-semibold text-right">Download</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredArchives.map((pa) => (
                    <tr key={pa.filename} className="hover:bg-slate-50/70">
                      <td className="py-2.5 px-4 font-medium text-slate-900 whitespace-nowrap">
                        {pa.title}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-700 whitespace-nowrap">
                        {pa.filename}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-slate-700">
                        {pa.file_count}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-slate-700 whitespace-nowrap">
                        {formatBytes(pa.size_bytes)}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-500 whitespace-nowrap">
                        {pa.sha256.slice(0, 16)}
                      </td>
                      <td className="py-2.5 px-4 text-right whitespace-nowrap">
                        <button
                          type="button"
                          disabled={downloadingFile !== null}
                          onClick={() => triggerDownload(`/downloads/${pa.filename}`, pa.filename)}
                          className="inline-block px-3 py-1.5 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 transition-colors cursor-pointer disabled:opacity-60"
                        >
                          {downloadingFile === pa.filename ? 'Downloading...' : 'Download ZIP'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Section B: Google Colab Notebooks */}
      {(resourceTab === 'all' || resourceTab === 'notebooks') && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                02. Google Colab-Compatible Executable Notebooks (.ipynb)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Each notebook contains Colab dependency installation, Drive/upload bootstrap, equations, visualizations, validation checks, and final ZIP export.
              </p>
            </div>
            <span className="text-xs font-mono tabular-nums text-slate-500 shrink-0">
              {filteredNotebooks.length} shown
            </span>
          </div>
          {filteredNotebooks.length === 0 ? (
            <div className="px-5 py-6 text-xs text-slate-500 flex items-center justify-between">
              <span>No notebooks match the active filter.</span>
              <button
                type="button"
                onClick={resetFilters}
                className="px-3 py-1.5 text-xs font-medium text-slate-800 border border-slate-300 rounded hover:bg-slate-50 cursor-pointer"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                    <th className="py-2.5 px-4 font-semibold">Phase</th>
                    <th className="py-2.5 px-3 font-semibold">Notebook File</th>
                    <th className="py-2.5 px-3 font-semibold">Description</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Cells</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Size</th>
                    <th className="py-2.5 px-4 font-semibold text-right">Download</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredNotebooks.map((nb) => (
                    <tr key={nb.filename} className="hover:bg-slate-50/70">
                      <td className="py-2.5 px-4 font-mono font-medium text-sky-800 whitespace-nowrap">
                        {nb.phase}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-900 whitespace-nowrap">
                        {nb.filename}
                      </td>
                      <td className="py-2.5 px-3 text-slate-600">{nb.description}</td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-slate-700">
                        {nb.cells}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-slate-700 whitespace-nowrap">
                        {formatBytes(nb.size_bytes)}
                      </td>
                      <td className="py-2.5 px-4 text-right whitespace-nowrap">
                        <button
                          type="button"
                          disabled={downloadingFile !== null}
                          onClick={() => triggerDownload(nb.href, nb.filename)}
                          className="inline-block px-3 py-1.5 text-xs font-medium text-slate-800 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors cursor-pointer disabled:opacity-60"
                        >
                          {downloadingFile === nb.filename ? 'Downloading...' : 'Download .ipynb'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Section C: Complete Typed Dataset Registry (XLSX + UTF-8 CSV) */}
      {(resourceTab === 'all' || resourceTab === 'datasets') && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                03. Typed Datasets — Native Excel (.xlsx) &amp; UTF-8 CSV (Phases 1–7)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Use <span className="font-mono font-semibold text-emerald-800">.xlsx</span> to open typed numeric columns cleanly in WPS Spreadsheets / Excel (FR/EN), or <span className="font-mono">.csv</span> for Python/pandas &amp; Google Colab.
              </p>
            </div>
            <span className="text-xs font-mono tabular-nums text-slate-500 shrink-0">
              {filteredDatasets.length} shown
            </span>
          </div>
          {filteredDatasets.length === 0 ? (
            <div className="px-5 py-6 text-xs text-slate-500 flex items-center justify-between">
              <span>No datasets match the active filter.</span>
              <button
                type="button"
                onClick={resetFilters}
                className="px-3 py-1.5 text-xs font-medium text-slate-800 border border-slate-300 rounded hover:bg-slate-50 cursor-pointer"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                    <th className="py-2.5 px-4 font-semibold">Phase</th>
                    <th className="py-2.5 px-3 font-semibold">Dataset &amp; Description</th>
                    <th className="py-2.5 px-3 font-semibold">Provenance</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Shape</th>
                    <th className="py-2.5 px-3 font-semibold text-right">CSV Size</th>
                    <th className="py-2.5 px-4 font-semibold text-right">Download</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredDatasets.map((ds) => {
                    const meta = sizeLookup.get(ds.filename);
                    const xlsxName = (ds as { xlsx_filename?: string }).xlsx_filename;
                    const xlsxHref = (ds as { xlsx_href?: string }).xlsx_href;
                    return (
                      <tr key={ds.relative_path} className="hover:bg-slate-50/70 align-top">
                        <td className="py-2.5 px-4 font-mono font-medium text-slate-700 whitespace-nowrap">
                          {ds.phase_of_origin}
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="font-mono font-medium text-slate-900">{ds.filename}</div>
                          <div className="text-slate-600 mt-0.5">{ds.description}</div>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-600 whitespace-nowrap">
                          {ds.provenance_status}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono tabular-nums text-slate-700 whitespace-nowrap">
                          {ds.row_count.toLocaleString()} × {ds.col_count}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono tabular-nums text-slate-600 whitespace-nowrap">
                          {meta ? formatBytes(meta.size_bytes) : '—'}
                        </td>
                        <td className="py-2.5 px-4 text-right whitespace-nowrap">
                          <div className="inline-flex items-center gap-1.5">
                            {xlsxHref && xlsxName && (
                              <button
                                type="button"
                                disabled={downloadingFile !== null}
                                onClick={() => triggerDownload(xlsxHref, xlsxName)}
                                className="px-2.5 py-1.5 text-xs font-medium text-emerald-900 bg-emerald-50 border border-emerald-300 rounded hover:bg-emerald-100 transition-colors cursor-pointer disabled:opacity-60"
                              >
                                {downloadingFile === xlsxName ? '...' : 'Excel .xlsx'}
                              </button>
                            )}
                            {ds.href ? (
                              <button
                                type="button"
                                disabled={downloadingFile !== null}
                                onClick={() => triggerDownload(ds.href, ds.filename)}
                                className="px-2.5 py-1.5 text-xs font-medium text-slate-800 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors cursor-pointer disabled:opacity-60"
                              >
                                {downloadingFile === ds.filename ? '...' : 'CSV'}
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Section D: Google Colab Execution Instructions */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              04. Running Notebooks Standalone in Google Colab &amp; Excel FR
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Reproducible workflow without hidden local paths or Colab environment lock-in.
            </p>
          </div>
          <button
            type="button"
            disabled={downloadingFile !== null}
            onClick={() => triggerDownload('/downloads/colab_execution_guide.md', 'colab_execution_guide.md')}
            className="px-3 py-1.5 text-xs font-medium text-slate-800 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
          >
            {downloadingFile === 'colab_execution_guide.md' ? 'Downloading...' : 'Download Colab Guide (.md)'}
          </button>
        </div>
        <ol className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs text-slate-700">
          <li className="border border-slate-200 rounded p-3 space-y-1">
            <div className="font-mono font-semibold text-slate-900">01. Download Package</div>
            <p className="text-slate-600 leading-relaxed">
              Download either a single phase archive (<span className="font-mono">EcoFarm_Phase05_Package.zip</span>) or the complete bundle (<span className="font-mono">EcoFarm_Complete_Phases1_to_7.zip</span>).
            </p>
          </li>
          <li className="border border-slate-200 rounded p-3 space-y-1">
            <div className="font-mono font-semibold text-slate-900">02. Open in Excel or Colab</div>
            <p className="text-slate-600 leading-relaxed">
              Open any <span className="font-mono">.xlsx</span> in WPS Spreadsheets / Excel with typed numeric cells, or upload any <span className="font-mono">.ipynb</span> in Google Colab.
            </p>
          </li>
          <li className="border border-slate-200 rounded p-3 space-y-1">
            <div className="font-mono font-semibold text-slate-900">03. Bootstrap &amp; Data</div>
            <p className="text-slate-600 leading-relaxed">
              Run Cell 1 (<span className="font-mono">!pip install</span> &amp; optional Google Drive mount) and Cell 2 to upload the phase ZIP or CSV files.
            </p>
          </li>
          <li className="border border-slate-200 rounded p-3 space-y-1">
            <div className="font-mono font-semibold text-slate-900">04. Execute &amp; Export</div>
            <p className="text-slate-600 leading-relaxed">
              Run all cells sequentially; the final packaging cell exports regenerated CSVs, plots, and <span className="font-mono">.pkl</span> artifacts via <span className="font-mono">files.download</span>.
            </p>
          </li>
        </ol>
      </div>
    </div>
  );
};
