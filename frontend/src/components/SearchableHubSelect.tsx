import React, { useState, useRef, useEffect, useMemo } from 'react';
import { CaretDown, MagnifyingGlass, Check, X } from '@phosphor-icons/react';
import type { LocationItem } from '../api';

export interface SearchableHubSelectProps {
  label?: string;
  icon?: React.ElementType;
  val: string;
  setVal: (v: string) => void;
  locations: LocationItem[];
  placeholder?: string;
  className?: string;
}

export const SearchableHubSelect: React.FC<SearchableHubSelectProps> = ({
  label,
  icon: Icon,
  val,
  setVal,
  locations,
  placeholder = 'Select a hub...',
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Active selected location item
  const selectedLocation = useMemo(
    () => locations.find((l) => l.location_key === val) || null,
    [locations, val]
  );

  // Filter locations by name, country_name, or country_code
  const filteredLocations = useMemo(() => {
    if (!search.trim()) return locations;
    const q = search.toLowerCase().trim();
    return locations.filter(
      (l) =>
        l.location_name.toLowerCase().includes(q) ||
        (l.country_name && l.country_name.toLowerCase().includes(q)) ||
        (l.country_code && l.country_code.toLowerCase().includes(q))
    );
  }, [locations, search]);

  // Focus search input on open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setSearch('');
    }
  }, [isOpen]);

  // Close on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [isOpen]);

  // Close on Escape key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  const handleSelect = (key: string) => {
    setVal(key);
    setIsOpen(false);
  };

  return (
    <div className={`space-y-1.5 relative ${className}`} ref={containerRef} onKeyDown={handleKeyDown}>
      {label && (
        <label className="text-[11px] font-mono uppercase tracking-wider text-[#84657E] font-bold flex items-center gap-1.5">
          {Icon && <Icon size={14} className="text-[#381932]" weight="bold" />}
          {label}
        </label>
      )}

      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full bg-white border border-[#381932]/15 rounded-full px-4 py-2 text-xs font-semibold text-[#381932] flex items-center justify-between gap-2.5 shadow-2xs hover:border-[#381932] focus:outline-none focus:border-[#381932] focus:ring-1 focus:ring-[#381932]/10 transition-all cursor-pointer text-left"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2 truncate min-w-0">
          {Icon && !label && <Icon size={14} className="text-[#381932] shrink-0" weight="bold" />}
          {selectedLocation ? (
            <>
              <span className="truncate">{selectedLocation.location_name}</span>
              <span className="font-mono text-[10px] bg-[#381932]/8 text-[#583351] px-2 py-0.5 rounded-full font-bold shrink-0">
                {selectedLocation.country_code}
              </span>
            </>
          ) : (
            <span className="text-[#84657E] font-normal">{placeholder}</span>
          )}
        </div>
        <CaretDown
          size={13}
          weight="bold"
          className={`text-[#84657E] shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180 text-[#381932]' : ''}`}
        />
      </button>

      {/* Popover Dropdown */}
      {isOpen && (
        <div
          className="absolute left-0 top-full mt-1.5 w-full min-w-[280px] max-w-[420px] bg-white border border-[#381932]/15 rounded-2xl shadow-xl z-50 overflow-hidden flex flex-col p-2.5 animate-in fade-in zoom-in-95 duration-100"
          style={{ boxShadow: '0 12px 32px rgba(56, 25, 50, 0.16)' }}
        >
          {/* Instant Search Input */}
          <div className="relative mb-2">
            <MagnifyingGlass size={14} className="absolute left-3 top-2.5 text-[#84657E]" weight="bold" />
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Type city, hub, or country..."
              className="w-full pl-8 pr-7 py-1.5 text-xs bg-[#FBF4EC]/70 border border-[#381932]/15 rounded-full text-[#381932] placeholder:text-[#84657E] outline-none focus:border-[#381932] focus:bg-white font-medium transition-all"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-2 text-[#84657E] hover:text-[#381932] cursor-pointer"
                title="Clear search"
              >
                <X size={13} weight="bold" />
              </button>
            )}
          </div>

          {/* Results Summary */}
          <div className="text-[10px] font-mono text-[#84657E] px-2.5 py-1 flex items-center justify-between border-b border-[#381932]/8 pb-1.5 mb-1">
            <span>
              {search.trim() ? `${filteredLocations.length} Matching Hubs` : `All ${locations.length} Geohubs`}
            </span>
            <span className="text-[9px] uppercase tracking-wider text-[#84657E]/70 font-semibold">
              Instant Filter
            </span>
          </div>

          {/* Scrollable Location List */}
          <div className="max-h-60 overflow-y-auto space-y-0.5 pr-0.5 custom-scrollbar" role="listbox">
            {filteredLocations.length === 0 ? (
              <div className="py-8 text-center text-xs text-[#84657E] font-medium">
                No geohubs found matching &ldquo;{search}&rdquo;
              </div>
            ) : (
              filteredLocations.map((loc) => {
                const isSelected = loc.location_key === val;
                return (
                  <button
                    key={loc.location_key}
                    type="button"
                    onClick={() => handleSelect(loc.location_key)}
                    className={`w-full flex items-center justify-between px-3 py-2 text-left rounded-xl text-xs transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-[#381932] text-[#FFF3E6] font-bold shadow-2xs'
                        : 'text-[#381932] hover:bg-[#FBF4EC] font-medium'
                    }`}
                    role="option"
                    aria-selected={isSelected}
                  >
                    <div className="flex flex-col truncate pr-2">
                      <span className="truncate">{loc.location_name}</span>
                      {loc.country_name && (
                        <span className={`text-[10px] truncate ${isSelected ? 'text-[#FFF3E6]/80' : 'text-[#84657E]'}`}>
                          {loc.country_name}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span
                        className={`font-mono text-[10px] px-2 py-0.5 rounded-full font-bold ${
                          isSelected
                            ? 'bg-[#FFF3E6]/20 text-[#FFF3E6]'
                            : 'bg-[#381932]/8 text-[#583351]'
                        }`}
                      >
                        {loc.country_code}
                      </span>
                      {isSelected && <Check size={13} weight="bold" className="text-[#FFF3E6]" />}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
