import React, { useState, useEffect } from 'react';
import { TrendUp, WarningCircle, MapPin } from '@phosphor-icons/react';
import { api, RISK_COLORS } from '../api';
import type { LocationItem, Pollutant, TrendPoint } from '../api';
import { formatIsoTimestamp, getTzShortLabel } from '../timezone';
import { SearchableHubSelect } from './SearchableHubSelect';

interface CityTrendsProps {
  locations: LocationItem[];
  pollutants: Pollutant[];
  initialLocationKey?: string;
  initialPollutantKey?: string;
  timezone?: string;
}

const THRESHOLDS = [
  { aqi: 50, color: '#059669' },
  { aqi: 100, color: '#D97706' },
  { aqi: 150, color: '#EA580C' },
  { aqi: 200, color: '#DC2626' },
  { aqi: 300, color: '#991B1B' },
];

export const CityTrends: React.FC<CityTrendsProps> = ({
  locations,
  pollutants,
  initialLocationKey,
  initialPollutantKey,
  timezone = 'UTC',
}) => {
  const [selectedLoc, setSelectedLoc] = useState(initialLocationKey || locations[0]?.location_key || '');
  const [selectedPol, setSelectedPol] = useState(initialPollutantKey || 'pm25');
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<TrendPoint | null>(null);

  useEffect(() => {
    if (initialLocationKey) setSelectedLoc(initialLocationKey);
  }, [initialLocationKey]);

  useEffect(() => {
    if (initialPollutantKey) {
      const match = pollutants.find(
        (p) =>
          p.parameter_name?.toLowerCase() === initialPollutantKey.toLowerCase() ||
          p.pollutant_key.toLowerCase() === initialPollutantKey.toLowerCase()
      );
      if (match) {
        setSelectedPol(match.pollutant_key);
        return;
      }
    }
    const pm25 = pollutants.find((p) => p.parameter_name?.toLowerCase() === 'pm25')?.pollutant_key;
    if (pm25) setSelectedPol(pm25);
    else if (pollutants[0]) setSelectedPol(pollutants[0].pollutant_key);
  }, [initialPollutantKey, pollutants]);

  useEffect(() => {
    if (!selectedLoc || !selectedPol) return;
    let active = true;
    setHovered(null);
    setLoading(true);

    api.getTrends(selectedLoc, selectedPol)
      .then((data) => {
        if (!active) return;
        setTrends([...data].sort((a, b) => new Date(a.measured_at_utc).getTime() - new Date(b.measured_at_utc).getTime()));
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setTrends([]);
        setLoading(false);
      });

    return () => { active = false; };
  }, [selectedLoc, selectedPol]);

  const activeLoc = locations.find((l) => l.location_key === selectedLoc);
  const activePol = pollutants.find((p) => p.pollutant_key === selectedPol);

  // SVG Chart Dimensions
  const W = 900, H = 280, pad = { top: 25, right: 30, bottom: 35, left: 50 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;
  const maxAqi = Math.max(350, ...trends.map((t) => t.aqi || 0));

  const scaleY = (aqi: number) => pad.top + plotH - (aqi / maxAqi) * plotH;
  const scaleX = (i: number) => pad.left + (trends.length <= 1 ? plotW / 2 : (i / (trends.length - 1)) * plotW);

  const linePath = trends.map((p, i) => `${i ? 'L' : 'M'} ${scaleX(i)},${scaleY(p.aqi)}`).join(' ');
  const areaPath = linePath ? `${linePath} L ${scaleX(trends.length - 1)},${scaleY(0)} L ${scaleX(0)},${scaleY(0)} Z` : '';

  return (
    <div className="space-y-8 mb-12">
      {/* Control Bar */}
      <div className="minimal-card p-6 md:p-8 flex flex-wrap items-center justify-between gap-6 relative z-20">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-full bg-[#381932] text-[#FFF3E6] flex items-center justify-center shadow-xs">
            <TrendUp size={18} weight="bold" />
          </div>
          <div>
            <div className="text-[10px] font-mono text-[#84657E] uppercase tracking-wider font-bold">Temporal Analysis</div>
            <h2 className="font-luxury text-xl md:text-2xl text-[#381932] font-bold tracking-tight">Temporal Trends</h2>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <div className="w-64 sm:w-72">
            <SearchableHubSelect
              label="Geohub"
              icon={MapPin}
              val={selectedLoc}
              setVal={setSelectedLoc}
              locations={locations}
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-[11px] font-mono uppercase tracking-wider text-[#84657E] font-bold">Parameter</label>
            <select
              value={selectedPol}
              onChange={(e) => setSelectedPol(e.target.value)}
              className="text-xs bg-white border border-[#381932]/15 rounded-full px-4 py-2 outline-none font-semibold text-[#381932] shadow-2xs focus:border-[#381932] focus:ring-1 focus:ring-[#381932]/10 transition-all cursor-pointer"
            >
              {pollutants.map((p) => (
                <option key={p.pollutant_key} value={p.pollutant_key}>{p.pollutant_display_name || p.parameter_name.toUpperCase()}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Main Chart Area */}
      <div className="minimal-card p-6 md:p-8">
        <div className="flex flex-wrap items-baseline justify-between gap-4 mb-6 pb-4 border-b border-[#381932]/10">
          <div>
            <div className="text-xs font-mono uppercase tracking-wider text-[#84657E] font-bold mb-1">
              Active Sensor Vector
            </div>
            <h3 className="font-luxury text-2xl md:text-3xl text-[#381932] font-bold tracking-tight">
              {activeLoc?.location_name || 'Geohub'} : <span className="font-normal text-[#84657E]">{activePol?.pollutant_display_name || activePol?.parameter_name.toUpperCase()}</span>
            </h3>
          </div>

          {trends.length > 0 && (
            <div className="flex items-center gap-6 text-xs font-mono text-[#84657E] bg-[#FBF4EC] px-4 py-1.5 rounded-full border border-[#381932]/10">
              <div>Obs: <strong className="text-[#381932]">{trends.length}</strong></div>
              <div>Peak AQI: <strong className="text-[#381932]">{Math.max(...trends.map((t) => t.aqi))}</strong></div>
              <div>Current: <strong className="text-[#381932]">{trends[trends.length - 1]?.aqi}</strong></div>
            </div>
          )}
        </div>

        {loading ? (
          <div className="h-[280px] flex items-center justify-center text-xs font-mono text-[#84657E] tracking-widest uppercase">
            Parsing Telemetry Vector...
          </div>
        ) : !trends.length ? (
          <div className="h-[280px] flex flex-col items-center justify-center gap-2 text-[#84657E]">
            <WarningCircle size={24} />
            <p className="text-xs">No historical readings recorded for this parameter.</p>
          </div>
        ) : (
          <div className="w-full overflow-x-auto">
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto max-h-[320px] block">
              <defs>
                <linearGradient id="luxeAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#381932" stopOpacity="0.12" />
                  <stop offset="100%" stopColor="#381932" stopOpacity="0" />
                </linearGradient>
              </defs>

              {/* Threshold Lines */}
              {THRESHOLDS.map((th) => {
                const y = scaleY(th.aqi);
                if (y < pad.top || y > pad.top + plotH) return null;
                return (
                  <g key={th.aqi}>
                    <line x1={pad.left} y1={y} x2={W - pad.right} y2={y} stroke={th.color} strokeDasharray="4 4" strokeOpacity={0.35} />
                    <text x={pad.left - 8} y={y + 3} fill="#84657E" fontSize={9} fontFamily="JetBrains Mono, monospace" textAnchor="end" fontWeight={600}>
                      {th.aqi}
                    </text>
                  </g>
                );
              })}

              {areaPath && <path d={areaPath} fill="url(#luxeAreaGrad)" />}
              <path d={linePath} fill="none" stroke="#381932" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />

              {trends.map((p, i) => (
                <circle
                  key={i}
                  cx={scaleX(i)}
                  cy={scaleY(p.aqi)}
                  r={hovered === p ? 6 : 3.5}
                  fill={RISK_COLORS[p.risk_tier] || '#381932'}
                  stroke="#FFF3E6"
                  strokeWidth={1.5}
                  className="cursor-pointer transition-all"
                  onMouseEnter={() => setHovered(p)}
                  onMouseLeave={() => setHovered(null)}
                />
              ))}
            </svg>

            {hovered && (
              <div className="mt-4 p-3.5 bg-[#381932] text-[#FFF3E6] rounded-2xl inline-flex flex-wrap items-center gap-6 text-xs font-mono border border-[#583351] shadow-lg">
                <div>Time: <strong>{formatIsoTimestamp(hovered.measured_at_utc, timezone)}</strong></div>
                <div>AQI: <strong className="font-luxury text-sm">{hovered.aqi}</strong></div>
                <div>Risk: <strong className="px-2 py-0.5 rounded-full text-[10px]" style={{ backgroundColor: RISK_COLORS[hovered.risk_tier] }}>{hovered.risk_tier}</strong></div>
                <div>Reading: <strong>{hovered.value_ugm3 ? hovered.value_ugm3.toFixed(1) : hovered.raw_value} ug/m3</strong></div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Observation History Table */}
      {trends.length > 0 && (
        <div className="minimal-card p-6 md:p-8">
          <h3 className="font-luxury text-xl md:text-2xl text-[#381932] font-bold tracking-tight mb-4">Observation History</h3>
          <div className="overflow-x-auto max-h-[300px]">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp ({getTzShortLabel(timezone)})</th>
                  <th>Raw Value</th>
                  <th>Normalized (ug/m3)</th>
                  <th>AQI Index</th>
                  <th>Classification</th>
                </tr>
              </thead>
              <tbody>
                {trends.slice().reverse().slice(0, 20).map((t, i) => (
                  <tr key={i} className={i === 0 ? 'bg-[#FBF4EC]' : undefined}>
                    <td className="font-mono text-xs text-[#84657E]">
                      <span className="inline-flex items-center gap-2">
                        {formatIsoTimestamp(t.measured_at_utc, timezone)}
                        {i === 0 && <span className="px-2 py-0.5 text-[9px] font-mono font-bold uppercase rounded-full bg-[#381932] text-[#FFF3E6]">Latest</span>}
                      </span>
                    </td>
                    <td className="tabular-nums font-mono text-xs text-[#583351]">{t.raw_value}</td>
                    <td className="tabular-nums font-mono text-xs text-[#583351]">{t.value_ugm3 ? t.value_ugm3.toFixed(1) : '-'}</td>
                    <td className="tabular-nums font-luxury font-bold text-sm text-[#381932]">{t.aqi}</td>
                    <td>
                      <span className="inline-flex items-center gap-2 text-xs">
                        <span className="w-2 h-2 rounded-full ring-1 ring-black/10" style={{ backgroundColor: RISK_COLORS[t.risk_tier] || '#381932' }} />
                        <span className="text-[#381932] font-medium">{t.risk_tier}</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
