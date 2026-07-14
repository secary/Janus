import { fetchHistoryChart, fetchLatestLogs, fetchLatestRates } from "./api.js";
import type { ChartPoint, HistoryChartResponse, LatestRate, LogEntry } from "./types";

interface ChartInstance {
  destroy(): void;
}

interface ChartConstructor {
  new (context: CanvasRenderingContext2D, config: unknown): ChartInstance;
}

declare const Chart: ChartConstructor;

const flagMap: Record<string, string> = {
  AUD: "🇦🇺",
  USD: "🇺🇸",
  JPY: "🇯🇵",
  EUR: "🇪🇺",
  GBP: "🇬🇧",
  CNY: "🇨🇳",
};

const currencyNameMap: Record<string, string> = {
  AUD: "澳大利亚元",
  USD: "美元",
  JPY: "日元",
  EUR: "欧元",
  GBP: "英镑",
  CNY: "人民币",
};

let chartInstance: ChartInstance | null = null;
let allData: HistoryChartResponse = {};
let crawlerRefreshTimer: ReturnType<typeof setTimeout> | null = null;
let dashboardBootstrapped = false;

function elementById<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element: #${id}`);
  }
  return element as T;
}

function rateTableBody(): HTMLTableSectionElement {
  const tbody = document.querySelector<HTMLTableSectionElement>("#rateTable tbody");
  if (!tbody) {
    throw new Error("Missing rate table body");
  }
  return tbody;
}

function chartContext(): CanvasRenderingContext2D {
  const canvas = elementById<HTMLCanvasElement>("rateChart");
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Unable to initialize chart canvas");
  }
  return context;
}

function displayCurrency(currency: string): string {
  return `${flagMap[currency] || ""} ${currencyNameMap[currency] || currency}`.trim();
}

function appendCell(row: HTMLTableRowElement, value: string): HTMLTableCellElement {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);
  return cell;
}

function parseCrawlerTime(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }

  const text = String(value).slice(0, 19).replace("T", " ");
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/);
  if (!match) {
    return null;
  }

  const [, year, month, day, hour, minute, second] = match;
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
  );
}

