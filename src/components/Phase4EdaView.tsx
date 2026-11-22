import React, { useMemo, useState } from 'react';
import phase4EdaStats from '../data/phase4EdaStats.json';

type EdaSubTab = 'temporal' | 'correlations' | 'distributions' | 'ml_prep';
type CorrScope = 'real' | 'coupled';
type CorrMethod = 'pearson' | 'spearman';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const Phase4EdaView: React.FC = () => {
  const [subTab, setSubTab] = useState<EdaSubTab>('temporal');
  const [corrScope, setCorrScope] = useState<CorrScope>('real');
  const [corrMethod, setCorrMethod] = useState<CorrMethod>('pearson');
  const [hoverDayIdx, setHoverDayIdx] = useState<number | null>(null);

  const {
    inspection,
    descriptive_stats,
    correlations,
    seasonal_stats,
    monthly_stats,
    diurnal_profile,
    daily_weekly_sampled,
    histograms,
    scatter_weather_pv,
    scatter_active_dryer,
  } = phase4EdaStats;

  const activeMatrix = useMemo(() => {
    if (corrScope === 'real') {
      return corrMethod === 'pearson' ? correlations.real_pearson : correlations.real_spearman;
    }
    return corrMethod === 'pearson'
      ? correlations.coupled_active_pearson
      : correlations.coupled_active_spearman;
  }, [corrScope, corrMethod, correlations]);

  const matrixKeys = Object.keys(activeMatrix);

  const cellTone = (val: number) => {
    if (val >= 0.75) return 'bg-sky-700 text-white';
    if (val >= 0.35) return 'bg-sky-200 text-slate-900';
    if (val > 0.05) return 'bg-sky-50 text-slate-800';
    if (val <= -0.75) return 'bg-rose-700 text-white';
    if (val <= -0.35) return 'bg-rose-200 text-slate-900';
    if (val < -0.05) return 'bg-rose-50 text-slate-800';
    return 'bg-slate-50 text-slate-600';
  };

  // Daily 4-year series geometry
  const tsW = 820;
  const tsH = 210;
  const padL = 46;
  const padR = 20;
  const padT = 18;
  const padB = 26;
  const plotW = tsW - padL - padR;
  const plotH = tsH - padT - padB;

  const xDay = (i: number) =>
    padL + (i / Math.max(1, daily_weekly_sampled.length - 1)) * plotW;

  const irrDailyPath = daily_weekly_sampled
    .map((d, i) => {
      const y = padT + plotH * (1 - d.meanIrr / 460);
      return `${i === 0 ? 'M' : 'L'} ${xDay(i).toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');

  const storedDailyPath = daily_weekly_sampled
    .map((d, i) => {
      const y = padT + plotH * (1 - d.meanStoredKwh / 120);
      return `${i === 0 ? 'M' : 'L'} ${xDay(i).toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');

  const hoveredDay = hoverDayIdx !== null ? daily_weekly_sampled[hoverDayIdx] : null;

  return (
    <div className="space-y-6">
      {/* Inspection & Quality Audit Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Dataset Continuity &amp; Completeness
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              100.0
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">% complete</span>
          </div>
          <div className="mt-1 text-xs text-emerald-700 font-medium">
            ● {inspection.real_dataset.rows.toLocaleString()} UTC hrs · 0 gaps · 0 duplicates
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Investigated PVGIS Sentinel Hours
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              13
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">rows (0.037%)</span>
          </div>
          <div className="mt-1 text-xs text-amber-800 font-medium">
            ▲ Midday H_sun=0 satellite frame flags (kept &amp; documented)
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Irradiance ↔ PV Power (Real)
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              +{correlations.key_pairs.irr_vs_pv_pearson.toFixed(4)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">Pearson r</span>
          </div>
          <div className="mt-1 text-xs text-slate-600 font-mono">
            Spearman ρ = +{correlations.key_pairs.irr_vs_pv_spearman.toFixed(4)}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Ambient Temp ↔ Active Dryer Load
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {correlations.key_pairs.temp_vs_active_dryer_pearson.toFixed(4)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">Pearson r</span>
          </div>
          <div className="mt-1 text-xs text-slate-600 font-mono">
            RH ↔ Dryer r = +{correlations.key_pairs.rh_vs_active_dryer_pearson.toFixed(4)} (n=17,532)
          </div>
        </div>
      </div>

      {/* Sub-Navigation Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white border border-slate-200 rounded-lg p-3">
        <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-100 rounded-md">
          {(
            [
              { id: 'temporal', label: 'Temporal & Seasonal' },
              { id: 'correlations', label: 'Correlations & Scatter' },
              { id: 'distributions', label: 'Histograms & Audit' },
              { id: 'ml_prep', label: 'Phase 5 ML Preparation' },
            ] as { id: EdaSubTab; label: string }[]
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
        <span className="text-xs font-mono text-slate-500">
          Real (PVGIS/Open-Meteo) vs. simulated_physics kept strictly separate
        </span>
      </div>

      {/* VIEW 1: TEMPORAL & SEASONAL */}
      {subTab === 'temporal' && (
        <div className="space-y-6">
          {/* 4-Year Weekly-Sampled Daily Time Series */}
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-200 bg-slate-50/70 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  4-Year Seasonal Envelope (2020–2023 · Settat Weekly-Sampled Daily Means)
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Daily mean solar irradiance (real PVGIS) overlaid with simulated sand storage energy (Medium scenario)
                </p>
              </div>
              <div className="font-mono text-xs tabular-nums text-slate-700">
                {hoveredDay ? (
                  <span>
                    {hoveredDay.date} · Irr={hoveredDay.meanIrr} W/m² · Temp={hoveredDay.meanTemp}°C · Stored={hoveredDay.meanStoredKwh} kWh_th
                  </span>
                ) : (
                  <span className="text-slate-400">Hover timeline to inspect date</span>
                )}
              </div>
            </div>

            <div className="p-5">
              <svg
                viewBox={`0 0 ${tsW} ${tsH}`}
                className="w-full h-auto cursor-crosshair select-none"
                onMouseLeave={() => setHoverDayIdx(null)}
              >
                {[0, 0.5, 1].map((f) => {
                  const y = padT + plotH * (1 - f);
                  return (
                    <g key={f}>
                      <line x1={padL} y1={y} x2={tsW - padR} y2={y} stroke="#E2E8F0" strokeWidth="1" />
                      <text x={padL - 6} y={y + 3} textAnchor="end" className="fill-amber-700 text-[10px] font-mono">
                        {Math.round(460 * f)}
                      </text>
                    </g>
                  );
                })}
                <path d={irrDailyPath} fill="none" stroke="#D97706" strokeWidth="1.6" />
                <path d={storedDailyPath} fill="none" stroke="#0F172A" strokeWidth="1.4" strokeDasharray="4 2" />

                {hoverDayIdx !== null && (
                  <line
                    x1={xDay(hoverDayIdx)}
                    y1={padT}
                    x2={xDay(hoverDayIdx)}
                    y2={padT + plotH}
                    stroke="#0284C7"
                    strokeWidth="1"
                  />
                )}

                {daily_weekly_sampled.map((pt, i) => (
                  <g key={pt.date}>
                    {i % 26 === 0 && (
                      <text x={xDay(i)} y={tsH - 6} textAnchor="middle" className="fill-slate-500 text-[9px] font-mono">
                        {pt.date.slice(0, 7)}
                      </text>
                    )}
                    <rect
                      x={xDay(i) - plotW / daily_weekly_sampled.length / 2}
                      y={padT}
                      width={plotW / daily_weekly_sampled.length}
                      height={plotH}
                      fill="transparent"
                      onMouseEnter={() => setHoverDayIdx(i)}
                    />
                  </g>
                ))}
              </svg>
              <div className="mt-2 pt-2 border-t border-slate-100 flex flex-wrap gap-6 text-xs font-mono">
                <span className="text-amber-700">━━ Daily Mean Irradiance (0–460 W/m², Real)</span>
                <span className="text-slate-900">┄┄ Daily Mean Sand Storage (0–120 kWh_th, Simulated Medium)</span>
              </div>
            </div>
          </div>

          {/* Monthly Boxplots (Ambient Temp & Stored Energy) + Seasonal Table */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <div className="lg:col-span-6 bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900">
                Monthly Ambient Temperature Boxplots (°C · Open-Meteo ERA5)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5 mb-3">
                Whiskers show Min–Max; box shows P25–P75 with median bar
              </p>
              <svg viewBox="0 0 540 210" className="w-full h-auto">
                {[0, 15, 30, 45].map((tVal) => {
                  const y = 180 - (tVal / 48) * 155;
                  return (
                    <g key={tVal}>
                      <line x1={38} y1={y} x2={525} y2={y} stroke="#E2E8F0" strokeWidth="1" />
                      <text x={32} y={y + 3} textAnchor="end" className="fill-slate-500 text-[9px] font-mono">
                        {tVal}°
                      </text>
                    </g>
                  );
                })}
                {monthly_stats.map((m, idx) => {
                  const cx = 58 + idx * 40;
                  const t = m.temp_c;
                  const yOf = (v: number) => 180 - (v / 48) * 155;
                  return (
                    <g key={m.month}>
                      <line x1={cx} y1={yOf(t.min)} x2={cx} y2={yOf(t.max)} stroke="#64748B" strokeWidth="1.2" />
                      <rect
                        x={cx - 10}
                        y={yOf(t.p75)}
                        width="20"
                        height={Math.max(2, yOf(t.p25) - yOf(t.p75))}
                        fill="#BAE6FD"
                        stroke="#0284C7"
                        strokeWidth="1.2"
                      />
                      <line x1={cx - 10} y1={yOf(t.median)} x2={cx + 10} y2={yOf(t.median)} stroke="#0F172A" strokeWidth="2" />
                      <text x={cx} y={198} textAnchor="middle" className="fill-slate-600 text-[9px] font-mono">
                        {MONTHS[idx]}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>

            <div className="lg:col-span-6 bg-white border border-slate-200 rounded-lg overflow-hidden">
              <div className="px-5 py-3.5 border-b border-slate-200">
                <h3 className="text-sm font-semibold text-slate-900">
                  Seasonal Supply vs. Demand Summary (Settat 2020–2023)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Winter brings peak active dryer demand and lowest solar/storage reserves
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                      <th className="py-2.5 px-3">Season</th>
                      <th className="py-2.5 px-3 text-right">Irr (W/m²)</th>
                      <th className="py-2.5 px-3 text-right">Temp (°C)</th>
                      <th className="py-2.5 px-3 text-right">RH (%)</th>
                      <th className="py-2.5 px-3 text-right">Dryer (kW_th)</th>
                      <th className="py-2.5 px-3 text-right">Stored (kWh)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono tabular-nums">
                    {Object.entries(seasonal_stats).map(([sname, st]) => (
                      <tr key={sname} className="hover:bg-slate-50/70">
                        <td className="py-2.5 px-3 font-sans font-medium text-slate-900">{sname}</td>
                        <td className="py-2.5 px-3 text-right text-amber-800">{st.irradiance_mean.toFixed(1)}</td>
                        <td className="py-2.5 px-3 text-right text-sky-800">{st.temp_mean_c.toFixed(1)}</td>
                        <td className="py-2.5 px-3 text-right text-slate-700">{st.rh_mean_pct.toFixed(1)}</td>
                        <td className="py-2.5 px-3 text-right text-slate-900 font-semibold">{st.dryer_active_mean_kw.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-right text-slate-800">{st.stored_energy_mean_kwh.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: CORRELATIONS & SCATTER */}
      {subTab === 'correlations' && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  Correlation Matrix ({corrMethod === 'pearson' ? 'Pearson r' : 'Spearman ρ'})
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Correlation measures statistical association and does not establish causation
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-md">
                  <button
                    type="button"
                    onClick={() => setCorrScope('real')}
                    className={`px-2.5 py-1 text-xs font-medium rounded cursor-pointer ${
                      corrScope === 'real' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600'
                    }`}
                  >
                    Real Weather &amp; PV (n=35,064)
                  </button>
                  <button
                    type="button"
                    onClick={() => setCorrScope('coupled')}
                    className={`px-2.5 py-1 text-xs font-medium rounded cursor-pointer ${
                      corrScope === 'coupled' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600'
                    }`}
                  >
                    Active Dryer Physics (n=17,532)
                  </button>
                </div>
                <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-md">
                  <button
                    type="button"
                    onClick={() => setCorrMethod('pearson')}
                    className={`px-2.5 py-1 text-xs font-medium rounded cursor-pointer ${
                      corrMethod === 'pearson' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600'
                    }`}
                  >
                    Pearson
                  </button>
                  <button
                    type="button"
                    onClick={() => setCorrMethod('spearman')}
                    className={`px-2.5 py-1 text-xs font-medium rounded cursor-pointer ${
                      corrMethod === 'spearman' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600'
                    }`}
                  >
                    Spearman
                  </button>
                </div>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr>
                    <th className="py-2 px-3 text-left text-slate-500 font-medium">Variable</th>
                    {matrixKeys.map((k) => (
                      <th key={k} className="py-2 px-2 text-center font-mono text-slate-700 whitespace-nowrap">
                        {k.split(' (')[0]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  {matrixKeys.map((rowKey) => (
                    <tr key={rowKey}>
                      <td className="py-2 px-3 font-sans font-medium text-slate-800 whitespace-nowrap border-t border-slate-100">
                        {rowKey}
                      </td>
                      {matrixKeys.map((colKey) => {
                        const val = (activeMatrix as Record<string, Record<string, number>>)[rowKey][colKey];
                        return (
                          <td
                            key={colKey}
                            className={`py-2 px-2 text-center border border-white font-semibold ${cellTone(val)}`}
                          >
                            {val >= 0 ? `+${val.toFixed(2)}` : val.toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Side-by-side Scatter Plots */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900">
                Irradiance vs. PV Power (Real PVGIS · r = +{correlations.key_pairs.irr_vs_pv_pearson})
              </h3>
              <p className="text-xs text-slate-500 mt-0.5 mb-3">
                Spread at high irradiance reflects PV cell temperature &amp; wind cooling derating
              </p>
              <svg viewBox="0 0 440 220" className="w-full h-auto bg-slate-50/50 border border-slate-200 rounded">
                {scatter_weather_pv.map((p, idx) => (
                  <circle
                    key={idx}
                    cx={38 + (p.irr / 1150) * 380}
                    cy={195 - (p.pv / 14.5) * 170}
                    r="2"
                    fill="#0284C7"
                    fillOpacity="0.5"
                  />
                ))}
                <text x={225} y={212} textAnchor="middle" className="fill-slate-600 text-[10px] font-mono">
                  Plane-of-Array Irradiance (W/m²)
                </text>
              </svg>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900">
                Ambient Temp vs. Active Dryer Demand (Simulated · r = {correlations.key_pairs.temp_vs_active_dryer_pearson})
              </h3>
              <p className="text-xs text-slate-500 mt-0.5 mb-3">
                Cooler intake air &amp; higher shell losses elevate required kW_th in winter
              </p>
              <svg viewBox="0 0 440 220" className="w-full h-auto bg-slate-50/50 border border-slate-200 rounded">
                {scatter_active_dryer.map((p, idx) => (
                  <circle
                    key={idx}
                    cx={38 + (p.temp / 46) * 380}
                    cy={195 - ((p.dryer - 22.0) / 5.0) * 170}
                    r="2"
                    fill="#D97706"
                    fillOpacity="0.55"
                  />
                ))}
                <text x={225} y={212} textAnchor="middle" className="fill-slate-600 text-[10px] font-mono">
                  Ambient Temperature (°C) → Demand (22–27 kW_th)
                </text>
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 3: HISTOGRAMS & QUALITY AUDIT */}
      {subTab === 'distributions' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900">
                Ambient Temperature Histogram (Real Open-Meteo ERA5 · n=35,064)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5 mb-3 font-mono">
                Mean={descriptive_stats.meteo_ambient_temp_c.mean}°C · Median={descriptive_stats.meteo_ambient_temp_c.median}°C · Range=[{descriptive_stats.meteo_ambient_temp_c.min}, {descriptive_stats.meteo_ambient_temp_c.max}]°C
              </p>
              <div className="flex items-end gap-1.5 h-40 pt-4 border-b border-slate-200">
                {histograms.ambient_temp_c.map((b) => {
                  const maxC = Math.max(...histograms.ambient_temp_c.map((x) => x.count));
                  const pct = (b.count / maxC) * 100;
                  return (
                    <div key={b.binStart} className="flex-1 flex flex-col items-center justify-end h-full">
                      <div
                        style={{ height: `${pct}%` }}
                        className="w-full bg-sky-700 rounded-t-xs"
                        title={`${b.binStart}–${b.binEnd}°C: ${b.count} hrs`}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1">
                <span>0°C</span>
                <span>16°C</span>
                <span>32°C</span>
                <span>48°C</span>
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-900">
                Active Biomass Dryer Demand Histogram (Simulated Medium · n=17,532)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5 mb-3 font-mono">
                Mean={descriptive_stats.dryer_demand_kw_active.mean} kW_th · Std={descriptive_stats.dryer_demand_kw_active.std} kW_th (Fixed batch mass/MC)
              </p>
              <div className="flex items-end gap-1.5 h-40 pt-4 border-b border-slate-200">
                {histograms.dryer_active_kw.map((b) => {
                  const maxC = Math.max(...histograms.dryer_active_kw.map((x) => x.count));
                  const pct = (b.count / maxC) * 100;
                  return (
                    <div key={b.binStart} className="flex-1 flex flex-col items-center justify-end h-full">
                      <div
                        style={{ height: `${pct}%` }}
                        className="w-full bg-amber-600 rounded-t-xs"
                        title={`${b.binStart}–${b.binEnd} kW_th: ${b.count} hrs`}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1">
                <span>18 kW</span>
                <span>21 kW</span>
                <span>24 kW</span>
                <span>26 kW</span>
              </div>
            </div>
          </div>

          {/* Physical Validation & Anomaly Findings */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-900">
              Investigated Physical Discontinuities &amp; Origin Notes (No Blind Deletion)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="border border-slate-200 rounded p-3.5 bg-slate-50/50">
                <div className="font-mono font-semibold text-amber-800">
                  PVGIS Midday Sentinel Zeros (13 hrs)
                </div>
                <p className="text-slate-600 mt-1 leading-relaxed">
                  Example: `2021-10-12 11:00 UTC` has `G=0.0, H_sun=0.0` flanked by `39.7°` and `49.7°`. Originates from missing Meteosat frames in PVGIS-SARAH3; flagged rather than silently deleted.
                </p>
              </div>
              <div className="border border-slate-200 rounded p-3.5 bg-slate-50/50">
                <div className="font-mono font-semibold text-slate-900">
                  Max Ambient Temp Step: {inspection.real_dataset.max_temp_jump_c_per_h} °C/h
                </div>
                <p className="text-slate-600 mt-1 leading-relaxed">
                  Consistent with rapid semi-arid morning warm-up or cold frontal passage in Settat; verified physically valid.
                </p>
              </div>
              <div className="border border-slate-200 rounded p-3.5 bg-slate-50/50">
                <div className="font-mono font-semibold text-slate-900">
                  Max Sand Temp Step: {inspection.simulated_dataset_medium.max_sand_temp_jump_c_per_h} °C/h
                </div>
                <p className="text-slate-600 mt-1 leading-relaxed">
                  Occurs during simultaneous solar thermal + NCG + surplus PV charging when dryer is off-shift; energy closure error remains &lt; 10⁻¹³ kWh.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 4: PHASE 5 ML PREPARATION */}
      {subTab === 'ml_prep' && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200">
            <h2 className="text-sm font-semibold text-slate-900">
              Proposed Phase 5 Feature / Target Matrix &amp; Data Sufficiency Audit
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Identifies leakage hazards, collinearity, feature transforms, and dataset coverage prior to Phase 5 model training
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                  <th className="py-3 px-4">ML Task</th>
                  <th className="py-3 px-4">Target</th>
                  <th className="py-3 px-4">Candidate Features &amp; Transforms</th>
                  <th className="py-3 px-4">Collinearity &amp; Leakage Risks</th>
                  <th className="py-3 px-4">Data Sufficiency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 align-top">
                <tr>
                  <td className="py-3 px-4 font-semibold text-slate-900 whitespace-nowrap">
                    Model 1: PV Power
                  </td>
                  <td className="py-3 px-4 font-mono text-sky-800 whitespace-nowrap">
                    pvgis_pv_power_kw
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    `pvgis_irradiance_wm2`, `meteo_ambient_temp_c`, `meteo_wind_speed_ms`, `meteo_relative_humidity_pct`, cyclical `sin/cos(hour_utc)`, `sin/cos(month)`
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    Drop `pvgis_sun_elevation_deg` (collinear with irradiance) and duplicate `pvgis_ambient_temp_c`. Never use `pv_surplus_heater_elec_kw` (leakage).
                  </td>
                  <td className="py-3 px-4 text-emerald-700 font-medium">
                    Sufficient (35,064 real-weather hours; audit 13 sentinel zero rows).
                  </td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-semibold text-slate-900 whitespace-nowrap">
                    Model 2: Dryer Demand
                  </td>
                  <td className="py-3 px-4 font-mono text-amber-800 whitespace-nowrap">
                    dryer_thermal_demand_kw
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    `biomass_mass_kg`, `initial_moisture_pct`, `target_moisture_pct`, `meteo_ambient_temp_c`, `meteo_relative_humidity_pct`, `dryer_inlet_air_temp_c`
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    Never include `water_evaporated_kg_h`, `sand_to_dryer_kw`, or `auxiliary_heating_needed_kw` (direct formula leakage).
                  </td>
                  <td className="py-3 px-4 text-amber-800 font-medium">
                    Single scenario (`medium`) insufficient! Must combine `low`/`medium`/`high` or parametric sweep over feedstock mass &amp; moisture.
                  </td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-semibold text-slate-900 whitespace-nowrap">
                    Model 3: Sand Storage
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-900 whitespace-nowrap">
                    stored_thermal_energy_kwh
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    Physics balance Q = m · Cp · (T_sand - T_min) / 3600 + UA standby loss
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    Exact thermodynamic identity already verified (&lt; 10⁻¹³ kWh). Do not force black-box ML where deterministic physics applies.
                  </td>
                  <td className="py-3 px-4 text-sky-700 font-medium">
                    Physics-based model selected (validated in Phase 3).
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
