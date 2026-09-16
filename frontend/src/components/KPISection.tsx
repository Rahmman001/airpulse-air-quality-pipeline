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
      <div className="py-20 text-center text-xs text-[#381932] tracking-widest uppercase flex items-center justify-center gap-3 font-medium">
        <span className="w-2 h-2 rounded-full bg-[#381932] animate-ping" />
        Synchronizing atmospheric telemetry stream...
      </div>
    );
  }

  const worst = kpis.worst_current_reading;
  const hasHazardous = kpis.hazardous_zones_count > 0;
  const formatted = formatLastUpdated(kpis.latest_data_date, kpis.latest_data_time, timezone);

  return (
    <section className="pt-2 pb-6 mb-4">
      {/* Luxury Hero Header */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <div className="text-[11px] font-mono uppercase tracking-widest text-[#84657E] mb-1 font-semibold">
            Global Atmospheric Intelligence
          </div>
          <h1 className="font-luxury text-3xl sm:text-4xl md:text-5xl text-[#381932] tracking-tight font-bold leading-tight">
            Air Quality &amp; Telemetry
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {kpis.latest_data_date && (
            <div className="flex items-center gap-2 text-xs text-[#583351] bg-white/80 backdrop-blur-xs border border-[#381932]/12 px-3.5 py-1.5 rounded-full shadow-2xs">
              <span className="text-[#84657E] text-[10px] uppercase font-bold tracking-wider">Synchronized:</span>
              <span className="font-semibold text-[#381932] font-mono">{formatted.full}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-xs font-mono text-[#381932] bg-white/80 backdrop-blur-xs border border-[#381932]/12 px-3.5 py-1.5 rounded-full shadow-2xs">
            <span className="w-2 h-2 rounded-full bg-[#C5A059] animate-pulse" />
            <span className="font-bold tracking-wider">LIVE TELEMETRY</span>
          </div>
        </div>
      </div>

      {/* High-Impact Minimalist Metric Rail */}
      <div className="minimal-card p-6 md:p-8 grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-0">
        
        {/* Metric 1: Network Scale */}
        <div className="flex flex-col justify-between md:pr-8">
          <div className="text-[11px] uppercase tracking-wider text-[#84657E] mb-2 font-bold font-mono">
            Monitored Stations
          </div>
          <div className="font-luxury text-4xl sm:text-5xl lg:text-6xl font-bold text-[#381932] leading-none my-1 tracking-tighter">
            {kpis.locations_monitored}
          </div>
          <div className="text-xs text-[#583351] mt-2 font-medium">
            Active global observation nodes
          </div>
        </div>

        {/* Metric 2: Critical Hotspot */}
        <div className="flex flex-col justify-between md:border-l md:border-[#381932]/10 md:px-8">
          <div className="flex items-center justify-between text-[11px] uppercase tracking-wider text-[#84657E] mb-2 font-bold font-mono">
            <span>Peak AQI Index</span>
            {worst && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-[#381932]/15 bg-[#FBF4EC] text-[#381932] font-bold">
                {worst.parameter_name.toUpperCase()}
              </span>
            )}
          </div>
          {worst ? (
            <div>
              <div className="font-luxury text-4xl sm:text-5xl lg:text-6xl font-bold leading-none my-1 text-[#381932] tracking-tighter">
                {Math.round(worst.avg_aqi)}
              </div>
              <div className="text-xs text-[#583351] font-medium flex items-center gap-1.5 mt-2">
                <MapPin size={13} className="text-[#381932] shrink-0" weight="fill" />
                <span className="font-semibold text-[#381932] truncate">{worst.location_name}</span>
                <span className="text-[#84657E] font-mono">({worst.country_name})</span>
              </div>
            </div>
          ) : (
            <div className="text-xs text-[#84657E]">No readings recorded</div>
          )}
        </div>

        {/* Metric 3: Operational Sentinel */}
        <div className="flex flex-col justify-between md:border-l md:border-[#381932]/10 md:pl-8">
          <div className="text-[11px] uppercase tracking-wider text-[#84657E] mb-2 font-bold font-mono">
            Critical Exceedances
          </div>
          <div className="font-luxury text-4xl sm:text-5xl lg:text-6xl font-bold leading-none my-1 text-[#381932] tracking-tighter">
            {kpis.hazardous_zones_count}
          </div>
          <div className="text-xs font-medium flex items-center gap-2 mt-2">
            {hasHazardous ? (
              <>
                <Warning size={15} className="text-[#381932] shrink-0" weight="bold" />
                <span className="text-[#381932] font-semibold">Threshold alerts active</span>
              </>
            ) : (
              <>
                <ShieldCheck size={15} className="text-[#059669] shrink-0" weight="bold" />
                <span className="text-[#059669] font-semibold">All corridors nominal</span>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