function formatAxisDate(value: string): string {
  const date = parseCrawlerTime(value) ?? new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hours}:${minutes}`;
}

function latestCrawlerStamp(latestData: LatestRate[]): number | null {
  let latest: Date | null = null;
  latestData.forEach((row) => {
    const date = parseCrawlerTime(row.Locals || row.Date);
    if (date && (!latest || date.getTime() > latest.getTime())) {
      latest = date;
    }
  });
  return latest ? latest.getTime() : null;
}

function scheduleCrawlerRefresh(latestStamp: number | null): void {
  if (crawlerRefreshTimer) {
    clearTimeout(crawlerRefreshTimer);
  }

  let delay = 30 * 1000;
  if (latestStamp) {
    const nextBoundary = latestStamp + 30 * 60 * 1000 + 5000;
    delay = Math.max(nextBoundary - Date.now(), 15 * 1000);
  }

  crawlerRefreshTimer = setTimeout(() => {
    void refreshDashboard();
  }, delay);
}

async function loadLogs(): Promise<void> {
  const container = elementById<HTMLDivElement>("logContainer");
  try {
    const logs = await fetchLatestLogs();
    renderLogs(container, logs);
  } catch {
    container.textContent = "⚠️ 日志加载失败。";
  }
}

function renderLogs(container: HTMLDivElement, logs: LogEntry[]): void {
  container.replaceChildren();

  if (!logs.length) {
    container.textContent = "⚠️ 暂无爬虫日志";
    return;
  }

  logs.forEach((row) => {
    const line = document.createElement("div");
    line.className = "log-entry";
    line.textContent = `[${row.timestamp}] [${row.level}] ${row.message}`;

    if (row.level === "ERROR") {
      line.style.color = "red";
    } else if (row.level === "WARNING") {
      line.style.color = "orange";
    } else if (row.level === "CRITICAL") {
      line.style.color = "purple";
    }

    container.appendChild(line);
  });

  container.scrollTop = container.scrollHeight;
}

async function loadLatestRates(): Promise<LatestRate[]> {
  const tbody = rateTableBody();
  try {
    const rates = await fetchLatestRates();
    renderLatestRates(tbody, rates);
    setupCnyConverter(rates);
    return rates;
  } catch {
    const row = document.createElement("tr");
    const cell = appendCell(row, "加载失败");
    cell.colSpan = 5;
    cell.style.color = "#888";
    tbody.replaceChildren(row);
    return [];
  }
}

function renderLatestRates(tbody: HTMLTableSectionElement, rates: LatestRate[]): void {
  tbody.replaceChildren();

  rates.forEach((row) => {
    const tr = document.createElement("tr");
    const displayTime = row.Locals || row.Date;
    const timeCell = appendCell(tr, displayTime);

    if (row.Date) {
      const sourceDate = document.createElement("div");
      sourceDate.className = "source-date";
      sourceDate.textContent = `源站：${row.Date}`;
      timeCell.appendChild(sourceDate);
    }

    appendCell(tr, displayCurrency(row.Currency));
    appendCell(tr, String(row.Rate));
    appendCell(
      tr,
      row.PredictedRate === null || row.PredictedRate === undefined
        ? "N/A"
        : Number(row.PredictedRate).toFixed(4),
    );
    appendCell(tr, row.PredictionDate || "—");
    tbody.appendChild(tr);
  });
}

function setupCnyConverter(latestData: LatestRate[]): void {
  const select = elementById<HTMLSelectElement>("sourceCurrency");
  const amountInput = elementById<HTMLInputElement>("sourceAmount");
  const convertedInput = elementById<HTMLInputElement>("convertedCny");
  const summary = elementById<HTMLParagraphElement>("exchangeSummary");
  const updatedTime = elementById<HTMLSpanElement>("updatedTime");
  const rates = latestData.reduce<Record<string, number>>((acc, row) => {
    if (row.Currency !== "CNY" && typeof row.Rate === "number") {
      acc[row.Currency] = row.Rate;
    }
    return acc;
  }, {});

  const options = Object.keys(rates).map((currency) => {
    const option = document.createElement("option");
    option.value = currency;
    option.textContent = displayCurrency(currency);
    return option;
  });
  select.replaceChildren(...options);

  if (rates.AUD !== undefined) {
    select.value = "AUD";
  } else {
    const firstOption = options[0];
    if (firstOption) {
      select.value = firstOption.value;
    }
  }

  const firstDate = latestData.find((row) => row.Locals || row.Date);
  updatedTime.textContent = firstDate ? firstDate.Locals || firstDate.Date : "-";

  const updateDisplay = () => {
    const currency = select.value;
    const rawRate = rates[currency];
    if (!currency || rawRate === undefined) {
      convertedInput.value = "";
      summary.replaceChildren();
      return;
    }

    const rate = rawRate / 100;
    const amount = Number.parseFloat(amountInput.value) || 0;
    convertedInput.value = (amount * rate).toFixed(4);

    const direct = document.createElement("div");
    direct.textContent = `1 ${currencyNameMap[currency] || currency} ≈ ${rate.toFixed(4)} 人民币`;
    const reverse = document.createElement("div");
    reverse.textContent = `1 人民币 ≈ ${(1 / rate).toFixed(4)} ${currencyNameMap[currency] || currency}`;
    summary.replaceChildren(direct, reverse);
  };

  select.addEventListener("change", () => {
    updateDisplay();
    updateChart();
  });
  amountInput.addEventListener("input", updateDisplay);
  updateDisplay();
}

async function loadChartData(): Promise<void> {
  try {
    allData = await fetchHistoryChart();
  } catch {
    allData = {};
  }

  const select = elementById<HTMLSelectElement>("sourceCurrency");
  const keys = Object.keys(allData).sort();
  if (keys.length && !keys.includes(select.value)) {
    const fallbackCurrency = keys.includes("AUD") ? "AUD" : keys[0];
    if (fallbackCurrency) {
      select.value = fallbackCurrency;
    }
  }
  updateChart();
}

function updateChart(): void {
  const currency = elementById<HTMLSelectElement>("sourceCurrency").value;
  const rows = [...(allData[currency] || [])].sort(
    (a, b) => Number(parseCrawlerTime(a.datetime)) - Number(parseCrawlerTime(b.datetime)),
  );

  if (!rows.length) {
    renderEmptyChart();
    return;
  }

  const timelineRows = rows.slice(-20);
  if (!timelineRows.length) {
    renderEmptyChart();
    return;
  }

  const labels = timelineRows.map((row) => formatAxisDate(row.prediction_datetime || row.datetime));
  const historyPoints = timelineRows.map((row) => ({
    x: formatAxisDate(row.datetime),
    y: row.rate,
  }));
  const predictionPoints = timelineRows.map((row) => ({
    x: formatAxisDate(row.prediction_datetime || row.datetime),
    y: row.predicted,
  }));

  renderLineChart(currency, labels, historyPoints, predictionPoints);
}

function renderEmptyChart(): void {
  if (chartInstance) {
    chartInstance.destroy();
  }
  chartInstance = new Chart(chartContext(), {
    type: "line",
    data: { datasets: [] },
    options: { responsive: true },
  });
}

function renderLineChart(
  currency: string,
  labels: string[],
  historyPoints: Array<{ x: string; y: ChartPoint["rate"] }>,
  predictionPoints: Array<{ x: string; y: ChartPoint["predicted"] }>,
): void {
  if (chartInstance) {
    chartInstance.destroy();
  }

  chartInstance = new Chart(chartContext(), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: `${currencyNameMap[currency] || currency} 历史汇率`,
          data: historyPoints,
          borderColor: "rgba(75, 192, 192, 1)",
          backgroundColor: "rgba(75, 192, 192, 0.1)",
          fill: true,
          tension: 0.2,
          pointRadius: 0,
          spanGaps: true,
        },
        {
          label: `${currencyNameMap[currency] || currency} 预测汇率`,
          data: predictionPoints,
          borderColor: "rgba(255, 99, 132, 1)",
          borderDash: [6, 6],
          pointBackgroundColor: "rgba(255, 99, 132, 1)",
          pointStyle: "circle",
          pointRadius: 4,
          fill: false,
          tension: 0,
          spanGaps: true,
          showLine: true,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "nearest", intersect: false, axis: "x" },
      plugins: {
        tooltip: {
          callbacks: {
            title: (items: Array<{ label: string }>) => {
              const item = items[0];
              return item ? `执行时间：${item.label}` : "";
            },
            label: (context: { dataset: { label: string }; parsed?: { y?: number } }) => {
              const value = typeof context.parsed?.y === "number" ? context.parsed.y : null;
              return `${context.dataset.label}：${value === null ? "-" : String(value)}`;
            },
          },
        },
        legend: {
          labels: {
            usePointStyle: true,
            filter: (item: { text: string }) => item.text !== "连接线",
          },
        },
      },
      scales: {
        x: {
          type: "category",
          grid: { color: "rgba(0, 0, 0, 0.08)" },
          ticks: {
            autoSkip: true,
            maxTicksLimit: 10,
            minRotation: 0,
            maxRotation: 0,
            align: "center",
          },
        },
        y: {
          title: { display: true, text: "汇率" },
          grace: "5%",
        },
      },
    },
  });
}

async function refreshDashboard(): Promise<LatestRate[]> {
  const rates = await loadLatestRates();
  await loadChartData();
  scheduleCrawlerRefresh(latestCrawlerStamp(rates));
  return rates;
}

window.addEventListener("pageshow", () => {
  void refreshDashboard();
  void loadLogs();

  if (!dashboardBootstrapped) {
    dashboardBootstrapped = true;
    setInterval(() => {
      void loadLogs();
    }, 1000 * 60 * 10);
  }
});

elementById<HTMLButtonElement>("refreshButton").addEventListener("click", () => {
  void refreshDashboard();
});
