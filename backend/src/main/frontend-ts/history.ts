import { fetchHistory } from "./api.js";
import type { HistoryRow } from "./types";

function elementById<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element: #${id}`);
  }
  return element as T;
}

function historyTableBody(): HTMLTableSectionElement {
  const tbody = document.querySelector<HTMLTableSectionElement>("#historyTable tbody");
  if (!tbody) {
    throw new Error("Missing history table body");
  }
  return tbody;
}

function appendCell(row: HTMLTableRowElement, value: string): void {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);
}

function renderHistory(rows: HistoryRow[]): void {
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

async function loadFilteredHistory(): Promise<void> {
  const select = elementById<HTMLSelectElement>("currencyFilter");
  const rows = await fetchHistory(select.value || undefined);
  renderHistory(rows);
}

window.addEventListener("pageshow", () => {
  void loadFilteredHistory();
});

elementById<HTMLSelectElement>("currencyFilter").addEventListener("change", () => {
  void loadFilteredHistory();
});
