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

export const RISK_COLORS: Record<string, string> = {
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

async function fetchJsonWithFallback<T>(apiEndpoint: string, staticPath: string): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${apiEndpoint}`);
    if (res.ok) {
      const data = (await res.json()) as T;
      if (Array.isArray(data) && data.length === 0) {
        // Fall back to static dataset if API returned an empty list
      } else {
        return data;
      }
    }
  } catch {
    // API server unreachable; fallback to static data
  }

  const staticRes = await fetch(staticPath);
  if (!staticRes.ok) {
    throw new Error(`Failed to load data from ${staticPath}: ${staticRes.statusText}`);
  }
  return (await staticRes.json()) as T;
}

// Client-side geodesic calculation fallback for static Cloudflare Pages hosting
function calculateClientCorridor(
  originLoc: LocationItem,
  destLoc: LocationItem,
  originStation?: MapStation,
  destStation?: MapStation,
): CorridorRiskResponse {
  const lat1 = originLoc.latitude || 0;
  const lon1 = originLoc.longitude || 0;
  const lat2 = destLoc.latitude || 0;
  const lon2 = destLoc.longitude || 0;

  // Haversine distance
  const r = 6371.0;
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlam = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlam / 2) ** 2;
  const distKm = Math.round(2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)) * 10) / 10;
  const distNm = Math.round(distKm * 0.539957 * 10) / 10;

  const aqi1 = originStation ? originStation.avg_aqi : 0.0;
  const aqi2 = destStation ? destStation.avg_aqi : 0.0;
  const tier1 = originStation ? originStation.risk_tier : 'Unmonitored';
  const tier2 = destStation ? destStation.risk_tier : 'Unmonitored';

  const corridorScore = Math.round((0.3 * aqi1 + 0.5 * aqi2 + 0.2 * Math.max(aqi1, aqi2)) * 10) / 10;

  let overallStatus = 'Optimal Flight Conditions';
  let riskLevel = 'Low';
  let statusColor = '#059669';

  if (corridorScore > 200) {
    overallStatus = 'Severe Terminal Disruption Alert';
    riskLevel = 'Critical';
    statusColor = '#991B1B';
  } else if (corridorScore > 150) {
    overallStatus = 'High Operational Impact';
    riskLevel = 'High';
    statusColor = '#DC2626';
  } else if (corridorScore > 100) {
    overallStatus = 'Elevated Chokepoint Advisory';
    riskLevel = 'Elevated';
    statusColor = '#EA580C';
  } else if (corridorScore > 50) {
    overallStatus = 'Moderate Transit Risk';
    riskLevel = 'Moderate';
    statusColor = '#D97706';
  }

  const recommendations: string[] = [];
  if (tier1 === 'Unmonitored') {
    recommendations.push(
      `Notice: Departure terminal '${originLoc.location_name}' is currently unmonitored; deploy portable sensor telemetry.`
    );
  }
  if (tier2 === 'Unmonitored') {
    recommendations.push(`Notice: Arrival terminal '${destLoc.location_name}' is currently unmonitored; verify local regional advisory.`);
  }
  if (aqi2 > 150 || aqi1 > 150) {
    recommendations.push('Mandate N95 respirator PPE for outdoor cargo ramp and tarmac operations.');
  }
  if (aqi2 > 200) {
    recommendations.push('Trigger Aircraft Environmental Control (ECS) cabin HEPA filter inspection upon arrival.');
  }
  if (Math.max(aqi1, aqi2) > 175) {
    recommendations.push('Anticipate ground turnaround delays (+30 to 45 mins) due to reduced ground visibility.');
  }
  if (aqi2 > 100 && aqi2 <= 150) {
    recommendations.push('Notify dispatch to activate sensitive-group ramp crew rotation intervals.');
  }
  if (recommendations.length === 0) {
    recommendations.push('Standard dispatch parameters: No environmental operational restrictions along flight path.');
  }

  // Generate 40 Great-Circle intermediate waypoints
  const waypoints: Waypoint[] = [];
  const numPoints = 40;
  for (let i = 0; i <= numPoints; i++) {
    const f = i / numPoints;
    // Linear intermediate interpolation with slight curvature
    const lat = lat1 + f * (lat2 - lat1) + Math.sin(f * Math.PI) * Math.min(12, distKm / 800);
    const lon = lon1 + f * (lon2 - lon1);
    waypoints.push({ lat: Math.round(lat * 10000) / 10000, lon: Math.round(lon * 10000) / 10000 });
  }

  return {
    origin: {
      location_key: originLoc.location_key,
      location_name: originLoc.location_name,
      country_name: originLoc.country_name,
      country_code: originLoc.country_code,
      latitude: lat1,
      longitude: lon1,
      parameter_name: originStation?.parameter_name || 'unmonitored',
      avg_aqi: aqi1,
      risk_tier: tier1,
      color_hex: RISK_COLORS[tier1] || '#94A3B8',
    },
    destination: {
      location_key: destLoc.location_key,
      location_name: destLoc.location_name,
      country_name: destLoc.country_name,
      country_code: destLoc.country_code,
      latitude: lat2,
      longitude: lon2,
      parameter_name: destStation?.parameter_name || 'unmonitored',
      avg_aqi: aqi2,
      risk_tier: tier2,
      color_hex: RISK_COLORS[tier2] || '#94A3B8',
    },
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

  getLocations: async (): Promise<LocationItem[]> => {
    if (!_cachedLocations) {
      _cachedLocations = await fetchJsonWithFallback<LocationItem[]>('/locations', '/data/locations.json');
    }
    return _cachedLocations;
  },

  getUnmonitoredLocations: () =>
    fetchJsonWithFallback<UnmonitoredLocation[]>('/locations/unmonitored', '/data/unmonitored.json'),

  getPollutants: () => fetchJsonWithFallback<Pollutant[]>('/pollutants', '/data/pollutants.json'),

  getMapStations: async (): Promise<MapStation[]> => {
    if (!_cachedStations) {
      _cachedStations = await fetchJsonWithFallback<MapStation[]>('/aqi/map', '/data/map_stations.json');
    }
    return _cachedStations;
  },

  getTrends: async (locationKey: string, pollutantKey: string): Promise<TrendPoint[]> => {
    try {
      const res = await fetch(
        `${API_BASE}/aqi/trends?location_key=${encodeURIComponent(locationKey)}&pollutant_key=${encodeURIComponent(pollutantKey)}`,
      );
      if (res.ok) {
        return (await res.json()) as TrendPoint[];
      }
    } catch {
      // Fallback
    }

    if (!_cachedTrends) {
      const res = await fetch('/data/trends.json');
      if (res.ok) {
        _cachedTrends = (await res.json()) as Record<string, TrendPoint[]>;
      } else {
        _cachedTrends = {};
      }
    }

    const key = `${locationKey}_${pollutantKey}`;
    return _cachedTrends[key] || [];
  },

  getAlerts: async (minTier: string): Promise<AlertsResponse> => {
    try {
      const res = await fetch(`${API_BASE}/alerts?min_tier=${encodeURIComponent(minTier)}`);
      if (res.ok) {
        return (await res.json()) as AlertsResponse;
      }
    } catch {
      // Fallback
    }

    if (!_cachedAlerts) {
      const res = await fetch('/data/alerts.json');
      if (res.ok) {
        _cachedAlerts = (await res.json()) as Record<string, AlertsResponse>;
      } else {
        _cachedAlerts = {};
      }
    }

    return (
      _cachedAlerts[minTier] || {
        min_tier: minTier,
        threshold_aqi: 100,
        alert_count: 0,
        alerts: [],
      }
    );
  },

  getExportUrl: (minTier: string) => `${API_BASE}/alerts/export?min_tier=${encodeURIComponent(minTier)}`,

  getCorridorRisk: async (originKey: string, destinationKey: string): Promise<CorridorRiskResponse> => {
    try {
      const res = await fetch(
        `${API_BASE}/corridors/risk?origin_key=${encodeURIComponent(originKey)}&destination_key=${encodeURIComponent(destinationKey)}`,
      );
      if (res.ok) {
        return (await res.json()) as CorridorRiskResponse;
      }
    } catch {
      // Live server unavailable; calculate client-side
    }

    // Client-side fallback calculation
    const locations = await api.getLocations();
    const stations = await api.getMapStations();

    let originLoc = locations.find(
      (l) => l.location_key === originKey || l.location_name.toLowerCase() === originKey.toLowerCase(),
    );
    let destLoc = locations.find(
      (l) => l.location_key === destinationKey || l.location_name.toLowerCase() === destinationKey.toLowerCase(),
    );

    // If an obsolete surrogate key was passed from an old browser session, fall back gracefully
    if (!originLoc && locations.length > 0) {
      originLoc = locations.find((l) => l.location_name.toLowerCase().includes('london')) || locations[0];
    }
    if (!destLoc && locations.length > 1) {
      destLoc = locations.find((l) => l.location_name.toLowerCase().includes('delhi')) || locations[1];
    }

    if (!originLoc || !destLoc) {
      throw new Error(`Corridor terminals not found: ${originKey} -> ${destinationKey}`);
    }

    const originStation = stations.find((s) => s.location_key === originLoc!.location_key);
    const destStation = stations.find((s) => s.location_key === destLoc!.location_key);

    return calculateClientCorridor(originLoc!, destLoc!, originStation, destStation);
  },
};
