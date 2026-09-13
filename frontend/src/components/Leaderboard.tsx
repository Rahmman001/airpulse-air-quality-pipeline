import React, { useState } from 'react';
import { MagnifyingGlass, CaretRight } from '@phosphor-icons/react';
import { RISK_COLORS } from '../api';
import type { MapStation, UnmonitoredLocation } from '../api';

interface LeaderboardProps {
  stations: MapStation[];
  unmonitored: UnmonitoredLocation[];
  onSelectStation?: (station: MapStation) => void;
}

export const Leaderboard: React.FC<LeaderboardProps> = ({
  stations,
  unmonitored,
  onSelectStation,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const q = searchTerm.toLowerCase().trim();
  const filteredStations = stations
    .filter((s) =>
      !q ||
      (s.city_name && s.city_name.toLowerCase().includes(q)) ||
      s.location_name.toLowerCase().includes(q) ||
      s.country_name.toLowerCase().includes(q) ||
      s.parameter_name.toLowerCase().includes(q)
    )
    .slice(0, 10);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start mb-12">
      {/* Top 10 Polluted Stations (8 cols) */}
      <div className="lg:col-span-8 minimal-card p-6 md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
          <div className="flex items-center gap-2.5">
            <span className="w-2 h-2 rounded-full bg-slate-900" />
            <h3 className="font-display text-xl text-slate-950 font-bold tracking-tight">
              Risk Leaderboard
            </h3>
          </div>
          <div className="relative">
            <MagnifyingGlass size={14} className="absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search city or country..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400 rounded-full focus:border-slate-800 focus:ring-1 focus:ring-slate-800/10 outline-none w-56 transition-all font-medium shadow-2xs"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 45 }}>#</th>
                <th>City / Station</th>
                <th>Parameter</th>
                <th>City AQI</th>
                <th>Risk Tier</th>
                <th style={{ width: 30 }}></th>
              </tr>
            </thead>
            <tbody>
              {filteredStations.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-xs text-slate-500 font-mono">
                    No stations match the search query.
                  </td>
                </tr>
              ) : (
                filteredStations.map((s, idx) => {
                  const color = RISK_COLORS[s.risk_tier] || '#0F172A';
                  const isTop = idx === 0;
                  return (
                    <tr
                      key={s.location_key}
                      onClick={() => onSelectStation && onSelectStation(s)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          onSelectStation && onSelectStation(s);
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      className="cursor-pointer group focus:outline-none focus:bg-slate-50"
                    >
                      <td className="font-mono text-xs font-semibold">
                        {isTop ? (
                          <span className="w-5 h-5 rounded-full bg-slate-950 text-white font-bold flex items-center justify-center text-[10px] shadow-2xs">
                            1
                          </span>
                        ) : (
                          <span className="text-slate-400 font-medium">{idx + 1}</span>
                        )}
                      </td>
                      <td>
                        <div className="font-semibold text-sm text-slate-900 group-hover:text-black group-hover:underline transition-colors">{s.location_name}</div>
                        <div className="text-xs text-slate-500 font-mono">{s.country_name}</div>
                      </td>
                      <td>
                        <span className="text-[11px] font-mono font-medium bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                          {s.parameter_name.toUpperCase()}
                        </span>
                      </td>
                      <td className="tabular-nums font-mono font-bold text-sm text-slate-950">
                        {Math.round(s.avg_aqi)}
                      </td>
                      <td>
                        <span className="inline-flex items-center gap-2 text-xs">
                          <span className="w-2 h-2 rounded-full ring-1 ring-black/10" style={{ backgroundColor: color }} />
                          <span className="font-medium text-xs text-slate-800">{s.risk_tier}</span>
                        </span>
                      </td>
                      <td>
                        <CaretRight size={13} className="text-slate-400 group-hover:text-slate-900 group-hover:translate-x-0.5 transition-transform" />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ingestion Diagnostics (4 cols) */}
      <div className="lg:col-span-4 minimal-card p-6 md:p-8">
        <div className="mb-3 pb-3 border-b border-slate-200/80">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <h3 className="font-display text-xl text-slate-950 font-bold tracking-tight">
                Stream Diagnostics
              </h3>
            </div>
            <span className="text-[10px] font-mono text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 uppercase tracking-wider font-semibold">
              {unmonitored.length} Offline
            </span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Stations in directory with no recent upstream OpenAQ readings.
          </p>
        </div>

        <div className="overflow-x-auto max-h-[380px]">
          <table className="data-table">
            <thead>
              <tr>
                <th>Location</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {unmonitored.length === 0 ? (
                <tr>
                  <td colSpan={2} className="text-center py-8 text-xs text-slate-500">
                    All configured stations actively streaming data.
                  </td>
                </tr>
              ) : (
                unmonitored.slice(0, 25).map((u, idx) => (
                  <tr key={`${u.location_name}-${idx}`}>
                    <td>
                      <div className="font-medium text-xs text-slate-900">{u.location_name}</div>
                      <div className="text-[10px] font-mono text-slate-500">{u.country_name || u.country_code}</div>
                    </td>
                    <td>
                      <span className="text-[10px] font-mono text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 font-medium">
                        {u.data_status === 'No recent AQI data' ? 'Awaiting Feed' : (u.data_status || 'Awaiting Feed')}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
