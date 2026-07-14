import { fetchHistory } from "./api.js";
function elementById(id) {
    const element = document.getElementById(id);
    if (!element) {
        throw new Error(`Missing element: #${id}`);
    }
    return element;
}
function historyTableBody() {
    const tbody = document.querySelector("#historyTable tbody");
    if (!tbody) {
        throw new Error("Missing history table body");
    }
    return tbody;
}
function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.appendChild(cell);
}
function renderHistory(rows) {
    const tbody = historyTableBody();
    const tableRows = rows.map((item) => {
        const row = document.createElement("tr");
        appendCell(row, item.Date);
        appendCell(row, item.Currency);
        appendCell(row, String(item.Rate));
        return row;
    });
    tbody.replaceChildren(...tableRows);
}
async function loadFilteredHistory() {
    const select = elementById("currencyFilter");
    const rows = await fetchHistory(select.value || undefined);
    renderHistory(rows);
}
window.addEventListener("pageshow", () => {
    void loadFilteredHistory();
});
elementById("currencyFilter").addEventListener("change", () => {
    void loadFilteredHistory();
});
