import React, { useState, useEffect } from 'react';
import { TrendUp, WarningCircle } from '@phosphor-icons/react';
import { api, RISK_COLORS } from '../api';
import type { LocationItem, Pollutant, TrendPoint } from '../api';
import { formatIsoTimestamp, getTzShortLabel } from '../timezone';

interface CityTrendsProps {
  locations: LocationItem[];
  pollutants: Pollutant[];
  initialLocationKey?: string;
  timezone?: string;
}

export const CityTrends: React.FC<CityTrendsProps> = ({
  locations,
  pollutants,
  initialLocationKey,
  timezone = 'UTC',
}) => {
  const [selectedLocation, setSelectedLocation] = useState<string>(
    initialLocationKey || (locations.length > 0 ? locations[0].location_key : '')
  );
  const [prevInitial, setPrevInitial] = useState(initialLocationKey);
  if (initialLocationKey !== prevInitial) {
    setPrevInitial(initialLocationKey);
    if (initialLocationKey) {
      setSelectedLocation(initialLocationKey);
    }
  }

  const defaultPollutantKey =
    pollutants.find((p) => p.parameter_name?.toLowerCase() === 'pm25')?.pollutant_key ||
    (pollutants.length > 0 ? pollutants[0].pollutant_key : 'pm25');

  const [selectedPollutant, setSelectedPollutant] = useState<string>(defaultPollutantKey);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [hoveredPoint, setHoveredPoint] = useState<TrendPoint | null>(null);

  useEffect(() => {
    if (pollutants.length > 0 && selectedPollutant === 'pm25') {
      const pm25 = pollutants.find((p) => p.parameter_name?.toLowerCase() === 'pm25');
      if (pm25) {
        setSelectedPollutant(pm25.pollutant_key);
      }
    }
  }, [pollutants, selectedPollutant]);

  useEffect(() => {
    if (!selectedLocation || !selectedPollutant) return;

    let isMounted = true;

    api
      .getTrends(selectedLocation, selectedPollutant)
      .then((data) => {
        if (isMounted) {
          // Sort chronologically (oldest to newest) for chart plotting
          const sorted = [...data].sort(
            (a, b) => new Date(a.measured_at_utc).getTime() - new Date(b.measured_at_utc).getTime()
          );
          setTrends(sorted);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to load trends:', err);
        if (isMounted) {
          setTrends([]);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [selectedLocation, selectedPollutant]);

  const activeLocation = locations.find((l) => l.location_key === selectedLocation);
  const activePollutant = pollutants.find((p) => p.pollutant_key === selectedPollutant);

  // SVG Chart Dimensions
  const chartWidth = 900;
  const chartHeight = 280;
  const padding = { top: 25, right: 30, bottom: 35, left: 50 };
  const plotWidth = chartWidth - padding.left - padding.right;
  const plotHeight = chartHeight - padding.top - padding.bottom;

  const maxAqi = Math.max(350, ...trends.map((t) => t.aqi || 0));
  const minAqi = 0;

  const scaleY = (aqi: number) => {
    return padding.top + plotHeight - ((aqi - minAqi) / (maxAqi - minAqi)) * plotHeight;
  };

  const scaleX = (index: number) => {
    if (trends.length <= 1) return padding.left + plotWidth / 2;
    return padding.left + (index / (trends.length - 1)) * plotWidth;
  };

  // Threshold lines at EPA breakpoints
  const thresholds = [
    { aqi: 50, label: '50 Good', color: '#059669' },
    { aqi: 100, label: '100 Moderate', color: '#D97706' },
    { aqi: 150, label: '150 USG', color: '#EA580C' },
    { aqi: 200, label: '200 Unhealthy', color: '#DC2626' },
    { aqi: 300, label: '300 Very Unhealthy', color: '#991B1B' },
  ];

  const linePath = trends.length > 0
    ? trends.reduce((acc, point, i) => {
        const x = scaleX(i);
        const y = scaleY(point.aqi);
        return i === 0 ? `M ${x},${y}` : `${acc} L ${x},${y}`;
      }, '')
    : '';

  const areaPath = trends.length > 0
    ? `${linePath} L ${scaleX(trends.length - 1)},${scaleY(0)} L ${scaleX(0)},${scaleY(0)} Z`
    : '';

  return (
    <div className="space-y-8 mb-12">
      {/* Modern Control Bar */}
      <div className="minimal-card p-6 flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-full bg-slate-950 text-white flex items-center justify-center shadow-xs">
            <TrendUp size={18} weight="bold" className="text-white" />
          </div>
          <div className="flex items-center gap-2.5">
            <span className="w-2 h-2 rounded-full bg-slate-900" />
            <h2 className="font-display text-xl md:text-2xl text-slate-950 font-bold tracking-tight">
              Temporal Trends
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div>
            <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1 font-semibold">
              Geohub
            </label>
            <select
              value={selectedLocation}
              onChange={(e) => setSelectedLocation(e.target.value)}
              className="text-xs bg-white border border-slate-200 rounded-lg px-3 py-1.5 outline-none font-medium text-slate-900 shadow-2xs focus:border-slate-800"
            >
              {locations.map((loc) => (
                <option key={loc.location_key} value={loc.location_key} className="text-slate-900">
                  {loc.location_name} ({loc.country_code})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1 font-semibold">
              Parameter
            </label>
            <select
              value={selectedPollutant}
              onChange={(e) => setSelectedPollutant(e.target.value)}
              className="text-xs bg-white border border-slate-200 rounded-lg px-3 py-1.5 outline-none font-medium text-slate-900 shadow-2xs focus:border-slate-800"
            >
              {pollutants.map((pol) => (
                <option key={pol.pollutant_key} value={pol.pollutant_key} className="text-slate-900">
                  {pol.pollutant_display_name || pol.parameter_name.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Main Chart Area */}
      <div className="minimal-card p-6 md:p-8">
        <div className="flex items-baseline justify-between mb-6 pb-4 border-b border-slate-200/80">
          <div>
            <h3 className="font-display text-2xl text-slate-950 font-bold">
              {activeLocation ? activeLocation.location_name : 'Selected Geohub'} :{' '}
              <span className="font-normal text-slate-600">
                {activePollutant ? (activePollutant.pollutant_display_name || activePollutant.parameter_name.toUpperCase()) : 'Pollutant'}
              </span>
            </h3>
          </div>

          {trends.length > 0 && (
            <div className="flex items-center gap-6 text-xs font-mono text-slate-500">
              <div>Observations: <strong className="text-slate-950 font-bold">{trends.length}</strong></div>
              <div>Peak AQI: <strong className="text-slate-950 font-bold">{Math.max(...trends.map((t) => t.aqi))}</strong></div>
              <div>Current: <strong className="text-slate-950 font-bold">{trends[trends.length - 1]?.aqi}</strong></div>
            </div>
          )}
        </div>

        {loading ? (
          <div className="h-[280px] flex items-center justify-center text-xs font-mono text-slate-500">
            PARSING TELEMETRY VECTOR...
          </div>
        ) : trends.length === 0 ? (
          <div className="h-[280px] flex flex-col items-center justify-center gap-2 text-slate-500">
            <WarningCircle size={24} className="text-slate-400" />
            <p className="text-xs text-slate-500">No historical readings recorded for this parameter.</p>
          </div>
        ) : (
          <div className="w-full overflow-x-auto">
            <svg
              viewBox={`0 0 ${chartWidth} ${chartHeight}`}
              className="w-full h-auto max-h-[320px] block"
            >
              {/* Threshold Guidelines */}
              {thresholds.map((th) => {
                const y = scaleY(th.aqi);
                if (y < padding.top || y > padding.top + plotHeight) return null;
                return (
                  <g key={th.aqi}>
                    <line
                      x1={padding.left}
                      y1={y}
                      x2={chartWidth - padding.right}
                      y2={y}
                      stroke={th.color}
                      strokeDasharray="4 4"
                      strokeOpacity={0.35}
                      strokeWidth={1}
                    />
                    <text
                      x={padding.left - 8}
                      y={y + 3}
                      fill="#64748B"
                      fontSize={9}
                      fontFamily="JetBrains Mono, monospace"
                      textAnchor="end"
                      fontWeight={600}
                    >
                      {th.aqi}
                    </text>
                  </g>
                );
              })}

              <defs>
                <linearGradient id="luxuryAreaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0F172A" stopOpacity="0.08" />
                  <stop offset="100%" stopColor="#0F172A" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Area Fill */}
              {areaPath && (
                <path
                  d={areaPath}
                  fill="url(#luxuryAreaGradient)"
                />
              )}

              {/* Trend Path in Deep Obsidian */}
              <path
                d={linePath}
                fill="none"
                stroke="#0F172A"
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Data Points */}
              {trends.map((point, idx) => {
                const cx = scaleX(idx);
                const cy = scaleY(point.aqi);
                const pointColor = RISK_COLORS[point.risk_tier] || '#0F172A';
                const isHovered = hoveredPoint === point;

                return (
                  <circle
                    key={idx}
                    cx={cx}
                    cy={cy}
                    r={isHovered ? 5.5 : 3}
                    fill={pointColor}
                    stroke="#FFFFFF"
                    strokeWidth={1.5}
                    style={{ cursor: 'pointer', transition: 'r 0.12s ease' }}
                    onMouseEnter={() => setHoveredPoint(point)}
                    onMouseLeave={() => setHoveredPoint(null)}
                  />
                );
              })}
            </svg>

            {/* Precision Tooltip */}
            {hoveredPoint && (
              <div className="mt-3 p-3 bg-slate-950 text-white rounded-lg inline-flex gap-5 text-xs font-mono border border-slate-800 shadow-md">
                <div>Time: <strong className="text-white">{formatIsoTimestamp(hoveredPoint.measured_at_utc, timezone)}</strong></div>
                <div>AQI: <strong className="text-white font-bold">{hoveredPoint.aqi}</strong></div>
                <div>Risk: <strong className="text-white font-bold">{hoveredPoint.risk_tier}</strong></div>
                <div>Reading: <strong className="text-white font-bold">{hoveredPoint.value_ugm3 ? hoveredPoint.value_ugm3.toFixed(1) : hoveredPoint.raw_value} ug/m3</strong></div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Historical Table */}
      {trends.length > 0 && (
        <div className="minimal-card p-6 md:p-8">
          <h3 className="font-display text-xl text-slate-950 font-bold mb-4">
            Observation History
          </h3>
          <div className="overflow-x-auto max-h-[280px]">
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
                {[...trends]
                  .sort((a, b) => new Date(b.measured_at_utc).getTime() - new Date(a.measured_at_utc).getTime())
                  .slice(0, 20)
                  .map((t, idx) => {
                    const color = RISK_COLORS[t.risk_tier] || '#0F172A';
                    return (
                      <tr key={idx} className={idx === 0 ? 'bg-emerald-50/30' : undefined}>
                        <td className="font-mono text-xs text-slate-600">
                          <span className="inline-flex items-center gap-2">
                            {formatIsoTimestamp(t.measured_at_utc, timezone)}
                            {idx === 0 && (
                              <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase tracking-wider rounded bg-emerald-100 text-emerald-800 border border-emerald-300/60">
                                Latest
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="tabular-nums font-mono text-xs text-slate-700">{t.raw_value}</td>
                        <td className="tabular-nums font-mono text-xs text-slate-700">{t.value_ugm3 ? t.value_ugm3.toFixed(1) : '-'}</td>
                        <td className="tabular-nums font-mono font-bold text-xs text-slate-950">{t.aqi}</td>
                        <td>
                          <span className="inline-flex items-center gap-2 text-xs">
                            <span className="w-2 h-2 rounded-full ring-1 ring-black/10" style={{ backgroundColor: color }} />
                            <span className="text-slate-800 font-medium">{t.risk_tier}</span>
                          </span>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
