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
  const [selectedPollutantKey, setSelectedPollutantKey] = useState<string>('');
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
    const param = typeof station === 'string' ? '' : station.parameter_name;
    setSelectedStationKey(key);
    if (param) setSelectedPollutantKey(param);
    setActiveTab('trends');
  };

  return (
    <div className="min-h-[100dvh] flex flex-col bg-[#FFF3E6] text-[#381932] selection:bg-[#381932] selection:text-[#FFF3E6] font-sans antialiased overflow-x-hidden relative">
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

      <main className="max-w-[1400px] mx-auto w-full px-6 py-8 flex-1">
        {activeTab === 'overview' && (
          <div className="space-y-6 transition-opacity duration-200">
            <KPISection kpis={kpis} loading={loading} timezone={timezone} />
            <RiskMap stations={mapStations} onSelectStation={handleSelectStation} />
            <Leaderboard
              stations={mapStations}
              unmonitored={unmonitored}
              onSelectStation={handleSelectStation}
            />
          </div>
        )}

        {activeTab === 'trends' && (
          <div className="transition-opacity duration-200">
            <CityTrends
              locations={locations}
              pollutants={pollutants}
              unmonitored={unmonitored}
              initialLocationKey={selectedStationKey}
              initialPollutantKey={selectedPollutantKey}
              timezone={timezone}
            />
          </div>
        )}

        {activeTab === 'corridors' && (
          <div className="transition-opacity duration-200">
            <RouteCorridor locations={locations} unmonitored={unmonitored} />
          </div>
        )}

        {activeTab === 'alerts' && (
          <div className="transition-opacity duration-200">
            <Alerts />
          </div>
        )}
      </main>

      <footer className="border-t border-[#381932]/10 py-8 px-6 text-xs text-[#583351] mt-16 font-sans bg-[#FFF3E6]/95 backdrop-blur-md">
        <div className="max-w-[1400px] mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-[#381932]" />
            <span className="font-luxury text-base text-[#381932] tracking-wider font-bold">AtmosRoute</span>
            <span className="text-[#381932]/30">/</span>
            <span className="text-xs text-[#583351] tracking-wider uppercase font-semibold">Atmospheric Telemetry &amp; Risk Intelligence</span>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-[#84657E]">
            <span>DuckDB Gold Marts + OpenAQ v3 Engine</span>
            <span className="text-[#381932]/20">•</span>
            <span>High-Precision Environmental Analytics</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
