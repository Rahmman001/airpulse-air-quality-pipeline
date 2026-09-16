import React, { useState, useEffect, useRef, useMemo } from 'react';
import L from 'leaflet';
import {
  AirplaneTakeoff,
  AirplaneLanding,
  ArrowsLeftRight,
  ShieldWarning,
  CheckCircle,
  Wind,
  NavigationArrow,
  ArrowClockwise,
  BookOpen,
} from '@phosphor-icons/react';
import { api, type LocationItem, type CorridorRiskResponse, type UnmonitoredLocation } from '../api';
import { SearchableHubSelect } from './SearchableHubSelect';
import { MethodologyModal } from './MethodologyModal';

interface RouteCorridorProps {
  locations: LocationItem[];
  unmonitored?: UnmonitoredLocation[];
}

export const RouteCorridor: React.FC<RouteCorridorProps> = ({ locations, unmonitored }) => {
  const [origin, setOrigin] = useState('');
  const [dest, setDest] = useState('');
  const [corridor, setCorridor] = useState<CorridorRiskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMethodologyOpen, setIsMethodologyOpen] = useState(false);

  const unmonitoredNames = useMemo(
    () => new Set(unmonitored?.map((u) => u.location_name.toLowerCase()) || []),
    [unmonitored]
  );

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layersGroupRef = useRef<L.LayerGroup | null>(null);

  const originKey = origin || locations.find((l) => /london/i.test(l.location_name))?.location_key || locations[0]?.location_key || '';
  const destKey = dest || locations.find((l) => /delhi/i.test(l.location_name))?.location_key || locations[1]?.location_key || locations[0]?.location_key || '';

  // Fetch corridor telemetry
  useEffect(() => {
    if (!originKey || !destKey) return;
    let active = true;
    setLoading(true);
    setError(null);

    api.getCorridorRisk(originKey, destKey)
      .then((data) => { if (active) { setCorridor(data); setLoading(false); } })
      .catch((err) => { if (active) { setError(err instanceof Error ? err.message : 'Telemetry failed'); setLoading(false); } });

    return () => { active = false; };
  }, [originKey, destKey]);

  // Leaflet lifecycle
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, { center: [25, 30], zoom: 2, minZoom: 1, maxZoom: 14, zoomControl: false, attributionControl: false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    layersGroupRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;
    setTimeout(() => map.invalidateSize(), 200);

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      layersGroupRef.current = null;
    };
  }, [locations.length]);

  // Update Waypoints & Markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = layersGroupRef.current;
    if (!map || !group || !corridor) return;

    group.clearLayers();

    const latlngs: L.LatLngExpression[] = corridor.waypoints
      .filter((w) => typeof w.lat === 'number' && !isNaN(w.lat) && typeof w.lon === 'number' && !isNaN(w.lon))
      .map((w) => [w.lat, w.lon]);
    const routeLine = L.polyline(latlngs, { color: corridor.status_color || '#381932', weight: 3.5, opacity: 0.85, dashArray: '8, 8' }).addTo(group);

    const departureSvg = `<svg width="15" height="15" viewBox="0 0 256 256" fill="currentColor"><path d="M247.16,145.49a16,16,0,0,0-15.74-6.85L172.58,146l-41.9-57.61a8,8,0,0,0-6.49-3.28H104a8,8,0,0,0-7.39,11.08l21.28,50.77-40.42,7.35L57,137.66A8,8,0,0,0,51.34,135H32a8,8,0,0,0-7.07,11.75l17.78,33.78a16.14,16.14,0,0,0,13.88,8.59l159-28.91A16,16,0,0,0,247.16,145.49ZM216,216H40a8,8,0,0,1,0-16H216a8,8,0,0,1,0,16Z"/></svg>`;
    const arrivalSvg = `<svg width="15" height="15" viewBox="0 0 256 256" fill="currentColor"><path d="M239.38,155.19l-37.49-51.55a8,8,0,0,0-6.48-3.28H176a8,8,0,0,0-7.38,11.09l21.27,50.76-40.42,7.35L108,137.66A8,8,0,0,0,102.34,135H83a8,8,0,0,0-7.07,11.75l17.78,33.78a16.14,16.14,0,0,0,13.88,8.59l107.56-19.56,8.23,11.32A16,16,0,0,0,236.4,186l14.28-7.78A16,16,0,0,0,257,163.42l-5-9.35A16.07,16.07,0,0,0,239.38,155.19ZM216,216H40a8,8,0,0,1,0-16H216a8,8,0,0,1,0,16Z"/></svg>`;

    [
      { hub: corridor.origin, svg: departureSvg, role: 'Departure Hub' },
      { hub: corridor.destination, svg: arrivalSvg, role: 'Arrival Hub' },
    ].forEach(({ hub, svg, role }) => {
      if (typeof hub.latitude === 'number' && !isNaN(hub.latitude) && typeof hub.longitude === 'number' && !isNaN(hub.longitude)) {
        L.marker([hub.latitude, hub.longitude], {
          icon: L.divIcon({
            className: 'custom-hub-marker',
            html: `<div style="background:#281224;border:2px solid ${hub.color_hex};width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 16px rgba(56,25,50,0.4);color:#FFF3E6;">${svg}</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
          }),
        }).bindPopup(`
          <div style="font-family:'Satoshi',sans-serif;padding:6px;min-width:145px;">
            <div style="font-size:10px;text-transform:uppercase;color:#84657E;letter-spacing:0.06em;font-weight:700;">${role}</div>
            <div style="font-family:'Playfair Display',serif;font-weight:700;font-size:15px;color:#381932;margin-top:2px;">${hub.location_name}</div>
            <div style="margin-top:6px;display:inline-block;padding:3px 8px;border-radius:9999px;font-size:11px;font-weight:700;font-family:'JetBrains Mono',monospace;background:${hub.color_hex};color:#FFF;">
              AQI ${hub.avg_aqi} • ${hub.risk_tier}
            </div>
          </div>
        `).addTo(group);
      }
    });

    try {
      const bounds = routeLine.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [50, 50], maxZoom: 6 });
    } catch {}
    setTimeout(() => map.invalidateSize(), 150);
  }, [corridor]);

  const handleSwap = () => {
    setOrigin(destKey);
    setDest(originKey);
  };

  if (!locations.length) {
    return (
      <div className="minimal-card p-12 text-center text-xs text-[#84657E] font-mono">
        Loading Global Corridor Hubs...
      </div>
    );
  }

  return (
    <div className="space-y-6 mb-12">
      {/* Route Control Header */}
      <div className="minimal-card p-6 md:p-8 relative z-20">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-6 border-b border-[#381932]/10">
          <div>
            <div className="flex items-center gap-3">
              <span className="p-2 rounded-xl bg-[#381932] text-[#FFF3E6] shadow-xs">
                <NavigationArrow size={18} weight="bold" />
              </span>
              <h2 className="font-luxury text-xl md:text-2xl font-bold text-[#381932] tracking-tight">
                Logistics &amp; Flight Corridor Triage
              </h2>
            </div>
            <p className="text-xs text-[#84657E] mt-1.5 leading-relaxed">
              Geodesic route risk modeling and automated ground crew advisories between major global hubs.
            </p>
            <div className="flex flex-wrap items-center gap-2.5 mt-2.5">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#381932]/5 border border-[#381932]/15 text-[11px] text-[#583351] font-mono font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-[#DFBA70]" />
                Scope: Terminal Airspace (&lt;10,000 ft AGL) &amp; Tarmac Operations
              </span>
              <button
                onClick={() => setIsMethodologyOpen(true)}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#84657E] hover:text-[#381932] transition-colors cursor-pointer underline decoration-dotted underline-offset-2"
                title="View mathematical weighting formula and regulatory citations"
              >
                <BookOpen size={13} weight="bold" className="text-[#DFBA70]" />
                Methodology &amp; Standards
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {loading ? (
              <span className="px-3.5 py-1.5 rounded-full text-xs font-semibold text-[#583351] bg-[#FBF4EC] border border-[#381932]/10 flex items-center gap-2">
                <ArrowClockwise size={13} className="animate-spin text-[#84657E]" />
                Calculating Flight Arc...
              </span>
            ) : corridor ? (
              <span className="px-3.5 py-1.5 rounded-full text-xs font-bold text-white shadow-sm flex items-center gap-2" style={{ backgroundColor: corridor.status_color }}>
                <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                {corridor.overall_status}
              </span>
            ) : null}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 font-medium flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setOrigin(originKey)} className="px-3 py-1 bg-rose-600 text-white rounded-full text-[11px] font-semibold flex items-center gap-1 cursor-pointer">
              <ArrowClockwise size={12} /> Retry
            </button>
          </div>
        )}

        {/* Hub Selectors */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr,auto,1fr] items-center gap-4 mt-6">
          <SearchableHubSelect
            label="Departure Hub (Origin)"
            icon={AirplaneTakeoff}
            val={originKey}
            setVal={setOrigin}
            locations={locations}
            unmonitoredNames={unmonitoredNames}
          />
          <div className="flex justify-center md:pt-6">
            <button 
              onClick={handleSwap} 
              title="Swap Hubs" 
              className="p-3 rounded-full bg-white hover:bg-[#FBF4EC] text-[#381932] border border-[#381932]/15 shadow-2xs transition-colors cursor-pointer"
            >
              <ArrowsLeftRight size={18} weight="bold" />
            </button>
          </div>
          <SearchableHubSelect
            label="Arrival Terminal (Destination)"
            icon={AirplaneLanding}
            val={destKey}
            setVal={setDest}
            locations={locations}
            unmonitoredNames={unmonitoredNames}
          />
        </div>
      </div>

      {/* Corridor Map & Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 minimal-card p-4 md:p-6 flex flex-col">
          <div className="flex items-center justify-between px-2 pb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-[#84657E] font-semibold flex items-center gap-1.5">
              <Wind size={14} className="text-[#381932]" />
              Geodesic Flight Arc &amp; Atmospheric Chokepoints
            </span>
            {corridor && (
              <span className="text-xs font-mono text-[#583351] bg-[#FBF4EC] border border-[#381932]/10 px-3 py-1 rounded-full font-semibold">
                {corridor.distance_km.toLocaleString()} km / {corridor.distance_nm.toLocaleString()} NM
              </span>
            )}
          </div>
          <div ref={mapContainerRef} className="w-full h-[460px] rounded-2xl overflow-hidden border border-[#381932]/12 relative z-0" style={{ isolation: 'isolate' }} />
        </div>

        {/* Intelligence Panel */}
        <div className="space-y-4">
          <div className="minimal-card p-6">
            <div className="text-[11px] font-mono uppercase tracking-wider text-[#84657E] font-bold">Corridor Risk Exposure</div>
            <div className="mt-3 flex items-baseline gap-3">
              <span className="text-5xl font-luxury font-bold text-[#381932] tracking-tight">{loading ? '—' : corridor?.corridor_risk_score}</span>
              <span className="text-xs text-[#84657E] font-mono">/ 500 AQI</span>
            </div>
            <div className="mt-3 text-xs text-[#583351] leading-relaxed font-medium">
              Weighted composite evaluating departure dispatch (30%), arrival terminal exposure (50%), and peak route chokepoint (20%).
            </div>
          </div>

          {corridor && (
            <>
              <div className="minimal-card p-5 space-y-3">
                <div className="text-[11px] font-mono uppercase tracking-wider text-[#84657E] font-bold">Terminal Environmental Comparison</div>
                {[corridor.origin, corridor.destination].map((h) => (
                  <div key={h.location_key} className="p-3.5 rounded-2xl bg-[#FBF4EC] border border-[#381932]/8 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-bold text-[#381932]">{h.location_name}</div>
                      <div className="text-[11px] text-[#84657E] font-mono">Primary: {h.parameter_name.toUpperCase()}</div>
                    </div>
                    <span className="px-3 py-1 rounded-full text-xs font-bold text-white font-mono" style={{ backgroundColor: h.color_hex }}>
                      AQI {h.avg_aqi}
                    </span>
                  </div>
                ))}
              </div>

              <div className="minimal-card p-5">
                <div className="text-[11px] font-mono uppercase tracking-wider text-[#84657E] font-bold flex items-center gap-1.5 mb-3">
                  <ShieldWarning size={14} className="text-amber-700" />
                  Dispatcher Operational Advisories
                </div>
                <ul className="space-y-2.5">
                  {corridor.recommendations.map((rec, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-xs text-[#381932] leading-relaxed font-medium">
                      <CheckCircle size={14} weight="bold" className="mt-0.5 text-amber-700 shrink-0" />
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </div>
      <MethodologyModal isOpen={isMethodologyOpen} onClose={() => setIsMethodologyOpen(false)} />
    </div>
  );
};
