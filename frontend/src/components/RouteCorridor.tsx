import React, { useState, useEffect, useRef, useCallback } from 'react';
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
} from '@phosphor-icons/react';
import { api, type LocationItem, type CorridorRiskResponse } from '../api';

interface RouteCorridorProps {
  locations: LocationItem[];
}

export const RouteCorridor: React.FC<RouteCorridorProps> = ({ locations }) => {
  // Derive natural defaults (prefer London -> New Delhi if present in warehouse)
  const london = locations.find((l) => l.location_name.toLowerCase().includes('london'));
  const delhi = locations.find((l) => l.location_name.toLowerCase().includes('delhi'));
  const defaultOrigin = london ? london.location_key : (locations[0]?.location_key || '');
  const defaultDest = delhi ? delhi.location_key : (locations[1]?.location_key || locations[0]?.location_key || '');

  const [selectedOrigin, setSelectedOrigin] = useState<string>('');
  const [selectedDest, setSelectedDest] = useState<string>('');
  const [corridor, setCorridor] = useState<CorridorRiskResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const validOrigin = locations.some((l) => l.location_key === selectedOrigin) ? selectedOrigin : '';
  const validDest = locations.some((l) => l.location_key === selectedDest) ? selectedDest : '';

  const originKey = validOrigin || defaultOrigin;
  const destKey = validDest || defaultDest;

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layersGroupRef = useRef<L.LayerGroup | null>(null);

  const fetchCorridorData = useCallback(async (origin: string, dest: string) => {
    if (!origin || !dest) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCorridorRisk(origin, dest);
      setCorridor(data);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to calculate corridor telemetry';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch corridor telemetry whenever origin or destination changes
  useEffect(() => {
    if (originKey && destKey) {
      fetchCorridorData(originKey, destKey);
    }
  }, [originKey, destKey, fetchCorridorData]);

  // Initialize Leaflet Map once with proper lifecycle cleanup
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [25, 30],
        zoom: 2,
        minZoom: 1,
        maxZoom: 14,
        zoomControl: false,
        attributionControl: false,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      const layersGroup = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
      layersGroupRef.current = layersGroup;

      const timer = setTimeout(() => {
        map.invalidateSize();
      }, 200);

      return () => {
        clearTimeout(timer);
        map.remove();
        mapInstanceRef.current = null;
        layersGroupRef.current = null;
      };
    }
  }, []);

  // Update Map Waypoints & Markers when corridor data changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layersGroupRef.current;

    if (!map || !layerGroup || !corridor) return;

    layerGroup.clearLayers();

    // Create polyline from geodesic waypoints
    const latlngs: L.LatLngExpression[] = corridor.waypoints.map((wp) => [wp.lat, wp.lon]);

    const routeLine = L.polyline(latlngs, {
      color: corridor.status_color || '#090D16',
      weight: 3.5,
      opacity: 0.85,
      dashArray: '8, 8',
    }).addTo(layerGroup);

    // Origin Marker (Departure Icon)
    const originIcon = L.divIcon({
      className: 'custom-hub-marker',
      html: `
        <div style="background: #090D16; border: 2.5px solid ${corridor.origin.color_hex}; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 14px rgba(0,0,0,0.3); color: #FFF; font-size: 15px;">
          🛫
        </div>
      `,
      iconSize: [34, 34],
      iconAnchor: [17, 17],
    });

    const originMarker = L.marker([corridor.origin.latitude, corridor.origin.longitude], {
      icon: originIcon,
    }).addTo(layerGroup);

    originMarker.bindPopup(`
      <div style="font-family: system-ui, sans-serif; padding: 4px; min-width: 140px;">
        <div style="font-size: 10px; text-transform: uppercase; color: #64748b; font-weight: bold;">Departure Hub</div>
        <div style="font-weight: 700; font-size: 14px; color: #090d16;">${corridor.origin.location_name}</div>
        <div style="margin-top: 4px; display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; background: ${corridor.origin.color_hex}; color: #FFF;">
          AQI ${corridor.origin.avg_aqi} (${corridor.origin.risk_tier})
        </div>
      </div>
    `);

    // Destination Marker (Arrival Icon)
    const destIcon = L.divIcon({
      className: 'custom-hub-marker',
      html: `
        <div style="background: #090D16; border: 2.5px solid ${corridor.destination.color_hex}; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 14px rgba(0,0,0,0.3); color: #FFF; font-size: 15px;">
          🛬
        </div>
      `,
      iconSize: [34, 34],
      iconAnchor: [17, 17],
    });

    const destMarker = L.marker([corridor.destination.latitude, corridor.destination.longitude], {
      icon: destIcon,
    }).addTo(layerGroup);

    destMarker.bindPopup(`
      <div style="font-family: system-ui, sans-serif; padding: 4px; min-width: 140px;">
        <div style="font-size: 10px; text-transform: uppercase; color: #64748b; font-weight: bold;">Arrival Hub</div>
        <div style="font-weight: 700; font-size: 14px; color: #090d16;">${corridor.destination.location_name}</div>
        <div style="margin-top: 4px; display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; background: ${corridor.destination.color_hex}; color: #FFF;">
          AQI ${corridor.destination.avg_aqi} (${corridor.destination.risk_tier})
        </div>
      </div>
    `);

    // Fit map bounds to view both hubs comfortably
    try {
      const bounds = routeLine.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 6 });
      }
    } catch {
      // Ignore initial bounds errors
    }

    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 150);

    return () => clearTimeout(timer);
  }, [corridor]);

  const handleSwap = () => {
    const temp = originKey;
    setSelectedOrigin(destKey);
    setSelectedDest(temp);
  };

  if (locations.length === 0) {
    return (
      <div className="bg-white rounded-2xl p-12 border border-slate-200/80 shadow-sm text-center">
        <div className="inline-flex p-3 rounded-2xl bg-slate-100 text-slate-700 animate-pulse mb-3">
          <NavigationArrow size={24} weight="bold" />
        </div>
        <h3 className="text-base font-bold text-slate-900">Loading Global Corridor Hubs...</h3>
        <p className="text-xs text-slate-500 mt-1">Connecting to analytical warehouse registry...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Route Control Header */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-6 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-[#090D16] text-white">
                <NavigationArrow size={16} weight="bold" />
              </span>
              <h2 className="font-display text-xl font-bold text-slate-900 tracking-tight">
                Logistics &amp; Flight Corridor Triage
              </h2>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Geodesic route risk modeling and automated ground crew advisories between major hubs.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {loading ? (
              <span className="px-3 py-1 rounded-full text-xs font-semibold text-slate-600 bg-slate-100 border border-slate-200 flex items-center gap-1.5">
                <ArrowClockwise size={13} className="animate-spin text-slate-500" />
                Calculating Flight Arc...
              </span>
            ) : corridor ? (
              <span
                className="px-3 py-1 rounded-full text-xs font-bold text-white shadow-sm flex items-center gap-1.5"
                style={{ backgroundColor: corridor.status_color }}
              >
                <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                {corridor.overall_status}
              </span>
            ) : null}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 font-medium flex items-center justify-between gap-3">
            <span>{error}</span>
            <button
              onClick={() => fetchCorridorData(originKey, destKey)}
              className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-1 flex-shrink-0"
            >
              <ArrowClockwise size={12} />
              Retry
            </button>
          </div>
        )}

        {/* Hub Selectors */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr,auto,1fr] items-center gap-4 mt-6">
          {/* Origin */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-mono uppercase tracking-wider text-slate-500 font-semibold flex items-center gap-1.5">
              <AirplaneTakeoff size={14} className="text-slate-700" />
              Departure Hub (Origin)
            </label>
            <select
              value={originKey}
              onChange={(e) => setSelectedOrigin(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-900 transition-all cursor-pointer"
            >
              {locations.map((loc) => (
                <option key={loc.location_key} value={loc.location_key}>
                  {loc.location_name} ({loc.country_code})
                </option>
              ))}
            </select>
          </div>

          {/* Swap Button */}
          <div className="flex justify-center pt-5">
            <button
              onClick={handleSwap}
              title="Swap Origin and Destination"
              className="p-2.5 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 hover:text-slate-950 transition-colors border border-slate-200 shadow-sm"
            >
              <ArrowsLeftRight size={18} weight="bold" />
            </button>
          </div>

          {/* Destination */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-mono uppercase tracking-wider text-slate-500 font-semibold flex items-center gap-1.5">
              <AirplaneLanding size={14} className="text-slate-700" />
              Arrival Terminal (Destination)
            </label>
            <select
              value={destKey}
              onChange={(e) => setSelectedDest(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-900 transition-all cursor-pointer"
            >
              {locations.map((loc) => (
                <option key={loc.location_key} value={loc.location_key}>
                  {loc.location_name} ({loc.country_code})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Corridor Map and Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Leaflet Geodesic Map */}
        <div className="lg:col-span-2 bg-white rounded-2xl p-4 border border-slate-200/80 shadow-sm flex flex-col">
          <div className="flex items-center justify-between px-2 pb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-semibold flex items-center gap-1.5">
              <Wind size={14} />
              Geodesic Flight Arc &amp; Atmospheric Chokepoints
            </span>
            {corridor && (
              <span className="text-xs font-mono text-slate-600 bg-slate-100 px-2.5 py-0.5 rounded-md font-semibold">
                {corridor.distance_km.toLocaleString()} km / {corridor.distance_nm.toLocaleString()} NM
              </span>
            )}
          </div>
          <div
            ref={mapContainerRef}
            className="w-full h-[460px] rounded-xl overflow-hidden border border-slate-100 relative z-0"
            style={{ isolation: 'isolate' }}
          />
        </div>

        {/* Operational Dispatcher Intelligence Panel */}
        <div className="space-y-4">
          {/* Risk Score Card */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
            <div className="text-[11px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
              Corridor Risk Exposure
            </div>
            <div className="mt-3 flex items-baseline gap-3">
              <span className="text-4xl font-display font-extrabold text-slate-950">
                {loading ? '—' : corridor?.corridor_risk_score}
              </span>
              <span className="text-xs text-slate-400 font-mono">/ 500 AQI</span>
            </div>
            <div className="mt-3 text-xs text-slate-600 leading-relaxed">
              Weighted composite evaluating departure dispatch (30%), arrival terminal exposure (50%), and peak route chokepoint (20%).
            </div>
          </div>

          {/* Departure vs Arrival Comparison */}
          {corridor ? (
            <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-sm space-y-4">
              <div className="text-[11px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
                Terminal Environmental Comparison
              </div>

              {/* Origin */}
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold text-slate-900">{corridor.origin.location_name}</div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    Primary: {corridor.origin.parameter_name.toUpperCase()}
                  </div>
                </div>
                <span
                  className="px-2.5 py-1 rounded-lg text-xs font-bold text-white font-mono"
                  style={{ backgroundColor: corridor.origin.color_hex }}
                >
                  AQI {corridor.origin.avg_aqi}
                </span>
              </div>

              {/* Destination */}
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold text-slate-900">{corridor.destination.location_name}</div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    Primary: {corridor.destination.parameter_name.toUpperCase()}
                  </div>
                </div>
                <span
                  className="px-2.5 py-1 rounded-lg text-xs font-bold text-white font-mono"
                  style={{ backgroundColor: corridor.destination.color_hex }}
                >
                  AQI {corridor.destination.avg_aqi}
                </span>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm text-center text-xs text-slate-400">
              Select terminals above to compare environmental parameters.
            </div>
          )}

          {/* Operational Advisory Checklist */}
          {corridor && (
            <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-sm">
              <div className="text-[11px] font-mono uppercase tracking-wider text-slate-500 font-semibold flex items-center gap-1.5 mb-3">
                <ShieldWarning size={14} className="text-amber-600" />
                Dispatcher Operational Advisories
              </div>
              <ul className="space-y-2.5">
                {corridor.recommendations.map((rec, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-700 leading-relaxed">
                    <span className="mt-0.5 text-amber-600 flex-shrink-0">
                      <CheckCircle size={14} weight="bold" />
                    </span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
