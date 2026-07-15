async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
        throw new Error(await responseErrorMessage(response));
    }
    return response.json();
}
async function postJson(url, body) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(await responseErrorMessage(response));
    }
    return response.json();
}
async function responseErrorMessage(response) {
    const fallback = `Request failed: ${response.status} ${response.statusText}`;
    try {
        const payload = await response.json();
        return payload.message || payload.error || fallback;
    }
    catch {
        return fallback;
    }
}
export function fetchLatestRates() {
    return fetchJson("/api/latest");
}
export function fetchHistory(currency) {
    const query = currency ? `?currency=${encodeURIComponent(currency)}` : "";
    return fetchJson(`/api/history${query}`);
}
export function fetchHistoryChart() {
    return fetchJson("/api/history/chart");
}
export function fetchLatestLogs() {
    return fetchJson("/api/logs/latest");
}
export function fetchScheduleConfigs() {
    return fetchJson("/api/admin/schedules");
}
export function saveScheduleConfigs(updates) {
    return postJson("/api/admin/schedules", updates);
}
export function fetchPredictionConfig() {
    return fetchJson("/api/admin/prediction-config");
}
export function savePredictionConfig(update) {
    return postJson("/api/admin/prediction-config", update);
}
