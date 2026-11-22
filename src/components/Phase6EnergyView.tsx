import React, { useState } from 'react';
import phase6EnergyStats from '../data/phase6EnergyStats.json';

type Phase6SubTab = 'comparison' | 'dispatch' | 'safety';
type StrategyKey = 'strategy_a' | 'strategy_b';

const MODE_BADGE_TONE: Record<string, string> = {
  MODE_1_CHARGE: 'bg-sky-100 text-sky-900',
  MODE_2_DISCHARGE: 'bg-amber-100 text-amber-900',
  MODE_3_RECOVERED_HEAT_PRIORITY: 'bg-emerald-100 text-emerald-900',
  MODE_4_STANDBY: 'bg-slate-100 text-slate-700',
  MODE_5_AUXILIARY_HEATING: 'bg-rose-100 text-rose-900',
  SAFE_STATE_SHUTDOWN: 'bg-red-700 text-white',
};

const MODE_LABELS: Record<string, string> = {
  MODE_1_CHARGE: 'Mode 1 · Charge',
  MODE_2_DISCHARGE: 'Mode 2 · Discharge',
  MODE_3_RECOVERED_HEAT_PRIORITY: 'Mode 3 · NCG Priority',
  MODE_4_STANDBY: 'Mode 4 · Standby',
  MODE_5_AUXILIARY_HEATING: 'Mode 5 · Aux Heat',
  SAFE_STATE_SHUTDOWN: 'SAFE SHUTDOWN',
};

