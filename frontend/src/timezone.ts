export interface TimezoneOption {
  label: string;
  value: string;
  short: string;
}

export const TIMEZONE_OPTIONS: TimezoneOption[] = [
  { label: 'UTC (Standard)', value: 'UTC', short: 'UTC' },
  { label: 'Local (Device)', value: 'local', short: 'Local' },
  { label: 'New York (ET)', value: 'America/New_York', short: 'ET' },
  { label: 'Chicago (CT)', value: 'America/Chicago', short: 'CT' },
  { label: 'Los Angeles (PT)', value: 'America/Los_Angeles', short: 'PT' },
  { label: 'London (GMT/BST)', value: 'Europe/London', short: 'GMT' },
  { label: 'Berlin / Paris (CET)', value: 'Europe/Berlin', short: 'CET' },
  { label: 'Kolkata (IST)', value: 'Asia/Kolkata', short: 'IST' },
  { label: 'Bangkok (ICT)', value: 'Asia/Bangkok', short: 'ICT' },
  { label: 'Tokyo (JST)', value: 'Asia/Tokyo', short: 'JST' },
];

export function getTzShortLabel(tz: string): string {
  const match = TIMEZONE_OPTIONS.find((t) => t.value === tz);
  if (match) return match.short;
  if (tz === 'local') return 'Local';
  return tz;
}

export function formatLastUpdated(
  dateStr?: string,
  timeStr?: string,
  tz: string = 'UTC'
): { date: string; time: string; full: string } {
  if (!dateStr) {
    return { date: '—', time: '', full: '—' };
  }

  // Parse into UTC timestamp
  let iso = dateStr;
  if (timeStr && timeStr.includes(':')) {
    const cleanTime = timeStr.replace(/[^0-9:]/g, '').trim();
    iso = `${dateStr}T${cleanTime.length === 5 ? cleanTime + ':00' : cleanTime}Z`;
  } else {
    iso = `${dateStr}T00:00:00Z`;
  }

  const d = new Date(iso);
  if (isNaN(d.getTime())) {
    const short = getTzShortLabel(tz);
    return {
      date: dateStr,
      time: timeStr ? `${timeStr} ${short}` : '',
      full: timeStr ? `${dateStr} • ${timeStr} ${short}` : dateStr,
    };
  }

  const timeZoneOption = tz === 'local' ? undefined : tz;
  const short = getTzShortLabel(tz);

  try {
    const fDate = new Intl.DateTimeFormat('en-CA', {
      timeZone: timeZoneOption,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(d);

    let fTime = '';
    if (timeStr && timeStr.includes(':')) {
      const formattedTime = new Intl.DateTimeFormat('en-GB', {
        timeZone: timeZoneOption,
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(d);
      fTime = `${formattedTime} ${short}`;
    }

    return {
      date: fDate,
      time: fTime,
      full: fTime ? `${fDate} • ${fTime}` : fDate,
    };
  } catch {
    return { date: dateStr, time: timeStr || '', full: `${dateStr} ${timeStr || ''}`.trim() };
  }
}

export function formatIsoTimestamp(isoString: string, tz: string = 'UTC'): string {
  const hasTz = isoString.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(isoString);
  const d = new Date(hasTz ? isoString : `${isoString}Z`);
  if (isNaN(d.getTime())) return isoString;

  const timeZoneOption = tz === 'local' ? undefined : tz;
  const short = getTzShortLabel(tz);

  try {
    const datePart = new Intl.DateTimeFormat('en-CA', {
      timeZone: timeZoneOption,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(d);

    const timePart = new Intl.DateTimeFormat('en-GB', {
      timeZone: timeZoneOption,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(d);

    return `${datePart} ${timePart} ${short}`;
  } catch {
    return d.toLocaleString();
  }
}
