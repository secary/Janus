async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`);
    }
    return response.json();
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
