import React, { useState, useEffect } from 'react';
import { WarningOctagon, DownloadSimple, ShieldCheck } from '@phosphor-icons/react';
import { api, RISK_COLORS, RISK_TIERS } from '../api';
import type { AlertsResponse } from '../api';

export const Alerts: React.FC = () => {
  const [minTier, setMinTier] = useState<string>('Unhealthy');
  const [alertsData, setAlertsData] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    api
      .getAlerts(minTier)
      .then((data) => {
        if (isMounted) {
          setAlertsData(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to load alerts:', err);
        if (isMounted) {
          setAlertsData(null);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [minTier]);

  const getMitigationProtocol = (tier: string) => {
    switch (tier) {
      case 'Hazardous':
        return 'Halt field ops; mandatory N95 / PAPR';
      case 'Very Unhealthy':
        return 'Cabin air recirc; limit exposure <2h';
      case 'Unhealthy':
        return 'Issue N95; advisory route dev';
      case 'Unhealthy for Sensitive Groups':
        return 'Sensitive group advisory; check HVAC';
      default:
        return 'Nominal dispatch status';
    }
  };

  return (
    <div className="space-y-8 mb-12">
      {/* Alert Header & Tier Selector */}
      <div className="minimal-card p-6 md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-6 mb-6">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-full bg-rose-50 text-rose-700 flex items-center justify-center border border-rose-200/80 shadow-xs">
              <WarningOctagon size={18} weight="bold" className="text-rose-700" />
            </div>
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-slate-900" />
              <h2 className="font-display text-xl md:text-2xl text-slate-950 font-bold tracking-tight">
                Dispatch Alerts
              </h2>
            </div>
          </div>

          <a
            href={api.getExportUrl(minTier)}
            download="airpulse_alerts.csv"
            className="inline-flex items-center gap-2 bg-slate-950 text-white px-4 py-2 text-xs font-mono font-medium rounded-full hover:bg-slate-800 transition-all shadow-xs"
          >
            <DownloadSimple size={14} weight="bold" className="text-white" />
            Export CSV
          </a>
        </div>

        {/* Modern Tier Filter */}
        <div>
          <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2 font-semibold">
            Minimum Threat Threshold:
          </div>
          <div className="flex flex-wrap gap-2">
            {RISK_TIERS.map((tier) => {
              const isSelected = minTier === tier;
              const color = RISK_COLORS[tier];
              return (
                <button
                  key={tier}
                  onClick={() => {
                    if (minTier !== tier) {
                      setMinTier(tier);
                      setLoading(true);
                    }
                  }}
                  className={`flex items-center gap-2 text-xs font-sans px-3.5 py-1.5 rounded-full border transition-all ${
                    isSelected
                      ? 'bg-slate-950 text-white border-slate-950 font-semibold shadow-xs'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300 font-medium'
                  }`}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  <span>{tier}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Alert Table */}
      <div className="minimal-card p-6 md:p-8">
        <div className="flex items-baseline justify-between mb-6 pb-4 border-b border-slate-200/80">
          <div className="flex items-center gap-3">
            <h3 className="font-display text-xl text-slate-950 font-bold">
              Exceedance Threshold: <span className="font-normal text-slate-600">{minTier}</span>
            </h3>
            {alertsData && (
              <span className="text-xs font-mono text-slate-700 bg-slate-100 px-2.5 py-0.5 rounded-full border border-slate-200 font-medium">
                {alertsData.alert_count} Active Geohubs
              </span>
            )}
          </div>
          <div className="text-xs font-mono text-slate-500 font-medium">
            Cutoff: AQI &gt;= {alertsData?.threshold_aqi ?? '-'}
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs font-mono text-slate-500">
            PARSING THRESHOLD VECTORS...
          </div>
        ) : !alertsData || alertsData.alert_count === 0 ? (
          <div className="py-12 text-center flex flex-col items-center gap-2">
            <ShieldCheck size={36} className="text-emerald-600" weight="bold" />
            <div className="font-semibold text-base text-slate-900">
              No Active Exceedances for Level "{minTier}"
            </div>
            <div className="text-xs text-slate-500">
              All monitored stations report AQI values below {alertsData?.threshold_aqi ?? 150}.
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
                {alertsData.alerts.map((a, idx) => {
                  const color = RISK_COLORS[a.risk_tier] || '#0F172A';
                  return (
                    <tr key={`${a.location_name}-${a.parameter_name}-${idx}`}>
                      <td className="font-semibold text-sm text-slate-900">{a.location_name}</td>
                      <td className="font-mono text-xs text-slate-500">{a.country_name}</td>
                      <td>
                        <span className="font-mono text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200 font-medium">
                          {a.parameter_name.toUpperCase()}
                        </span>
                      </td>
                      <td className="tabular-nums font-mono text-xs text-slate-700">
                        {a.flagged_reading_count} / {a.reading_count}
                      </td>
                      <td className="tabular-nums font-mono font-bold text-sm text-slate-950">
                        {Math.round(a.avg_aqi)}
                      </td>
                      <td>
                        <span className="inline-flex items-center gap-2 text-xs">
                          <span className="w-2 h-2 rounded-full ring-1 ring-black/10" style={{ backgroundColor: color }} />
                          <span className="text-slate-800 font-medium">{a.risk_tier}</span>
                        </span>
                      </td>
                      <td className="text-xs text-slate-700 font-medium">
                        {getMitigationProtocol(a.risk_tier)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
