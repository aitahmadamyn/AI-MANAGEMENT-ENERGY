import React, { useState } from 'react';
import {
  SchematicNodeId,
  SUBSYSTEM_BOUNDARIES,
  SubsystemBoundarySpec,
} from '../data/phase1Data';

interface LayerState {
  thermal: boolean;
  electrical: boolean;
  aiAdvisory: boolean;
  plcPerimeter: boolean;
}

export const PlantSchematic: React.FC = () => {
  const [selectedNode, setSelectedNode] = useState<SchematicNodeId>('sand_storage');
  const [layers, setLayers] = useState<LayerState>({
    thermal: true,
    electrical: true,
    aiAdvisory: true,
    plcPerimeter: true,
  });

  const activeSpec: SubsystemBoundarySpec = SUBSYSTEM_BOUNDARIES[selectedNode];

  const toggleLayer = (key: keyof LayerState) => {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const nodeCardStyle = (id: SchematicNodeId) => {
    const isSelected = selectedNode === id;
    return isSelected
      ? 'fill-sky-50 stroke-sky-700 stroke-2'
      : 'fill-white stroke-slate-300 hover:stroke-slate-500 stroke-[1.25]';
  };

  const handleKeySelect = (e: React.KeyboardEvent, id: SchematicNodeId) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setSelectedNode(id);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Main Schematic Viewport (8 columns on lg) */}
      <div className="lg:col-span-8 bg-white border border-slate-200 rounded-lg overflow-hidden">
        {/* Schematic HUD Toolbar */}
        <div className="px-5 py-3.5 border-b border-slate-200 flex flex-wrap items-center justify-between gap-4 bg-slate-50/70">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">
              System Boundary & Energy Flow Schematic
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Select any subsystem block to inspect inputs, physical equations, and PLC vs. AI authority
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={() => toggleLayer('thermal')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded border transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                layers.thermal
                  ? 'bg-amber-50 text-amber-800 border-amber-300'
                  : 'bg-white text-slate-500 border-slate-200 hover:text-slate-800'
              }`}
            >
              Thermal Flows
            </button>
            <button
              type="button"
              onClick={() => toggleLayer('electrical')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded border transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                layers.electrical
                  ? 'bg-sky-50 text-sky-800 border-sky-300'
                  : 'bg-white text-slate-500 border-slate-200 hover:text-slate-800'
              }`}
            >
              PV Electrical
            </button>
            <button
              type="button"
              onClick={() => toggleLayer('aiAdvisory')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded border transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                layers.aiAdvisory
                  ? 'bg-indigo-50 text-indigo-800 border-indigo-300'
                  : 'bg-white text-slate-500 border-slate-200 hover:text-slate-800'
              }`}
            >
              AI Advisory
            </button>
            <button
              type="button"
              onClick={() => toggleLayer('plcPerimeter')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded border transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                layers.plcPerimeter
                  ? 'bg-rose-50 text-rose-800 border-rose-300'
                  : 'bg-white text-slate-500 border-slate-200 hover:text-slate-800'
              }`}
            >
              PLC Interlocks
            </button>
          </div>
        </div>

        {/* Interactive SVG Diagram */}
        <div className="p-5 bg-white">
          <svg
            viewBox="0 0 920 470"
            className="w-full h-auto select-none"
            role="img"
            aria-label="EcoFarm Circular Thermodynamic and Control Boundary Schematic"
          >
            <defs>
              <marker
                id="arrow-thermal"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#D97706" />
              </marker>
              <marker
                id="arrow-elec"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#0284C7" />
              </marker>
              <marker
                id="arrow-ai"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#4338CA" />
              </marker>
              <marker
                id="arrow-mass"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569" />
              </marker>
              <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
                <path
                  d="M 24 0 L 0 0 0 24"
                  fill="none"
                  stroke="#F1F5F9"
                  strokeWidth="1"
                />
              </pattern>
            </defs>

            {/* Engineering grid backdrop */}
            <rect width="920" height="470" fill="url(#grid)" rx="6" />

            {/* Outer System Boundary */}
            <rect
              x="16"
              y="14"
              width="888"
              height="312"
              rx="6"
              fill="none"
              stroke="#94A3B8"
              strokeWidth="1.2"
              strokeDasharray="6 4"
            />
            <text x="28" y="32" className="fill-slate-500 text-[10px] font-mono font-medium">
              PLANT THERMODYNAMIC CONTROL VOLUME (PHASE 1 BOUNDARY)
            </text>

            {/* PLC Safety Perimeter */}
            {layers.plcPerimeter && (
              <g
                onClick={() => setSelectedNode('plc_safety')}
                onKeyDown={(e) => handleKeySelect(e, 'plc_safety')}
                tabIndex={0}
                role="button"
                aria-label="Inspect PLC Safety Interlock Perimeter"
                className="cursor-pointer focus:outline-none"
              >
                <rect
                  x="265"
                  y="44"
                  width="625"
                  height="268"
                  rx="6"
                  fill={selectedNode === 'plc_safety' ? 'rgba(254, 242, 242, 0.55)' : 'rgba(255, 251, 235, 0.25)'}
                  stroke={selectedNode === 'plc_safety' ? '#BE123C' : '#E11D48'}
                  strokeWidth={selectedNode === 'plc_safety' ? '2' : '1.2'}
                  strokeDasharray="4 3"
                />
                <text x="278" y="61" className="fill-rose-700 text-[10px] font-mono font-semibold">
                  HARDWIRED PLC SAFETY PERIMETER (O2, PRESSURE, &gt;600 °C TRIP — NO AI OVERRIDE)
                </text>
              </g>
            )}

            {/* Node 1: Solar PV & Thermal */}
            <g
              onClick={() => setSelectedNode('solar_pv_thermal')}
              onKeyDown={(e) => handleKeySelect(e, 'solar_pv_thermal')}
              tabIndex={0}
              role="button"
              aria-label="Inspect Solar PV and Thermal Collectors"
              className="cursor-pointer focus:outline-none"
            >
              <rect x="34" y="68" width="185" height="92" rx="5" className={nodeCardStyle('solar_pv_thermal')} />
              <text x="48" y="92" className="fill-slate-900 text-[12px] font-semibold">
                Solar PV &amp; Thermal
              </text>
              <text x="48" y="110" className="fill-slate-500 text-[10px] font-mono">
                PVGIS Irradiance, T_amb, Wind
              </text>
              <text x="48" y="128" className="fill-sky-700 text-[10px] font-mono">
                Model 1 Target: P_pv (kW)
              </text>
              <text x="48" y="146" className="fill-slate-500 text-[10px]">
                Surplus-only resistance heat
              </text>
            </g>

            {/* Node 2: Slow Pyrolysis & NCG Recovery */}
            <g
              onClick={() => setSelectedNode('pyrolysis_ncg')}
              onKeyDown={(e) => handleKeySelect(e, 'pyrolysis_ncg')}
              tabIndex={0}
              role="button"
              aria-label="Inspect Slow Pyrolysis and NCG Heat Recovery"
              className="cursor-pointer focus:outline-none"
            >
              <rect x="282" y="198" width="205" height="96" rx="5" className={nodeCardStyle('pyrolysis_ncg')} />
              <text x="296" y="222" className="fill-slate-900 text-[12px] font-semibold">
                Slow Pyrolysis &amp; NCG
              </text>
              <text x="296" y="240" className="fill-slate-500 text-[10px] font-mono">
                Biochar + NCG Combustion
              </text>
              <text x="296" y="258" className="fill-amber-700 text-[10px] font-mono">
                Recovered Heat: Q_rec (kW)
              </text>
              <text x="296" y="276" className="fill-rose-700 text-[10px]">
                PLC: O2 &amp; flame supervision
              </text>
            </g>

            {/* Node 3: Sand Thermal Energy Storage */}
            <g
              onClick={() => setSelectedNode('sand_storage')}
              onKeyDown={(e) => handleKeySelect(e, 'sand_storage')}
              tabIndex={0}
              role="button"
              aria-label="Inspect Sand Thermal Energy Storage"
              className="cursor-pointer focus:outline-none"
            >
              <rect x="282" y="76" width="205" height="96" rx="5" className={nodeCardStyle('sand_storage')} />
              <text x="296" y="100" className="fill-slate-900 text-[12px] font-semibold">
                Sand Thermal Battery
              </text>
              <text x="296" y="118" className="fill-slate-500 text-[10px] font-mono">
                Q = m · Cp · (T_sand - T_min)
              </text>
              <text x="296" y="136" className="fill-amber-700 text-[10px] font-mono">
                Model 3: 120–550 °C Window
              </text>
              <text x="296" y="154" className="fill-slate-500 text-[10px]">
                Sensible storage + standby loss
              </text>
            </g>

            {/* Node 4: HTF Loop & Indirect HX */}
            <g
              onClick={() => setSelectedNode('htf_hx')}
              onKeyDown={(e) => handleKeySelect(e, 'htf_hx')}
              tabIndex={0}
              role="button"
              aria-label="Inspect HTF Circuit and Indirect Heat Exchanger"
              className="cursor-pointer focus:outline-none"
            >
              <rect x="530" y="76" width="156" height="96" rx="5" className={nodeCardStyle('htf_hx')} />
              <text x="544" y="100" className="fill-slate-900 text-[12px] font-semibold">
                HTF &amp; Indirect HX
              </text>
              <text x="544" y="118" className="fill-slate-500 text-[10px] font-mono">
                T_htf_in / T_htf_out
              </text>
              <text x="544" y="136" className="fill-slate-600 text-[10px] font-mono">
                Max Safe: 320 °C
              </text>
              <text x="544" y="154" className="fill-slate-500 text-[10px]">
                Pump flow &amp; relief valve
              </text>
            </g>

            {/* Node 5: Biomass Dryer */}
            <g
              onClick={() => setSelectedNode('biomass_dryer')}
              onKeyDown={(e) => handleKeySelect(e, 'biomass_dryer')}
              tabIndex={0}
              role="button"
              aria-label="Inspect Biomass Dryer"
              className="cursor-pointer focus:outline-none"
            >
              <rect x="720" y="76" width="156" height="218" rx="5" className={nodeCardStyle('biomass_dryer')} />
              <text x="734" y="104" className="fill-slate-900 text-[12px] font-semibold">
                Biomass Dryer
              </text>
              <text x="734" y="124" className="fill-slate-500 text-[10px] font-mono">
                Wet mass, RH, T_air
              </text>
              <text x="734" y="142" className="fill-sky-700 text-[10px] font-mono">
                Model 2: Q_dryer (kW)
              </text>
              <line x1="734" y1="158" x2="862" y2="158" stroke="#E2E8F0" strokeWidth="1" />
              <text x="734" y="176" className="fill-slate-600 text-[10px]">
                Moisture: 45% → 12%
              </text>
              <text x="734" y="196" className="fill-slate-500 text-[10px]">
                Latent + sensible heat
              </text>
              <text x="734" y="214" className="fill-slate-500 text-[10px]">
                + thermal losses (η)
              </text>
              <text x="734" y="276" className="fill-slate-700 text-[10px] font-mono">
                Feed to Pyrolysis ↓
              </text>
            </g>

            {/* Node 6: AI Decision-Support Layer */}
            {layers.aiAdvisory && (
              <g
                onClick={() => setSelectedNode('ai_advisor')}
                onKeyDown={(e) => handleKeySelect(e, 'ai_advisor')}
                tabIndex={0}
                role="button"
                aria-label="Inspect AI Decision-Support Layer"
                className="cursor-pointer focus:outline-none"
              >
                <rect
                  x="34"
                  y="352"
                  width="852"
                  height="98"
                  rx="5"
                  className={
                    selectedNode === 'ai_advisor'
                      ? 'fill-indigo-50 stroke-indigo-700 stroke-2'
                      : 'fill-white stroke-indigo-300 hover:stroke-indigo-500 stroke-[1.25]'
                  }
                />
                <text x="50" y="376" className="fill-slate-900 text-[12px] font-semibold">
                  AI Decision-Support Layer (Simulation &amp; Supervisory Recommendations Only)
                </text>
                <text x="50" y="397" className="fill-slate-600 text-[11px] font-mono">
                  Inputs: Forecast PV (Model 1) + Forecast Dryer Load (Model 2) + Sand Storage State (Model 3) + NCG Status
                </text>
                <text x="50" y="420" className="fill-indigo-700 text-[11px] font-mono">
                  Outputs: MODE 1 CHARGE · MODE 2 DISCHARGE · MODE 3 NCG PRIORITY · MODE 4 STANDBY · MODE 5 AUXILIARY
                </text>
                <text x="50" y="438" className="fill-slate-500 text-[10px]">
                  Strictly advisory: physical actuation &amp; interlocks remain under hardwired PLC supervision
                </text>
              </g>
            )}

            {/* Energy & Mass Flows */}
            {layers.electrical && (
              <g>
                <path
                  d="M 219 102 L 278 102"
                  fill="none"
                  stroke="#0284C7"
                  strokeWidth="1.75"
                  markerEnd="url(#arrow-elec)"
                />
                <text x="223" y="95" className="fill-sky-700 text-[9px] font-mono">
                  Surplus PV
                </text>
              </g>
            )}

            {layers.thermal && (
              <g>
                {/* Solar thermal to Sand */}
                <path
                  d="M 219 134 L 278 134"
                  fill="none"
                  stroke="#D97706"
                  strokeWidth="1.75"
                  markerEnd="url(#arrow-thermal)"
                />
                <text x="223" y="148" className="fill-amber-700 text-[9px] font-mono">
                  Solar Th.
                </text>

                {/* NCG Recovery to Sand */}
                <path
                  d="M 384 198 L 384 176"
                  fill="none"
                  stroke="#D97706"
                  strokeWidth="1.75"
                  markerEnd="url(#arrow-thermal)"
                />
                <text x="392" y="190" className="fill-amber-700 text-[9px] font-mono">
                  NCG Heat
                </text>

                {/* Sand to HTF */}
                <path
                  d="M 487 124 L 526 124"
                  fill="none"
                  stroke="#D97706"
                  strokeWidth="1.75"
                  markerEnd="url(#arrow-thermal)"
                />

                {/* HTF to Dryer */}
                <path
                  d="M 686 124 L 716 124"
                  fill="none"
                  stroke="#D97706"
                  strokeWidth="1.75"
                  markerEnd="url(#arrow-thermal)"
                />
              </g>
            )}

            {/* Dried Biomass flow: Dryer -> Pyrolysis */}
            <path
              d="M 720 250 L 491 250"
              fill="none"
              stroke="#475569"
              strokeWidth="1.5"
              strokeDasharray="3 2"
              markerEnd="url(#arrow-mass)"
            />
            <text x="556" y="242" className="fill-slate-600 text-[9px] font-mono">
              Dried Biomass (~12% MC)
            </text>

            {/* Read-only Telemetry to AI Advisory */}
            {layers.aiAdvisory && (
              <g>
                <path
                  d="M 126 160 L 126 348"
                  fill="none"
                  stroke="#4338CA"
                  strokeWidth="1.25"
                  strokeDasharray="3 3"
                  markerEnd="url(#arrow-ai)"
                />
                <path
                  d="M 440 294 L 440 348"
                  fill="none"
                  stroke="#4338CA"
                  strokeWidth="1.25"
                  strokeDasharray="3 3"
                  markerEnd="url(#arrow-ai)"
                />
                <path
                  d="M 798 294 L 798 348"
                  fill="none"
                  stroke="#4338CA"
                  strokeWidth="1.25"
                  strokeDasharray="3 3"
                  markerEnd="url(#arrow-ai)"
                />
                <text x="134" y="340" className="fill-indigo-700 text-[9px] font-mono">
                  Read-only telemetry
                </text>
              </g>
            )}
          </svg>

          {/* Compact Legend Row (clean text, zero pills) */}
          <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-6 text-xs text-slate-600">
            <span className="font-mono">
              <span className="text-amber-600 font-bold">—▸</span> Thermal Heat Flow (kW_th)
            </span>
            <span className="font-mono">
              <span className="text-sky-600 font-bold">—▸</span> Surplus PV Electrical (kW_e)
            </span>
            <span className="font-mono">
              <span className="text-slate-600 font-bold">--▸</span> Biomass Mass Stream (kg)
            </span>
            <span className="font-mono">
              <span className="text-indigo-700 font-bold">┄▸</span> Read-Only AI Telemetry
            </span>
            <span className="font-mono">
              <span className="text-rose-600 font-bold">┄</span> Hardwired PLC Safety Boundary
            </span>
          </div>
        </div>
      </div>

      {/* Right Subsystem Boundary Inspector (4 columns on lg) */}
      <div className="lg:col-span-4 bg-white border border-slate-200 rounded-lg p-5 space-y-5">
        <div className="border-b border-slate-200 pb-4">
          <div className="text-xs font-mono text-slate-500">
            {activeSpec.category} · {activeSpec.controlAuthority}
          </div>
          <h3 className="text-lg font-semibold text-slate-900 mt-1">
            {activeSpec.title}
          </h3>
        </div>

        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Boundary Inputs
          </h4>
          <ul className="space-y-1.5 text-sm text-slate-700">
            {activeSpec.inputs.map((item) => (
              <li key={item} className="flex items-start gap-2">
                <span className="text-slate-400 font-mono text-xs mt-0.5">→</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="pt-3 border-t border-slate-100">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Boundary Outputs
          </h4>
          <ul className="space-y-1.5 text-sm text-slate-700">
            {activeSpec.outputs.map((item) => (
              <li key={item} className="flex items-start gap-2">
                <span className="text-sky-700 font-mono text-xs mt-0.5">←</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="pt-3 border-t border-slate-100">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Governing Physics &amp; Rules
          </h4>
          <div className="space-y-2">
            {activeSpec.governingEquations.map((eq) => (
              <div
                key={eq}
                className="bg-slate-50 border border-slate-200 rounded px-3 py-2 text-xs font-mono text-slate-800 break-words"
              >
                {eq}
              </div>
            ))}
          </div>
        </div>

        <div className="pt-3 border-t border-slate-100">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-rose-700 mb-2">
            PLC Hardwired Constraints
          </h4>
          <ul className="space-y-1.5 text-xs text-slate-700">
            {activeSpec.plcConstraints.map((rule) => (
              <li key={rule} className="flex items-start gap-2">
                <span className="text-rose-600 font-mono font-semibold">!</span>
                <span>{rule}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="pt-3 border-t border-slate-100">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-700 mb-1.5">
            AI Decision-Support Role
          </h4>
          <p className="text-xs text-slate-700 leading-relaxed">{activeSpec.aiRole}</p>
        </div>

        <div className="pt-3 border-t border-slate-100">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-700 mb-1.5">
            Open Parameters for Phase 2–3
          </h4>
          <ul className="space-y-1 text-xs text-slate-600">
            {activeSpec.missingParameters.map((mp) => (
              <li key={mp}>• {mp}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};
