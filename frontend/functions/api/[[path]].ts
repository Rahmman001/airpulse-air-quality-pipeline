/**
 * Cloudflare Pages Functions API Handler for AirPulse.
 * Implements serverless edge endpoints for /api/v1/* with zero external servers.
 */

interface Env {
  ASSETS: {
    fetch: (request: Request | URL) => Promise<Response>;
  };
  R2_BUCKET?: {
    get: (key: string) => Promise<any>;
  };
}

const RISK_TIERS: Record<string, string> = {
  Good: '#059669',
  Moderate: '#D97706',
  'Unhealthy for Sensitive Groups': '#EA580C',
  Unhealthy: '#DC2626',
  'Very Unhealthy': '#991B1B',
  Hazardous: '#581C87',
  Unmonitored: '#94A3B8',
};

function calculateCorridor(origin: any, dest: any, originStation: any, destStation: any) {
  const lat1 = origin.latitude || 0;
  const lon1 = origin.longitude || 0;
  const lat2 = dest.latitude || 0;
  const lon2 = dest.longitude || 0;

  const toRad = (d: number) => (d * Math.PI) / 180;
  const dphi = toRad(lat2 - lat1);
  const dlam = toRad(lon2 - lon1);
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dlam / 2) ** 2;
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
    tier1 === 'Unmonitored' && `Notice: Departure terminal '${origin.location_name}' is currently unmonitored; deploy portable sensor telemetry.`,
    tier2 === 'Unmonitored' && `Notice: Arrival terminal '${dest.location_name}' is currently unmonitored; verify local regional advisory.`,
    (aqi2 > 150 || aqi1 > 150) && 'Mandate N95 respirator PPE for outdoor cargo ramp and tarmac operations.',
    aqi2 > 200 && 'Trigger Aircraft Environmental Control (ECS) cabin HEPA filter inspection upon arrival.',
    Math.max(aqi1, aqi2) > 175 && 'Anticipate ground turnaround delays (+30 to 45 mins) due to reduced ground visibility.',
    aqi2 > 100 && aqi2 <= 150 && 'Notify dispatch to activate sensitive-group ramp crew rotation intervals.',
  ].filter(Boolean) as string[];

  if (!recommendations.length) {
    recommendations.push('Standard dispatch parameters: No environmental operational restrictions along flight path.');
  }

  const waypoints = Array.from({ length: 41 }, (_, i) => {
    const f = i / 40;
    return {
      lat: +(lat1 + f * (lat2 - lat1) + Math.sin(f * Math.PI) * Math.min(12, distKm / 800)).toFixed(4),
      lon: +(lon1 + f * (lon2 - lon1)).toFixed(4),
    };
  });

  const createHub = (loc: any, st: any, aqi: number, tier: string) => ({
    location_key: loc.location_key,
    location_name: loc.location_name,
    country_name: loc.country_name,
    country_code: loc.country_code,
    latitude: loc.latitude || 0,
    longitude: loc.longitude || 0,
    parameter_name: st?.parameter_name || 'unmonitored',
    avg_aqi: aqi,
    risk_tier: tier,
    color_hex: RISK_TIERS[tier] || '#94A3B8',
  });

  return {
    origin: createHub(origin, originStation, aqi1, tier1),
    destination: createHub(dest, destStation, aqi2, tier2),
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

export const onRequest: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);
  const path = url.pathname;

  const jsonHeaders = {
    'content-type': 'application/json; charset=utf-8',
    'access-control-allow-origin': '*',
    'cache-control': 'public, max-age=300',
  };

  // 1. Health Check
  if (path === '/api/v1/health' || path === '/api/health') {
    return new Response(JSON.stringify({ status: 'ok', engine: 'cloudflare-pages-edge', timestamp: new Date().toISOString() }), {
      headers: jsonHeaders,
    });
  }

  // 2. CSV Alerts Export
  if (path === '/api/v1/alerts/export') {
    const minTier = url.searchParams.get('min_tier') || 'Unhealthy';
    const alertsRes = await context.env.ASSETS.fetch(new URL('/data/alerts.json', context.request.url));
    if (!alertsRes.ok) return new Response('Alerts dataset unavailable', { status: 404 });
    const alertsMap = (await alertsRes.json()) as Record<string, { alerts: any[] }>;
    const tierData = alertsMap[minTier] || { alerts: [] };

    const headers = ['location_name,country_name,parameter_name,avg_aqi,risk_tier,reading_count,flagged_reading_count'];
    const esc = (v: any) => String(v ?? '').replace(/^[=+\-@]/, "'$&");
    const rows = tierData.alerts.map(
      (a) => `"${esc(a.location_name)}","${esc(a.country_name)}","${esc(a.parameter_name)}",${a.avg_aqi},"${esc(a.risk_tier)}",${a.reading_count},${a.flagged_reading_count}`
    );

    return new Response(headers.concat(rows).join('\n'), {
      headers: {
        'content-type': 'text/csv; charset=utf-8',
        'content-disposition': `attachment; filename="airpulse_alerts_${minTier.toLowerCase().replace(/\s+/g, '_')}.csv"`,
        'access-control-allow-origin': '*',
      },
    });
  }

  // 3. Flight Corridor Risk Triage
  if (path === '/api/v1/corridors/risk') {
    const originKey = url.searchParams.get('origin_key') || '';
    const destKey = url.searchParams.get('destination_key') || '';

    const [locRes, stRes] = await Promise.all([
      context.env.ASSETS.fetch(new URL('/data/locations.json', context.request.url)),
      context.env.ASSETS.fetch(new URL('/data/map_stations.json', context.request.url)),
    ]);

    const locations = (await locRes.json()) as any[];
    const stations = (await stRes.json()) as any[];

    const origin = locations.find((l) => l.location_key === originKey || l.location_name.toLowerCase() === originKey.toLowerCase()) || locations[0];
    const dest = locations.find((l) => l.location_key === destKey || l.location_name.toLowerCase() === destKey.toLowerCase()) || locations[1];

    if (!origin || !dest) {
      return new Response(JSON.stringify({ error: 'Origin or destination terminal not found' }), { status: 404, headers: jsonHeaders });
    }

    const originSt = stations.find((s) => s.location_key === origin.location_key);
    const destSt = stations.find((s) => s.location_key === dest.location_key);

    return new Response(JSON.stringify(calculateCorridor(origin, dest, originSt, destSt)), { headers: jsonHeaders });
  }

  // 4. Hourly Trends API
  if (path === '/api/v1/aqi/trends') {
    const loc = url.searchParams.get('location_key') || '';
    const pol = url.searchParams.get('pollutant_key') || '';
    const trendsRes = await context.env.ASSETS.fetch(new URL('/data/trends.json', context.request.url));
    const trendsMap = (await trendsRes.json()) as Record<string, any[]>;
    const series = trendsMap[`${loc}_${pol}`] || [];
    return new Response(JSON.stringify(series), { headers: jsonHeaders });
  }

  // 5. Categorized Alerts API
  if (path === '/api/v1/alerts') {
    const minTier = url.searchParams.get('min_tier') || 'Unhealthy';
    const alertsRes = await context.env.ASSETS.fetch(new URL('/data/alerts.json', context.request.url));
    const alertsMap = (await alertsRes.json()) as Record<string, any>;
    const tierData = alertsMap[minTier] || { min_tier: minTier, threshold_aqi: 100, alert_count: 0, alerts: [] };
    return new Response(JSON.stringify(tierData), { headers: jsonHeaders });
  }

  // 6. Direct Static Dataset Routes
  const staticRouteMap: Record<string, string> = {
    '/api/v1/kpis': '/data/kpis.json',
    '/api/v1/locations': '/data/locations.json',
    '/api/v1/locations/unmonitored': '/data/unmonitored.json',
    '/api/v1/pollutants': '/data/pollutants.json',
    '/api/v1/aqi/latest': '/data/latest_aqi.json',
    '/api/v1/aqi/map': '/data/map_stations.json',
  };

  if (staticRouteMap[path]) {
    const assetRes = await context.env.ASSETS.fetch(new URL(staticRouteMap[path], context.request.url));
    return new Response(assetRes.body, { status: assetRes.status, headers: jsonHeaders });
  }

  return context.next();
};