export const Phase6EnergyView: React.FC = () => {
  const [subTab, setSubTab] = useState<Phase6SubTab>('comparison');
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('high_solar');
  const [logStrategy, setLogStrategy] = useState<StrategyKey>('strategy_b');
  const [hoverHour, setHoverHour] = useState<number | null>(null);

  const {
    safety_disclaimer,
    configurable_plc_limits,
    operating_modes,
    aggregate_totals,
    scenarios,
    plc_fault_injection_tests,
    sample_traces_72h,
    sample_mode_transitions,
  } = phase6EnergyStats;

  const activeScenario =
    scenarios.find((s) => s.scenario_id === selectedScenarioId) ?? scenarios[0];

  const traces =
    (sample_traces_72h as Record<string, { strategy_a: any[]; strategy_b: any[] }>)[
      selectedScenarioId
    ] ?? sample_traces_72h.high_solar;

  const transitions =
    (sample_mode_transitions as Record<string, { strategy_a: any[]; strategy_b: any[] }>)[
      selectedScenarioId
    ] ?? sample_mode_transitions.high_solar;

  const activeTraceA = traces.strategy_a;
  const activeTraceB = traces.strategy_b;
  const activeHoverA = hoverHour !== null ? activeTraceA[hoverHour] : null;
  const activeHoverB = hoverHour !== null ? activeTraceB[hoverHour] : null;

  // Chart geometry for 72h Sand Bed Temperature & Dispatch
  const cw = 820;
  const ch = 230;
  const padL = 52;
  const padR = 20;
  const padT = 18;
  const padB = 30;
  const pw = cw - padL - padR;
  const ph = ch - padT - padB;

  const allTemps = [
    ...activeTraceA.map((p) => p.sand_temp_c),
    ...activeTraceB.map((p) => p.sand_temp_c),
  ];
  const minT = 100;
  const maxT = Math.max(260, Math.ceil(Math.max(...allTemps) / 25) * 25 + 15);
  const spanT = maxT - minT;

  const buildTempPath = (pts: any[]) =>
    pts
      .map((p, i) => {
        const x = padL + (i / Math.max(1, pts.length - 1)) * pw;
        const y = padT + ph * (1 - (p.sand_temp_c - minT) / spanT);
        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(' ');

  return (
    <div className="space-y-6">
      {/* Safety & Decision-Support Notice */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-950 leading-relaxed">
        <span className="font-semibold">Decision-Support &amp; PLC Boundary Notice: </span>
        {safety_disclaimer}
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Thermal Demand Satisfaction</div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              100.0
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">% across 7 scenarios</span>
          </div>
          <div className="mt-1 text-xs text-emerald-700 font-medium">
            ● {aggregate_totals.total_dryer_demand_kwh_th.toLocaleString()} kWh_th delivered
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">High-Solar Aux Heat Reduction</div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              -26.8
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">% (AI vs. Rule)</span>
          </div>
          <div className="mt-1 text-xs text-sky-700 font-medium">
            ◆ Aggregate saved: {aggregate_totals.total_aux_reduction_kwh_th.toFixed(1)} kWh_th ({aggregate_totals.total_aux_reduction_pct.toFixed(2)}%)
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">Storage Cycling Reversals</div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {aggregate_totals.total_cycles_b}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">
              vs. {aggregate_totals.total_cycles_a} (Rule)
            </span>
          </div>
          <div className="mt-1 text-xs text-emerald-700 font-medium">
            ▲ -53.5% fewer storage direction switches
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">PLC Safety &amp; Conflict Audit</div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {aggregate_totals.total_safety_violations} / {aggregate_totals.total_conflicting_commands}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">violations / conflicts</span>
          </div>
          <div className="mt-1 text-xs text-slate-600 font-medium">
            6/6 fault-injection safe-state checks passed
          </div>
        </div>
      </div>

      {/* Sub-navigation */}
      <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-200/70 rounded-md w-fit">
        {(
          [
            { id: 'comparison', label: 'Strategy A vs. Strategy B (7 Scenarios)' },
            { id: 'dispatch', label: '72h Dispatch Profile & Mode Logs' },
            { id: 'safety', label: '5 Operating Modes & PLC Safety Layer' },
          ] as { id: Phase6SubTab; label: string }[]
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

      {/* TAB 1: STRATEGY COMPARISON */}
      {subTab === 'comparison' && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  Identical 168-Hour Scenario Benchmark (Untouched 2023 Settat Weather)
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Strategy A = Instantaneous Rule-Based Baseline · Strategy B = Causal Phase 5 ML Forecast Supervisor
                </p>
              </div>
              <span className="text-xs font-mono text-slate-600">
                Electrical (kWh_e) &amp; Thermal (kWh_th) strictly separated
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
                    <th className="py-2.5 px-4 font-semibold">Scenario</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Demand (kWh_th)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Aux A / B (kWh_th)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Non-Aux Cov A / B</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Sol Util A / B</th>
                    <th className="py-2.5 px-3 font-semibold text-right">NCG Util A / B</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Storage Loss A / B</th>
                    <th className="py-2.5 px-4 font-semibold text-right">Cycles A / B</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {scenarios.map((s) => {
                    const a = s.strategy_a;
                    const b = s.strategy_b;
                    const isSelected = s.scenario_id === selectedScenarioId;
                    return (
                      <tr
                        key={s.scenario_id}
                        onClick={() => {
                          setSelectedScenarioId(s.scenario_id);
                          setSubTab('dispatch');
                        }}
                        className={`cursor-pointer transition-colors ${
                          isSelected ? 'bg-sky-50/70' : 'hover:bg-slate-50'
                        }`}
                      >
                        <td className="py-2.5 px-4">
                          <div className="font-medium text-slate-900">{s.title}</div>
                          <div className="text-[11px] text-slate-500">{s.weather_window}</div>
                        </td>
                        <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                          {a.dryer_demand_kwh_th.toFixed(1)}
                        </td>
                        <td className="py-2.5 px-3 font-mono tabular-nums text-right">
                          <span className="text-slate-600">{a.auxiliary_heating_kwh_th.toFixed(1)}</span>
                          <span className="text-slate-400 mx-1">/</span>
                          <span
                            className={
                              b.auxiliary_heating_kwh_th < a.auxiliary_heating_kwh_th
                                ? 'font-semibold text-emerald-700'
                                : 'font-semibold text-slate-900'
                            }
                          >
                            {b.auxiliary_heating_kwh_th.toFixed(1)}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono tabular-nums text-right">
                          <span className="text-slate-600">
                            {a.non_aux_renewable_coverage_pct.toFixed(1)}%
                          </span>
                          <span className="text-slate-400 mx-1">/</span>
                          <span className="font-semibold text-sky-700">
                            {b.non_aux_renewable_coverage_pct.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                          {a.solar_thermal_utilization_pct.toFixed(1)}% /{' '}
                          {b.solar_thermal_utilization_pct.toFixed(1)}%
                        </td>
                        <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                          {a.ncg_utilization_pct.toFixed(1)}% / {b.ncg_utilization_pct.toFixed(1)}%
                        </td>
                        <td className="py-2.5 px-3 font-mono tabular-nums text-right text-slate-700">
                          {a.storage_total_loss_kwh_th.toFixed(0)} /{' '}
                          {b.storage_total_loss_kwh_th.toFixed(0)}
                        </td>
                        <td className="py-2.5 px-4 font-mono tabular-nums text-right text-slate-800 font-medium">
                          {a.storage_direction_reversals} / {b.storage_direction_reversals}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-5 py-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-600">
              Click any scenario row to inspect its 72-hour sand bed trajectory and operating mode transition log.
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-2">
              <h3 className="text-sm font-semibold text-slate-900">
                When Forecast-Based AI Delivers Measurable Gains
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                In <span className="font-mono text-slate-900">high_solar</span>, aligning drying batches directly with
                predicted solar and NCG peaks cuts auxiliary heat by <span className="font-mono font-semibold text-emerald-700">26.8%</span>{' '}
                (101.0 kWh_th saved) and reduces storage losses by <span className="font-mono font-semibold">15.2%</span> by
                avoiding the 17.2% sand charge/discharge round-trip penalty. In{' '}
                <span className="font-mono text-slate-900">low_dryer_demand</span> and{' '}
                <span className="font-mono text-slate-900">high_ncg_recovery</span>, Strategy B eliminates storage cycling
                completely (<span className="font-mono font-semibold">13 → 0</span> reversals) and avoids dumping 215.1 kWh_e
                of PV electricity into unneeded resistance heating.
              </p>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-2">
              <h3 className="text-sm font-semibold text-slate-900">
                Physical Boundary Under Combined Adverse Deficit
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                In <span className="font-mono text-slate-900">high_dryer_demand</span> and{' '}
                <span className="font-mono text-slate-900">combined_adverse</span> (4,369–4,399 kWh_th drying demand vs.
                cold cloudy February weather and low NCG), renewable supply falls well below demand all week. Both
                strategies rely predominantly on Mode 5 auxiliary heat (3,960.2 vs. 3,961.9 kWh_th), showing honestly that
                forecast dispatch optimizes timing and efficiency—not total energy creation.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: 72H DISPATCH PROFILE & MODE TRANSITIONS */}
      {subTab === 'dispatch' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 bg-white border border-slate-200 rounded-lg p-4">
            <div className="space-y-0.5">
              <div className="text-xs text-slate-500">Selected Scenario</div>
              <div className="text-sm font-semibold text-slate-900">{activeScenario.title}</div>
              <div className="text-xs text-slate-600">{activeScenario.description}</div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {scenarios.map((s) => (
                <button
                  key={s.scenario_id}
                  type="button"
                  onClick={() => {
                    setSelectedScenarioId(s.scenario_id);
                    setHoverHour(null);
                  }}
                  className={`px-2.5 py-1.5 text-xs rounded border cursor-pointer transition-colors ${
                    s.scenario_id === selectedScenarioId
                      ? 'bg-slate-900 text-white border-slate-900'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {s.title.replace(' Availability', '').replace(' Recovery', '')}
                </button>
              ))}
            </div>
          </div>

          {/* 72h Sand Bed Temperature SVG */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  72-Hour Sand Bed Temperature Trajectory (°C) — Strategy A vs. Strategy B
                </h3>
                <p className="text-xs text-slate-500">
                  Hover across the timeline to compare instantaneous sand temperature, operating modes, and auxiliary heat
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-600">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-4 h-0.5 bg-slate-500 inline-block" /> Strategy A (Rule-Based)
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-4 h-0.5 bg-sky-600 inline-block" /> Strategy B (Forecast AI)
                </span>
              </div>
            </div>

            <svg
              viewBox={`0 0 ${cw} ${ch}`}
              className="w-full h-auto select-none"
              onMouseLeave={() => setHoverHour(null)}
            >
              {[0, 0.25, 0.5, 0.75, 1].map((t) => {
                const v = minT + spanT * t;
                const y = padT + ph * (1 - t);
                return (
                  <g key={t}>
                    <line x1={padL} y1={y} x2={padL + pw} y2={y} stroke="#e2e8f0" strokeWidth="1" />
                    <text x={padL - 7} y={y + 3} textAnchor="end" fontSize="10" fill="#64748b">
                      {v.toFixed(0)}°C
                    </text>
                  </g>
                );
              })}

              {/* T_min 120 C line */}
              {(() => {
                const yMin = padT + ph * (1 - (120 - minT) / spanT);
                return (
                  <>
                    <line
                      x1={padL}
                      y1={yMin}
                      x2={padL + pw}
                      y2={yMin}
                      stroke="#b91c1c"
                      strokeWidth="1.2"
                      strokeDasharray="4,3"
                    />
                    <text x={padL + pw} y={yMin - 4} textAnchor="end" fontSize="9.5" fill="#b91c1c">
                      T_min Operating Floor (120 °C)
                    </text>
                  </>
                );
              })()}

              <path
                d={buildTempPath(activeTraceA)}
                fill="none"
                stroke="#64748b"
                strokeWidth="2"
                strokeDasharray="5,3"
              />
              <path d={buildTempPath(activeTraceB)} fill="none" stroke="#0284c7" strokeWidth="2.4" />

              {hoverHour !== null && (
                <line
                  x1={padL + (hoverHour / Math.max(1, activeTraceA.length - 1)) * pw}
                  y1={padT}
                  x2={padL + (hoverHour / Math.max(1, activeTraceA.length - 1)) * pw}
                  y2={padT + ph}
                  stroke="#0f172a"
                  strokeWidth="1"
                />
              )}

              {/* Invisible hover columns */}
              {activeTraceA.map((_, i) => {
                const colW = pw / activeTraceA.length;
                const x = padL + (i / activeTraceA.length) * pw;
                return (
                  <rect
                    key={i}
                    x={x}
                    y={padT}
                    width={colW}
                    height={ph}
                    fill="transparent"
                    onMouseEnter={() => setHoverHour(i)}
                    className="cursor-crosshair"
                  />
                );
              })}

              <text x={padL} y={padT + ph + 18} fontSize="10" fill="#64748b">
                {activeTraceA[0]?.timestamp} UTC
              </text>
              <text x={padL + pw} y={padT + ph + 18} textAnchor="end" fontSize="10" fill="#64748b">
                {activeTraceA[activeTraceA.length - 1]?.timestamp} UTC (72h window)
              </text>
            </svg>

            <div className="bg-slate-50 border border-slate-200 rounded px-3 py-2 text-xs font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              {activeHoverA && activeHoverB ? (
                <>
                  <span className="text-slate-900 font-semibold">{activeHoverA.timestamp} UTC</span>
                  <span className="text-slate-700">
                    Rule: T={activeHoverA.sand_temp_c}°C ({MODE_LABELS[activeHoverA.mode]}, Aux={activeHoverA.aux_heating_kw} kW)
                  </span>
                  <span className="text-sky-800 font-semibold">
                    AI: T={activeHoverB.sand_temp_c}°C ({MODE_LABELS[activeHoverB.mode]}, Aux={activeHoverB.aux_heating_kw} kW)
                  </span>
                </>
              ) : (
                <>
                  <span className="text-slate-600">
                    Aux Heated: Rule {activeScenario.strategy_a.auxiliary_heating_kwh_th.toFixed(1)} kWh_th vs. AI{' '}
                    {activeScenario.strategy_b.auxiliary_heating_kwh_th.toFixed(1)} kWh_th
                  </span>
                  <span className="text-slate-600">
                    PV Heater Used: Rule {activeScenario.strategy_a.pv_heater_surplus_used_kwh_e.toFixed(1)} vs. AI{' '}
                    {activeScenario.strategy_b.pv_heater_surplus_used_kwh_e.toFixed(1)} kWh_e
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Operating Mode Transition Logs */}
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Operating Mode Transition Log ({activeScenario.title})
                </h3>
                <p className="text-xs text-slate-500">
                  Every mode transition records timestamp, trigger reason, sand temperature, and PLC permissive status
                </p>
              </div>
              <div className="flex items-center gap-1 p-0.5 bg-slate-100 rounded text-xs">
                <button
                  type="button"
                  onClick={() => setLogStrategy('strategy_b')}
                  className={`px-2.5 py-1 rounded cursor-pointer ${
                    logStrategy === 'strategy_b' ? 'bg-white text-slate-900 font-medium shadow-2xs' : 'text-slate-600'
                  }`}
                >
                  Strategy B (Forecast AI)
                </button>
                <button
                  type="button"
                  onClick={() => setLogStrategy('strategy_a')}
                  className={`px-2.5 py-1 rounded cursor-pointer ${
                    logStrategy === 'strategy_a' ? 'bg-white text-slate-900 font-medium shadow-2xs' : 'text-slate-600'
                  }`}
                >
                  Strategy A (Rule-Based)
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
                    <th className="py-2.5 px-4 font-semibold">Timestamp (UTC)</th>
                    <th className="py-2.5 px-3 font-semibold">From Mode</th>
                    <th className="py-2.5 px-3 font-semibold">To Mode</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Sand Temp</th>
                    <th className="py-2.5 px-4 font-semibold">Transition Reason &amp; PLC Guard</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(transitions[logStrategy] ?? []).map((tr: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-50/70">
                      <td className="py-2 px-4 font-mono text-slate-700 whitespace-nowrap">
                        {tr.timestamp}
                      </td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${MODE_BADGE_TONE[tr.from_mode] ?? 'bg-slate-100'}`}>
                          {MODE_LABELS[tr.from_mode] ?? tr.from_mode}
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${MODE_BADGE_TONE[tr.to_mode] ?? 'bg-slate-100'}`}>
                          {MODE_LABELS[tr.to_mode] ?? tr.to_mode}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-mono tabular-nums text-right text-slate-900">
                        {tr.sand_temp_c.toFixed(1)} °C
                      </td>
                      <td className="py-2 px-4 text-slate-600">{tr.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: OPERATING MODES & PLC SAFETY LAYER */}
      {subTab === 'safety' && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200">
              <h2 className="text-sm font-semibold text-slate-900">
                Five Operating Modes + Fail-Safe Shutdown State Machine
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Mutually exclusive actuator commands enforce zero simultaneous sand charge/discharge conflicts.
              </p>
            </div>
            <div className="divide-y divide-slate-100">
              {operating_modes.map((m) => (
                <div key={m.mode} className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`px-2.5 py-1 rounded font-mono font-semibold ${MODE_BADGE_TONE[m.mode] ?? 'bg-slate-100'}`}>
                      {m.mode}
                    </span>
                  </div>
                  <div className="text-slate-700 leading-relaxed sm:text-right max-w-3xl">
                    {m.entry_exit_rule}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Fault Injection Verification */}
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-200">
                <h3 className="text-sm font-semibold text-slate-900">
                  PLC Safety Layer Fault-Injection Verification
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Confirms invalid signals and hardware interlock trips override AI commands into SAFE_STATE_SHUTDOWN.
                </p>
              </div>
              <div className="divide-y divide-slate-100 text-xs">
                {plc_fault_injection_tests.map((ft, idx) => (
                  <div key={idx} className="px-5 py-3 flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-slate-900">{ft.test_case}</div>
                      <div className="font-mono text-[11px] text-slate-500 mt-0.5">
                        {ft.active_interlocks.length > 0 ? ft.active_interlocks.join(', ') : 'All permissives nominal'}
                      </div>
                    </div>
                    <span className={`px-2 py-0.5 rounded font-mono text-[11px] shrink-0 ${MODE_BADGE_TONE[ft.resulting_mode]}`}>
                      {ft.resulting_mode === 'SAFE_STATE_SHUTDOWN' ? 'SAFE STATE' : 'OPERATE'}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Configurable Equipment Safety Limits */}
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-200">
                <h3 className="text-sm font-semibold text-slate-900">
                  Configurable PLC Hardware Limits (`PLCSafetyLimits`)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Unknown pilot-plant limits remain parameterized here until hardware commissioning.
                </p>
              </div>
              <div className="p-5 grid grid-cols-2 gap-3 text-xs">
                {Object.entries(configurable_plc_limits).map(([k, v]) => (
                  <div key={k} className="bg-slate-50 border border-slate-200 rounded p-2.5">
                    <div className="font-mono text-[11px] text-slate-500">{k}</div>
                    <div className="font-mono font-semibold text-slate-900 mt-0.5">{String(v)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
