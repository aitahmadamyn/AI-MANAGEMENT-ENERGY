import React, { useState } from 'react';
import phase5MlStats from '../data/phase5MlStats.json';

type Phase5SubTab = 'solar' | 'dryer' | 'audit';
type SolarPlotMode = 'scatter' | 'july_ts';

const FEEDSTOCK_COLORS: Record<string, string> = {
  olive_pomace: '#0284c7',
  wheat_straw: '#d97706',
  wood_chips: '#0f766e',
};

const FEEDSTOCK_LABELS: Record<string, string> = {
  olive_pomace: 'Olive Pomace',
  wheat_straw: 'Wheat Straw',
  wood_chips: 'Wood Chips',
};

export const Phase5MlView: React.FC = () => {
  const [subTab, setSubTab] = useState<Phase5SubTab>('solar');
  const [solarPlotMode, setSolarPlotMode] = useState<SolarPlotMode>('scatter');
  const [hoverSolarPt, setHoverSolarPt] = useState<number | null>(null);
  const [hoverDryerPt, setHoverDryerPt] = useState<number | null>(null);

  const solar = phase5MlStats.solar_model;
  const dryer = phase5MlStats.dryer_model;
  const smoke = phase5MlStats.inference_smoke_check;

  const selectedSolar = solar.models.find((m) => m.selected) ?? solar.models[solar.models.length - 1];
  const selectedDryer = dryer.models.find((m) => m.selected) ?? dryer.models[dryer.models.length - 1];

  // Geometry helper for scatter plots
  const scW = 460;
  const scH = 290;
  const padL = 52;
  const padR = 20;
  const padT = 20;
  const padB = 42;
  const pw = scW - padL - padR;
  const ph = scH - padT - padB;

  const solarMax = Math.max(
    14.5,
    ...solar.scatter_sample.map((p) => Math.max(p.actual, p.predicted))
  );
  const dryerMax = Math.max(
    10.0,
    ...dryer.scatter_sample.map((p) => Math.max(p.actual, p.predicted))
  ) * 1.05;

  const activeSolarPt = hoverSolarPt !== null ? solar.scatter_sample[hoverSolarPt] : null;
  const activeDryerPt = hoverDryerPt !== null ? dryer.scatter_sample[hoverDryerPt] : null;

  return (
    <div className="space-y-6">
      {/* KPI Summary Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Model 1 Winner (2022 Val → 2023 Test)</div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {selectedSolar.test.rmse.toFixed(4)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">kW RMSE</span>
          </div>
          <div className="mt-1 text-xs text-sky-700 font-medium">
            ◆ {selectedSolar.short_label.replace('\n', ' ')} · Test R² = {selectedSolar.test.r2.toFixed(5)}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Model 2 Winner (Unified Multi-Feedstock)</div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {selectedDryer.test.rmse.toFixed(4)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">kW_th RMSE</span>
          </div>
          <div className="mt-1 text-xs text-emerald-700 font-medium">
            ▲ {selectedDryer.short_label.replace('\n', ' ')} · Test R² = {selectedDryer.test.r2.toFixed(5)}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Chronological Split &amp; Leakage Guard</div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              2020–23
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">strict order</span>
          </div>
          <div className="mt-1 text-xs text-slate-600 font-medium">
            Train 20–21 · Val 22 (Select) · Test 23 (Final)
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Multi-Feedstock Dryer Coverage</div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {dryer.feedstocks.length}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">agricultural residues</span>
          </div>
          <div className="mt-1 text-xs text-amber-800 font-medium">
            ▲ Olive Pomace · Wheat Straw · Wood Chips
          </div>
        </div>
      </div>

      {/* Sub-navigation */}
      <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-200/70 rounded-md w-fit">
        {(
          [
            { id: 'solar', label: 'Model 1: Solar PV Power' },
            { id: 'dryer', label: 'Model 2: Biomass Dryer Demand' },
            { id: 'audit', label: 'Multi-Feedstock Library & Leakage Audit' },
          ] as { id: Phase5SubTab; label: string }[]
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setSubTab(tab.id)}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
              subTab === tab.id
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* MODEL 1: SOLAR PV PREDICTION */}
      {subTab === 'solar' && (
        <div className="space-y-6">
          <div className="bg-sky-50 border border-sky-200 rounded-lg p-4 text-xs text-sky-950 leading-relaxed">
            <span className="font-semibold">Reference-System Provenance: </span>
            {solar.reference_system_note} Midday PVGIS satellite-frame zero sentinels kept transparently across splits:
            <span className="font-mono ml-1.5">
              Train={solar.splits.train_2020_2021.sentinel_hours}h · Val={solar.splits.val_2022.sentinel_hours}h · Test={solar.splits.test_2023.sentinel_hours}h
            </span>
            .
          </div>

          {/* Model 1 Comparison Table */}
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  Model 1 — Chronological Training, 2022 Validation Selection &amp; 2023 Test Comparison
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Target: <span className="font-mono">pvgis_pv_power_kw</span> (kW AC, 15 kWp reference) · Scaler fit strictly on 2020–2021 Train
                </p>
              </div>
              <span className="text-xs font-mono text-sky-700 font-semibold">
                Selection: {solar.selected_model_name}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
                    <th className="py-2.5 px-4 font-semibold">Model / Baseline</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Train RMSE</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Val RMSE (2022)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Test RMSE (2023)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Test MAE</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Test R²</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Daytime Test RMSE</th>
                    <th className="py-2.5 px-4 font-semibold">Fit Check</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {solar.models.map((m) => (
                    <tr
                      key={m.key}
                      className={m.selected ? 'bg-sky-50/70 font-medium' : 'hover:bg-slate-50/80'}
                    >
                      <td className="py-2.5 px-4 text-slate-900">
                        {m.name}
                        {m.selected && (
                          <span className="ml-2 text-[11px] font-mono font-semibold text-sky-700">
                            [SELECTED]
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {m.train.rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-900 font-semibold">
                        {m.val.rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-900 font-semibold">
                        {m.test.rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {m.test.mae.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-800">
                        {m.test.r2.toFixed(5)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {m.test_daytime.rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-4 text-slate-600">{m.overfit_status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Diagnostics Row: Actual vs Predicted + Residual Histogram */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    2023 Test Parity &amp; 72h Trajectory ({selectedSolar.short_label.replace('\n', ' ')})
                  </h3>
                  <p className="text-xs text-slate-500">
                    {solarPlotMode === 'scatter'
                      ? 'Hover points for timestamp, actual PVGIS kW, and predicted kW'
                      : '72-hour July 2023 hourly overlay (Actual vs. Predicted kW)'}
                  </p>
                </div>
                <div className="flex items-center gap-1 p-0.5 bg-slate-100 rounded text-[11px]">
                  <button
                    type="button"
                    onClick={() => setSolarPlotMode('scatter')}
                    className={`px-2 py-1 rounded cursor-pointer ${
                      solarPlotMode === 'scatter' ? 'bg-white text-slate-900 font-medium shadow-2xs' : 'text-slate-600'
                    }`}
                  >
                    Parity Scatter
                  </button>
                  <button
                    type="button"
                    onClick={() => setSolarPlotMode('july_ts')}
                    className={`px-2 py-1 rounded cursor-pointer ${
                      solarPlotMode === 'july_ts' ? 'bg-white text-slate-900 font-medium shadow-2xs' : 'text-slate-600'
                    }`}
                  >
                    72h Profile
                  </button>
                </div>
              </div>

              {solarPlotMode === 'scatter' ? (
                <svg viewBox={`0 0 ${scW} ${scH}`} className="w-full h-auto">
                  {[0, 0.25, 0.5, 0.75, 1].map((t) => {
                    const val = t * solarMax;
                    const y = padT + ph * (1 - t);
                    const x = padL + pw * t;
                    return (
                      <g key={t}>
                        <line x1={padL} y1={y} x2={padL + pw} y2={y} stroke="#e2e8f0" strokeWidth="1" />
                        <line x1={x} y1={padT} x2={x} y2={padT + ph} stroke="#e2e8f0" strokeWidth="1" />
                        <text x={padL - 7} y={y + 3} textAnchor="end" fontSize="10" fill="#64748b">
                          {val.toFixed(1)}
                        </text>
                        <text x={x} y={padT + ph + 15} textAnchor="middle" fontSize="10" fill="#64748b">
                          {val.toFixed(1)}
                        </text>
                      </g>
                    );
                  })}
                  <rect x={padL} y={padT} width={pw} height={ph} fill="none" stroke="#94a3b8" strokeWidth="1" />
                  <line
                    x1={padL}
                    y1={padT + ph}
                    x2={padL + pw}
                    y2={padT}
                    stroke="#0f172a"
                    strokeWidth="1.25"
                    strokeDasharray="4,3"
                  />
                  {solar.scatter_sample.map((pt, idx) => {
                    const cx = padL + (pt.actual / solarMax) * pw;
                    const cy = padT + ph - (pt.predicted / solarMax) * ph;
                    return (
                      <circle
                        key={idx}
                        cx={cx}
                        cy={cy}
                        r={hoverSolarPt === idx ? 4.5 : 2.4}
                        fill={hoverSolarPt === idx ? '#0f172a' : '#0284c7'}
                        fillOpacity={hoverSolarPt === idx ? 0.95 : 0.45}
                        onMouseEnter={() => setHoverSolarPt(idx)}
                        onMouseLeave={() => setHoverSolarPt(null)}
                        className="cursor-pointer"
                      />
                    );
                  })}
                  <text x={padL + pw / 2} y={scH - 6} textAnchor="middle" fontSize="10.5" fill="#334155">
                    Actual PVGIS PV Power (kW)
                  </text>
                  <text
                    x={14}
                    y={padT + ph / 2}
                    transform={`rotate(-90 14 ${padT + ph / 2})`}
                    textAnchor="middle"
                    fontSize="10.5"
                    fill="#334155"
                  >
                    Predicted (kW)
                  </text>
                </svg>
              ) : (
                <svg viewBox={`0 0 ${scW} ${scH}`} className="w-full h-auto">
                  {[0, 4, 8, 12, 14].map((kw) => {
                    const y = padT + ph * (1 - kw / solarMax);
                    return (
                      <g key={kw}>
                        <line x1={padL} y1={y} x2={padL + pw} y2={y} stroke="#e2e8f0" strokeWidth="1" />
                        <text x={padL - 7} y={y + 3} textAnchor="end" fontSize="10" fill="#64748b">
                          {kw}
                        </text>
                      </g>
                    );
                  })}
                  <path
                    d={solar.timeseries_sample_july_2023
                      .map((p, i) => {
                        const x = padL + (i / (solar.timeseries_sample_july_2023.length - 1)) * pw;
                        const y = padT + ph * (1 - p.actual / solarMax);
                        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
                      })
                      .join(' ')}
                    fill="none"
                    stroke="#0f172a"
                    strokeWidth="2"
                  />
                  <path
                    d={solar.timeseries_sample_july_2023
                      .map((p, i) => {
                        const x = padL + (i / (solar.timeseries_sample_july_2023.length - 1)) * pw;
                        const y = padT + ph * (1 - p.predicted / solarMax);
                        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
                      })
                      .join(' ')}
                    fill="none"
                    stroke="#0284c7"
                    strokeWidth="1.75"
                    strokeDasharray="4,2"
                  />
                  <text x={padL} y={padT + ph + 16} fontSize="10" fill="#64748b">
                    2023-07-10 00:00
                  </text>
                  <text x={padL + pw} y={padT + ph + 16} textAnchor="end" fontSize="10" fill="#64748b">
                    2023-07-12 23:00 UTC
                  </text>
                </svg>
              )}

              <div className="text-xs font-mono text-slate-600 bg-slate-50 border border-slate-200 rounded px-3 py-2 flex items-center justify-between">
                {activeSolarPt ? (
                  <>
                    <span>{activeSolarPt.timestamp} UTC (G={activeSolarPt.irradiance_wm2} W/m²)</span>
                    <span>
                      Actual {activeSolarPt.actual.toFixed(3)} · Pred {activeSolarPt.predicted.toFixed(3)} kW
                    </span>
                  </>
                ) : (
                  <>
                    <span>2023 Test Bias: {selectedSolar.test.bias >= 0 ? '+' : ''}{selectedSolar.test.bias.toFixed(4)} kW</span>
                    <span>Solid black = parity / actual · Dashed blue = predicted</span>
                  </>
                )}
              </div>
            </div>

            {/* Residual Histogram + Permutation Importance */}
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  2023 Test Residual Distribution &amp; Permutation Importance
                </h3>
                <p className="text-xs text-slate-500">
                  Residuals (<span className="font-mono">Actual - Predicted</span>): Mean{' '}
                  <span className="font-mono">{solar.test_residual_summary.mean >= 0 ? '+' : ''}{solar.test_residual_summary.mean.toFixed(4)} kW</span>,
                  Std <span className="font-mono">{solar.test_residual_summary.std.toFixed(4)} kW</span>,
                  P05–P95 [<span className="font-mono">{solar.test_residual_summary.p05.toFixed(3)}, {solar.test_residual_summary.p95.toFixed(3)}</span>]
                </p>
              </div>

              {/* Residual Histogram SVG */}
              <svg viewBox="0 0 460 128" className="w-full h-auto">
                {(() => {
                  const hist = solar.test_residual_summary.histogram;
                  const maxC = Math.max(...hist.map((h) => h.count), 1);
                  const bw = 420 / hist.length;
                  const lo = hist[0].bin_start;
                  const hi = hist[hist.length - 1].bin_end;
                  const zx = 20 + ((0 - lo) / Math.max(hi - lo, 1e-6)) * 420;
                  return (
                    <>
                      {hist.map((b, i) => {
                        const bh = (b.count / maxC) * 92;
                        return (
                          <rect
                            key={i}
                            x={20 + i * bw + 0.5}
                            y={104 - bh}
                            width={Math.max(2, bw - 1)}
                            height={bh}
                            fill="#0f766e"
                            fillOpacity={0.82}
                          />
                        );
                      })}
                      <line x1={20} y1={104} x2={440} y2={104} stroke="#94a3b8" strokeWidth="1" />
                      {lo < 0 && hi > 0 && (
                        <line x1={zx} y1={8} x2={zx} y2={104} stroke="#b91c1c" strokeWidth="1.2" strokeDasharray="3,2" />
                      )}
                      <text x={20} y={120} fontSize="9.5" fill="#64748b">{lo.toFixed(2)} kW</text>
                      <text x={230} y={120} textAnchor="middle" fontSize="9.5" fill="#334155">0.00 kW</text>
                      <text x={440} y={120} textAnchor="end" fontSize="9.5" fill="#64748b">+{hi.toFixed(2)} kW</text>
                    </>
                  );
                })()}
              </svg>

              <div className="space-y-2 pt-1 border-t border-slate-100">
                <div className="text-xs font-semibold text-slate-700">
                  Permutation Importance (2023 Test MAE Increase)
                </div>
                {solar.permutation_importance.slice(0, 6).map((imp) => (
                  <div key={imp.feature} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-700">{imp.label}</span>
                      <span className="font-mono tabular-nums text-slate-900 font-medium">
                        +{imp.mae_increase.toFixed(4)} kW ({imp.relative_pct.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-sky-600 rounded-full"
                        style={{ width: `${Math.max(1.5, Math.min(100, imp.relative_pct))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODEL 2: BIOMASS DRYER THERMAL DEMAND */}
      {subTab === 'dryer' && (
        <div className="space-y-6">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-950 leading-relaxed">
            <span className="font-semibold">Simulated Target Disclaimer (simulated_physics): </span>
            {dryer.simulated_label_disclaimer}
          </div>

          {/* Model 2 Algorithm Comparison */}
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  Model 2 — Unified Multi-Feedstock Biomass Dryer Regression Comparison
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Target: <span className="font-mono">dryer_thermal_demand_kw</span> (kW_th, simulated_physics) · Train {dryer.splits.train_2020_2021.rows.toLocaleString()} / Val {dryer.splits.val_2022.rows.toLocaleString()} / Test {dryer.splits.test_2023.rows.toLocaleString()}
                </p>
              </div>
              <span className="text-xs font-mono text-emerald-700 font-semibold">
                Selection: {dryer.selected_model_name}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
                    <th className="py-2.5 px-4 font-semibold">Model / Baseline</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Train RMSE</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Val RMSE (2022)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Test RMSE (2023)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Test MAE</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Test R²</th>
                    <th className="py-2.5 px-4 font-semibold">Generalization Check</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {dryer.models.map((m) => (
                    <tr
                      key={m.key}
                      className={m.selected ? 'bg-emerald-50/60 font-medium' : 'hover:bg-slate-50/80'}
                    >
                      <td className="py-2.5 px-4 text-slate-900">
                        {m.name}
                        {m.selected && (
                          <span className="ml-2 text-[11px] font-mono font-semibold text-emerald-700">
                            [SELECTED]
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {m.train.rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-900 font-semibold">
                        {m.val.rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-900 font-semibold">
                        {m.test.rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {m.test.mae.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-800">
                        {m.test.r2.toFixed(5)}
                      </td>
                      <td className="py-2.5 px-4 text-slate-600">{m.overfit_status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Unified vs Separate Per-Feedstock Evaluation */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Single Multi-Feedstock Model vs. Separate Per-Feedstock Models
              </h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                {dryer.multi_feedstock_verdict}
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
                    <th className="py-2.5 px-3 font-semibold">Feedstock</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Cp (kJ/kg·K)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Unified Val RMSE</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Unified Test RMSE</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Unified R²</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Separate Test RMSE</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Separate R²</th>
                    <th className="py-2.5 px-3 font-semibold text-right">ΔRMSE (Uni − Sep)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {dryer.unified_vs_per_feedstock.map((row) => (
                    <tr key={row.feedstock_id} className="hover:bg-slate-50/70">
                      <td className="py-2.5 px-3 font-medium text-slate-900">{row.display_name}</td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {row.cp_kj_kg_k.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {row.unified_val_rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right font-semibold text-sky-700">
                        {row.unified_test_rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-800">
                        {row.unified_test_r2.toFixed(5)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right font-semibold text-amber-700">
                        {row.separate_test_rmse.toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-800">
                        {row.separate_test_r2.toFixed(5)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {row.delta_rmse_unified_minus_sep >= 0 ? '+' : ''}
                        {row.delta_rmse_unified_minus_sep.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Model 2 Scatter + Feature Importance */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  2023 Test Parity by Feedstock (Actual Simulated vs. ML Predicted)
                </h3>
                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 mt-1">
                  {Object.entries(FEEDSTOCK_LABELS).map(([fid, lbl]) => (
                    <span key={fid} className="inline-flex items-center gap-1.5">
                      <span
                        className="w-2.5 h-2.5 rounded-full inline-block"
                        style={{ backgroundColor: FEEDSTOCK_COLORS[fid] }}
                      />
                      {lbl}
                    </span>
                  ))}
                </div>
              </div>

              <svg viewBox={`0 0 ${scW} ${scH}`} className="w-full h-auto">
                {[0, 0.25, 0.5, 0.75, 1].map((t) => {
                  const val = t * dryerMax;
                  const y = padT + ph * (1 - t);
                  const x = padL + pw * t;
                  return (
                    <g key={t}>
                      <line x1={padL} y1={y} x2={padL + pw} y2={y} stroke="#e2e8f0" strokeWidth="1" />
                      <line x1={x} y1={padT} x2={x} y2={padT + ph} stroke="#e2e8f0" strokeWidth="1" />
                      <text x={padL - 7} y={y + 3} textAnchor="end" fontSize="10" fill="#64748b">
                        {val.toFixed(0)}
                      </text>
                      <text x={x} y={padT + ph + 15} textAnchor="middle" fontSize="10" fill="#64748b">
                        {val.toFixed(0)}
                      </text>
                    </g>
                  );
                })}
                <rect x={padL} y={padT} width={pw} height={ph} fill="none" stroke="#94a3b8" strokeWidth="1" />
                <line
                  x1={padL}
                  y1={padT + ph}
                  x2={padL + pw}
                  y2={padT}
                  stroke="#0f172a"
                  strokeWidth="1.25"
                  strokeDasharray="4,3"
                />
                {dryer.scatter_sample.map((pt, idx) => {
                  const cx = padL + (pt.actual / dryerMax) * pw;
                  const cy = padT + ph - (pt.predicted / dryerMax) * ph;
                  return (
                    <circle
                      key={idx}
                      cx={cx}
                      cy={cy}
                      r={hoverDryerPt === idx ? 4.5 : 2.6}
                      fill={FEEDSTOCK_COLORS[pt.feedstock] ?? '#0284c7'}
                      fillOpacity={hoverDryerPt === idx ? 0.98 : 0.55}
                      onMouseEnter={() => setHoverDryerPt(idx)}
                      onMouseLeave={() => setHoverDryerPt(null)}
                      className="cursor-pointer"
                    />
                  );
                })}
                <text x={padL + pw / 2} y={scH - 6} textAnchor="middle" fontSize="10.5" fill="#334155">
                  Simulated Physics Demand (kW_th)
                </text>
                <text
                  x={14}
                  y={padT + ph / 2}
                  transform={`rotate(-90 14 ${padT + ph / 2})`}
                  textAnchor="middle"
                  fontSize="10.5"
                  fill="#334155"
                >
                  ML Predicted (kW_th)
                </text>
              </svg>

              <div className="text-xs font-mono text-slate-600 bg-slate-50 border border-slate-200 rounded px-3 py-2 flex items-center justify-between">
                {activeDryerPt ? (
                  <>
                    <span>{FEEDSTOCK_LABELS[activeDryerPt.feedstock] ?? activeDryerPt.feedstock}</span>
                    <span>
                      Sim {activeDryerPt.actual.toFixed(2)} · ML {activeDryerPt.predicted.toFixed(2)} kW_th
                    </span>
                  </>
                ) : (
                  <>
                    <span>2023 Test Residual Mean: {dryer.test_residual_summary.mean >= 0 ? '+' : ''}{dryer.test_residual_summary.mean.toFixed(4)} kW_th</span>
                    <span>Std: {dryer.test_residual_summary.std.toFixed(4)} kW_th</span>
                  </>
                )}
              </div>
            </div>

            {/* Model 2 Permutation Importance */}
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Dryer Feature Importance (2023 Test Permutation MAE Increase)
                </h3>
                <p className="text-xs text-slate-500">
                  Physical alignment check: batch mass, initial moisture, duration, and target moisture dominate demand.
                </p>
              </div>
              <div className="space-y-2.5 pt-1">
                {dryer.permutation_importance.slice(0, 9).map((imp) => (
                  <div key={imp.feature} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-700">{imp.label}</span>
                      <span className="font-mono tabular-nums text-slate-900 font-medium">
                        +{imp.mae_increase.toFixed(4)} kW_th ({imp.relative_pct.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-600 rounded-full"
                        style={{ width: `${Math.max(1.2, Math.min(100, imp.relative_pct))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MULTI-FEEDSTOCK LIBRARY & LEAKAGE AUDIT */}
      {subTab === 'audit' && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200">
              <h2 className="text-sm font-semibold text-slate-900">
                Supported Biomass Feedstock Thermophysical Library (`BIOMASS_FEEDSTOCK_LIBRARY`)
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Reusable Model 2 interface accepts arbitrary feedstock parameters within physical moisture bounds.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
                    <th className="py-2.5 px-4 font-semibold">Feedstock</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Dry Cp (kJ/kg·K)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Bulk Density (kg/m³)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Batch Mass (kg)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Initial Moisture (%)</th>
                    <th className="py-2.5 px-4 font-semibold text-right">Target Moisture (%)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {dryer.feedstocks.map((f) => (
                    <tr key={f.id}>
                      <td className="py-2.5 px-4 font-medium text-slate-900">{f.name}</td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {f.cp_kj_kg_k.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {f.bulk_density_kg_m3.toFixed(0)}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {f.batch_mass_range_kg[0]}–{f.batch_mass_range_kg[1]}
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                        {f.init_moisture_range_pct[0]}–{f.init_moisture_range_pct[1]}%
                      </td>
                      <td className="py-2.5 px-4 font-mono tabular-nums text-right text-slate-700">
                        {f.target_moisture_range_pct[0]}–{f.target_moisture_range_pct[1]}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
              <h3 className="text-sm font-semibold text-slate-900">
                Data Leakage &amp; Excluded Feature Audit (Model 1)
              </h3>
              <ul className="space-y-2.5 text-xs text-slate-700">
                {Object.entries(solar.excluded_features_reason).map(([feat, reason]) => (
                  <li key={feat} className="border-b border-slate-100 pb-2 last:border-none last:pb-0">
                    <div className="font-mono font-semibold text-slate-900">{feat}</div>
                    <div className="text-slate-600 mt-0.5">{reason}</div>
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
              <h3 className="text-sm font-semibold text-slate-900">
                Persisted `.pkl` Model Artifacts &amp; Phase 6 Inference Check
              </h3>
              <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 border border-slate-200 rounded p-3">
                <div>
                  <div className="text-slate-500">Saved Model 1 Inference</div>
                  <div className="font-mono font-semibold text-slate-900 mt-0.5">
                    {smoke.solar_kw_850wm2_28c.toFixed(3)} kW AC
                  </div>
                  <div className="text-[11px] text-slate-500">850 W/m², 28 °C, 3.2 m/s</div>
                </div>
                <div>
                  <div className="text-slate-500">Saved Model 2 Inference</div>
                  <div className="font-mono font-semibold text-slate-900 mt-0.5">
                    {smoke.dryer_kw_olive_250kg_45to12pct.toFixed(3)} kW_th
                  </div>
                  <div className="text-[11px] text-slate-500">Olive pomace 250 kg, 45→12%</div>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[...solar.saved_artifacts, ...dryer.saved_artifacts].map((path) => (
                  <span
                    key={path}
                    className="text-[11px] font-mono bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200"
                  >
                    {path}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
