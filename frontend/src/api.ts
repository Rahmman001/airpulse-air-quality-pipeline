/**
 * AirPulse API Client and Data Types
 * Supports Dual-Mode: Live FastAPI Analytical Server or Zero-Cost Static Edge (Cloudflare Pages)
 */

export interface WorstReading {
  location_key: string;
  location_name: string;
  country_name: string;
  parameter_name: string;
  avg_aqi: number;
  risk_tier: string;
}

export interface KpiData {
  locations_monitored: number;
  worst_current_reading: WorstReading | null;
  hazardous_zones_count: number;
  latest_data_date: string;
  latest_data_time?: string;
  data_source_label: string;
}

export interface LocationItem {
  location_key: string;
  location_name: string;
  country_code: string;
  country_name: string;
  latitude: number | null;
  longitude: number | null;
}

export interface MapStation {
  location_key: string;
  location_name: string;
  city_name?: string;
  country_name: string;
  latitude: number | null;
  longitude: number | null;
  parameter_name: string;
  avg_aqi: number;
  city_avg_aqi?: number;
  city_stations_count?: number;
  risk_tier: string;
  color_hex: string;
  radius: number;
}

export interface Pollutant {
  pollutant_key: string;
  parameter_name: string;
  pollutant_display_name: string;
  standard_unit: string;
}

export interface TrendPoint {
  measured_at_utc: string;
  aqi: number;
  raw_value: number;
  value_ugm3: number;
  risk_tier: string;
}

export interface AlertItem {
  location_name: string;
  country_name: string;
  parameter_name: string;
  avg_aqi: number;
  risk_tier: string;
  reading_count: number;
  flagged_reading_count: number;
  color_hex: string;
}

export interface AlertsResponse {
  min_tier: string;
  threshold_aqi: number;
  alert_count: number;
  alerts: AlertItem[];
}

export interface UnmonitoredLocation {
  location_name: string;
  country_name: string;
  country_code: string;
  data_status: string;
}

export interface CorridorHub {
  location_key: string;
  location_name: string;
  country_name: string;
  country_code: string;
  latitude: number;
  longitude: number;
  parameter_name: string;
  avg_aqi: number;
  risk_tier: string;
  color_hex: string;
}

export interface Waypoint {
  lat: number;
  lon: number;
}

export interface CorridorRiskResponse {
  origin: CorridorHub;
  destination: CorridorHub;
  distance_km: number;
  distance_nm: number;
  corridor_risk_score: number;
  overall_status: string;
  risk_level: string;
  status_color: string;
  recommendations: string[];
  waypoints: Waypoint[];
}

export const RISK_TIERS = [
  'Good',
  'Moderate',
  'Unhealthy for Sensitive Groups',
  'Unhealthy',
  'Very Unhealthy',
  'Hazardous',
] as const;

export const ALERT_FILTER_TIERS = [
  'All',
  'Hazardous',
  'Very Unhealthy',
  'Unhealthy',
  'Unhealthy for Sensitive Groups',
  'Moderate',
  'Good',
] as const;

export const RISK_COLORS: Record<string, string> = {
  All: '#381932',
  Good: '#059669',
  Moderate: '#D97706',
  'Unhealthy for Sensitive Groups': '#EA580C',
  Unhealthy: '#DC2626',
  'Very Unhealthy': '#991B1B',
  Hazardous: '#581C87',
  Unmonitored: '#94A3B8',
};

const API_BASE = '/api/v1';

// In-memory cache for static snapshots on Cloudflare Pages
let _cachedTrends: Record<string, TrendPoint[]> | null = null;
let _cachedAlerts: Record<string, AlertsResponse> | null = null;
let _cachedStations: MapStation[] | null = null;
let _cachedLocations: LocationItem[] | null = null;

const isJson = (res: Response) => res.ok && (res.headers.get('content-type') || '').includes('application/json');

