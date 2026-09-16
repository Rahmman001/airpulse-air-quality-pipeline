import React, { useState, useEffect, useMemo } from 'react';
import { WarningOctagon, DownloadSimple, ShieldCheck, MagnifyingGlass } from '@phosphor-icons/react';
import { api, RISK_COLORS, ALERT_FILTER_TIERS, type AlertsResponse } from '../api';

const PROTOCOLS: Record<string, string> = {
  Hazardous: 'Halt field ops; mandatory N95 / PAPR',
  'Very Unhealthy': 'Cabin air recirc; limit exposure <2h',
  Unhealthy: 'Issue N95; advisory route dev',
  'Unhealthy for Sensitive Groups': 'Sensitive group advisory; check HVAC',
  Moderate: 'Standard flight & cargo protocols',
  Good: 'Optimal conditions; standard operations',
};

export const Alerts: React.FC = () => {
  const [minTier, setMinTier] = useState('Unhealthy');
  const [alertsData, setAlertsData] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.getAlerts(minTier)
      .then((d) => { if (active) { setAlertsData(d); setLoading(false); } })
      .catch(() => { if (active) { setAlertsData(null); setLoading(false); } });
    return () => { active = false; };
  }, [minTier]);

  const filteredAlerts = useMemo(() => {
    if (!alertsData?.alerts) return [];
    if (!searchTerm.trim()) return alertsData.alerts;
    const q = searchTerm.toLowerCase();
    return alertsData.alerts.filter(
      (a) =>
        a.location_name.toLowerCase().includes(q) ||
        a.country_name.toLowerCase().includes(q) ||
        a.parameter_name.toLowerCase().includes(q)
    );
  }, [alertsData, searchTerm]);

  const handleExportCsv = (e: React.MouseEvent) => {
    e.preventDefault();
    if (filteredAlerts.length) {
      const headers = ['location_name,country_name,parameter_name,avg_aqi,risk_tier,reading_count,flagged_reading_count'];
      const esc = (v: any) => String(v ?? '').replace(/^[=+\-@]/, "'$&");
      const rows = filteredAlerts.map(
        (a) => `"${esc(a.location_name)}","${esc(a.country_name)}","${esc(a.parameter_name)}",${a.avg_aqi},"${esc(a.risk_tier)}",${a.reading_count},${a.flagged_reading_count}`
      );
      const blob = new Blob([headers.concat(rows).join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `atmosroute_alerts_${minTier.toLowerCase().replace(/\s+/g, '_')}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="space-y-8 mb-12">
      {/* Alert Header & Tier Selector */}
      <div className="minimal-card p-6 md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-6 mb-6">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-full bg-[#381932] text-[#FFF3E6] flex items-center justify-center shadow-xs">
              <WarningOctagon size={18} weight="bold" />
            </div>
            <div>
              <div className="text-[10px] font-mono text-[#84657E] uppercase tracking-wider font-bold">Operational Triage</div>
              <h2 className="font-luxury text-xl md:text-2xl text-[#381932] font-bold tracking-tight">Dispatch Alerts</h2>
            </div>
          </div>
          <a
            href={api.getExportUrl(minTier)}
            onClick={handleExportCsv}
            download="atmosroute_alerts.csv"
            className="inline-flex items-center gap-2 bg-[#381932] text-[#FFF3E6] px-5 py-2 text-xs font-medium rounded-full hover:bg-[#583351] transition-all shadow-xs cursor-pointer"
          >
            <DownloadSimple size={14} weight="bold" />
            Export CSV Report
          </a>
        </div>

        <div>
          <div className="text-[11px] font-mono text-[#84657E] uppercase tracking-wider mb-2.5 font-bold">
            Filter by Threat Classification:
          </div>
          <div className="flex flex-wrap gap-2">
            {ALERT_FILTER_TIERS.map((tier) => {
              const active = minTier === tier;
              return (
                <button
                  key={tier}
                  onClick={() => minTier !== tier && setMinTier(tier)}
                  className={`flex items-center gap-2 text-xs px-4 py-2 rounded-full border transition-all cursor-pointer ${
                    active
                      ? 'bg-[#381932] text-[#FFF3E6] border-[#381932] font-bold shadow-xs'
                      : 'bg-white text-[#583351] border-[#381932]/15 hover:border-[#381932] font-semibold'
                  }`}
                >
                  {tier !== 'All' && (
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: RISK_COLORS[tier] }} />
                  )}
                  <span>{tier}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Alert Table */}
      <div className="minimal-card p-6 md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6 pb-4 border-b border-[#381932]/10">
          <div className="flex items-center gap-3">
            <h3 className="font-luxury text-xl md:text-2xl text-[#381932] font-bold tracking-tight">
              Classification: <span className="font-normal text-[#84657E]">{minTier}</span>
            </h3>
            {alertsData && (
              <span className="text-xs font-mono text-[#583351] bg-[#FBF4EC] px-3 py-1 rounded-full border border-[#381932]/10 font-bold">
                {filteredAlerts.length} {filteredAlerts.length === 1 ? 'Station' : 'Stations'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <MagnifyingGlass size={14} className="absolute left-3.5 top-2.5 text-[#84657E]" />
              <input
                type="text"
                placeholder="Search station or country..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-4 py-1.5 text-xs bg-white border border-[#381932]/15 text-[#381932] placeholder:text-[#84657E] rounded-full focus:border-[#381932] focus:ring-1 focus:ring-[#381932]/10 outline-none w-56 font-medium shadow-2xs transition-all"
              />
            </div>
            <div className="text-xs font-mono text-[#84657E] font-medium bg-[#FBF4EC] px-3 py-1 rounded-full border border-[#381932]/8">
              {minTier === 'All' ? 'All Monitored Hubs' : `Tier: ${minTier}`}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="py-16 text-center text-xs font-mono text-[#84657E] tracking-widest uppercase">
            Parsing Threat Vectors...
          </div>
        ) : !filteredAlerts.length ? (
          <div className="py-16 text-center flex flex-col items-center gap-3">
            <div className="w-14 h-14 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-700 mb-1 shadow-2xs">
              <ShieldCheck size={32} weight="bold" />
            </div>
            <div className="font-luxury font-bold text-lg text-[#381932]">
              {searchTerm ? 'No Matching Geohubs' : `No Stations in "${minTier}"`}
            </div>
            <div className="text-xs text-[#84657E] max-w-md leading-relaxed">
              {searchTerm
                ? `No stations in "${minTier}" matched the search query "${searchTerm}".`
                : `Currently, no active stations are categorized as "${minTier}".`}
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Location Geohub</th>
                  <th>Country</th>
                  <th>Parameter</th>
                  <th>Flagged Exceedances</th>
                  <th>AQI Index</th>
                  <th>Classification</th>
                  <th>Required Mitigation Protocol</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((a, idx) => (
                  <tr key={`${a.location_name}-${a.parameter_name}-${idx}`}>
                    <td className="font-semibold text-sm text-[#381932]">{a.location_name}</td>
                    <td className="font-mono text-xs text-[#84657E]">{a.country_name}</td>
                    <td>
                      <span className="font-mono text-[11px] bg-[#FBF4EC] text-[#583351] px-2.5 py-0.5 rounded-full border border-[#381932]/10 font-bold">
                        {a.parameter_name.toUpperCase()}
                      </span>
                    </td>
                    <td className="tabular-nums font-mono text-xs text-[#583351] font-semibold">{a.flagged_reading_count} / {a.reading_count}</td>
                    <td className="tabular-nums font-luxury font-bold text-base text-[#381932]">{Math.round(a.avg_aqi)}</td>
                    <td>
                      <span className="inline-flex items-center gap-2 text-xs">
                        <span className="w-2 h-2 rounded-full ring-1 ring-black/10" style={{ backgroundColor: RISK_COLORS[a.risk_tier] || '#381932' }} />
                        <span className="text-[#381932] font-semibold">{a.risk_tier}</span>
                      </span>
                    </td>
                    <td className="text-xs text-[#583351] font-medium">{PROTOCOLS[a.risk_tier] || 'Nominal dispatch status'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

