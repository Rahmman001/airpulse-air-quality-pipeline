import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { KPISection } from './components/KPISection';
import { RiskMap } from './components/RiskMap';
import { Leaderboard } from './components/Leaderboard';
import { CityTrends } from './components/CityTrends';
import { Alerts } from './components/Alerts';
import { RouteCorridor } from './components/RouteCorridor';
import { api } from './api';
import type {
  KpiData,
  MapStation,
  LocationItem,
  Pollutant,
  UnmonitoredLocation,
} from './api';

export function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'trends' | 'alerts' | 'corridors'>('overview');
  const [kpis, setKpis] = useState<KpiData | null>(null);
  const [mapStations, setMapStations] = useState<MapStation[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [unmonitored, setUnmonitored] = useState<UnmonitoredLocation[]>([]);
  const [pollutants, setPollutants] = useState<Pollutant[]>([]);
  const [selectedStationKey, setSelectedStationKey] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [timezone, setTimezone] = useState<string>(() => {
    return localStorage.getItem('airpulse_tz') || 'UTC';
  });

  const handleTimezoneChange = (tz: string) => {
    setTimezone(tz);
    localStorage.setItem('airpulse_tz', tz);
  };

  useEffect(() => {
    Promise.all([
      api.getKpis().catch(() => null),
      api.getMapStations().catch(() => []),
      api.getLocations().catch(() => []),
      api.getUnmonitoredLocations().catch(() => []),
      api.getPollutants().catch(() => []),
    ]).then(([kpiRes, mapRes, locRes, unmonRes, polRes]) => {
      if (kpiRes) setKpis(kpiRes);
      setMapStations(mapRes);
      setLocations(locRes);
      setUnmonitored(unmonRes);
      setPollutants(polRes);
      if (locRes.length > 0) {
        setSelectedStationKey(locRes[0].location_key);
      }
      setLoading(false);
    });
  }, []);

  const handleSelectStation = (station: MapStation | string) => {
    const key = typeof station === 'string' ? station : station.location_key;
    setSelectedStationKey(key);
    setActiveTab('trends');
  };

  return (
    <div className="min-h-[100dvh] flex flex-col bg-[#F8FAFC] text-slate-900 selection:bg-slate-950 selection:text-white font-sans antialiased overflow-x-hidden relative">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        dataSourceLabel={kpis?.data_source_label || ''}
        alertCount={kpis?.hazardous_zones_count || 0}
        latestDataDate={kpis?.latest_data_date || ''}
        latestDataTime={kpis?.latest_data_time || ''}
        timezone={timezone}
        onTimezoneChange={handleTimezoneChange}
      />

      <main className="max-w-[1360px] mx-auto w-full px-6 py-8 flex-1">
        {activeTab === 'overview' && (
          <>
            <KPISection kpis={kpis} loading={loading} timezone={timezone} />
            <RiskMap stations={mapStations} onSelectStation={handleSelectStation} />
            <Leaderboard
              stations={mapStations}
              unmonitored={unmonitored}
              onSelectStation={handleSelectStation}
            />
          </>
        )}

        {activeTab === 'trends' && (
          <CityTrends
            locations={locations}
            pollutants={pollutants}
            initialLocationKey={selectedStationKey}
            timezone={timezone}
          />
        )}

        {activeTab === 'corridors' && <RouteCorridor locations={locations} />}

        {activeTab === 'alerts' && <Alerts />}
      </main>

      <footer className="border-t border-slate-200/80 py-6 px-6 text-xs text-slate-500 mt-12 font-sans bg-white/60 backdrop-blur-md">
        <div className="max-w-[1360px] mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-900" />
            <span className="font-display text-sm text-slate-950 tracking-tight font-bold">AirPulse</span>
            <span className="text-slate-300">/</span>
            <span className="text-xs text-slate-500 font-mono">Telemetry Console</span>
          </div>
          <div className="font-mono text-[11px] text-slate-500">
            DuckDB Warehouse + OpenAQ v3
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
