import React, { useMemo, useState } from 'react';
import phase2RealStats from '../data/phase2RealStats.json';

type ChartProfileMode = 'diurnal' | 'monthly';

const MONTH_NAMES = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

export const Phase2DataView: React.FC = () => {
  const [profileMode, setProfileMode] = useState<ChartProfileMode>('diurnal');
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const { collectionMetadata, qualityReport, monthlyProfile, diurnalProfile, sample24h } =
    phase2RealStats;

  const pvgisAudit = qualityReport.pvgis_audit;
  const meteoAudit = qualityReport.open_meteo_audit;
  const merged = qualityReport.merged_summary;

  const activeSeries = useMemo(() => {
    if (profileMode === 'diurnal') {
      return diurnalProfile.map((d) => ({
        xLabel: `${String(d.hourUtc).padStart(2, '0')}:00`,
        irradiance: d.meanIrradianceWm2,
        pvKw: d.meanPvPowerKw,
        tempC: d.meanTempC,
        rhPct: d.meanRhPct,
      }));
    }
    return monthlyProfile.map((m) => ({
      xLabel: MONTH_NAMES[m.month - 1],
      irradiance: m.meanIrradianceWm2,
      pvKw: m.meanPvPowerKw,
      tempC: m.meanTempC,
      rhPct: m.meanRhPct,
    }));
  }, [profileMode, diurnalProfile, monthlyProfile]);

  const maxIrr = useMemo(
    () => Math.max(100, ...activeSeries.map((s) => s.irradiance)),
    [activeSeries]
  );
  const maxTemp = useMemo(
    () => Math.max(35, ...activeSeries.map((s) => s.tempC)),
    [activeSeries]
  );

  // SVG dimensions
  const width = 760;
  const height = 270;
  const padL = 52;
  const padR = 52;
  const padT = 22;
  const padB = 34;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const xPos = (i: number) =>
    padL + (i / Math.max(1, activeSeries.length - 1)) * plotW;
  const yIrr = (val: number) => padT + plotH - (val / (maxIrr * 1.1)) * plotH;
  const yTemp = (val: number) => padT + plotH - (val / (maxTemp * 1.15)) * plotH;

  const irrPath = activeSeries
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xPos(i).toFixed(1)} ${yIrr(d.irradiance).toFixed(1)}`)
    .join(' ');
  const tempPath = activeSeries
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xPos(i).toFixed(1)} ${yTemp(d.tempC).toFixed(1)}`)
    .join(' ');

  const hoveredPoint = hoverIdx !== null ? activeSeries[hoverIdx] : null;

  return (
    <div className="space-y-6">
      {/* Real Data Provenance Summary Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            PVGIS Solar &amp; PV Archive
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {pvgisAudit.rows_after_clean.toLocaleString()}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">hours UTC</span>
          </div>
          <div className="mt-1 text-xs text-emerald-700 font-medium">
            ● {collectionMetadata.sources.pvgis.radiation_db} · 0 missing · 0 duplicates
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Open-Meteo Weather Archive
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {meteoAudit.rows_after_clean.toLocaleString()}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">hours UTC</span>
          </div>
          <div className="mt-1 text-xs text-emerald-700 font-medium">
            ● ERA5 Reanalysis · RH, Temp, Wind (m/s)
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Cross-Source Temp Agreement
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {merged.cross_source_temp_mae_c.toFixed(2)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">°C MAE</span>
          </div>
          <div className="mt-1 text-xs text-slate-600">
            PVGIS T2m vs. Open-Meteo T2m (No imputation)
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Provisional Coordinates (Settat)
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-xl font-mono font-semibold tabular-nums text-slate-900">
              33.00°N, -7.62°E
            </span>
          </div>
          <div className="mt-1 text-xs text-slate-600">
            Elevation {collectionMetadata.sources.pvgis.elevation_m} m · 2020–2023
          </div>
        </div>
      </div>

      {/* Interactive Real Climatology Chart + Chronological Split Audit */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 8 cols: Dual-Axis Real PVGIS + Open-Meteo Chart */}
        <div className="lg:col-span-8 bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200 bg-slate-50/70 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Settat Real Solar Irradiance &amp; Ambient Temperature (2020–2023)
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Empirical averages computed directly from cleaned PVGIS-SARAH3 &amp; Open-Meteo ERA5 records
              </p>
            </div>
            <div className="flex items-center gap-1 p-1 bg-slate-200/70 rounded-md">
              <button
                type="button"
                onClick={() => setProfileMode('diurnal')}
                className={`px-3 py-1 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                  profileMode === 'diurnal'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Diurnal Cycle (UTC)
              </button>
              <button
                type="button"
                onClick={() => setProfileMode('monthly')}
                className={`px-3 py-1 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                  profileMode === 'monthly'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Monthly Means
              </button>
            </div>
          </div>

          <div className="p-5">
            <svg
              viewBox={`0 0 ${width} ${height}`}
              className="w-full h-auto cursor-crosshair select-none"
              onMouseLeave={() => setHoverIdx(null)}
            >
              {/* Horizontal Gridlines */}
              {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
                const y = padT + plotH * (1 - frac);
                const irrVal = Math.round(maxIrr * 1.1 * frac);
                const tempVal = (maxTemp * 1.15 * frac).toFixed(0);
                return (
                  <g key={frac}>
                    <line
                      x1={padL}
                      y1={y}
                      x2={width - padR}
                      y2={y}
                      stroke="#E2E8F0"
                      strokeWidth="1"
                    />
                    <text
                      x={padL - 8}
                      y={y + 3}
                      textAnchor="end"
                      className="fill-amber-700 text-[10px] font-mono tabular-nums"
                    >
                      {irrVal}
                    </text>
                    <text
                      x={width - padR + 8}
                      y={y + 3}
                      textAnchor="start"
                      className="fill-sky-700 text-[10px] font-mono tabular-nums"
                    >
                      {tempVal}°C
                    </text>
                  </g>
                );
              })}

              {/* Axis unit labels */}
              <text x={padL} y={13} className="fill-amber-700 text-[10px] font-mono font-semibold">
                Irradiance (W/m²)
              </text>
              <text
                x={width - padR}
                y={13}
                textAnchor="end"
                className="fill-sky-700 text-[10px] font-mono font-semibold"
              >
                Ambient Temp (°C)
              </text>

              {/* Irradiance line (solid amber) */}
              <path d={irrPath} fill="none" stroke="#D97706" strokeWidth="2.2" />

              {/* Temperature line (dashed sky cobalt) */}
              <path
                d={tempPath}
                fill="none"
                stroke="#0284C7"
                strokeWidth="2"
                strokeDasharray="5 3"
              />

              {/* Hover hairline */}
              {hoverIdx !== null && (
                <line
                  x1={xPos(hoverIdx)}
                  y1={padT}
                  x2={xPos(hoverIdx)}
                  y2={padT + plotH}
                  stroke="#0F172A"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                />
              )}

              {/* Data points + X axis labels + wide hit targets */}
              {activeSeries.map((pt, i) => {
                const showTick =
                  profileMode === 'monthly' || i % 3 === 0 || i === activeSeries.length - 1;
                return (
                  <g key={pt.xLabel}>
                    {showTick && (
                      <text
                        x={xPos(i)}
                        y={height - 10}
                        textAnchor="middle"
                        className="fill-slate-500 text-[10px] font-mono"
                      >
                        {pt.xLabel}
                      </text>
                    )}
                    <circle
                      cx={xPos(i)}
                      cy={yIrr(pt.irradiance)}
                      r={hoverIdx === i ? 4.5 : 2.5}
                      fill="#D97706"
                    />
                    <circle
                      cx={xPos(i)}
                      cy={yTemp(pt.tempC)}
                      r={hoverIdx === i ? 4.5 : 2.5}
                      fill="#0284C7"
                    />
                    <rect
                      x={xPos(i) - plotW / activeSeries.length / 2}
                      y={padT}
                      width={plotW / activeSeries.length}
                      height={plotH}
                      fill="transparent"
                      onMouseEnter={() => setHoverIdx(i)}
                    />
                  </g>
                );
              })}
            </svg>

            {/* Compact Monospace Readout Strip */}
            <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-4 text-xs">
              <div className="flex flex-wrap items-center gap-5">
                <span className="font-mono text-amber-800">
                  ━━ PVGIS Plane-of-Array Irradiance (W/m²)
                </span>
                <span className="font-mono text-sky-800">
                  ┄┄ Open-Meteo Ambient Temp (°C)
                </span>
              </div>
              <div className="font-mono tabular-nums text-slate-700">
                {hoveredPoint ? (
                  <span>
                    {hoveredPoint.xLabel} · G={hoveredPoint.irradiance} W/m² · PV={hoveredPoint.pvKw} kW · T={hoveredPoint.tempC}°C · RH={hoveredPoint.rhPct}%
                  </span>
                ) : (
                  <span className="text-slate-400">Hover chart to inspect exact hourly/monthly coordinates</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right 4 cols: Chronological Split & Traceability Audit */}
        <div className="lg:col-span-4 bg-white border border-slate-200 rounded-lg p-5 space-y-5">
          <div className="border-b border-slate-200 pb-3">
            <h3 className="text-sm font-semibold text-slate-900">
              Chronological Split &amp; Data Quality Audit
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Immutable raw archives verified before chronological ML partitioning
            </p>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Train Split (2020–2021)</span>
              <span className="font-mono tabular-nums font-semibold text-slate-900">
                {merged.chronological_splits.train_2020_2021_rows.toLocaleString()} rows
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Validation Split (2022)</span>
              <span className="font-mono tabular-nums font-semibold text-slate-900">
                {merged.chronological_splits.val_2022_rows.toLocaleString()} rows
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Test Split (2023)</span>
              <span className="font-mono tabular-nums font-semibold text-slate-900">
                {merged.chronological_splits.test_2023_rows.toLocaleString()} rows
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Synthetic Imputation</span>
              <span className="font-mono font-semibold text-emerald-700">
                Disabled (False)
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Physical Bound Violations</span>
              <span className="font-mono tabular-nums font-semibold text-slate-900">
                0
              </span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-600">Nighttime PV Anomalies</span>
              <span className="font-mono tabular-nums font-semibold text-slate-900">
                {pvgisAudit.nighttime_pv_anomalies}
              </span>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-200 space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Raw Archive SHA-256 Checksums
            </h4>
            <div className="bg-slate-50 border border-slate-200 rounded p-2.5 text-[11px] font-mono text-slate-700 space-y-1.5 break-all">
              <div>
                <span className="font-semibold text-slate-900">pvgis_raw.json:</span>{' '}
                {collectionMetadata.sources.pvgis.files.json_sha256.slice(0, 24)}…
              </div>
              <div>
                <span className="font-semibold text-slate-900">open_meteo_raw.json:</span>{' '}
                {collectionMetadata.sources.open_meteo.files.json_sha256.slice(0, 24)}…
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Real 24-Hour Aligned UTC Sample Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Source-Traceable Sample Window (2020-07-01 UTC · Settat)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Shows canonical UTC alignment alongside original PVGIS satellite overpass string (`pvgis_raw_time`)
            </p>
          </div>
          <span className="text-xs font-mono text-slate-500">
            solar_weather_merged_clean.csv
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600">
                <th className="py-2.5 px-4">UTC Timestamp</th>
                <th className="py-2.5 px-4">Raw PVGIS Time</th>
                <th className="py-2.5 px-4 text-right">Irradiance (W/m²)</th>
                <th className="py-2.5 px-4 text-right">PV Power (kW)</th>
                <th className="py-2.5 px-4 text-right">Temp (°C)</th>
                <th className="py-2.5 px-4 text-right">RH (%)</th>
                <th className="py-2.5 px-4 text-right">Wind (m/s)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs font-mono tabular-nums">
              {sample24h.map((row) => (
                <tr key={row.timestamp} className="hover:bg-slate-50/70">
                  <td className="py-2 px-4 text-slate-900 whitespace-nowrap">{row.timestamp}</td>
                  <td className="py-2 px-4 text-slate-500 whitespace-nowrap">{row.pvgis_raw_time}</td>
                  <td className="py-2 px-4 text-right text-amber-800">{row.pvgis_irradiance_wm2.toFixed(1)}</td>
                  <td className="py-2 px-4 text-right text-sky-800 font-semibold">{row.pvgis_pv_power_kw.toFixed(2)}</td>
                  <td className="py-2 px-4 text-right text-slate-800">{row.meteo_ambient_temp_c.toFixed(1)}</td>
                  <td className="py-2 px-4 text-right text-slate-700">{row.meteo_relative_humidity_pct.toFixed(0)}</td>
                  <td className="py-2 px-4 text-right text-slate-700">{row.meteo_wind_speed_ms.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
