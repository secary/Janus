import type {
  HistoryChartResponse,
  HistoryRow,
  LatestRate,
  LogEntry,
  PredictionConfig,
  PredictionConfigUpdate,
  ScheduleConfig,
  ScheduleUpdate,
} from "./types";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
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
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<T>;
}

async function responseErrorMessage(response: Response): Promise<string> {
  const fallback = `Request failed: ${response.status} ${response.statusText}`;
  try {
    const payload = (await response.json()) as { message?: string; error?: string };
    return payload.message || payload.error || fallback;
  } catch {
    return fallback;
  }
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

export function fetchPredictionConfig(): Promise<PredictionConfig> {
  return fetchJson<PredictionConfig>("/api/admin/prediction-config");
}

export function savePredictionConfig(update: PredictionConfigUpdate): Promise<PredictionConfig> {
  return postJson<PredictionConfig>("/api/admin/prediction-config", update);
}
