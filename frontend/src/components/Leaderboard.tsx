import React, { useState } from 'react';
import { MagnifyingGlass, CaretRight } from '@phosphor-icons/react';
import { RISK_COLORS } from '../api';
import type { MapStation, UnmonitoredLocation } from '../api';

interface LeaderboardProps {
  stations: MapStation[];
  unmonitored: UnmonitoredLocation[];
  onSelectStation?: (station: MapStation) => void;
}

export const Leaderboard: React.FC<LeaderboardProps> = ({ stations, unmonitored, onSelectStation }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const q = searchTerm.toLowerCase().trim();

  const filtered = stations
    .filter((s) => !q || (s.city_name || '').toLowerCase().includes(q) || s.location_name.toLowerCase().includes(q) || s.country_name.toLowerCase().includes(q) || s.parameter_name.toLowerCase().includes(q))
    .slice(0, 10);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start mb-12">
      {/* Risk Leaderboard */}
      <div className="lg:col-span-8 minimal-card p-6 md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-2.5">
            <span className="w-2 h-2 rounded-full bg-[#381932]" />
            <h3 className="font-luxury text-xl md:text-2xl text-[#381932] font-bold tracking-tight">Risk Leaderboard</h3>
          </div>
          <div className="relative">
            <MagnifyingGlass size={14} className="absolute left-3.5 top-2.5 text-[#84657E]" />
            <input
              type="text"
              placeholder="Search city or country..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-4 py-1.5 text-xs bg-white border border-[#381932]/15 text-[#381932] placeholder:text-[#84657E] rounded-full focus:border-[#381932] focus:ring-1 focus:ring-[#381932]/10 outline-none w-60 font-medium shadow-2xs transition-all"
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
              {!filtered.length ? (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-xs text-[#84657E] font-mono">
                    No stations match the search query.
                  </td>
                </tr>
              ) : (
                filtered.map((s, idx) => (
                  <tr
                    key={s.location_key}
                    onClick={() => onSelectStation?.(s)}
                    tabIndex={0}
                    role="button"
                    className="cursor-pointer group focus:outline-none focus:bg-[#FDF9F5]"
                  >
                    <td className="font-mono text-xs font-semibold">
                      {idx === 0 ? (
                        <span className="w-5 h-5 rounded-full bg-[#381932] text-[#E0BA70] font-bold flex items-center justify-center text-[10px] shadow-2xs">
                          1
                        </span>
                      ) : (
                        <span className="text-[#84657E] font-medium">{idx + 1}</span>
                      )}
                    </td>
                    <td>
                      <div className="font-semibold text-sm text-[#381932] group-hover:text-[#583351] transition-colors">
                        {s.location_name}
                      </div>
                      <div className="text-xs text-[#84657E] font-mono">{s.country_name}</div>
                    </td>
                    <td>
                      <span className="text-[11px] font-mono font-medium bg-[#FBF4EC] text-[#583351] px-2.5 py-0.5 rounded-full border border-[#381932]/10">
                        {s.parameter_name.toUpperCase()}
                      </span>
                    </td>
                    <td className="tabular-nums font-luxury font-bold text-base text-[#381932]">
                      {Math.round(s.avg_aqi)}
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-2 text-xs">
                        <span
                          className="w-2 h-2 rounded-full ring-1 ring-black/10"
                          style={{ backgroundColor: RISK_COLORS[s.risk_tier] || '#381932' }}
                        />
                        <span className="font-medium text-xs text-[#381932]">{s.risk_tier}</span>
                      </span>
                    </td>
                    <td>
                      <CaretRight
                        size={13}
                        className="text-[#84657E] group-hover:text-[#381932] group-hover:translate-x-0.5 transition-transform"
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stream Diagnostics */}
      <div className="lg:col-span-4 minimal-card p-6 md:p-8">
        <div className="mb-4 pb-4 border-b border-[#381932]/10">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-amber-600" />
              <h3 className="font-luxury text-xl text-[#381932] font-bold tracking-tight">Stream Diagnostics</h3>
            </div>
            <span className="text-[10px] font-mono text-amber-900 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200 uppercase tracking-wider font-semibold">
              {unmonitored.length} Offline
            </span>
          </div>
          <p className="text-xs text-[#84657E] mt-1.5 leading-relaxed">
            Stations in directory with no recent upstream OpenAQ telemetry feeds.
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
              {!unmonitored.length ? (
                <tr>
                  <td colSpan={2} className="text-center py-10 text-xs text-[#84657E]">
                    All configured stations actively streaming data.
                  </td>
                </tr>
              ) : (
                unmonitored.slice(0, 25).map((u, idx) => (
                  <tr key={`${u.location_name}-${idx}`}>
                    <td>
                      <div className="font-medium text-xs text-[#381932]">{u.location_name}</div>
                      <div className="text-[10px] font-mono text-[#84657E]">{u.country_name || u.country_code}</div>
                    </td>
                    <td>
                      <span className="text-[10px] font-mono text-amber-900 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200 font-medium whitespace-nowrap">
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
