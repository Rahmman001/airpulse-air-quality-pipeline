import React from 'react';
import { Warning, ShieldCheck, MapPin } from '@phosphor-icons/react';
import type { KpiData } from '../api';
import { formatLastUpdated } from '../timezone';

interface KPISectionProps {
  kpis: KpiData | null;
  loading: boolean;
  timezone?: string;
}

export const KPISection: React.FC<KPISectionProps> = ({ kpis, loading, timezone = 'UTC' }) => {
  if (loading || !kpis) {
    return (
      <div className="py-16 text-center font-mono text-xs text-black tracking-[0.2em] uppercase flex items-center justify-center gap-2">
        <span className="w-2 h-2 rounded-full bg-black animate-ping" />
        Connecting to atmospheric telemetry stream...
      </div>
    );
  }

  const worst = kpis.worst_current_reading;
  const hasHazardous = kpis.hazardous_zones_count > 0;
  const formatted = formatLastUpdated(kpis.latest_data_date, kpis.latest_data_time, timezone);

  return (
    <section className="pt-4 pb-6 mb-6">
      {/* Tight Minimal Hero Header */}
      <div className="flex flex-wrap items-baseline justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl md:text-5xl text-slate-950 tracking-tight font-bold leading-tight">
            Air Quality &amp; Telemetry
          </h1>
        </div>
        <div className="flex items-center gap-2.5">
          {kpis.latest_data_date && (
            <div className="flex items-center gap-1.5 text-xs font-mono text-slate-700 bg-white border border-slate-200 px-3 py-1 rounded-full shadow-2xs">
              <span className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">Last Updated:</span>
              <span className="font-semibold text-slate-900">{formatted.full}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-xs font-mono text-slate-600 bg-white border border-slate-200 px-3 py-1 rounded-full shadow-2xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>LIVE PIPELINE</span>
          </div>
        </div>
      </div>

      {/* High-Density Metric Rail */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 py-6 px-7 border border-slate-200/90 rounded-2xl bg-white shadow-xs">
        
        {/* Metric 1: Network Scale */}
        <div className="flex flex-col justify-between">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-500 mb-1 font-semibold">
            Monitored Stations
          </div>
          <div className="font-display text-4xl md:text-5xl font-bold text-slate-950 leading-none my-1">
            {kpis.locations_monitored}
          </div>
          <div className="text-xs text-slate-500 font-mono">
            Active global observation nodes
          </div>
        </div>

        {/* Metric 2: Critical Hotspot */}
        <div className="md:border-l md:border-slate-200/90 md:pl-7 flex flex-col justify-between">
          <div className="flex items-center justify-between text-[11px] font-mono uppercase tracking-wider text-slate-500 mb-1 font-semibold">
            <span>Peak AQI Index</span>
            {worst && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-slate-200 bg-slate-100 text-slate-800 font-bold">
                {worst.parameter_name.toUpperCase()}
              </span>
            )}
          </div>
          {worst ? (
            <div>
              <div className="font-display text-4xl md:text-5xl font-bold leading-none my-1 text-slate-950">
                {Math.round(worst.avg_aqi)}
              </div>
              <div className="text-xs text-slate-700 font-medium flex items-center gap-1.5 pt-1">
                <MapPin size={13} className="text-rose-600" weight="fill" />
                <span className="font-semibold text-slate-900">{worst.location_name}</span>
                <span className="text-slate-500 font-mono">({worst.country_name})</span>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500 font-mono">No readings recorded</div>
          )}
        </div>

        {/* Metric 3: Operational Sentinel */}
        <div className="md:border-l md:border-slate-200/90 md:pl-7 flex flex-col justify-between">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-500 mb-1 font-semibold">
            Critical Exceedances
          </div>
          <div className="font-display text-4xl md:text-5xl font-bold leading-none my-1 text-slate-950">
            {kpis.hazardous_zones_count}
          </div>
          <div className="text-xs font-medium flex items-center gap-1.5 pt-1 font-mono">
            {hasHazardous ? (
              <>
                <Warning size={14} className="text-rose-600" weight="bold" />
                <span className="text-rose-700 font-semibold">Threshold alerts active</span>
              </>
            ) : (
              <>
                <ShieldCheck size={14} className="text-emerald-600" weight="bold" />
                <span className="text-emerald-700 font-semibold">All corridors nominal</span>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
