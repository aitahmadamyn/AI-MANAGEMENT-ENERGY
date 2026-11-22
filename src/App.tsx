import React, { useState } from 'react';
import { PlantSchematic } from './components/PlantSchematic';
import { DataDictionaryView } from './components/DataDictionaryView';
import { Phase2DataView } from './components/Phase2DataView';
import { Phase3ThermalView } from './components/Phase3ThermalView';
import { Phase4EdaView } from './components/Phase4EdaView';
import { Phase5MlView } from './components/Phase5MlView';
import { Phase6EnergyView } from './components/Phase6EnergyView';
import { Phase7DashboardView } from './components/Phase7DashboardView';
import { PhysicsCheckView } from './components/PhysicsCheckView';
import { ProjectFilesView } from './components/ProjectFilesView';
import {
  DEFAULT_DESIGN_ASSUMPTIONS,
  MISSING_PLANT_INFO,
  SUBSYSTEM_BOUNDARIES,
  VARIABLE_SCHEMA,
} from './data/phase1Data';
import phase2RealStats from './data/phase2RealStats.json';
import phase3SimStats from './data/phase3SimStats.json';
import phase4EdaStats from './data/phase4EdaStats.json';
import phase5MlStats from './data/phase5MlStats.json';
import phase6EnergyStats from './data/phase6EnergyStats.json';
import phase7DashboardStats from './data/phase7DashboardStats.json';

type WorkbenchTab = 'boundaries' | 'data_eda' | 'sim_ml' | 'dispatch_ui' | 'files';
type BoundarySubView = 'schematic' | 'dictionary' | 'calculator';
type DataEdaSubView = 'solar_weather' | 'eda';
type SimMlSubView = 'thermal_sim' | 'ml_models';
type DispatchUiSubView = 'dispatch_ai' | 'dashboard_ui';

