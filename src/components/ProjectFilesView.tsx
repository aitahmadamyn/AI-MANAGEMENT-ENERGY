import React, { useState } from 'react';
import { MISSING_PLANT_INFO, PHASE1_FILES } from '../data/phase1Data';
import { ExportProtocolHub } from './ExportProtocolHub';

type FilesSubView = 'exports' | 'code';

export const ProjectFilesView: React.FC = () => {
  const [subView, setSubView] = useState<FilesSubView>('exports');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  const activeFile = PHASE1_FILES[selectedIndex];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(activeFile.content);
      setCopiedPath(activeFile.path);
      setTimeout(() => setCopiedPath(null), 1800);
    } catch {
      setCopiedPath(null);
    }
  };

  const handleDownloadFile = () => {
    const blob = new Blob([activeFile.content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = activeFile.path.split('/').pop() || 'phase1_file.txt';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Sub-view switcher */}
      <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-200/70 rounded-md w-fit">
        <button
          type="button"
          onClick={() => setSubView('exports')}
          className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
            subView === 'exports'
              ? 'bg-white text-slate-900 shadow-xs'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Exports, CSVs &amp; Colab Packages (Phases 1–7)
        </button>
        <button
          type="button"
          onClick={() => setSubView('code')}
          className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
            subView === 'code'
              ? 'bg-white text-slate-900 shadow-xs'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Source Modules &amp; Pilot Assumptions
        </button>
      </div>

      {subView === 'exports' && <ExportProtocolHub />}

      {subView === 'code' && (
        <>
          {/* File Explorer + Code Viewer */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <div className="lg:col-span-4 bg-white border border-slate-200 rounded-lg p-4 space-y-3">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  EcoFarm_AI Project Modules &amp; Reports (Phases 1–7)
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Generated engineering modules, notebooks, traceability registers, and validation reports for Phases 1–7.
                </p>
              </div>

              <div className="space-y-1.5 pt-2 border-t border-slate-100 max-h-[420px] overflow-y-auto pr-1">
                {PHASE1_FILES.map((file, idx) => (
                  <button
                    key={file.path}
                    type="button"
                    onClick={() => setSelectedIndex(idx)}
                    className={`w-full text-left px-3 py-2.5 rounded border transition-colors cursor-pointer ${
                      idx === selectedIndex
                        ? 'bg-sky-50 border-sky-300 text-slate-900'
                        : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    <div className="font-mono text-xs font-semibold truncate">
                      {file.path}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">
                      {file.summary}
                    </div>
                  </button>
                ))}
              </div>

              <div className="pt-3 border-t border-slate-100 text-xs text-slate-600 space-y-1 font-mono">
                <div className="font-sans font-semibold text-slate-700 mb-1">
                  Active Project Directories (Phases 1–7)
                </div>
                <div>data/raw · processed · simulated · ml · outputs</div>
                <div>notebooks · models · dashboard · reports · exports</div>
              </div>
            </div>

        {/* Code Viewer */}
        <div className="lg:col-span-8 bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-mono text-xs font-semibold text-slate-900">
                {activeFile.path}
              </div>
              <div className="text-xs text-slate-500">{activeFile.summary}</div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopy}
                className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
              >
                {copiedPath === activeFile.path ? 'Copied' : 'Copy Code'}
              </button>
              <button
                type="button"
                onClick={handleDownloadFile}
                className="px-3 py-1.5 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
              >
                Download File
              </button>
            </div>
          </div>
          <pre className="p-4 text-xs font-mono text-slate-800 bg-slate-50/40 overflow-x-auto leading-relaxed max-h-[460px]">
            <code>{activeFile.content}</code>
          </pre>
        </div>
      </div>

      {/* Missing Plant Information & Phase 2 Readiness Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200">
          <h3 className="text-sm font-semibold text-slate-900">
            Identified Missing Pilot-Plant Information (To Confirm in Phases 2–3)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Where pilot hardware specifications are not yet finalized, Phase 1 records explicit engineering assumptions rather than inventing measurements.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600">
                <th className="py-2.5 px-4">ID</th>
                <th className="py-2.5 px-4">Subsystem</th>
                <th className="py-2.5 px-4">Missing Parameter</th>
                <th className="py-2.5 px-4">Phase 1 Baseline Assumption</th>
                <th className="py-2.5 px-4">Needed By</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {MISSING_PLANT_INFO.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/70 align-top">
                  <td className="py-3 px-4 font-mono font-semibold text-slate-800 whitespace-nowrap">
                    {item.id}
                  </td>
                  <td className="py-3 px-4 font-medium text-slate-700 whitespace-nowrap">
                    {item.subsystem}
                  </td>
                  <td className="py-3 px-4 text-slate-800">
                    <div className="font-medium">{item.parameter}</div>
                    <div className="text-slate-500 mt-0.5">{item.impact}</div>
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-700">
                    {item.phase1Assumption}
                  </td>
                  <td className="py-3 px-4 font-mono text-sky-700 whitespace-nowrap">
                    {item.neededForPhase}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
        </>
      )}
    </div>
  );
};
