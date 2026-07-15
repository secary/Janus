import type {
  HistoryChartResponse,
  HistoryRow,
  LatestRate,
  LogEntry,
  ScheduleConfig,
  ScheduleUpdate,
} from "./types";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function fetchLatestRates(): Promise<LatestRate[]> {
  return fetchJson<LatestRate[]>("/api/latest");
}

export function fetchHistory(currency?: string): Promise<HistoryRow[]> {
  const query = currency ? `?currency=${encodeURIComponent(currency)}` : "";
  return fetchJson<HistoryRow[]>(`/api/history${query}`);
}

export function fetchHistoryChart(): Promise<HistoryChartResponse> {
  return fetchJson<HistoryChartResponse>("/api/history/chart");
}

export function fetchLatestLogs(): Promise<LogEntry[]> {
  return fetchJson<LogEntry[]>("/api/logs/latest");
}

export function fetchScheduleConfigs(): Promise<ScheduleConfig[]> {
  return fetchJson<ScheduleConfig[]>("/api/admin/schedules");
}

export function saveScheduleConfigs(updates: ScheduleUpdate[]): Promise<ScheduleConfig[]> {
  return postJson<ScheduleConfig[]>("/api/admin/schedules", updates);
}
