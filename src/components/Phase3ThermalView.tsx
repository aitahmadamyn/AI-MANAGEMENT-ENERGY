import React, { useMemo, useState } from 'react';
import phase3SimStats from '../data/phase3SimStats.json';

type ScenarioKey = 'low' | 'medium' | 'high';
type SeasonWindowKey = 'summer72h' | 'winter72h';

export const Phase3ThermalView: React.FC = () => {
  const [scenario, setScenario] = useState<ScenarioKey>('medium');
  const [season, setSeason] = useState<SeasonWindowKey>('summer72h');
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const { report, windows, dataDictionary } = phase3SimStats;
  const activeScenario = report.scenarios[scenario];
  const summary = activeScenario.summary_4yr;
  const validation = activeScenario.validation;
  const series = windows[scenario][season];

  // SVG chart scales
  const width = 820;
  const heightPower = 210;
  const heightTemp = 175;
  const padL = 52;
  const padR = 52;
  const padT = 20;
  const padB = 26;
  const plotW = width - padL - padR;

  const maxPower = useMemo(() => {
    const vals = series.flatMap((d) => [
      d.dryerDemandKw,
      d.solarThermalKw,
      d.ncgRecoveredKw,
      d.auxKw,
    ]);
    return Math.max(20, ...vals) * 1.15;
  }, [series]);

  const xPos = (i: number) =>
    padL + (i / Math.max(1, series.length - 1)) * plotW;

  const yPow = (kw: number) =>
    padT + (heightPower - padT - padB) * (1 - kw / maxPower);

  const maxTempAxis = 620;
  const yTemp = (tC: number) =>
    padT + (heightTemp - padT - padB) * (1 - Math.min(maxTempAxis, Math.max(0, tC)) / maxTempAxis);

  const buildPath = (extractor: (d: (typeof series)[0]) => number, yFn: (v: number) => number) =>
    series
      .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xPos(i).toFixed(1)} ${yFn(extractor(d)).toFixed(1)}`)
      .join(' ');

  const hovered = hoverIdx !== null ? series[hoverIdx] : null;

  return (
    <div className="space-y-6">
      {/* Provenance & Scenario Control Toolbar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="text-xs font-mono text-amber-800 font-semibold">
            ▲ Provenance: simulated_physics · Coupled to Real Settat Weather (2020–2023 UTC)
          </div>
          <p className="text-xs text-slate-600 mt-0.5">
            {activeScenario.description} · Energy vectors kept separate (kW_th vs. kW_e)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Scenario selector */}
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-md">
            {(['low', 'medium', 'high'] as ScenarioKey[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setScenario(key)}
                className={`px-3 py-1.5 text-xs font-medium rounded capitalize transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                  scenario === key
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {key} Scenario
              </button>
            ))}
          </div>

          {/* Season selector */}
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-md">
            <button
              type="button"
              onClick={() => setSeason('summer72h')}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                season === 'summer72h'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Summer 72h (Jul 2023)
            </button>
            <button
              type="button"
              onClick={() => setSeason('winter72h')}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                season === 'winter72h'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Winter 72h (Jan 2023)
            </button>
          </div>
        </div>
      </div>

      {/* 4-Column Scenario Summary & Validation Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            4-Year Dryer Thermal Demand
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {summary.dryer_demand_mwh_th.toFixed(1)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">MWh_th</span>
          </div>
          <div className="mt-1 text-xs font-mono text-slate-500">
            Solar Th: {summary.solar_thermal_mwh_th} · NCG: {summary.ncg_recovered_mwh_th} MWh_th
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Renewable &amp; NCG Coverage
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {summary.renewable_recovered_coverage_pct.toFixed(1)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">%</span>
          </div>
          <div className="mt-1 text-xs font-mono text-slate-500">
            Auxiliary needed: {summary.auxiliary_heating_mwh_th} MWh_th
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Sand Bed Operating Envelope
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {summary.sand_temp_min_c.toFixed(0)}–{summary.sand_temp_max_c.toFixed(0)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">°C</span>
          </div>
          <div className="mt-1 text-xs text-emerald-700 font-medium">
            ● {validation.plc_safety_margin_violations} PLC safety margin violations
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            First-Law Energy Closure Error
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {validation.max_energy_closure_residual_kwh.toExponential(1)}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">kWh max</span>
          </div>
          <div className="mt-1 text-xs font-mono text-emerald-700 font-medium">
            ● Mass residual: {validation.max_mass_balance_residual_kg_s.toExponential(1)} kg/s
          </div>
        </div>
      </div>

      {/* Main 72-Hour Coupled Dynamics Chart */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200 bg-slate-50/70 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">
              72-Hour Coupled Thermal Power &amp; Sand Storage Trajectory ({scenario.toUpperCase()} Scenario)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Hover across any hour to inspect dryer load, solar thermal, NCG heat, auxiliary heat, and sand temperature
            </p>
          </div>
          <div className="font-mono text-xs tabular-nums text-slate-700">
            {hovered ? (
              <span>
                {hovered.label} UTC · Dryer={hovered.dryerDemandKw.toFixed(1)} kW · SolTh={hovered.solarThermalKw.toFixed(1)} kW · NCG={hovered.ncgRecoveredKw.toFixed(1)} kW · Sand={hovered.sandTempC.toFixed(1)}°C ({hovered.storedKwh.toFixed(1)} kWh)
              </span>
            ) : (
              <span className="text-slate-400">Crosshair idle — hover chart</span>
            )}
          </div>
        </div>

        <div className="p-5 space-y-4">
          {/* Top Panel: Thermal Power Flows (kW_th) */}
          <svg
            viewBox={`0 0 ${width} ${heightPower}`}
            className="w-full h-auto cursor-crosshair select-none"
            onMouseLeave={() => setHoverIdx(null)}
          >
            {[0, 0.25, 0.5, 0.75, 1].map((f) => {
              const y = padT + (heightPower - padT - padB) * (1 - f);
              return (
                <g key={f}>
                  <line x1={padL} y1={y} x2={width - padR} y2={y} stroke="#E2E8F0" strokeWidth="1" />
                  <text x={padL - 8} y={y + 3} textAnchor="end" className="fill-slate-500 text-[10px] font-mono tabular-nums">
                    {(maxPower * f).toFixed(0)}
                  </text>
                </g>
              );
            })}
            <text x={padL} y={12} className="fill-slate-700 text-[10px] font-mono font-semibold">
              Thermal Power Flows (kW_th)
            </text>

            {/* Paths */}
            <path d={buildPath((d) => d.dryerDemandKw, yPow)} fill="none" stroke="#0F172A" strokeWidth="2" />
            <path d={buildPath((d) => d.solarThermalKw, yPow)} fill="none" stroke="#D97706" strokeWidth="1.8" />
            <path d={buildPath((d) => d.ncgRecoveredKw, yPow)} fill="none" stroke="#0284C7" strokeWidth="1.8" strokeDasharray="4 2" />
            <path d={buildPath((d) => d.auxKw, yPow)} fill="none" stroke="#E11D48" strokeWidth="1.5" strokeDasharray="2 2" />

            {hoverIdx !== null && (
              <line
                x1={xPos(hoverIdx)}
                y1={padT}
                x2={xPos(hoverIdx)}
                y2={heightPower - padB}
                stroke="#475569"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
            )}

            {series.map((pt, i) => (
              <g key={pt.timestamp}>
                {i % 12 === 0 && (
                  <text x={xPos(i)} y={heightPower - 7} textAnchor="middle" className="fill-slate-500 text-[9px] font-mono">
                    {pt.label}
                  </text>
                )}
                <rect
                  x={xPos(i) - plotW / series.length / 2}
                  y={padT}
                  width={plotW / series.length}
                  height={heightPower - padT - padB}
                  fill="transparent"
                  onMouseEnter={() => setHoverIdx(i)}
                />
              </g>
            ))}
          </svg>

          {/* Bottom Panel: Sand Bed Temperature (°C) + PLC Margin */}
          <svg
            viewBox={`0 0 ${width} ${heightTemp}`}
            className="w-full h-auto cursor-crosshair select-none"
            onMouseLeave={() => setHoverIdx(null)}
          >
            {[0, 150, 300, 450, 600].map((tVal) => {
              const y = yTemp(tVal);
              return (
                <g key={tVal}>
                  <line x1={padL} y1={y} x2={width - padR} y2={y} stroke="#E2E8F0" strokeWidth="1" />
                  <text x={padL - 8} y={y + 3} textAnchor="end" className="fill-slate-500 text-[10px] font-mono tabular-nums">
                    {tVal}°C
                  </text>
                </g>
              );
            })}
            <text x={padL} y={12} className="fill-slate-700 text-[10px] font-mono font-semibold">
              Sand Thermal Storage Temperature (°C) &amp; PLC Safety Envelope
            </text>

            {/* PLC Trip & AI Ceiling reference lines */}
            <line x1={padL} y1={yTemp(600)} x2={width - padR} y2={yTemp(600)} stroke="#E11D48" strokeWidth="1.2" strokeDasharray="5 3" />
            <text x={width - padR + 6} y={yTemp(600) + 3} className="fill-rose-700 text-[9px] font-mono">
              PLC Trip (600°C)
            </text>

            <line x1={padL} y1={yTemp(550)} x2={width - padR} y2={yTemp(550)} stroke="#D97706" strokeWidth="1.1" strokeDasharray="3 3" />
            <text x={width - padR + 6} y={yTemp(550) + 3} className="fill-amber-700 text-[9px] font-mono">
              T_max (550°C)
            </text>

            <line x1={padL} y1={yTemp(120)} x2={width - padR} y2={yTemp(120)} stroke="#64748B" strokeWidth="1" strokeDasharray="3 3" />
            <text x={width - padR + 6} y={yTemp(120) + 3} className="fill-slate-600 text-[9px] font-mono">
              T_min (120°C)
            </text>

            <path d={buildPath((d) => d.sandTempC, yTemp)} fill="none" stroke="#B45309" strokeWidth="2.2" />

            {hoverIdx !== null && (
              <g>
                <line
                  x1={xPos(hoverIdx)}
                  y1={padT}
                  x2={xPos(hoverIdx)}
                  y2={heightTemp - padB}
                  stroke="#475569"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                />
                <circle
                  cx={xPos(hoverIdx)}
                  cy={yTemp(series[hoverIdx].sandTempC)}
                  r="4"
                  fill="#B45309"
                />
              </g>
            )}

            {series.map((pt, i) => (
              <rect
                key={pt.timestamp}
                x={xPos(i) - plotW / series.length / 2}
                y={padT}
                width={plotW / series.length}
                height={heightTemp - padT - padB}
                fill="transparent"
                onMouseEnter={() => setHoverIdx(i)}
              />
            ))}
          </svg>

          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center gap-6 text-xs font-mono">
            <span className="text-slate-900">━━ Dryer Demand (kW_th)</span>
            <span className="text-amber-700">━━ Solar Thermal (kW_th)</span>
            <span className="text-sky-700">┄┄ NCG Recovery (kW_th)</span>
            <span className="text-rose-700">┈┈ Aux Heating (kW_th)</span>
            <span className="text-amber-800">━━ Sand Temp (°C)</span>
          </div>
        </div>
      </div>

      {/* Sensitivity & Simulated Data Dictionary Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Sensitivity Sweeps (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-lg p-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Physical Sensitivity Verification
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Confirms monotonic physical response across moisture, ambient humidity, and vessel insulation UA
            </p>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <div className="font-semibold text-slate-700 mb-1.5">
                1. Biomass Initial Moisture → Dryer Thermal Demand
              </div>
              <div className="space-y-1">
                {report.sensitivity.moisture_sensitivity.map((item) => (
                  <div key={item.initial_moisture_pct} className="flex items-center justify-between font-mono tabular-nums py-1 border-b border-slate-100">
                    <span className="text-slate-600">MC = {item.initial_moisture_pct}% ({item.water_evap_kg_h} kg/h H₂O)</span>
                    <span className="font-semibold text-slate-900">{item.dryer_demand_kw} kW_th</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2">
              <div className="font-semibold text-slate-700 mb-1.5">
                2. Ambient Relative Humidity → Psychrometric Airflow &amp; Demand
              </div>
              <div className="space-y-1">
                {report.sensitivity.humidity_sensitivity.map((item) => (
                  <div key={item.ambient_rh_pct} className="flex items-center justify-between font-mono tabular-nums py-1 border-b border-slate-100">
                    <span className="text-slate-600">RH = {item.ambient_rh_pct}% ({item.airflow_kg_dry_air_s} kg/s air)</span>
                    <span className="font-semibold text-slate-900">{item.dryer_demand_kw} kW_th</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2">
              <div className="font-semibold text-slate-700 mb-1.5">
                3. Storage Insulation UA → 24h Standby Temp Drop (from 450 °C)
              </div>
              <div className="space-y-1">
                {report.sensitivity.insulation_ua_sensitivity.map((item) => (
                  <div key={item.standby_ua_w_k} className="flex items-center justify-between font-mono tabular-nums py-1 border-b border-slate-100">
                    <span className="text-slate-600">UA = {item.standby_ua_w_k} W/K</span>
                    <span className="font-semibold text-slate-900">-{item.temp_drop_24h_c} °C (to {item.temp_after_24h_standby_c}°C)</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Simulated Data Dictionary (7 cols) */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-200">
            <h3 className="text-sm font-semibold text-slate-900">
              Phase 3 Simulated Dataset Dictionary (`EcoFarm_AI/data/simulated/`)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Every simulated thermal variable is labeled `simulated_physics` and separated from real Phase 2 weather
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600">
                  <th className="py-2.5 px-4">Variable</th>
                  <th className="py-2.5 px-4">Unit</th>
                  <th className="py-2.5 px-4">Provenance</th>
                  <th className="py-2.5 px-4">Governing Equation / Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {dataDictionary.map((row) => (
                  <tr key={row.name} className="hover:bg-slate-50/70">
                    <td className="py-2 px-4 font-mono font-semibold text-slate-900 whitespace-nowrap">
                      {row.name}
                    </td>
                    <td className="py-2 px-4 font-mono text-slate-600 whitespace-nowrap">
                      {row.unit}
                    </td>
                    <td className="py-2 px-4 whitespace-nowrap">
                      <span
                        className={`font-medium ${
                          row.provenance === 'simulated_physics'
                            ? 'text-amber-700'
                            : row.provenance === 'calculated'
                              ? 'text-sky-700'
                              : 'text-emerald-700'
                        }`}
                      >
                        {row.provenance === 'simulated_physics' ? '▲ ' : '● '}
                        {row.provenance}
                      </span>
                    </td>
                    <td className="py-2 px-4 font-mono text-[11px] text-slate-600">
                      {row.equation_or_note}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