const NAV_ITEMS: { id: WorkbenchTab; label: string }[] = [
  { id: 'boundaries', label: 'Boundaries' },
  { id: 'data_eda', label: 'Data & EDA' },
  { id: 'sim_ml', label: 'Sim & ML' },
  { id: 'dispatch_ui', label: 'Dispatch & UI' },
  { id: 'files', label: 'Project Files' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<WorkbenchTab>('dispatch_ui');
  const [boundarySubView, setBoundarySubView] = useState<BoundarySubView>('schematic');
  const [dataEdaSubView, setDataEdaSubView] = useState<DataEdaSubView>('eda');
  const [simMlSubView, setSimMlSubView] = useState<SimMlSubView>('ml_models');
  const [dispatchSubView, setDispatchSubView] = useState<DispatchUiSubView>('dashboard_ui');
  const [exportNotice, setExportNotice] = useState(false);

  const selectedSolar =
    phase5MlStats.solar_model.models.find((m) => m.selected) ??
    phase5MlStats.solar_model.models[phase5MlStats.solar_model.models.length - 1];
  const selectedDryer =
    phase5MlStats.dryer_model.models.find((m) => m.selected) ??
    phase5MlStats.dryer_model.models[phase5MlStats.dryer_model.models.length - 1];

  const handleExportSpec = () => {
    const specPayload = {
      project: 'EcoFarm Circular — AI-Based Intelligent Energy Management System',
      completedPhases: [
        'Phase 1: System Boundaries',
        'Phase 2: Real Solar & Weather Data',
        'Phase 3: Thermal Simulation & Validation',
        'Phase 4: Exploratory Data Analysis (EDA)',
        'Phase 5: Machine Learning Model Training & Comparison',
        'Phase 6: Intelligent Energy Management & Dispatch Supervisor',
        'Phase 7: Interactive Decision-Support Dashboard (Streamlit)',
      ],
      generatedAtUtc: new Date().toISOString(),
      disclaimer:
        'Decision-support simulation prototype only. PLC safety limits remain hardwired/configurable and separate from AI commands; NOT certified as an industrial safety system.',
      designAssumptions: DEFAULT_DESIGN_ASSUMPTIONS,
      subsystemBoundaries: SUBSYSTEM_BOUNDARIES,
      variableSchema: VARIABLE_SCHEMA,
      phase2QualityReport: phase2RealStats.qualityReport,
      phase3ValidationReport: phase3SimStats.report,
      phase4EdaSummary: {
        inspection: phase4EdaStats.inspection,
        correlations: phase4EdaStats.correlations.key_pairs,
        seasonalStats: phase4EdaStats.seasonal_stats,
      },
      phase5MlSummary: {
        solarSelected: phase5MlStats.solar_model.selected_model_name,
        solarTestMetrics: selectedSolar.test,
        dryerSelected: phase5MlStats.dryer_model.selected_model_name,
        dryerTestMetrics: selectedDryer.test,
      },
      phase6EnergySummary: phase6EnergyStats.aggregate_totals,
      phase7ValidationSummary: phase7DashboardStats.validation_summary,
      missingInformation: MISSING_PLANT_INFO,
    };

    const blob = new Blob([JSON.stringify(specPayload, null, 2)], {
      type: 'application/json;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'ecofarm_phase1_to_phase7_spec.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setExportNotice(true);
    setTimeout(() => setExportNotice(false), 2200);
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Bar Contract: 3 zones separated by gap-8 */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-[1440px] mx-auto px-6 h-14 flex items-center justify-between gap-8">
          {/* Zone 1: Single text element wordmark */}
          <button
            type="button"
            onClick={() => setActiveTab('dispatch_ui')}
            className="text-base font-bold tracking-tight text-slate-900 whitespace-nowrap shrink-0 cursor-pointer"
          >
            EcoFarm Circular
          </button>

          {/* Zone 2: 5 single-line navigation links */}
          <nav
            aria-label="Engineering Workbench Sections"
            className="flex items-center gap-6 overflow-x-auto"
          >
            {NAV_ITEMS.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`py-1 text-sm font-medium transition-colors whitespace-nowrap shrink-0 border-b-2 cursor-pointer ${
                    isActive
                      ? 'text-slate-900 border-sky-700'
                      : 'text-slate-600 border-transparent hover:text-slate-900'
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Zone 3: 1 primary action */}
          <div className="flex items-center shrink-0">
            <button
              type="button"
              onClick={handleExportSpec}
              className="px-4 py-2 text-xs font-medium text-white bg-slate-900 rounded hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
            >
              {exportNotice ? 'Exported Spec' : 'Export Phase Spec'}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto px-6 py-8 space-y-8">
        {/* Clean Editorial Phase Context Header */}
        <section className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 border-b border-slate-200 pb-6">
          <div className="max-w-3xl">
            <div className="text-xs font-mono text-slate-500">
              Phase 7 of 9 · Interactive Decision-Support Dashboard · 9 Streamlit Views &amp; Verified Exports
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 mt-1.5 text-balance">
              07. Streamlit Decision-Support Dashboard &amp; Verified Exports
            </h1>
            <p className="text-sm text-slate-600 mt-2 leading-relaxed max-w-2xl">
              Modular Streamlit interface (<span className="font-mono">EcoFarm_AI/dashboard/app.py</span>) wired directly to
              validated Phases 2–6 outputs, Colab notebook launcher, and verified CSV/ZIP archives under non-overridable PLC limits.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-6 shrink-0 border-t lg:border-t-0 pt-4 lg:pt-0 border-slate-200">
            <div>
              <div className="text-xs text-slate-500">Phase 7 QA Tests</div>
              <div className="text-xl font-mono font-semibold tabular-nums text-emerald-800 mt-0.5">
                {phase7DashboardStats.validation_summary.tests_passed}/{phase7DashboardStats.validation_summary.tests_total}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Artifacts Ready</div>
              <div className="text-xl font-mono font-semibold tabular-nums text-slate-900 mt-0.5">
                {phase7DashboardStats.validation_summary.artifacts_ready}/{phase7DashboardStats.validation_summary.artifacts_total}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Next Milestone</div>
              <div className="text-sm font-mono font-semibold text-sky-700 mt-1.5">
                Phase 8: Validation
              </div>
            </div>
          </div>
        </section>

        {/* Active Section */}
        <section aria-live="polite" className="space-y-6">
          {activeTab === 'boundaries' && (
            <>
              <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-200/70 rounded-md w-fit">
                <button
                  type="button"
                  onClick={() => setBoundarySubView('schematic')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    boundarySubView === 'schematic'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  System Schematic &amp; PLC Perimeter
                </button>
                <button
                  type="button"
                  onClick={() => setBoundarySubView('dictionary')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    boundarySubView === 'dictionary'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Data Dictionary (20 Variables)
                </button>
                <button
                  type="button"
                  onClick={() => setBoundarySubView('calculator')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    boundarySubView === 'calculator'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Batch Physics Sanity Calculator
                </button>
              </div>
              {boundarySubView === 'schematic' && <PlantSchematic />}
              {boundarySubView === 'dictionary' && <DataDictionaryView />}
              {boundarySubView === 'calculator' && <PhysicsCheckView />}
            </>
          )}

          {activeTab === 'data_eda' && (
            <>
              <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-200/70 rounded-md w-fit">
                <button
                  type="button"
                  onClick={() => setDataEdaSubView('solar_weather')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    dataEdaSubView === 'solar_weather'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Phase 2 · Solar &amp; Weather (Settat 2020–2023)
                </button>
                <button
                  type="button"
                  onClick={() => setDataEdaSubView('eda')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    dataEdaSubView === 'eda'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Phase 4 · Exploratory Data Analysis (EDA)
                </button>
              </div>
              {dataEdaSubView === 'solar_weather' && <Phase2DataView />}
              {dataEdaSubView === 'eda' && <Phase4EdaView />}
            </>
          )}

          {activeTab === 'sim_ml' && (
            <>
              <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-200/70 rounded-md w-fit">
                <button
                  type="button"
                  onClick={() => setSimMlSubView('thermal_sim')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    simMlSubView === 'thermal_sim'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Phase 3 · Thermal Simulation &amp; Validation
                </button>
                <button
                  type="button"
                  onClick={() => setSimMlSubView('ml_models')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    simMlSubView === 'ml_models'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Phase 5 · ML Model Training &amp; Comparison
                </button>
              </div>
              {simMlSubView === 'thermal_sim' && <Phase3ThermalView />}
              {simMlSubView === 'ml_models' && <Phase5MlView />}
            </>
          )}

          {activeTab === 'dispatch_ui' && (
            <>
              <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-200/70 rounded-md w-fit">
                <button
                  type="button"
                  onClick={() => setDispatchSubView('dashboard_ui')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    dispatchSubView === 'dashboard_ui'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Phase 7 · Streamlit Dashboard &amp; Exports
                </button>
                <button
                  type="button"
                  onClick={() => setDispatchSubView('dispatch_ai')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    dispatchSubView === 'dispatch_ai'
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Phase 6 · Intelligent Dispatch AI (7 Scenarios)
                </button>
              </div>
              {dispatchSubView === 'dashboard_ui' && <Phase7DashboardView />}
              {dispatchSubView === 'dispatch_ai' && <Phase6EnergyView />}
            </>
          )}
          {activeTab === 'files' && <ProjectFilesView />}
        </section>
      </main>

      {/* Quiet Engineering Footer */}
      <footer className="border-t border-slate-200 bg-white mt-12">
        <div className="max-w-[1440px] mx-auto px-6 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-slate-500">
          <span>
            EcoFarm Circular · Biomass Valorization AI Energy Management · Global Sustainability Challenge 2026–2027
          </span>
          <span className="font-mono">
            Phase 7 Complete (9/9 QA Checks) · Ready for Phase 8 (Scenario Validation &amp; Stress Testing)
          </span>
        </div>
      </footer>
    </div>
  );
}
