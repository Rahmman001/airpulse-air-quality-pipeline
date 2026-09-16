import React, { useEffect } from 'react';
import { X, BookOpen, ShieldCheck, AirplaneTakeoff, Database, Scales } from '@phosphor-icons/react';

interface MethodologyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MethodologyModal: React.FC<MethodologyModalProps> = ({ isOpen, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="bg-[#281224] border border-[#FFF3E6]/20 rounded-3xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl text-[#FFF3E6] flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="methodology-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-[#FFF3E6]/15 sticky top-0 bg-[#281224]/95 backdrop-blur-md z-10">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#DFBA70]/20 text-[#DFBA70] border border-[#DFBA70]/40 flex items-center justify-center">
              <BookOpen size={18} weight="bold" />
            </div>
            <div>
              <h2 id="methodology-title" className="font-luxury text-lg font-bold text-[#FFF3E6] tracking-wide">
                Operational Methodology &amp; Standards
              </h2>
              <p className="text-[11px] text-[#DFBA70] font-mono">
                Scope, Formula Weights &amp; Regulatory Citations
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-[#FFF3E6]/10 hover:bg-[#FFF3E6]/20 text-[#FFF3E6] flex items-center justify-center transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 text-xs text-[#FFF3E6]/85 leading-relaxed font-sans">
          {/* Section 1: Scope & Altitude */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-[#DFBA70]">
              <AirplaneTakeoff size={16} weight="bold" />
              <span>1. Altitude Scope &amp; Boundary Layer Dynamics</span>
            </div>
            <p>
              Ground-level PM2.5 and gas sensors measure ambient air in the <strong>planetary boundary layer</strong> (surface to ~3,000 ft AGL). Commercial passenger and cargo aircraft cruise at <strong>FL300–FL410 (30,000–41,000 ft)</strong> in the clean upper troposphere and stratosphere where surface particulates do not penetrate.
            </p>
            <p className="bg-[#381932]/70 p-3 rounded-xl border border-[#FFF3E6]/10 text-[#FFF3E6]/90">
              <strong>Operational Scope:</strong> AtmosRoute specifically assesses <strong>terminal maneuvering (&lt;10,000 ft AGL), taxi, and ground turnaround</strong>—the precise flight phases where aircraft Environmental Control Systems (ECS) pull in ambient air via ground conditioning units or APUs, and where ramp and baggage crews operate outdoors.
            </p>
          </div>

          {/* Section 2: Mathematical Scoring Formula */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-[#DFBA70]">
              <Scales size={16} weight="bold" />
              <span>2. Corridor Risk Weighting Formula</span>
            </div>
            <p>
              Route risk evaluates both terminal chokepoints with an asymmetric emphasis on the arrival hub (where ground turnaround, baggage handling, and deplaning crew exposure occur):
            </p>
            <div className="bg-[#1C0D19] p-3 rounded-xl border border-[#DFBA70]/30 font-mono text-[11px] text-[#DFBA70]">
              Score = 0.30 &times; AQI_origin + 0.50 &times; AQI_dest + 0.20 &times; max(AQI_origin, AQI_dest)
            </div>
            <p className="text-[11px] text-[#FFF3E6]/70">
              If a terminal is offline or unmonitored, the index calculates exposure strictly from the active monitored terminal with an explicit coverage notice rather than assuming zero risk.
            </p>
          </div>

          {/* Section 3: Regulatory Citations */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-[#DFBA70]">
              <ShieldCheck size={16} weight="bold" />
              <span>3. Regulatory Baselines &amp; Dispatch Rules</span>
            </div>
            <ul className="space-y-2 list-none">
              <li className="p-2.5 rounded-xl bg-[#381932]/50 border border-[#FFF3E6]/10">
                <span className="font-bold text-[#DFBA70]">Cal/OSHA Title 8 §5141.1:</span> Mandates N95 respirator protective equipment (PPE) for outdoor employers when ambient PM2.5 AQI exceeds 151.
              </li>
              <li className="p-2.5 rounded-xl bg-[#381932]/50 border border-[#FFF3E6]/10">
                <span className="font-bold text-[#DFBA70]">ICAO / FAA CAT II/III Low-Visibility SOPs:</span> Anticipates +30 to 45 min ground turnaround delays during severe particulate/smog inversions due to reduced tarmac vehicle transit speeds and taxiway hold-short restrictions.
              </li>
              <li className="p-2.5 rounded-xl bg-[#381932]/50 border border-[#FFF3E6]/10">
                <span className="font-bold text-[#DFBA70]">Aircraft Maintenance Manual (AMM) Guidance:</span> Recommends expedited recirculation filter inspection when operating through heavy wildfire smoke or volcanic particulate zones.
              </li>
            </ul>
          </div>

          {/* Section 4: Architecture & Data Lineage */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-[#DFBA70]">
              <Database size={16} weight="bold" />
              <span>4. Data Engineering Lineage</span>
            </div>
            <p>
              Data originates from the <strong>OpenAQ Global Air Quality API</strong> (v2/v3), normalized via a <strong>Medallion Lakehouse Architecture</strong>:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 font-mono text-[10px] text-center">
              <div className="p-2 rounded-lg bg-[#381932] border border-[#FFF3E6]/15">
                <div className="font-bold text-[#DFBA70]">🥉 Bronze</div>
                <div className="text-[#FFF3E6]/60 mt-0.5">Partitioned Parquet + Raw JSON audit</div>
              </div>
              <div className="p-2 rounded-lg bg-[#381932] border border-[#FFF3E6]/15">
                <div className="font-bold text-[#DFBA70]">🥈 Silver (dbt)</div>
                <div className="text-[#FFF3E6]/60 mt-0.5">Deduplication &amp; Unit conversion</div>
              </div>
              <div className="p-2 rounded-lg bg-[#381932] border border-[#FFF3E6]/15">
                <div className="font-bold text-[#DFBA70]">🥇 Gold (DuckDB)</div>
                <div className="text-[#FFF3E6]/60 mt-0.5">Star Schema + EPA AQI Breakpoints</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#FFF3E6]/15 flex items-center justify-between text-[11px] text-[#FFF3E6]/60 bg-[#281224]">
          <span>Telemetry Batch Interval: 6 Hours</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-full bg-[#DFBA70] hover:bg-[#EAC885] text-[#281224] font-bold text-xs transition-colors cursor-pointer"
          >
            Acknowledge
          </button>
        </div>
      </div>
    </div>
  );
};
