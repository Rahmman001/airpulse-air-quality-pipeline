import React from 'react';
import { AirplaneTakeoff, Clock, GlobeSimple, TrendUp, WarningOctagon } from '@phosphor-icons/react';
import { TIMEZONE_OPTIONS, formatLastUpdated } from '../timezone';

interface HeaderProps {
  activeTab: 'overview' | 'trends' | 'alerts' | 'corridors';
  setActiveTab: (tab: 'overview' | 'trends' | 'alerts' | 'corridors') => void;
  dataSourceLabel: string;
  alertCount: number;
  latestDataDate?: string;
  latestDataTime?: string;
  timezone: string;
  onTimezoneChange: (tz: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  dataSourceLabel,
  alertCount,
  latestDataDate,
  latestDataTime,
  timezone,
  onTimezoneChange,
}) => {
  const formatted = formatLastUpdated(latestDataDate, latestDataTime, timezone);
  return (
    <header className="border-b border-white/10 bg-[#090D16]/95 backdrop-blur-xl sticky top-0 z-50 transition-colors shadow-md">
      <div className="max-w-[1360px] mx-auto px-6 h-16 flex items-center justify-between">
        {/* Modern Brand Identity */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-slate-800 to-slate-900 border border-white/15 flex items-center justify-center text-white text-xs font-display font-bold">
            AP
          </div>
          <div className="flex items-center gap-2">
            <span className="font-display text-xl text-white tracking-tight font-bold leading-none">
              AirPulse
            </span>
            <span className="text-[9px] font-mono font-semibold tracking-wider uppercase text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LIVE
            </span>
          </div>
        </div>

        {/* Minimalist Tab Navigation */}
        <nav className="flex items-center gap-1 bg-[#131A29]/90 p-1 rounded-full border border-white/10 shadow-inner">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-1.5 px-3.5 py-1 text-xs rounded-full transition-all duration-200 ${
              activeTab === 'overview'
                ? 'bg-white text-slate-950 font-bold shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-white/5 font-medium'
            }`}
          >
            <GlobeSimple size={14} weight={activeTab === 'overview' ? 'bold' : 'regular'} />
            <span>Overview</span>
          </button>
          <button
            onClick={() => setActiveTab('corridors')}
            className={`flex items-center gap-1.5 px-3.5 py-1 text-xs rounded-full transition-all duration-200 ${
              activeTab === 'corridors'
                ? 'bg-white text-slate-950 font-bold shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-white/5 font-medium'
            }`}
          >
            <AirplaneTakeoff size={14} weight={activeTab === 'corridors' ? 'bold' : 'regular'} />
            <span>Corridors</span>
          </button>
          <button
            onClick={() => setActiveTab('trends')}
            className={`flex items-center gap-1.5 px-3.5 py-1 text-xs rounded-full transition-all duration-200 ${
              activeTab === 'trends'
                ? 'bg-white text-slate-950 font-bold shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-white/5 font-medium'
            }`}
          >
            <TrendUp size={14} weight={activeTab === 'trends' ? 'bold' : 'regular'} />
            <span>Trends</span>
          </button>
          <button
            onClick={() => setActiveTab('alerts')}
            className={`flex items-center gap-1.5 px-3.5 py-1 text-xs rounded-full transition-all duration-200 ${
              activeTab === 'alerts'
                ? 'bg-white text-slate-950 font-bold shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-white/5 font-medium'
            }`}
          >
            <WarningOctagon size={14} weight={activeTab === 'alerts' ? 'bold' : 'regular'} />
            <span>Alerts</span>
            {alertCount > 0 && (
              <span className="bg-rose-600 text-white text-[10px] font-mono px-1.5 rounded-full ml-0.5 font-bold">
                {alertCount}
              </span>
            )}
          </button>
        </nav>

        {/* Right Section: Timezone Selector & Telemetry Status Chip */}
        <div className="flex items-center gap-2.5">
          {/* Timezone Selector Dropdown */}
          <div className="flex items-center gap-1.5 bg-white/5 border border-white/10 px-2.5 py-1 rounded-full text-xs font-mono text-slate-300 hover:border-white/20 transition-colors">
            <Clock size={13} className="text-slate-400 shrink-0" weight="bold" />
            <select
              value={timezone}
              onChange={(e) => onTimezoneChange(e.target.value)}
              className="bg-transparent text-slate-200 text-xs font-mono focus:outline-none cursor-pointer pr-1"
              aria-label="Select Time Zone"
            >
              {TIMEZONE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-slate-900 text-slate-200">
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Telemetry Status Chip */}
          <div className="hidden lg:flex items-center gap-2 text-xs font-mono text-slate-300 bg-white/5 border border-white/10 px-3 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[11px] uppercase tracking-wider text-slate-200 font-semibold">{dataSourceLabel || 'DuckDB Gold'}</span>
            {formatted.full !== '—' && (
              <span className="text-[10px] text-slate-400 border-l border-white/10 pl-2 font-mono">
                {formatted.full}
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
