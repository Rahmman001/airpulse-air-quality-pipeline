import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MagnifyingGlass, ArrowsClockwise } from '@phosphor-icons/react';
import { RISK_COLORS, RISK_TIERS } from '../api';
import type { MapStation } from '../api';

interface RiskMapProps {
  stations: MapStation[];
  onSelectStation?: (station: MapStation | string) => void;
}

export const RiskMap: React.FC<RiskMapProps> = ({ stations, onSelectStation }) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);
  const markersByLocationKey = useRef<Map<string, L.CircleMarker>>(new Map());

  const [searchQuery, setSearchQuery] = useState('');
  const [matchingStations, setMatchingStations] = useState<MapStation[]>([]);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [22.0, 20.0],
        zoom: 2,
        minZoom: 2,
        maxZoom: 16,
        attributionControl: false,
      });

      // Clean, reliable OpenStreetMap basemap with zero watermarks and no API keys needed
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        subdomains: ['a', 'b', 'c'],
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      const layerGroup = L.layerGroup().addTo(map);
      layerGroupRef.current = layerGroup;
      mapInstanceRef.current = map;

      setTimeout(() => {
        map.invalidateSize();
      }, 100);
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update Markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layerGroupRef.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();
    markersByLocationKey.current.clear();

    const validStations = stations.filter(
      (s) => s.latitude !== null && s.longitude !== null && !isNaN(Number(s.latitude)) && !isNaN(Number(s.longitude))
    );

    if (validStations.length === 0) return;

    const bounds = L.latLngBounds([]);

    validStations.forEach((station) => {
      const lat = Number(station.latitude);
      const lon = Number(station.longitude);
      const tierColor = station.color_hex || RISK_COLORS[station.risk_tier] || '#708090';
      const baseRadius = Math.min(18, Math.max(7, (station.avg_aqi || 50) / 16));
      const cityName = station.city_name || station.location_name;
      const isAggregated = station.city_stations_count && station.city_stations_count > 1;

      const marker = L.circleMarker([lat, lon], {
        radius: baseRadius,
        fillColor: tierColor,
        color: '#FFFFFF',
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.88,
      });

      // Rich Instant Hover Tooltip showing City Name, Station count, and live AQI
      const tooltipContent = `
        <div style="display: flex; flex-direction: column; gap: 3px; min-width: 140px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
            <span style="font-weight: 800; font-size: 0.92rem; color: #FFFFFF; letter-spacing: -0.01em;">
              ${cityName}
            </span>
            <span style="font-size: 0.68rem; font-family: 'JetBrains Mono', monospace; font-weight: 800; padding: 2px 6px; border-radius: 4px; background: ${tierColor}; color: #FFFFFF;">
              ${Math.round(station.avg_aqi)} AQI
            </span>
          </div>
          <div style="font-size: 0.72rem; color: #94A3B8; font-weight: 500;">
            ${isAggregated ? `${station.city_stations_count} Stations Averaged` : station.country_name}
          </div>
          <div style="display: flex; align-items: center; gap: 6px; font-size: 0.68rem; color: #CBD5E1; font-family: 'JetBrains Mono', monospace; margin-top: 2px; border-top: 1px solid rgba(255,255,255,0.12); padding-top: 3px;">
            <span>${station.country_name}</span>
            <span>•</span>
            <span style="color: #38BDF8; font-weight: 700;">${station.parameter_name.toUpperCase()}</span>
            <span>•</span>
            <span>${station.risk_tier}</span>
          </div>
        </div>
      `;

      marker.bindTooltip(tooltipContent, {
        permanent: false,
        direction: 'top',
        offset: [0, -baseRadius],
        className: 'custom-station-tooltip',
        opacity: 1,
      });

      // Hover expansion micro-interaction
      marker.on('mouseover', () => {
        marker.setRadius(baseRadius + 3);
        marker.setStyle({ weight: 2.5, color: '#0F172A', fillOpacity: 1.0 });
      });

      marker.on('mouseout', () => {
        marker.setRadius(baseRadius);
        marker.setStyle({ weight: 1.5, color: '#FFFFFF', fillOpacity: 0.88 });
      });

      // Click Detailed Modal Popup
      const popupContent = document.createElement('div');
      popupContent.style.fontFamily = "'Plus Jakarta Sans', -apple-system, sans-serif";
      popupContent.style.padding = '4px 2px';
      popupContent.innerHTML = `
        <div style="font-weight: 800; font-size: 1.05rem; color: #0F172A; margin-bottom: 2px;">
          ${cityName}
        </div>
        <div style="font-size: 0.75rem; color: #64748B; margin-bottom: 8px;">
          ${station.country_name} • <span style="font-family: 'JetBrains Mono', monospace;">${isAggregated ? `${station.city_stations_count} stations averaged` : '1 station'}</span>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 4px; padding: 4px 0; border-bottom: 1px solid #E2E8F0;">
          <span style="font-size: 0.7rem; color: #64748B; text-transform: uppercase;">Primary Pollutant:</span>
          <span style="font-weight: 700; font-size: 0.76rem; font-family: 'JetBrains Mono', monospace; color: #0F172A;">${station.parameter_name.toUpperCase()}</span>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 4px; padding: 4px 0;">
          <span style="font-size: 0.7rem; color: #64748B; text-transform: uppercase;">City Average AQI:</span>
          <span style="font-weight: 800; font-size: 1.1rem; font-family: 'JetBrains Mono', monospace; color: #0F172A;">${Math.round(station.avg_aqi)}</span>
        </div>
        <div style="display: block; width: 100%; text-align: center; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #FFFFFF; background: ${tierColor}; padding: 4px 6px; border-radius: 6px; margin-bottom: 8px;">
          ${station.risk_tier}
        </div>
        <button id="view-trends-${station.location_key}" style="display: flex; align-items: center; justify-content: center; width: 100%; padding: 6px 10px; background: #0F172A; color: #FFFFFF; font-size: 0.72rem; font-weight: 700; border: none; border-radius: 6px; cursor: pointer; transition: background 0.15s;">
          Explore 72h Timeline →
        </button>
      `;

      marker.bindPopup(popupContent);

      marker.on('popupopen', () => {
        const btn = document.getElementById(`view-trends-${station.location_key}`);
        if (btn) {
          btn.onclick = () => {
            if (onSelectStation) {
              onSelectStation(station);
            }
          };
        }
      });

      marker.addTo(layerGroup);
      markersByLocationKey.current.set(station.location_key, marker);
      bounds.extend([lat, lon]);
    });

    if (validStations.length > 0 && bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 5 });
    }

    setTimeout(() => {
      map.invalidateSize();
    }, 150);
  }, [stations, onSelectStation]);

  // Live search and fly-to station/city
  const handleSearchChange = (q: string) => {
    setSearchQuery(q);
    if (!q.trim()) {
      setMatchingStations([]);
      return;
    }
    const cleanQ = q.toLowerCase();
    const matches = stations
      .filter((s) => {
        const city = (s.city_name || '').toLowerCase();
        const loc = s.location_name.toLowerCase();
        const country = s.country_name.toLowerCase();
        return city.includes(cleanQ) || loc.includes(cleanQ) || country.includes(cleanQ);
      })
      .slice(0, 6);
    setMatchingStations(matches);
  };

  const handleSelectCityFromSearch = (station: MapStation) => {
    setSearchQuery(station.city_name || station.location_name);
    setMatchingStations([]);
    const map = mapInstanceRef.current;
    if (!map || station.latitude === null || station.longitude === null) return;

    map.flyTo([Number(station.latitude), Number(station.longitude)], 10, {
      duration: 1.2,
    });

    const marker = markersByLocationKey.current.get(station.location_key);
    if (marker) {
      setTimeout(() => {
        marker.openPopup();
      }, 1250);
    }
  };

  const resetView = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    setSearchQuery('');
    setMatchingStations([]);
    map.flyTo([22.0, 20.0], 2, { duration: 1.0 });
  };

  return (
    <div className="minimal-card p-6 md:p-8 mb-10">
      {/* Header with Search and Live Status */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse ring-4 ring-emerald-100" />
          <h2 className="font-display text-xl md:text-2xl text-slate-950 font-bold tracking-tight">
            Global City AQI Radar
          </h2>
          <span className="text-xs font-mono text-slate-500 font-semibold bg-slate-100 px-2.5 py-0.5 rounded-full border border-slate-200">
            {stations.length} Monitored Cities
          </span>
        </div>

        {/* Quick City Jump Bar */}
        <div className="flex items-center gap-2.5 relative">
          <div className="relative">
            <MagnifyingGlass size={14} className="absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Find city (e.g. Delhi, London, Tokyo)..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400 rounded-lg focus:border-slate-800 outline-none w-64 font-medium shadow-2xs transition-all"
            />
            {matchingStations.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 overflow-hidden py-1">
                {matchingStations.map((s) => (
                  <button
                    key={s.location_key}
                    onClick={() => handleSelectCityFromSearch(s)}
                    className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50 flex items-center justify-between transition-colors"
                  >
                    <div>
                      <strong className="text-slate-900 font-semibold">{s.city_name || s.location_name}</strong>
                      <span className="text-slate-500 text-[11px] block">{s.country_name} • {s.city_stations_count && s.city_stations_count > 1 ? `${s.city_stations_count} stations averaged` : '1 station'}</span>
                    </div>
                    <span
                      className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded text-white"
                      style={{ backgroundColor: s.color_hex || RISK_COLORS[s.risk_tier] }}
                    >
                      {Math.round(s.avg_aqi)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={resetView}
            title="Reset to Global World View"
            className="p-1.5 bg-white border border-slate-200 text-slate-600 hover:text-slate-950 hover:border-slate-800 rounded-lg transition-colors shadow-2xs"
          >
            <ArrowsClockwise size={16} />
          </button>
        </div>
      </div>

      {/* Map Surface */}
      <div 
        className="w-full h-[480px] relative border border-slate-200 rounded-xl overflow-hidden shadow-xs z-10"
        style={{ isolation: 'isolate', position: 'relative' }}
      >
        <div 
          ref={mapContainerRef} 
          className="w-full h-full relative" 
          style={{ width: '100%', height: '480px', position: 'relative', overflow: 'hidden' }}
        />
      </div>

      {/* Modern Legend */}
      <div className="flex flex-wrap items-center justify-between gap-3 mt-4 pt-4 border-t border-slate-200/80">
        <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wider flex items-center gap-2 font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-slate-950" />
          <span>Standard Risk Scale:</span>
        </span>
        <div className="flex flex-wrap gap-4">
          {RISK_TIERS.map((tier) => {
            const color = RISK_COLORS[tier];
            return (
              <div
                key={tier}
                className="flex items-center gap-2 text-xs"
              >
                <span
                  className="w-2.5 h-2.5 rounded-full ring-1 ring-black/10"
                  style={{ backgroundColor: color }}
                />
                <span className="text-xs font-medium text-slate-700">{tier}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

