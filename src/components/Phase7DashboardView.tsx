import React, { useMemo, useState } from 'react';
import phase3SimStats from '../data/phase3SimStats.json';
import phase5MlStats from '../data/phase5MlStats.json';
import phase6EnergyStats from '../data/phase6EnergyStats.json';
import phase7DashboardStats from '../data/phase7DashboardStats.json';
import exportManifest from '../data/exportProtocolManifest.json';
import { downloadStagedAsset } from '../utils/downloadFile';

type SectionId =
  | 'overview'
  | 'solar'
  | 'dryer'
  | 'storage'
  | 'ncg'
  | 'dispatch'
  | 'comparison'
  | 'safety'
  | 'reports';

type WindowKey = keyof typeof phase7DashboardStats.weather_windows_2023;
type FeedstockKey = 'olive_pomace' | 'wheat_straw' | 'wood_chips';

const FEEDSTOCK_DEFAULTS: Record<
  FeedstockKey,
  { name: string; cp: number; mass: number; dur: number; initMc: number; targMc: number; tempC: number }
> = {
  olive_pomace: {
    name: "Olive Pomace (Grignons d'olive)",
    cp: 1.45,
    mass: 280,
    dur: 4.5,
    initMc: 50,
    targMc: 11,
    tempC: 90,
  },
  wheat_straw: {
    name: 'Wheat Straw (Paille de blé)',
    cp: 1.38,
    mass: 165,
    dur: 3.8,
    initMc: 27,
    targMc: 10.5,
    tempC: 82.5,
  },
  wood_chips: {
    name: "Orchard Wood Chips (Bois d'élagage)",
    cp: 1.62,
    mass: 250,
    dur: 4.5,
    initMc: 42.5,
    targMc: 11.5,
    tempC: 95,
  },
};

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function downloadCsv(filename: string, rows: Record<string, string | number>[]) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(','),
    ...rows.map((r) => headers.map((h) => JSON.stringify(r[h] ?? '')).join(',')),
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export const Phase7DashboardView: React.FC = () => {
  const [section, setSection] = useState<SectionId>('overview');
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleStagedDownload = async (href: string, filename: string) => {
    setDownloadError(null);
    setDownloadingFile(filename);
    try {
      await downloadStagedAsset(href, filename);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : `Failed to download ${filename}`);
    } finally {
      setDownloadingFile(null);
    }
  };

  // Solar Energy interactive controls
  const [windowKey, setWindowKey] = useState<WindowKey>('spring_clear');
  const [collectorAreaM2, setCollectorAreaM2] = useState<number>(35);

  // Biomass Dryer interactive controls
  const [feedstock, setFeedstock] = useState<FeedstockKey>('olive_pomace');
  const [batchMassKg, setBatchMassKg] = useState<number>(250);
  const [durationH, setDurationH] = useState<number>(4.0);
  const [initMoisturePct, setInitMoisturePct] = useState<number>(45);
  const [targMoisturePct, setTargMoisturePct] = useState<number>(12);
  const [ambTempC, setAmbTempC] = useState<number>(18);
  const [ambRhPct, setAmbRhPct] = useState<number>(65);

  // Sand Storage interactive check
  const [checkSandTempC, setCheckSandTempC] = useState<number>(260);
  const [checkAmbTempC, setCheckAmbTempC] = useState<number>(20);

  // NCG Recovery interactive controls
  const [ncgFeedKgH, setNcgFeedKgH] = useState<number>(55);
  const [ncgYieldFrac, setNcgYieldFrac] = useState<number>(0.22);
  const [ncgLhvKjKg, setNcgLhvKjKg] = useState<number>(9500);
  const [ncgBurnerOn, setNcgBurnerOn] = useState<boolean>(true);

  // Energy Management scenario preview
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('high_solar');

  // Simulated Safety Monitoring controls (cannot change PLC limits)
  const [simSandT, setSimSandT] = useState<number>(260);
  const [simHtfT, setSimHtfT] = useState<number>(210);
  const [simHtfP, setSimHtfP] = useState<number>(3.2);
  const [simHtfFlow, setSimHtfFlow] = useState<number>(0.85);
  const [simDryerT, setSimDryerT] = useState<number>(85);
  const [simReactorO2, setSimReactorO2] = useState<number>(0.4);
  const [simEstop, setSimEstop] = useState<boolean>(false);

  const {
    streamlit_pages,
    plc_limits,
    validation_summary,
    artifact_inventory,
    downloadables,
    weather_windows_2023,
    feedstock_benchmarks,
  } = phase7DashboardStats;

  const activeWindow = weather_windows_2023[windowKey];
  const areaScale = collectorAreaM2 / 35.0;

  // Scaled collector thermal output cleanly matching EN 12975 collector curve proportionality
  const solarSeries = useMemo(() => {
    return activeWindow.points.map((p) => ({
      ...p,
      solar_th_scaled: Number((p.solar_th * areaScale).toFixed(2)),
    }));
  }, [activeWindow, areaScale]);

  const solarWindowTotals = useMemo(() => {
    const pvRefSum = solarSeries.reduce((s, p) => s + p.pv_ref, 0);
    const pvMlSum = solarSeries.reduce((s, p) => s + p.pv_ml, 0);
    const solThSum = solarSeries.reduce((s, p) => s + p.solar_th_scaled, 0);
    const peakIrr = Math.max(...solarSeries.map((p) => p.irr));
    return { pvRefSum, pvMlSum, solThSum, peakIrr };
  }, [solarSeries]);

  // First-Law Biomass Dryer Physics Check mirroring src/thermal_model.py
  const dryerCalc = useMemo(() => {
    const errs: string[] = [];
    if (batchMassKg < 10 || batchMassKg > 2000) errs.push('Batch mass must be between 10 kg and 2,000 kg.');
    if (durationH < 0.5 || durationH > 24) errs.push('Batch duration must be between 0.5 h and 24.0 h.');
    if (targMoisturePct >= initMoisturePct || targMoisturePct < 5 || initMoisturePct > 80) {
      errs.push('Moisture bounds require 5% <= target < initial <= 80%.');
    }
    if (errs.length > 0) return { valid: false, errors: errs };

    const spec = FEEDSTOCK_DEFAULTS[feedstock];
    const xi = initMoisturePct / 100.0;
    const xf = targMoisturePct / 100.0;
    const mWetRateKgS = batchMassKg / (durationH * 3600.0);
    const mDryKgS = mWetRateKgS * (1.0 - xi);
    const mEvapKgS = mWetRateKgS * ((xi - xf) / (1.0 - xf));
    const mWaterRemainKgS = mDryKgS * (xf / (1.0 - xf));

    const tChamber = 85.0;
    const tExhaust = 61.2;
    const tOutletBio = 66.2;
    const hfg = 2501.3 - 2.369 * tChamber;

    // Magnus-Tetens humidity ratio
    const pAtm = 97.007; // Settat 366m
    const pSatAmb = 0.61078 * Math.exp((17.27 * ambTempC) / (ambTempC + 237.3));
    const pvAmb = (ambRhPct / 100.0) * pSatAmb;
    const wAmb = 0.621945 * (pvAmb / Math.max(1.0, pAtm - pvAmb));
    const pSatExh = 0.61078 * Math.exp((17.27 * tExhaust) / (tExhaust + 237.3));
    const pvExh = 0.8 * pSatExh;
    const wExhTarget = 0.621945 * (pvExh / Math.max(1.0, pAtm - pvExh));
    const wExh = Math.max(wAmb + 0.004, Math.min(wExhTarget, wAmb + 0.045));
    const mDryAirKgS = mEvapKgS / Math.max(1e-6, wExh - wAmb);

    const qEvapVaporKw = mEvapKgS * (4.186 * (tChamber - ambTempC) + hfg + 1.86 * (tExhaust - tChamber));
    const qBioSensibleKw = mDryKgS * spec.cp * (tOutletBio - ambTempC);
    const qWaterRemKw = mWaterRemainKgS * 4.186 * (tOutletBio - ambTempC);
    const qAirExhaustKw = mDryAirKgS * (1.006 + 1.86 * wAmb) * (tExhaust - ambTempC);
    const qShellLossKw = 0.025 * (tChamber - ambTempC);
    const qUsefulKw = qEvapVaporKw + qBioSensibleKw + qWaterRemKw + qAirExhaustKw + qShellLossKw;
    const qDemandKw = qUsefulKw / 0.85;

    return {
      valid: true,
      errors: [] as string[],
      qDemandKw,
      waterEvapKgH: mEvapKgS * 3600.0,
      dryAirflowKgS: mDryAirKgS,
      breakdown: {
        evapVaporKw: qEvapVaporKw,
        bioSensibleKw: qBioSensibleKw,
        waterRemKw: qWaterRemKw,
        airExhaustKw: qAirExhaustKw,
        shellLossKw: qShellLossKw,
      },
    };
  }, [feedstock, batchMassKg, durationH, initMoisturePct, targMoisturePct, ambTempC, ambRhPct]);

  // Sand storage instantaneous calculation (matching src/storage_model.py)
  const sandMassKg = 4000;
  const sandCp = 0.83;
  const sandUaWk = 18.0;
  const sandUsableKwh = Math.max(0, (sandMassKg * sandCp * (checkSandTempC - plc_limits.sand_temp_min_operating_c)) / 3600);
  const sandStandbyLossKw = Math.max(0, (sandUaWk * (checkSandTempC - checkAmbTempC)) / 1000);

  // NCG recovery calculation (matching src/thermal_model.py)
  const ncgMassKgH = ncgBurnerOn ? ncgFeedKgH * ncgYieldFrac : 0;
  const ncgRecoveredKw = ncgBurnerOn ? (ncgMassKgH / 3600) * ncgLhvKjKg * 0.88 * 0.82 : 0;

  // Simulated PLC interlock evaluation (mirroring PLCSafetySupervisor)
  const plcEval = useMemo(() => {
    const trips: string[] = [];
    if (simEstop) trips.push('EMERGENCY_STOP_ACTIVE');
    if (simSandT >= plc_limits.sand_temp_plc_trip_c) trips.push(`SAND_OVER_TEMP (>= ${plc_limits.sand_temp_plc_trip_c} °C)`);
    if (simHtfT >= plc_limits.htf_max_temp_c) trips.push(`HTF_OVER_TEMP (>= ${plc_limits.htf_max_temp_c} °C)`);
    if (simHtfP < plc_limits.htf_min_pressure_bar) trips.push(`HTF_LOW_PRESSURE (< ${plc_limits.htf_min_pressure_bar} bar)`);
    if (simHtfP > plc_limits.htf_max_pressure_bar) trips.push(`HTF_OVER_PRESSURE (> ${plc_limits.htf_max_pressure_bar} bar)`);
    if (simHtfFlow < plc_limits.htf_min_flow_kg_s) trips.push(`HTF_LOW_FLOW (< ${plc_limits.htf_min_flow_kg_s} kg/s)`);
    if (simDryerT > plc_limits.dryer_max_inlet_air_temp_c) trips.push(`DRYER_AIR_OVER_TEMP (> ${plc_limits.dryer_max_inlet_air_temp_c} °C)`);
    if (simReactorO2 > plc_limits.ncg_max_reactor_o2_pct) trips.push(`PYROLYSIS_HIGH_O2 (> ${plc_limits.ncg_max_reactor_o2_pct}%)`);

    const safe = trips.length === 0;
    return {
      safe,
      trips,
      resultingMode: safe ? 'MODE_3_RECOVERED_HEAT_PRIORITY' : 'SAFE_STATE_SHUTDOWN',
    };
  }, [simEstop, simSandT, simHtfT, simHtfP, simHtfFlow, simDryerT, simReactorO2, plc_limits]);

  const activeScenario =
    phase6EnergyStats.scenarios.find((s) => s.scenario_id === selectedScenarioId) ?? phase6EnergyStats.scenarios[0];

  const med4Yr = phase3SimStats.report.scenarios.medium.summary_4yr;
  const solarBest = phase5MlStats.solar_model.models.find((m) => m.selected) ?? phase5MlStats.solar_model.models[3];
  const dryerBest = phase5MlStats.dryer_model.models.find((m) => m.selected) ?? phase5MlStats.dryer_model.models[3];

  // Helper for SVG dual-line charts
  const renderDualChartSvg = (
    labels: string[],
    aVals: number[],
    aLabel: string,
    aColor: string,
    bVals: number[],
    bLabel: string,
    bColor: string,
    unitLabel: string
  ) => {
    const w = 780;
    const h = 210;
    const pl = 48;
    const pr = 16;
    const pt = 14;
    const pb = 26;
    const pw = w - pl - pr;
    const ph = h - pt - pb;
    const all = [...aVals, ...bVals];
    const minV = Math.min(0, ...all);
    const maxV = Math.max(1, Math.ceil(Math.max(...all) * 1.1));
    const span = Math.max(1e-6, maxV - minV);
    const mkPath = (arr: number[]) =>
      arr
        .map((v, i) => {
          const x = pl + (i / Math.max(1, arr.length - 1)) * pw;
          const y = pt + ph * (1 - (v - minV) / span);
          return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(' ');

    return (
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: aColor }} />
              {aLabel}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: bColor }} />
              {bLabel}
            </span>
          </div>
          <span className="font-mono text-[11px] text-slate-500">Y-axis: {unitLabel}</span>
        </div>
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto select-none">
          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const val = minV + span * t;
            const y = pt + ph * (1 - t);
            return (
              <g key={t}>
                <line x1={pl} y1={y} x2={pl + pw} y2={y} stroke="#e2e8f0" strokeWidth="1" />
                <text x={pl - 6} y={y + 3} textAnchor="end" fontSize="10" fill="#64748b">
                  {val.toFixed(0)}
                </text>
              </g>
            );
          })}
          <path d={mkPath(aVals)} fill="none" stroke={aColor} strokeWidth="2" />
          <path d={mkPath(bVals)} fill="none" stroke={bColor} strokeWidth="2" strokeDasharray="5,3" />
          <text x={pl} y={pt + ph + 16} fontSize="10" fill="#64748b">
            {labels[0]} UTC
          </text>
          <text x={pl + pw} y={pt + ph + 16} textAnchor="end" fontSize="10" fill="#64748b">
            {labels[labels.length - 1]} UTC ({labels.length}h)
          </text>
        </svg>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Decision-Support & Safety Disclaimer */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs text-amber-950">
        <div>
          <span className="font-semibold">Decision-Support &amp; Safety Notice: </span>
          Streamlit dashboard (<span className="font-mono">EcoFarm_AI/dashboard/app.py</span>) and this live preview
          are engineering simulation tools only. Hardwired PLC limits ({plc_limits.sand_temp_plc_trip_c} °C trip) remain
          strictly non-overridable.
        </div>
        <a
          href="/downloads/EcoFarm_Phase7_Package.zip"
          download="EcoFarm_Phase7_Package.zip"
          className="px-3 py-1.5 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0"
        >
          Download Phase 7 ZIP ({formatBytes(downloadables[0]?.size_bytes ?? 0)})
        </a>
      </div>

      {/* Main Dashboard Layout: Sidebar (9 Streamlit Pages) + Active Viewport */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Navigation Sidebar mirroring Streamlit app.py */}
        <aside className="lg:col-span-3 bg-white border border-slate-200 rounded-lg p-3 space-y-3">
          <div className="px-2 pt-1 pb-2 border-b border-slate-100">
            <div className="text-xs font-semibold text-slate-900">Dashboard Navigation (9 Views)</div>
            <div className="text-[11px] text-slate-500 mt-0.5">
              Mirrors <span className="font-mono">EcoFarm_AI/dashboard/app.py</span>
            </div>
          </div>

          <nav aria-label="Dashboard Sections" className="space-y-1">
            {streamlit_pages.map((p) => {
              const active = section === (p.id as SectionId);
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setSection(p.id as SectionId)}
                  className={`w-full text-left px-3 py-2 rounded text-xs transition-colors cursor-pointer ${
                    active
                      ? 'bg-slate-900 text-white font-medium'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <div className="truncate">{p.name}</div>
                  <div className={`text-[10px] font-mono truncate ${active ? 'text-slate-300' : 'text-slate-400'}`}>
                    {p.provenance}
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="pt-2 border-t border-slate-100 px-2 space-y-1.5 text-[11px] text-slate-600">
            <div className="flex justify-between">
              <span>Verified Artifacts</span>
              <span className="font-mono tabular-nums font-semibold text-emerald-700">
                {validation_summary.artifacts_ready}/{validation_summary.artifacts_total} Ready
              </span>
            </div>
            <div className="flex justify-between">
              <span>Phase 7 QA Checks</span>
              <span className="font-mono tabular-nums font-semibold text-emerald-700">
                {validation_summary.tests_passed}/{validation_summary.tests_total} Passed
              </span>
            </div>
            <div className="flex justify-between">
              <span>Compiled Py Modules</span>
              <span className="font-mono tabular-nums font-semibold text-slate-800">
                {validation_summary.compiled_modules_count} modules
              </span>
            </div>
          </div>
        </aside>

        {/* Active Dashboard Viewport */}
        <div className="lg:col-span-9 space-y-6">
          {/* 1. OVERVIEW */}
          {section === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <div className="text-xs text-slate-500">Real Weather Continuity</div>
                  <div className="text-xl font-mono font-semibold tabular-nums text-slate-900 mt-1">
                    35,064 UTC hrs
                  </div>
                  <div className="text-[11px] text-emerald-700 mt-1">measured_external · 0 gaps</div>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <div className="text-xs text-slate-500">Model 1 PV Test R² (2023)</div>
                  <div className="text-xl font-mono font-semibold tabular-nums text-slate-900 mt-1">
                    {solarBest.test.r2.toFixed(5)}
                  </div>
                  <div className="text-[11px] text-sky-700 mt-1">
                    predicted_ml · RMSE {solarBest.test.rmse.toFixed(4)} kW_e
                  </div>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <div className="text-xs text-slate-500">Model 2 Dryer Test R²</div>
                  <div className="text-xl font-mono font-semibold tabular-nums text-slate-900 mt-1">
                    {dryerBest.test.r2.toFixed(5)}
                  </div>
                  <div className="text-[11px] text-sky-700 mt-1">
                    predicted_ml · RMSE {dryerBest.test.rmse.toFixed(4)} kW_th
                  </div>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <div className="text-xs text-slate-500">Phase 7 Verification</div>
                  <div className="text-xl font-mono font-semibold tabular-nums text-emerald-800 mt-1">
                    {validation_summary.tests_passed}/{validation_summary.tests_total} Passed
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">0 PLC violations · ZIP CRC OK</div>
                </div>
              </div>

              {/* Dual-Domain Plant Baseline & Electrical/Thermal Separation */}
              <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900">
                      Dual-Domain Energy Flow Topology (Electrical kW_e vs. Thermal kW_th Kept Separate)
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      4-year Phase 3 Medium Baseline ({phase7DashboardStats.site}) · Provenance: simulated_physics
                    </p>
                  </div>
                  <span className="text-xs font-mono text-slate-600">No unit mixing</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="border border-sky-200 bg-sky-50/50 rounded-md p-4 space-y-2">
                    <div className="font-semibold text-sky-900">Electrical Domain (kW_e / MWh_e)</div>
                    <div className="flex justify-between font-mono tabular-nums text-slate-700">
                      <span>PV Reference Output (15 kWp PVGIS)</span>
                      <span className="font-semibold text-slate-900">{med4Yr.pv_electrical_mwh_e.toFixed(2)} MWh_e</span>
                    </div>
                    <div className="text-[11px] text-slate-600 leading-relaxed">
                      Feeds 2.0 kW_e parasitic plant base load first; genuine surplus routes via PLC-interlocked
                      resistance heater contactor into silica sand thermal storage.
                    </div>
                  </div>

                  <div className="border border-amber-200 bg-amber-50/50 rounded-md p-4 space-y-2">
                    <div className="font-semibold text-amber-900">Thermal Domain (kW_th / MWh_th)</div>
                    <div className="flex justify-between font-mono tabular-nums text-slate-700">
                      <span>Solar Thermal Collector (35 m²)</span>
                      <span className="font-semibold text-slate-900">{med4Yr.solar_thermal_mwh_th.toFixed(2)} MWh_th</span>
                    </div>
                    <div className="flex justify-between font-mono tabular-nums text-slate-700">
                      <span>Pyrolysis NCG Recovered Heat</span>
                      <span className="font-semibold text-slate-900">{med4Yr.ncg_recovered_mwh_th.toFixed(2)} MWh_th</span>
                    </div>
                    <div className="flex justify-between font-mono tabular-nums text-slate-700">
                      <span>Dryer Thermal Demand ({med4Yr.renewable_recovered_coverage_pct.toFixed(1)}% covered)</span>
                      <span className="font-semibold text-slate-900">{med4Yr.dryer_demand_mwh_th.toFixed(2)} MWh_th</span>
                    </div>
                  </div>
                </div>

                {/* Provenance Legend */}
                <div className="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-600">
                  <div>
                    <span className="font-mono font-semibold text-emerald-700">measured_external</span> — Historical Settat
                    weather &amp; PVGIS solar irradiance (2020–2023 UTC)
                  </div>
                  <div>
                    <span className="font-mono font-semibold text-amber-700">simulated_physics</span> — Phase 3 First-Law
                    psychrometric dryer &amp; sand storage balance
                  </div>
                  <div>
                    <span className="font-mono font-semibold text-sky-700">predicted_ml</span> — Phase 5 Gradient Boosting
                    forecasts (<span className="font-mono">.pkl</span> artifacts)
                  </div>
                  <div>
                    <span className="font-mono font-semibold text-indigo-700">hypothetical_scenario</span> — Interactive
                    what-if explorer runs in Pages 3–6
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 2. SOLAR ENERGY */}
          {section === 'solar' && (
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Solar Energy — Real 2023 Weather, PVGIS Reference PV &amp; Phase 5 ML Forecast
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Target <span className="font-mono">pvgis_pv_power_kw</span> represents 15.0 kWp reference array (31° tilt, 14% loss), not metered plant output.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    downloadCsv(
                      `ecofarm_solar_${windowKey}.csv`,
                      solarSeries.map((p) => ({
                        timestamp_utc: p.ts,
                        irradiance_wm2: p.irr,
                        pvgis_pv_kw_e: p.pv_ref,
                        ml_pred_pv_kw_e: p.pv_ml,
                        solar_thermal_kw_th: p.solar_th_scaled,
                        ambient_temp_c: p.t_amb,
                      }))
                    )
                  }
                  className="px-3 py-1.5 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 whitespace-nowrap shrink-0 cursor-pointer"
                >
                  Download Window CSV
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50 border border-slate-200 rounded-md p-4">
                <div>
                  <label htmlFor="win-select" className="block text-xs font-medium text-slate-700 mb-1">
                    Untouched 2023 Weather Window (UTC)
                  </label>
                  <select
                    id="win-select"
                    value={windowKey}
                    onChange={(e) => setWindowKey(e.target.value as WindowKey)}
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded bg-white"
                  >
                    {(Object.keys(weather_windows_2023) as WindowKey[]).map((k) => (
                      <option key={k} value={k}>
                        {weather_windows_2023[k].title}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <label htmlFor="coll-area" className="font-medium text-slate-700">
                      Solar Thermal Collector Aperture Area
                    </label>
                    <span className="font-mono tabular-nums font-semibold text-slate-900">{collectorAreaM2} m²</span>
                  </div>
                  <input
                    id="coll-area"
                    type="range"
                    min={10}
                    max={80}
                    step={5}
                    value={collectorAreaM2}
                    onChange={(e) => setCollectorAreaM2(Number(e.target.value))}
                    className="w-full accent-sky-700 cursor-pointer"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="border border-slate-200 rounded p-3">
                  <div className="text-slate-500">Peak Irradiance</div>
                  <div className="text-lg font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
                    {solarWindowTotals.peakIrr.toFixed(1)} W/m²
                  </div>
                </div>
                <div className="border border-slate-200 rounded p-3">
                  <div className="text-slate-500">PVGIS Reference Sum</div>
                  <div className="text-lg font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
                    {solarWindowTotals.pvRefSum.toFixed(1)} kWh_e
                  </div>
                </div>
                <div className="border border-slate-200 rounded p-3">
                  <div className="text-slate-500">Phase 5 ML Forecast</div>
                  <div className="text-lg font-mono font-semibold tabular-nums text-sky-700 mt-0.5">
                    {solarWindowTotals.pvMlSum.toFixed(1)} kWh_e
                  </div>
                </div>
                <div className="border border-slate-200 rounded p-3">
                  <div className="text-slate-500">Solar Thermal ({collectorAreaM2} m²)</div>
                  <div className="text-lg font-mono font-semibold tabular-nums text-amber-700 mt-0.5">
                    {solarWindowTotals.solThSum.toFixed(1)} kWh_th
                  </div>
                </div>
              </div>

              {renderDualChartSvg(
                solarSeries.map((p) => p.ts),
                solarSeries.map((p) => p.pv_ref),
                'PVGIS Reference PV (kW_e)',
                '#0f172a',
                solarSeries.map((p) => p.pv_ml),
                'Phase 5 ML Forecast (kW_e)',
                '#0284c7',
                'Electrical kW_e'
              )}

              {renderDualChartSvg(
                solarSeries.map((p) => p.ts),
                solarSeries.map((p) => p.solar_th_scaled),
                `Solar Thermal Collector (${collectorAreaM2} m², kW_th)`,
                '#d97706',
                solarSeries.map((p) => p.t_amb),
                'Ambient Temp (°C)',
                '#0f766e',
                'kW_th / °C'
              )}
            </div>
          )}

          {/* 3. BIOMASS DRYER */}
          {section === 'dryer' && (
            <div className="space-y-6">
              <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Biomass Dryer — Interactive Thermodynamic Calculator (hypothetical_scenario)
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Uses Phase 3 non-overlapping First-Law enthalpy balance &amp; Magnus-Tetens psychrometrics.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                  <div>
                    <label htmlFor="fs-sel" className="block font-medium text-slate-700 mb-1">Feedstock</label>
                    <select
                      id="fs-sel"
                      value={feedstock}
                      onChange={(e) => setFeedstock(e.target.value as FeedstockKey)}
                      className="w-full px-2.5 py-1.5 border border-slate-300 rounded bg-white"
                    >
                      {(Object.keys(FEEDSTOCK_DEFAULTS) as FeedstockKey[]).map((k) => (
                        <option key={k} value={k}>
                          {FEEDSTOCK_DEFAULTS[k].name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="bm-in" className="block font-medium text-slate-700 mb-1">Wet Batch Mass (kg)</label>
                    <input
                      id="bm-in"
                      type="number"
                      min={10}
                      max={2000}
                      step={10}
                      value={batchMassKg}
                      onChange={(e) => setBatchMassKg(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 font-mono tabular-nums border border-slate-300 rounded bg-white"
                    />
                  </div>
                  <div>
                    <label htmlFor="dur-in" className="block font-medium text-slate-700 mb-1">Batch Duration (hours)</label>
                    <input
                      id="dur-in"
                      type="number"
                      min={0.5}
                      max={24}
                      step={0.5}
                      value={durationH}
                      onChange={(e) => setDurationH(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 font-mono tabular-nums border border-slate-300 rounded bg-white"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div>
                    <div className="flex justify-between mb-1">
                      <span>Initial Moisture</span>
                      <span className="font-mono font-semibold">{initMoisturePct}%</span>
                    </div>
                    <input
                      type="range"
                      min={12}
                      max={75}
                      value={initMoisturePct}
                      onChange={(e) => setInitMoisturePct(Number(e.target.value))}
                      className="w-full accent-sky-700 cursor-pointer"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <span>Target Moisture</span>
                      <span className="font-mono font-semibold">{targMoisturePct}%</span>
                    </div>
                    <input
                      type="range"
                      min={5}
                      max={25}
                      value={targMoisturePct}
                      onChange={(e) => setTargMoisturePct(Number(e.target.value))}
                      className="w-full accent-sky-700 cursor-pointer"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <span>Ambient Temp</span>
                      <span className="font-mono font-semibold">{ambTempC} °C</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={45}
                      value={ambTempC}
                      onChange={(e) => setAmbTempC(Number(e.target.value))}
                      className="w-full accent-sky-700 cursor-pointer"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <span>Ambient RH</span>
                      <span className="font-mono font-semibold">{ambRhPct}%</span>
                    </div>
                    <input
                      type="range"
                      min={10}
                      max={98}
                      value={ambRhPct}
                      onChange={(e) => setAmbRhPct(Number(e.target.value))}
                      className="w-full accent-sky-700 cursor-pointer"
                    />
                  </div>
                </div>

                {!dryerCalc.valid ? (
                  <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-900">
                    {dryerCalc.errors.join(' ')}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-2">
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                      <div className="text-slate-500">Thermal Demand</div>
                      <div className="text-lg font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
                        {dryerCalc.qDemandKw!.toFixed(2)} kW_th
                      </div>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                      <div className="text-slate-500">Water Evaporation</div>
                      <div className="text-lg font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
                        {dryerCalc.waterEvapKgH!.toFixed(2)} kg/h
                      </div>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                      <div className="text-slate-500">Latent Evap Term</div>
                      <div className="text-lg font-mono font-semibold tabular-nums text-sky-700 mt-0.5">
                        {dryerCalc.breakdown!.evapVaporKw.toFixed(2)} kW_th
                      </div>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                      <div className="text-slate-500">Dry Airflow Rate</div>
                      <div className="text-lg font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
                        {dryerCalc.dryAirflowKgS!.toFixed(3)} kg_da/s
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Verified Python Bridge Table: Phase 3 Physics vs Phase 5 ML */}
              <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-200">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Verified Python Bridge Benchmark (Phase 3 Physics vs. Phase 5 Gradient Boosting .pkl)
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                        <th className="py-2 px-4">Feedstock</th>
                        <th className="py-2 px-3 text-right">Batch (kg)</th>
                        <th className="py-2 px-3 text-right">Moisture</th>
                        <th className="py-2 px-3 text-right">Phase 3 Physics</th>
                        <th className="py-2 px-4 text-right">Phase 5 ML (.pkl)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {feedstock_benchmarks.map((fb) => (
                        <tr key={fb.feedstock_id}>
                          <td className="py-2.5 px-4 font-medium text-slate-900">{fb.display_name}</td>
                          <td className="py-2.5 px-3 text-right font-mono tabular-nums">{fb.typical_batch_kg} kg</td>
                          <td className="py-2.5 px-3 text-right font-mono tabular-nums">
                            {fb.typical_moisture_pct}% → {fb.target_moisture_pct}%
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono tabular-nums text-slate-900">
                            {fb.physics_kw_th.toFixed(2)} kW_th
                          </td>
                          <td className="py-2.5 px-4 text-right font-mono tabular-nums font-semibold text-sky-700">
                            {fb.ml_pred_kw_th.toFixed(2)} kW_th
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* 4. SAND STORAGE */}
          {section === 'storage' && (
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Sand Thermal Energy Storage — 2023 Window Profile &amp; Instantaneous Capacity Check
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    4,000 kg silica sand · T_min = {plc_limits.sand_temp_min_operating_c} °C · AI ceiling ={' '}
                    {plc_limits.sand_ai_ceiling_c} °C · Hardwired PLC trip = {plc_limits.sand_temp_plc_trip_c} °C
                  </p>
                </div>
                <select
                  aria-label="Select 2023 Sand Window"
                  value={windowKey}
                  onChange={(e) => setWindowKey(e.target.value as WindowKey)}
                  className="px-2.5 py-1.5 text-xs border border-slate-300 rounded bg-white"
                >
                  {(Object.keys(weather_windows_2023) as WindowKey[]).map((k) => (
                    <option key={k} value={k}>
                      {weather_windows_2023[k].title}
                    </option>
                  ))}
                </select>
              </div>

              {renderDualChartSvg(
                solarSeries.map((p) => p.ts),
                solarSeries.map((p) => p.sand_temp),
                'Sand Bed Temp (°C)',
                '#b45309',
                solarSeries.map((p) => p.stored_kwh),
                'Usable Stored Energy (kWh_th)',
                '#0284c7',
                '°C / kWh_th'
              )}

              <div className="pt-4 border-t border-slate-200 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="space-y-3 bg-slate-50 border border-slate-200 rounded p-4">
                  <div className="flex justify-between">
                    <label htmlFor="chk-sand-t" className="font-medium text-slate-700">Check Sand Bed Temperature</label>
                    <span className="font-mono font-semibold">{checkSandTempC} °C</span>
                  </div>
                  <input
                    id="chk-sand-t"
                    type="range"
                    min={25}
                    max={plc_limits.sand_ai_ceiling_c}
                    step={5}
                    value={checkSandTempC}
                    onChange={(e) => setCheckSandTempC(Number(e.target.value))}
                    className="w-full accent-sky-700 cursor-pointer"
                  />
                  <div className="flex justify-between">
                    <label htmlFor="chk-amb-t" className="font-medium text-slate-700">Ambient Temperature</label>
                    <span className="font-mono font-semibold">{checkAmbTempC} °C</span>
                  </div>
                  <input
                    id="chk-amb-t"
                    type="range"
                    min={0}
                    max={45}
                    value={checkAmbTempC}
                    onChange={(e) => setCheckAmbTempC(Number(e.target.value))}
                    className="w-full accent-sky-700 cursor-pointer"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-slate-200 rounded p-4">
                    <div className="text-slate-500">Usable Energy (&gt;120 °C)</div>
                    <div className="text-2xl font-mono font-semibold tabular-nums text-slate-900 mt-1">
                      {sandUsableKwh.toFixed(1)} kWh_th
                    </div>
                  </div>
                  <div className="border border-slate-200 rounded p-4">
                    <div className="text-slate-500">UA Standby Heat Loss</div>
                    <div className="text-2xl font-mono font-semibold tabular-nums text-amber-700 mt-1">
                      {sandStandbyLossKw.toFixed(3)} kW_th
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 5. NCG RECOVERY */}
          {section === 'ncg' && (
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-5">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  Pyrolysis Non-Condensable Gas (NCG) Heat Recovery Simulator
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Configurable feed rate, NCG yield, LHV, and combustion efficiency. Mode 3 activates when burner permissive is active.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs bg-slate-50 border border-slate-200 rounded p-4">
                <div>
                  <div className="flex justify-between mb-1">
                    <span>Pyrolysis Feed</span>
                    <span className="font-mono font-semibold">{ncgFeedKgH} kg/h</span>
                  </div>
                  <input
                    type="range"
                    min={10}
                    max={120}
                    step={5}
                    value={ncgFeedKgH}
                    onChange={(e) => setNcgFeedKgH(Number(e.target.value))}
                    className="w-full accent-sky-700 cursor-pointer"
                  />
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span>NCG Mass Yield</span>
                    <span className="font-mono font-semibold">{(ncgYieldFrac * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min={0.1}
                    max={0.35}
                    step={0.01}
                    value={ncgYieldFrac}
                    onChange={(e) => setNcgYieldFrac(Number(e.target.value))}
                    className="w-full accent-sky-700 cursor-pointer"
                  />
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span>NCG LHV</span>
                    <span className="font-mono font-semibold">{ncgLhvKjKg.toLocaleString()} kJ/kg</span>
                  </div>
                  <input
                    type="range"
                    min={5000}
                    max={14000}
                    step={250}
                    value={ncgLhvKjKg}
                    onChange={(e) => setNcgLhvKjKg(Number(e.target.value))}
                    className="w-full accent-sky-700 cursor-pointer"
                  />
                </div>
                <div className="flex items-center">
                  <label className="inline-flex items-center gap-2 font-medium text-slate-800 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ncgBurnerOn}
                      onChange={(e) => setNcgBurnerOn(e.target.checked)}
                      className="accent-emerald-700"
                    />
                    NCG Burner Active (PLC O₂ OK)
                  </label>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div className="border border-slate-200 rounded p-4">
                  <div className="text-slate-500">NCG Mass Flow Rate</div>
                  <div className="text-2xl font-mono font-semibold tabular-nums text-slate-900 mt-1">
                    {ncgMassKgH.toFixed(2)} kg/h
                  </div>
                </div>
                <div className="border border-slate-200 rounded p-4">
                  <div className="text-slate-500">Recovered Thermal Power</div>
                  <div className="text-2xl font-mono font-semibold tabular-nums text-emerald-700 mt-1">
                    {ncgRecoveredKw.toFixed(2)} kW_th
                  </div>
                </div>
                <div className="border border-slate-200 rounded p-4">
                  <div className="text-slate-500">Operating Priority Mode</div>
                  <div className="text-sm font-mono font-semibold text-slate-900 mt-2">
                    {ncgBurnerOn ? 'MODE_3_RECOVERED_HEAT_PRIORITY' : 'STANDBY / SOLAR / STORAGE'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 6. ENERGY MANAGEMENT */}
          {section === 'dispatch' && (
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Energy Management — Modes 1–5 &amp; Causal Scenario Dispatch
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Inspect audited Phase 6 scenario dispatch or run full custom Python simulations inside Streamlit/Colab.
                  </p>
                </div>
                <select
                  aria-label="Select Phase 6 Scenario"
                  value={selectedScenarioId}
                  onChange={(e) => setSelectedScenarioId(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-300 rounded bg-white"
                >
                  {phase6EnergyStats.scenarios.map((s) => (
                    <option key={s.scenario_id} value={s.scenario_id}>
                      {s.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="border border-slate-200 rounded p-3">
                  <div className="text-slate-500">Dryer Demand (168h)</div>
                  <div className="text-lg font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
                    {activeScenario.strategy_b.dryer_demand_kwh_th.toFixed(1)} kWh_th
                  </div>
                </div>
                <div className="border border-slate-200 rounded p-3">
                  <div className="text-slate-500">Aux Heat (AI vs. Rule)</div>
                  <div className="text-lg font-mono font-semibold tabular-nums text-emerald-700 mt-0.5">
                    {activeScenario.strategy_b.auxiliary_heating_kwh_th.toFixed(1)} vs{' '}
                    {activeScenario.strategy_a.auxiliary_heating_kwh_th.toFixed(1)} kWh_th
                  </div>
                </div>
                <div className="border border-slate-200 rounded p-3">
                  <div className="text-slate-500">PV Heater Surplus (Elec)</div>
                  <div className="text-lg font-mono font-semibold tabular-nums text-sky-700 mt-0.5">
                    {activeScenario.strategy_b.pv_heater_surplus_used_kwh_e.toFixed(1)} kWh_e
                  </div>
                </div>
                <div className="border border-slate-200 rounded p-3">
                  <div className="text-slate-500">Safety Violations</div>
                  <div className="text-lg font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
                    {activeScenario.strategy_b.safety_violations} / 0 conflicts
                  </div>
                </div>
              </div>

              <div className="divide-y divide-slate-100 border border-slate-200 rounded text-xs">
                {phase6EnergyStats.operating_modes.map((m) => (
                  <div key={m.mode} className="px-4 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <span className="font-mono font-semibold text-slate-900 shrink-0">{m.mode}</span>
                    <span className="text-slate-600 sm:text-right">{m.entry_exit_rule}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 7. STRATEGY COMPARISON */}
          {section === 'comparison' && (
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Strategy A (Rule-Based) vs. Strategy B (Forecast AI) — 7 Audited 2023 Scenarios
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Aggregate aux saved: {phase6EnergyStats.aggregate_totals.total_aux_reduction_kwh_th.toFixed(1)} kWh_th · Storage cycles reduced 43 → 20
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    downloadCsv(
                      'ecofarm_phase6_strategy_comparison.csv',
                      phase6EnergyStats.scenarios.map((s) => ({
                        scenario: s.title,
                        demand_kwh_th: s.strategy_a.dryer_demand_kwh_th,
                        aux_rule_kwh_th: s.strategy_a.auxiliary_heating_kwh_th,
                        aux_ai_kwh_th: s.strategy_b.auxiliary_heating_kwh_th,
                        non_aux_cov_rule_pct: s.strategy_a.non_aux_renewable_coverage_pct,
                        non_aux_cov_ai_pct: s.strategy_b.non_aux_renewable_coverage_pct,
                        cycles_rule: s.strategy_a.storage_direction_reversals,
                        cycles_ai: s.strategy_b.storage_direction_reversals,
                      }))
                    )
                  }
                  className="px-3 py-1.5 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 whitespace-nowrap shrink-0 cursor-pointer"
                >
                  Download Comparison CSV
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                      <th className="py-2.5 px-4">Scenario</th>
                      <th className="py-2.5 px-3 text-right">Demand (kWh_th)</th>
                      <th className="py-2.5 px-3 text-right">Aux Rule / AI</th>
                      <th className="py-2.5 px-3 text-right">Non-Aux Cov Rule / AI</th>
                      <th className="py-2.5 px-4 text-right">Cycles Rule / AI</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {phase6EnergyStats.scenarios.map((s) => (
                      <tr key={s.scenario_id}>
                        <td className="py-2.5 px-4 font-medium text-slate-900">{s.title}</td>
                        <td className="py-2.5 px-3 text-right font-mono tabular-nums">
                          {s.strategy_a.dryer_demand_kwh_th.toFixed(1)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono tabular-nums">
                          {s.strategy_a.auxiliary_heating_kwh_th.toFixed(1)} /{' '}
                          <span className="font-semibold text-emerald-700">
                            {s.strategy_b.auxiliary_heating_kwh_th.toFixed(1)}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono tabular-nums">
                          {s.strategy_a.non_aux_renewable_coverage_pct.toFixed(1)}% /{' '}
                          <span className="font-semibold text-sky-700">
                            {s.strategy_b.non_aux_renewable_coverage_pct.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                          {s.strategy_a.storage_direction_reversals} / {s.strategy_b.storage_direction_reversals}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 8. SAFETY MONITORING */}
          {section === 'safety' && (
            <div className="space-y-6">
              <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
                <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-950">
                  <span className="font-semibold">HARDWIRED SAFETY LOCK: </span>
                  Sand over-temperature trip is fixed at {plc_limits.sand_temp_plc_trip_c} °C (AI ceiling{' '}
                  {plc_limits.sand_ai_ceiling_c} °C). Dashboard sliders simulate fault conditions only and can never bypass hardware limits.
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <label htmlFor="plc-sand" className="block text-slate-700 mb-1">Sim Sand Temp (°C)</label>
                    <input
                      id="plc-sand"
                      type="number"
                      value={simSandT}
                      onChange={(e) => setSimSandT(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 font-mono border border-slate-300 rounded"
                    />
                  </div>
                  <div>
                    <label htmlFor="plc-htft" className="block text-slate-700 mb-1">Sim HTF Temp (°C)</label>
                    <input
                      id="plc-htft"
                      type="number"
                      value={simHtfT}
                      onChange={(e) => setSimHtfT(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 font-mono border border-slate-300 rounded"
                    />
                  </div>
                  <div>
                    <label htmlFor="plc-htfp" className="block text-slate-700 mb-1">Sim HTF Pressure (bar)</label>
                    <input
                      id="plc-htfp"
                      type="number"
                      step={0.1}
                      value={simHtfP}
                      onChange={(e) => setSimHtfP(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 font-mono border border-slate-300 rounded"
                    />
                  </div>
                  <div>
                    <label htmlFor="plc-flow" className="block text-slate-700 mb-1">Sim HTF Flow (kg/s)</label>
                    <input
                      id="plc-flow"
                      type="number"
                      step={0.05}
                      value={simHtfFlow}
                      onChange={(e) => setSimHtfFlow(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 font-mono border border-slate-300 rounded"
                    />
                  </div>
                  <div>
                    <label htmlFor="plc-dryt" className="block text-slate-700 mb-1">Sim Dryer Air (°C)</label>
                    <input
                      id="plc-dryt"
                      type="number"
                      value={simDryerT}
                      onChange={(e) => setSimDryerT(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 font-mono border border-slate-300 rounded"
                    />
                  </div>
                  <div>
                    <label htmlFor="plc-o2" className="block text-slate-700 mb-1">Sim Reactor O₂ (%)</label>
                    <input
                      id="plc-o2"
                      type="number"
                      step={0.1}
                      value={simReactorO2}
                      onChange={(e) => setSimReactorO2(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 font-mono border border-slate-300 rounded"
                    />
                  </div>
                  <div className="col-span-2 flex items-end pb-1.5">
                    <label className="inline-flex items-center gap-2 font-medium text-slate-900 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={simEstop}
                        onChange={(e) => setSimEstop(e.target.checked)}
                        className="accent-red-700"
                      />
                      Trigger Simulated Emergency Stop Loop
                    </label>
                  </div>
                </div>

                <div
                  className={`rounded p-3 border text-xs font-mono ${
                    plcEval.safe
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-950'
                      : 'bg-red-50 border-red-300 text-red-950 font-semibold'
                  }`}
                >
                  {plcEval.safe
                    ? `SIMULATED PANEL: SAFE TO OPERATE (${plcEval.resultingMode}) · NOT HARDWARE TELEMETRY`
                    : `SIMULATED PANEL: FORCED ${plcEval.resultingMode} · Interlocks: ${plcEval.trips.join(', ')}`}
                </div>
              </div>

              {/* Phase 7 Automated Validation Suite T01-T09 */}
              <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-200">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Executed Phase 7 Automated Verification Suite ({validation_summary.tests_passed}/{validation_summary.tests_total} Passed)
                  </h3>
                </div>
                <div className="divide-y divide-slate-100 text-xs">
                  {validation_summary.tests.map((t) => (
                    <div key={t.test_id} className="px-5 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <div className="font-medium text-slate-900">
                          <span className="font-mono text-slate-500 mr-2">{t.test_id}</span>
                          {t.name}
                        </div>
                        <div className="text-slate-600 mt-0.5">{t.detail}</div>
                      </div>
                      <span className="font-mono font-semibold text-emerald-700 shrink-0">{t.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 9. DATA & REPORTS */}
          {section === 'reports' && (
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

              <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Project-Wide Export Protocol (Phases 1–7 · {exportManifest.total_datasets_documented} Datasets · {exportManifest.total_notebooks} Colab Notebooks)
                  </h2>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Open <span className="font-medium text-slate-900">Project Files</span> in the top bar for per-phase filtering and native typed <span className="font-mono">.xlsx</span> / <span className="font-mono">.csv</span> exports, or download the master archives below.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <button
                    type="button"
                    disabled={downloadingFile !== null}
                    onClick={() => handleStagedDownload('/downloads/DATA_DICTIONARY.xlsx', 'DATA_DICTIONARY.xlsx')}
                    className="px-3 py-1.5 text-xs font-medium text-emerald-900 bg-emerald-50 border border-emerald-300 rounded hover:bg-emerald-100 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
                  >
                    {downloadingFile === 'DATA_DICTIONARY.xlsx' ? '...' : 'DATA_DICTIONARY.xlsx'}
                  </button>
                  <button
                    type="button"
                    disabled={downloadingFile !== null}
                    onClick={() => handleStagedDownload('/downloads/PROJECT_MANIFEST.xlsx', 'PROJECT_MANIFEST.xlsx')}
                    className="px-3 py-1.5 text-xs font-medium text-emerald-900 bg-emerald-50 border border-emerald-300 rounded hover:bg-emerald-100 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
                  >
                    {downloadingFile === 'PROJECT_MANIFEST.xlsx' ? '...' : 'PROJECT_MANIFEST.xlsx'}
                  </button>
                  <button
                    type="button"
                    disabled={downloadingFile !== null}
                    onClick={() => handleStagedDownload('/downloads/DATA_DICTIONARY.csv', 'DATA_DICTIONARY.csv')}
                    className="px-3 py-1.5 text-xs font-medium text-slate-800 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
                  >
                    {downloadingFile === 'DATA_DICTIONARY.csv' ? '...' : 'Dictionary CSV'}
                  </button>
                  <button
                    type="button"
                    disabled={downloadingFile !== null}
                    onClick={() =>
                      handleStagedDownload(
                        `/downloads/${exportManifest.master_archive.filename}`,
                        exportManifest.master_archive.filename
                      )
                    }
                    className="px-3.5 py-1.5 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
                  >
                    {downloadingFile === exportManifest.master_archive.filename
                      ? 'Downloading ZIP...'
                      : `Master Phases 1–7 ZIP (${formatBytes(exportManifest.master_archive.size_bytes)})`}
                  </button>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-200">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Verified Phase 7 Deliverables &amp; Direct File Downloads
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Phase 7 ZIP archive, Google Colab launcher notebook (<span className="font-mono">06_dashboard.ipynb</span>), CSV/XLSX datasets, and evaluation reports.
                  </p>
                </div>
                <div className="divide-y divide-slate-100">
                  {downloadables.map((d) => (
                    <div key={d.filename} className="px-5 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                      <div>
                        <div className="font-medium text-slate-900">{d.label}</div>
                        <div className="font-mono text-[11px] text-slate-500 mt-0.5">
                          {d.filename} · {formatBytes(d.size_bytes)} · SHA-256: {d.sha256_short}
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={downloadingFile !== null}
                        onClick={() => handleStagedDownload(d.href, d.filename)}
                        className="px-3 py-1.5 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0 cursor-pointer disabled:opacity-60"
                      >
                        {downloadingFile === d.filename ? 'Downloading...' : 'Download'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-200">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Audited Phase 2–6 Project Artifact Inventory ({validation_summary.artifacts_ready}/{validation_summary.artifacts_total} Ready)
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                        <th className="py-2 px-4">Artifact</th>
                        <th className="py-2 px-3">Path</th>
                        <th className="py-2 px-3 text-right">Size</th>
                        <th className="py-2 px-4 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {artifact_inventory.map((a) => (
                        <tr key={a.key}>
                          <td className="py-2 px-4 font-medium text-slate-900">{a.label}</td>
                          <td className="py-2 px-3 font-mono text-slate-600">{a.relative_path}</td>
                          <td className="py-2 px-3 text-right font-mono tabular-nums">{formatBytes(a.size_bytes)}</td>
                          <td className="py-2 px-4 text-right font-mono font-semibold text-emerald-700">{a.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
