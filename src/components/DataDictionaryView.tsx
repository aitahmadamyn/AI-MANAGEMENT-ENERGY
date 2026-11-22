import React, { useMemo, useState } from 'react';
import {
  DataProvenance,
  PROVENANCE_LABELS,
  SUBSYSTEM_LABELS,
  SubsystemId,
  VARIABLE_SCHEMA,
} from '../data/phase1Data';

export const DataDictionaryView: React.FC = () => {
  const [subsystemFilter, setSubsystemFilter] = useState<'all' | SubsystemId>('all');
  const [provenanceFilter, setProvenanceFilter] = useState<'all' | DataProvenance>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredVariables = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return VARIABLE_SCHEMA.filter((v) => {
      if (subsystemFilter !== 'all' && v.subsystem !== subsystemFilter) return false;
      if (provenanceFilter !== 'all' && v.provenance !== provenanceFilter) return false;
      if (
        q &&
        !v.name.toLowerCase().includes(q) &&
        !v.label.toLowerCase().includes(q) &&
        !v.description.toLowerCase().includes(q) &&
        !v.mlRole.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [subsystemFilter, provenanceFilter, searchQuery]);

  const provenanceCounts = useMemo(() => {
    const counts: Record<DataProvenance, number> = {
      measured_external: 0,
      calculated: 0,
      simulated: 0,
      predicted_ml: 0,
    };
    VARIABLE_SCHEMA.forEach((v) => {
      counts[v.provenance] += 1;
    });
    return counts;
  }, []);

  return (
    <div className="space-y-6">
      {/* Provenance Summary Strip (flat hairline cells, zero pills) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Measured (External Archives)
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {provenanceCounts.measured_external}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">variables</span>
          </div>
          <div className="mt-1 text-xs text-emerald-700 font-medium">
            ● PVGIS &amp; Meteorological Reanalysis
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Calculated (Deterministic Physics)
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {provenanceCounts.calculated}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">variables</span>
          </div>
          <div className="mt-1 text-xs text-sky-700 font-medium">
            ◆ Energy Balance &amp; Drying Identities
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Simulated (Thermal Subsystem)
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              {provenanceCounts.simulated}
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">variables</span>
          </div>
          <div className="mt-1 text-xs text-amber-700 font-medium">
            ▲ Clearly Tagged — Never Real Telemetry
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="text-xs font-medium text-slate-500">
            Timebase &amp; Split Standard
          </div>
          <div className="mt-1.5 flex items-baseline">
            <span className="text-2xl font-mono font-semibold tabular-nums text-slate-900">
              60
            </span>
            <span className="text-xs font-mono text-slate-500 ml-1.5">min (UTC)</span>
          </div>
          <div className="mt-1 text-xs text-slate-600">
            Chronological Train / Val / Test Only
          </div>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Subsystem segmented buttons */}
          <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-100 rounded-md">
            <button
              type="button"
              onClick={() => setSubsystemFilter('all')}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                subsystemFilter === 'all'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              All Subsystems ({VARIABLE_SCHEMA.length})
            </button>
            {(Object.keys(SUBSYSTEM_LABELS) as SubsystemId[]).map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => setSubsystemFilter(id)}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                  subsystemFilter === id
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {SUBSYSTEM_LABELS[id]}
              </button>
            ))}
          </div>

          {/* Search box */}
          <div className="flex items-center gap-3">
            <label htmlFor="schema-search" className="sr-only">
              Filter variables
            </label>
            <input
              id="schema-search"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search variable, unit, or ML role..."
              className="w-full sm:w-72 px-3 py-1.5 text-xs border border-slate-300 rounded bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-sky-600"
            />
          </div>
        </div>

        {/* Provenance filter row */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100">
          <span className="text-xs font-medium text-slate-500 mr-1">Provenance:</span>
          <button
            type="button"
            onClick={() => setProvenanceFilter('all')}
            className={`px-2.5 py-1 text-xs font-medium rounded border transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
              provenanceFilter === 'all'
                ? 'bg-slate-900 text-white border-slate-900'
                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
            }`}
          >
            All Types
          </button>
          {(['measured_external', 'calculated', 'simulated'] as DataProvenance[]).map((prov) => (
            <button
              key={prov}
              type="button"
              onClick={() => setProvenanceFilter(prov)}
              className={`px-2.5 py-1 text-xs font-medium rounded border transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                provenanceFilter === prov
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
              }`}
            >
              {PROVENANCE_LABELS[prov].glyph} {PROVENANCE_LABELS[prov].label}
            </button>
          ))}
        </div>
      </div>

      {/* Data Dictionary Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600">
                <th className="py-3 px-4">Variable Identifier</th>
                <th className="py-3 px-4">Unit</th>
                <th className="py-3 px-4">Subsystem</th>
                <th className="py-3 px-4">Data Provenance</th>
                <th className="py-3 px-4 text-right">Valid Range</th>
                <th className="py-3 px-4">Source &amp; ML Role</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {filteredVariables.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 px-4 text-center text-xs text-slate-500">
                    No variables match the active filter criteria.
                  </td>
                </tr>
              ) : (
                filteredVariables.map((v) => {
                  const prov = PROVENANCE_LABELS[v.provenance];
                  return (
                    <tr key={v.name} className="hover:bg-slate-50/70 transition-colors align-top">
                      <td className="py-3 px-4">
                        <div className="font-mono text-xs font-semibold text-slate-900">
                          {v.name}
                        </div>
                        <div className="text-xs text-slate-600 mt-0.5">{v.label}</div>
                        <div className="text-xs text-slate-500 mt-1 max-w-md">
                          {v.description}
                        </div>
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-slate-700 whitespace-nowrap">
                        {v.unit}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-700 whitespace-nowrap">
                        {SUBSYSTEM_LABELS[v.subsystem]}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className={`text-xs font-medium ${prov.tone}`}>
                          {prov.glyph} {prov.label}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-xs tabular-nums text-slate-700 text-right whitespace-nowrap">
                        {v.minValid} .. {v.maxValid}
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-700">
                        <div className="font-medium text-slate-800">{v.mlRole}</div>
                        <div className="text-slate-500 mt-0.5">{v.source}</div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
