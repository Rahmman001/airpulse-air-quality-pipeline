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
    <header className="border-b border-[#FFF3E6]/15 bg-[#381932]/95 backdrop-blur-md sticky top-0 z-50 transition-colors shadow-[0_4px_24px_-4px_rgba(56,25,50,0.4)]">
      <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
        {/* Luxury Brand Identity */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-b from-[#381932] to-[#200D1C] border border-[#C5A059]/40 flex items-center justify-center text-[#E0BA70] text-xs font-luxury font-bold tracking-wider shadow-xs">
            AR
          </div>
          <div className="flex items-center gap-2">
            <span className="font-luxury text-xl text-[#FFF3E6] tracking-wider font-bold leading-none">
              AtmosRoute
            </span>
            <span className="text-[9px] font-mono font-semibold tracking-wider uppercase text-[#DFBA70] px-2 py-0.5 rounded-full border border-[#C5A059]/40 bg-[#C5A059]/15 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#DFBA70] animate-pulse" />
              LIVE
            </span>
          </div>
        </div>

        {/* Minimalist Luxury Tab Navigation */}
        <nav className="flex items-center gap-1 bg-[#281224]/90 p-1 rounded-full border border-[#FFF3E6]/15 shadow-inner">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-1.5 px-3.5 py-1 text-xs rounded-full transition-all duration-200 cursor-pointer ${
              activeTab === 'overview'
                ? 'bg-[#FFF3E6] text-[#381932] font-bold shadow-sm'
                : 'text-[#FFF3E6]/75 hover:text-[#FFF3E6] hover:bg-[#FFF3E6]/10 font-medium'
            }`}
          >
            <GlobeSimple size={14} weight={activeTab === 'overview' ? 'bold' : 'regular'} />
            <span>Overview</span>
          </button>
          <button
            onClick={() => setActiveTab('corridors')}
            className={`flex items-center gap-1.5 px-3.5 py-1 text-xs rounded-full transition-all duration-200 cursor-pointer ${
              activeTab === 'corridors'
                ? 'bg-[#FFF3E6] text-[#381932] font-bold shadow-sm'
                : 'text-[#FFF3E6]/75 hover:text-[#FFF3E6] hover:bg-[#FFF3E6]/10 font-medium'
            }`}
          >
            <AirplaneTakeoff size={14} weight={activeTab === 'corridors' ? 'bold' : 'regular'} />
            <span>Corridors</span>
          </button>
          <button
            onClick={() => setActiveTab('trends')}
            className={`flex items-center gap-1.5 px-3.5 py-1 text-xs rounded-full transition-all duration-200 cursor-pointer ${
              activeTab === 'trends'
                ? 'bg-[#FFF3E6] text-[#381932] font-bold shadow-sm'
                : 'text-[#FFF3E6]/75 hover:text-[#FFF3E6] hover:bg-[#FFF3E6]/10 font-medium'
            }`}
          >
            <TrendUp size={14} weight={activeTab === 'trends' ? 'bold' : 'regular'} />
            <span>Trends</span>
          </button>
          <button
            onClick={() => setActiveTab('alerts')}
            className={`flex items-center gap-1.5 px-3.5 py-1 text-xs rounded-full transition-all duration-200 cursor-pointer ${
              activeTab === 'alerts'
                ? 'bg-[#FFF3E6] text-[#381932] font-bold shadow-sm'
                : 'text-[#FFF3E6]/75 hover:text-[#FFF3E6] hover:bg-[#FFF3E6]/10 font-medium'
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
          <div className="flex items-center gap-1.5 bg-[#281224] border border-[#FFF3E6]/20 px-2.5 py-1 rounded-full text-xs font-mono text-[#FFF3E6] hover:border-[#FFF3E6]/40 transition-colors">
            <Clock size={13} className="text-[#DFBA70] shrink-0" weight="bold" />
            <select
              value={timezone}
              onChange={(e) => onTimezoneChange(e.target.value)}
              className="bg-transparent text-[#FFF3E6] text-xs font-mono focus:outline-none cursor-pointer pr-1"
              aria-label="Select Time Zone"
            >
              {TIMEZONE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-[#381932] text-[#FFF3E6]">
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Telemetry Status Chip */}
          <div className="hidden lg:flex items-center gap-2 text-xs font-mono text-[#FFF3E6]/90 bg-[#281224] border border-[#FFF3E6]/20 px-3 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-[#DFBA70] animate-pulse" />
            <span className="text-[11px] uppercase tracking-wider text-[#FFF3E6] font-semibold">{dataSourceLabel || 'DuckDB Gold'}</span>
            {formatted.full !== '—' && (
              <span className="text-[10px] text-[#FFF3E6]/60 border-l border-[#FFF3E6]/20 pl-2 font-mono">
                {formatted.full}
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
