import React, { useMemo, useState } from 'react';
import { DEFAULT_DESIGN_ASSUMPTIONS, DesignAssumptions } from '../data/phase1Data';

export const PhysicsCheckView: React.FC = () => {
  const [params, setParams] = useState<DesignAssumptions>(DEFAULT_DESIGN_ASSUMPTIONS);

  const updateParam = (key: keyof DesignAssumptions, value: number) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  };

  const resetDefaults = () => {
    setParams(DEFAULT_DESIGN_ASSUMPTIONS);
  };

  const results = useMemo(() => {
    // 1. Sand Thermal Energy Storage Boundary (Q = m * Cp * dT)
    const safeTMax = Math.max(params.sandTMaxC, params.sandTMinC + 10);
    const deltaTSand = safeTMax - params.sandTMinC;
    const sandCapacityKwh =
      (params.sandMassKg * params.sandCpKjKgK * deltaTSand) / 3600;
    const safetyMarginToPlcTripC = params.sandPlcTripC - safeTMax;

    // 2. Biomass Dryer Batch Thermodynamic Balance
    const xi = params.initialMoisturePct / 100;
    const xf = Math.min(params.targetMoisturePct / 100, xi - 0.01);
    const drySolidMassKg = params.biomassBatchKg * (1 - xi);
    const waterEvaporatedKg = params.biomassBatchKg * ((xi - xf) / (1 - xf));
    const initialWaterMassKg = params.biomassBatchKg * xi;

    const deltaTBiomass = Math.max(5, params.dryerTargetTempC - params.ambientTempC);
    const hfgWaterKjKg = 2257.0;
    const cpWater = 4.186;
    const cpDryBiomass = 1.45;

    const qLatentKwh = (waterEvaporatedKg * hfgWaterKjKg) / 3600;
    const qSensibleBiomassKwh = (drySolidMassKg * cpDryBiomass * deltaTBiomass) / 3600;
    const qSensibleWaterKwh = (initialWaterMassKg * cpWater * deltaTBiomass) / 3600;
    const qUsefulBatchKwh = qLatentKwh + qSensibleBiomassKwh + qSensibleWaterKwh;
    const qTotalDemandBatchKwh = qUsefulBatchKwh / params.dryerEfficiency;
    const qThermalLossesKwh = qTotalDemandBatchKwh - qUsefulBatchKwh;

    // 3. Storage Autonomy Ratio & Clear-sky PV Peak Sanity Check
    const batchesPerFullStorage =
      qTotalDemandBatchKwh > 0 ? sandCapacityKwh / qTotalDemandBatchKwh : 0;
    const peakClearSkyPvKw = params.pvCapacityKwp * (1 - params.pvLossFraction);

    const latentSharePct =
      qTotalDemandBatchKwh > 0 ? (qLatentKwh / qTotalDemandBatchKwh) * 100 : 0;
    const sensibleSharePct =
      qTotalDemandBatchKwh > 0
        ? ((qSensibleBiomassKwh + qSensibleWaterKwh) / qTotalDemandBatchKwh) * 100
        : 0;
    const lossSharePct =
      qTotalDemandBatchKwh > 0 ? (qThermalLossesKwh / qTotalDemandBatchKwh) * 100 : 0;

    return {
      deltaTSand,
      sandCapacityKwh,
      safetyMarginToPlcTripC,
      drySolidMassKg,
      waterEvaporatedKg,
      qLatentKwh,
      qSensibleKwh: qSensibleBiomassKwh + qSensibleWaterKwh,
      qThermalLossesKwh,
      qTotalDemandBatchKwh,
      batchesPerFullStorage,
      peakClearSkyPvKw,
      latentSharePct,
      sensibleSharePct,
      lossSharePct,
    };
  }, [params]);

  return (
    <div className="space-y-6">
      {/* Scientific Disclaimer Banner */}
      <div className="bg-amber-50/70 border border-amber-200 rounded-lg px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="text-xs text-amber-900">
          <span className="font-semibold">Phase 1 Design Boundary Sanity Check:</span>{' '}
          These numbers verify thermodynamic consistency using baseline engineering assumptions. They are{' '}
          <span className="underline">not</span> experimental plant measurements.
        </div>
        <button
          type="button"
          onClick={resetDefaults}
          className="px-3 py-1.5 text-xs font-medium text-amber-900 bg-white border border-amber-300 rounded hover:bg-amber-100/60 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
        >
          Reset Phase 1 Defaults
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Parameter Column (5 columns) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-lg p-5 space-y-5">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Baseline Plant Design Assumptions
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Synchronized with EcoFarm_AI/src/config.py (PlantDesignAssumptions)
            </p>
          </div>

          {/* Sand Storage Controls */}
          <div className="pt-3 border-t border-slate-100 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Sand Thermal Storage (Model 3 Boundary)
            </h3>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <label htmlFor="sand-mass" className="text-slate-700 font-medium">
                  Sand Mass (m_sand)
                </label>
                <span className="font-mono tabular-nums text-slate-900">
                  {params.sandMassKg} kg
                </span>
              </div>
              <input
                id="sand-mass"
                type="range"
                min={1000}
                max={12000}
                step={250}
                value={params.sandMassKg}
                onChange={(e) => updateParam('sandMassKg', Number(e.target.value))}
                className="w-full accent-sky-700 cursor-pointer"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="sand-tmin" className="block text-xs text-slate-700 mb-1">
                  T_min Operating (°C)
                </label>
                <input
                  id="sand-tmin"
                  type="number"
                  min={60}
                  max={250}
                  value={params.sandTMinC}
                  onChange={(e) => updateParam('sandTMinC', Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-xs font-mono tabular-nums border border-slate-300 rounded bg-white"
                />
              </div>
              <div>
                <label htmlFor="sand-tmax" className="block text-xs text-slate-700 mb-1">
                  T_max AI Target (°C)
                </label>
                <input
                  id="sand-tmax"
                  type="number"
                  min={260}
                  max={580}
                  value={params.sandTMaxC}
                  onChange={(e) => updateParam('sandTMaxC', Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-xs font-mono tabular-nums border border-slate-300 rounded bg-white"
                />
              </div>
            </div>
          </div>

          {/* Biomass Dryer Controls */}
          <div className="pt-3 border-t border-slate-100 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Biomass Dryer Batch (Model 2 Boundary)
            </h3>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <label htmlFor="batch-mass" className="text-slate-700 font-medium">
                  Wet Biomass Batch Mass
                </label>
                <span className="font-mono tabular-nums text-slate-900">
                  {params.biomassBatchKg} kg
                </span>
              </div>
              <input
                id="batch-mass"
                type="range"
                min={50}
                max={1000}
                step={25}
                value={params.biomassBatchKg}
                onChange={(e) => updateParam('biomassBatchKg', Number(e.target.value))}
                className="w-full accent-sky-700 cursor-pointer"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="mc-init" className="block text-xs text-slate-700 mb-1">
                  Initial Moisture (%)
                </label>
                <input
                  id="mc-init"
                  type="number"
                  min={20}
                  max={70}
                  value={params.initialMoisturePct}
                  onChange={(e) => updateParam('initialMoisturePct', Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-xs font-mono tabular-nums border border-slate-300 rounded bg-white"
                />
              </div>
              <div>
                <label htmlFor="mc-target" className="block text-xs text-slate-700 mb-1">
                  Target Moisture (%)
                </label>
                <input
                  id="mc-target"
                  type="number"
                  min={5}
                  max={18}
                  value={params.targetMoisturePct}
                  onChange={(e) => updateParam('targetMoisturePct', Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-xs font-mono tabular-nums border border-slate-300 rounded bg-white"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <label htmlFor="dryer-eff" className="text-slate-700 font-medium">
                  Dryer Thermal Efficiency (η_dryer)
                </label>
                <span className="font-mono tabular-nums text-slate-900">
                  {(params.dryerEfficiency * 100).toFixed(0)} %
                </span>
              </div>
              <input
                id="dryer-eff"
                type="range"
                min={0.45}
                max={0.85}
                step={0.01}
                value={params.dryerEfficiency}
                onChange={(e) => updateParam('dryerEfficiency', Number(e.target.value))}
                className="w-full accent-sky-700 cursor-pointer"
              />
            </div>
          </div>

          {/* PV Array Control */}
          <div className="pt-3 border-t border-slate-100 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Photovoltaic Array (Model 1 Boundary)
            </h3>
            <div>
              <div className="flex justify-between text-xs mb-1">
                <label htmlFor="pv-kwp" className="text-slate-700 font-medium">
                  Nominal PV Capacity
                </label>
                <span className="font-mono tabular-nums text-slate-900">
                  {params.pvCapacityKwp} kWp
                </span>
              </div>
              <input
                id="pv-kwp"
                type="range"
                min={5}
                max={50}
                step={1}
                value={params.pvCapacityKwp}
                onChange={(e) => updateParam('pvCapacityKwp', Number(e.target.value))}
                className="w-full accent-sky-700 cursor-pointer"
              />
            </div>
          </div>
        </div>

        {/* Right Thermodynamic Output Stage (7 columns) */}
        <div className="lg:col-span-7 space-y-5">
          {/* 4-column Boundary Readout Strip */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <div className="text-xs font-medium text-slate-500">
                Usable Sand Storage Capacity
              </div>
              <div className="mt-1.5 flex items-baseline">
                <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
                  {results.sandCapacityKwh.toFixed(1)}
                </span>
                <span className="text-xs font-mono text-slate-500 ml-1.5">kWh</span>
              </div>
              <div className="mt-1.5 text-xs font-mono text-slate-500">
                ΔT = {results.deltaTSand.toFixed(0)} °C · PLC margin: {results.safetyMarginToPlcTripC.toFixed(0)} °C
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <div className="text-xs font-medium text-slate-500">
                Dryer Batch Thermal Demand
              </div>
              <div className="mt-1.5 flex items-baseline">
                <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
                  {results.qTotalDemandBatchKwh.toFixed(1)}
                </span>
                <span className="text-xs font-mono text-slate-500 ml-1.5">kWh / batch</span>
              </div>
              <div className="mt-1.5 text-xs font-mono text-slate-500">
                Evaporates {results.waterEvaporatedKg.toFixed(1)} kg water → {results.drySolidMassKg.toFixed(1)} kg dry solid
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <div className="text-xs font-medium text-slate-500">
                Storage-to-Dryer Autonomy Ratio
              </div>
              <div className="mt-1.5 flex items-baseline">
                <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
                  {results.batchesPerFullStorage.toFixed(2)}
                </span>
                <span className="text-xs font-mono text-slate-500 ml-1.5">batches / charge</span>
              </div>
              <div className="mt-1.5 text-xs text-slate-500">
                Full sand charge covers ~{results.batchesPerFullStorage.toFixed(1)} drying cycles
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-4">
              <div className="text-xs font-medium text-slate-500">
                Clear-Sky PV Peak Reference
              </div>
              <div className="mt-1.5 flex items-baseline">
                <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
                  {results.peakClearSkyPvKw.toFixed(1)}
                </span>
                <span className="text-xs font-mono text-slate-500 ml-1.5">kW AC</span>
              </div>
              <div className="mt-1.5 text-xs text-slate-500">
                At 1,000 W/m² after {(params.pvLossFraction * 100).toFixed(0)}% system loss
              </div>
            </div>
          </div>

          {/* Energy Breakdown Chart */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Biomass Dryer Thermal Load Breakdown (Single Batch)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Physical decomposition required before generating Phase 3 synthetic training data
                </p>
              </div>
              <span className="text-xs font-mono tabular-nums text-slate-700">
                Total: {results.qTotalDemandBatchKwh.toFixed(2)} kWh
              </span>
            </div>

            {/* Stacked Horizontal SVG Bar */}
            <div className="w-full h-8 bg-slate-100 rounded overflow-hidden flex border border-slate-200">
              <div
                style={{ width: `${results.latentSharePct}%` }}
                className="bg-sky-700 h-full transition-all"
                title={`Latent heat of evaporation: ${results.qLatentKwh.toFixed(2)} kWh`}
              />
              <div
                style={{ width: `${results.sensibleSharePct}%` }}
                className="bg-amber-500 h-full transition-all"
                title={`Sensible heating: ${results.qSensibleKwh.toFixed(2)} kWh`}
              />
              <div
                style={{ width: `${results.lossSharePct}%` }}
                className="bg-slate-400 h-full transition-all"
                title={`Exhaust & shell losses: ${results.qThermalLossesKwh.toFixed(2)} kWh`}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs pt-1">
              <div className="border border-slate-200 rounded p-3 bg-slate-50/50">
                <div className="text-sky-800 font-medium">
                  ■ Latent Evaporation Heat
                </div>
                <div className="font-mono tabular-nums text-slate-900 font-semibold mt-1">
                  {results.qLatentKwh.toFixed(2)} kWh ({results.latentSharePct.toFixed(1)}%)
                </div>
                <div className="text-slate-500 mt-0.5 font-mono text-[11px]">
                  m_w · 2257 kJ/kg
                </div>
              </div>

              <div className="border border-slate-200 rounded p-3 bg-slate-50/50">
                <div className="text-amber-800 font-medium">
                  ■ Sensible Biomass + Water
                </div>
                <div className="font-mono tabular-nums text-slate-900 font-semibold mt-1">
                  {results.qSensibleKwh.toFixed(2)} kWh ({results.sensibleSharePct.toFixed(1)}%)
                </div>
                <div className="text-slate-500 mt-0.5 font-mono text-[11px]">
                  (m_dry·Cp_b + m_w0·Cp_w)·ΔT
                </div>
              </div>

              <div className="border border-slate-200 rounded p-3 bg-slate-50/50">
                <div className="text-slate-700 font-medium">
                  ■ Dryer Efficiency Losses
                </div>
                <div className="font-mono tabular-nums text-slate-900 font-semibold mt-1">
                  {results.qThermalLossesKwh.toFixed(2)} kWh ({results.lossSharePct.toFixed(1)}%)
                </div>
                <div className="text-slate-500 mt-0.5 font-mono text-[11px]">
                  Q_useful · (1/η - 1)
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