async function fetchJsonWithFallback<T>(apiEndpoint: string, staticPath: string): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${apiEndpoint}`);
    if (isJson(res)) {
      const data = await res.json();
      if (!Array.isArray(data) || data.length > 0) return data as T;
    }
  } catch {}
  const staticRes = await fetch(staticPath);
  if (!staticRes.ok) throw new Error(`Failed to load ${staticPath}: ${staticRes.statusText}`);
  return (await staticRes.json()) as T;
}

// Client-side geodesic calculation fallback for static Cloudflare Pages hosting
function calculateClientCorridor(
  originLoc: LocationItem,
  destLoc: LocationItem,
  originStation?: MapStation,
  destStation?: MapStation,
): CorridorRiskResponse {
  const { latitude: lat1 = 0, longitude: lon1 = 0 } = originLoc;
  const { latitude: lat2 = 0, longitude: lon2 = 0 } = destLoc;

  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dphi = toRad((lat2 || 0) - (lat1 || 0));
  const dlam = toRad((lon2 || 0) - (lon1 || 0));
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(toRad(lat1 || 0)) * Math.cos(toRad(lat2 || 0)) * Math.sin(dlam / 2) ** 2;
  const distKm = Math.round(2 * 6371 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)) * 10) / 10;
  const distNm = Math.round(distKm * 0.539957 * 10) / 10;

  const aqi1 = originStation?.avg_aqi || 0;
  const aqi2 = destStation?.avg_aqi || 0;
  const tier1 = originStation?.risk_tier || 'Unmonitored';
  const tier2 = destStation?.risk_tier || 'Unmonitored';
  const corridorScore = Math.round((0.3 * aqi1 + 0.5 * aqi2 + 0.2 * Math.max(aqi1, aqi2)) * 10) / 10;

  const [overallStatus, riskLevel, statusColor] =
    corridorScore > 200 ? ['Severe Terminal Disruption Alert', 'Critical', '#991B1B'] :
    corridorScore > 150 ? ['High Operational Impact', 'High', '#DC2626'] :
    corridorScore > 100 ? ['Elevated Chokepoint Advisory', 'Elevated', '#EA580C'] :
    corridorScore > 50  ? ['Moderate Transit Risk', 'Moderate', '#D97706'] :
    ['Optimal Flight Conditions', 'Low', '#059669'];

  const recommendations = [
    tier1 === 'Unmonitored' && `Notice: Departure terminal '${originLoc.location_name}' is currently unmonitored; deploy portable sensor telemetry.`,
    tier2 === 'Unmonitored' && `Notice: Arrival terminal '${destLoc.location_name}' is currently unmonitored; verify local regional advisory.`,
    (aqi2 > 150 || aqi1 > 150) && 'Mandate N95 respirator PPE for outdoor cargo ramp and tarmac operations.',
    aqi2 > 200 && 'Trigger Aircraft Environmental Control (ECS) cabin HEPA filter inspection upon arrival.',
    Math.max(aqi1, aqi2) > 175 && 'Anticipate ground turnaround delays (+30 to 45 mins) due to reduced ground visibility.',
    aqi2 > 100 && aqi2 <= 150 && 'Notify dispatch to activate sensitive-group ramp crew rotation intervals.',
  ].filter(Boolean) as string[];

  if (!recommendations.length) {
    recommendations.push('Standard dispatch parameters: No environmental operational restrictions along flight path.');
  }

  const waypoints: Waypoint[] = Array.from({ length: 41 }, (_, i) => {
    const f = i / 40;
    return {
      lat: +((lat1 || 0) + f * ((lat2 || 0) - (lat1 || 0)) + Math.sin(f * Math.PI) * Math.min(12, distKm / 800)).toFixed(4),
      lon: +((lon1 || 0) + f * ((lon2 || 0) - (lon1 || 0))).toFixed(4),
    };
  });

  const createHub = (loc: LocationItem, st?: MapStation, aqi = 0, tier = 'Unmonitored'): CorridorHub => ({
    location_key: loc.location_key,
    location_name: loc.location_name,
    country_name: loc.country_name,
    country_code: loc.country_code,
    latitude: loc.latitude || 0,
    longitude: loc.longitude || 0,
    parameter_name: st?.parameter_name || 'unmonitored',
    avg_aqi: aqi,
    risk_tier: tier,
    color_hex: RISK_COLORS[tier] || '#94A3B8',
  });

  return {
    origin: createHub(originLoc, originStation, aqi1, tier1),
    destination: createHub(destLoc, destStation, aqi2, tier2),
    distance_km: distKm,
    distance_nm: distNm,
    corridor_risk_score: corridorScore,
    overall_status: overallStatus,
    risk_level: riskLevel,
    status_color: statusColor,
    recommendations,
    waypoints,
  };
}

export const api = {
  getKpis: () => fetchJsonWithFallback<KpiData>('/kpis', '/data/kpis.json'),
  getLocations: async () => (_cachedLocations ??= await fetchJsonWithFallback<LocationItem[]>('/locations', '/data/locations.json')),
  getUnmonitoredLocations: () => fetchJsonWithFallback<UnmonitoredLocation[]>('/locations/unmonitored', '/data/unmonitored.json'),
  getPollutants: () => fetchJsonWithFallback<Pollutant[]>('/pollutants', '/data/pollutants.json'),
  getMapStations: async () => (_cachedStations ??= await fetchJsonWithFallback<MapStation[]>('/aqi/map', '/data/map_stations.json')),

  getTrends: async (loc: string, pol: string): Promise<TrendPoint[]> => {
    try {
      const res = await fetch(`${API_BASE}/aqi/trends?location_key=${encodeURIComponent(loc)}&pollutant_key=${encodeURIComponent(pol)}`);
      if (isJson(res)) return (await res.json()) as TrendPoint[];
    } catch {}
    _cachedTrends ??= await fetch('/data/trends.json').then((r) => r.ok ? r.json() : {}).catch(() => ({}));
    return _cachedTrends?.[`${loc}_${pol}`] || [];
  },

  getAlerts: async (minTier: string): Promise<AlertsResponse> => {
    try {
      const res = await fetch(`${API_BASE}/alerts?min_tier=${encodeURIComponent(minTier)}`);
      if (isJson(res)) return (await res.json()) as AlertsResponse;
    } catch {}
    _cachedAlerts ??= await fetch('/data/alerts.json').then((r) => r.ok ? r.json() : {}).catch(() => ({}));
    return _cachedAlerts?.[minTier] || _cachedAlerts?.['All'] || { min_tier: minTier, threshold_aqi: 0, alert_count: 0, alerts: [] };
  },

  getExportUrl: (minTier: string) => `${API_BASE}/alerts/export?min_tier=${encodeURIComponent(minTier)}`,

  getCorridorRisk: async (originKey: string, destKey: string): Promise<CorridorRiskResponse> => {
    try {
      const res = await fetch(`${API_BASE}/corridors/risk?origin_key=${encodeURIComponent(originKey)}&destination_key=${encodeURIComponent(destKey)}`);
      if (isJson(res)) return (await res.json()) as CorridorRiskResponse;
    } catch {}

    const [locations, stations] = await Promise.all([api.getLocations(), api.getMapStations()]);
    const originLoc = locations.find((l) => l.location_key === originKey || l.location_name.toLowerCase() === originKey.toLowerCase())
      || locations.find((l) => /london/i.test(l.location_name)) || locations[0];
    const destLoc = locations.find((l) => l.location_key === destKey || l.location_name.toLowerCase() === destKey.toLowerCase())
      || locations.find((l) => /delhi/i.test(l.location_name)) || locations[1];

    if (!originLoc || !destLoc) throw new Error(`Terminals not found: ${originKey} -> ${destKey}`);

    const originSt = stations.find((s) => s.location_key === originLoc.location_key);
    const destSt = stations.find((s) => s.location_key === destLoc.location_key);
    return calculateClientCorridor(originLoc, destLoc, originSt, destSt);
  },
};
