import type { HistoryChartResponse, HistoryRow, LatestRate, LogEntry } from "./types";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
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
