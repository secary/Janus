import {
  fetchPredictionConfig,
  fetchScheduleConfigs,
  savePredictionConfig,
  saveScheduleConfigs,
} from "./api.js";
import type { PredictionConfig, PredictionMethod, ScheduleConfig, ScheduleUpdate } from "./types";

const cronFieldPattern = /^[0-9A-Za-z*/,-]+$/;
const cronPresets = [
  { label: "常用频率", value: "" },
  { label: "每 10 分钟", value: "*/10 * * * *" },
  { label: "每 30 分钟", value: "*/30 * * * *" },
  { label: "每小时", value: "0 * * * *" },
  { label: "每天 02:00", value: "0 2 * * *" },
  { label: "每月 1 日 03:00", value: "0 3 1 * *" },
];

let schedules: ScheduleConfig[] = [];
let predictionConfig: PredictionConfig | null = null;

function elementById<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element: #${id}`);
  }
  return element as T;
}

function scheduleTableBody(): HTMLTableSectionElement {
  const tbody = document.querySelector<HTMLTableSectionElement>("#scheduleTable tbody");
  if (!tbody) {
    throw new Error("Missing schedule table body");
  }
  return tbody;
}

function appendCell(row: HTMLTableRowElement): HTMLTableCellElement {
  const cell = document.createElement("td");
  row.appendChild(cell);
  return cell;
}

function setStatus(
  id: "statusText" | "scheduleStatus" | "predictionStatus",
  message: string,
  tone: "idle" | "success" | "error" = "idle",
): void {
  const status = elementById<HTMLSpanElement>(id);
  status.textContent = message;
  status.dataset.tone = tone;
}

function setLoading(loading: boolean): void {
  elementById<HTMLButtonElement>("saveButton").disabled = loading;
  elementById<HTMLButtonElement>("reloadButton").disabled = loading;
}

function normalizeCronExpression(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function validateCronExpression(value: string): string {
  const expression = normalizeCronExpression(value);
  const fields = expression.split(" ");
  if (fields.length !== 5) {
    throw new Error("cron 表达式必须包含 5 个字段");
  }

  const invalid = fields.find((field) => !cronFieldPattern.test(field));
  if (invalid) {
    throw new Error(`cron 字段不支持：${invalid}`);
  }

  return expression;
}

function validateLimit(input: HTMLInputElement): number {
  const value = Number.parseInt(input.value, 10);
  if (!Number.isFinite(value) || value < 1 || value > 10000) {
    throw new Error("导出条数必须在 1 到 10000 之间");
  }
  return value;
}

function validateHorizonDays(): number {
  const input = elementById<HTMLInputElement>("predictionHorizon");
  const value = Number.parseInt(input.value, 10);
  if (!Number.isFinite(value) || value < 1 || value > 30) {
    throw new Error("预测天数必须在 1 到 30 之间");
  }
  return value;
}

function findScheduleRow(jobKey: string): HTMLTableRowElement {
  const rows = Array.from(document.querySelectorAll<HTMLTableRowElement>("#scheduleTable tbody tr"));
  const row = rows.find((item) => item.dataset.jobKey === jobKey);
  if (!row) {
    throw new Error(`Missing schedule row: ${jobKey}`);
  }
  return row;
}

function renderSummary(): void {
  elementById<HTMLDivElement>("taskCount").textContent = schedules.length ? String(schedules.length) : "-";
  elementById<HTMLDivElement>("enabledCount").textContent = schedules.length
    ? String(schedules.filter((item) => item.enabled).length)
    : "-";
  elementById<HTMLDivElement>("predictionMethodSummary").textContent = predictionConfig
    ? displayPredictionMethod(predictionConfig.method)
    : "-";
  elementById<HTMLDivElement>("horizonSummary").textContent = predictionConfig
    ? String(predictionConfig.horizonDays)
    : "-";
}

function displayPredictionMethod(method: PredictionMethod): string {
  return method === "last_observed" ? "Last" : "LSTM";
}

function renderScheduleRows(data: ScheduleConfig[]): void {
  const tbody = scheduleTableBody();
  const rows = data.map((schedule) => {
    const row = document.createElement("tr");
    row.dataset.jobKey = schedule.jobKey;

    const nameCell = appendCell(row);
    const name = document.createElement("div");
    name.className = "job-name";
    name.textContent = schedule.jobName;
    const key = document.createElement("div");
    key.className = "muted";
    key.textContent = schedule.jobKey;
    nameCell.replaceChildren(name, key);

    const enabledCell = appendCell(row);
    const enabled = document.createElement("input");
    enabled.className = "enabled-input";
    enabled.type = "checkbox";
    enabled.checked = schedule.enabled;
    enabled.setAttribute("aria-label", `${schedule.jobName} 启用状态`);
    enabledCell.appendChild(enabled);

    const cronCell = appendCell(row);
    const cronGroup = document.createElement("div");
    cronGroup.className = "cron-control";

    const cronInput = document.createElement("input");
    cronInput.className = "cron-input";
    cronInput.type = "text";
    cronInput.value = schedule.cronExpression;
    cronInput.spellcheck = false;
    cronInput.setAttribute("aria-label", `${schedule.jobName} cron 表达式`);

    const presetSelect = document.createElement("select");
    presetSelect.setAttribute("aria-label", `${schedule.jobName} 常用频率`);
    presetSelect.replaceChildren(
      ...cronPresets.map((preset) => {
        const option = document.createElement("option");
        option.value = preset.value;
        option.textContent = preset.label;
        return option;
      }),
    );
    presetSelect.addEventListener("change", () => {
      if (presetSelect.value) {
        cronInput.value = presetSelect.value;
        cronInput.classList.remove("invalid");
        setStatus("statusText", "");
      }
      presetSelect.value = "";
    });

    cronGroup.replaceChildren(cronInput, presetSelect);
    cronCell.appendChild(cronGroup);

    const descriptionCell = appendCell(row);
    descriptionCell.className = "muted";
    descriptionCell.textContent = schedule.description || "-";

    const updatedCell = appendCell(row);
    updatedCell.className = "muted nowrap";
    updatedCell.textContent = schedule.updatedAt || "-";

    return row;
  });

  tbody.replaceChildren(...rows);
}

function renderPredictionConfig(config: PredictionConfig): void {
  const methodSelect = elementById<HTMLSelectElement>("predictionMethod");
  const horizonInput = elementById<HTMLInputElement>("predictionHorizon");
  methodSelect.value = config.method;
  horizonInput.value = String(config.horizonDays);
}

function collectScheduleUpdates(): ScheduleUpdate[] {
  document.querySelectorAll<HTMLInputElement>(".cron-input").forEach((input) => {
    input.classList.remove("invalid");
  });

  return schedules.map((schedule) => {
    const row = findScheduleRow(schedule.jobKey);
    const cronInput = row.querySelector<HTMLInputElement>(".cron-input");
    const enabledInput = row.querySelector<HTMLInputElement>(".enabled-input");
    if (!cronInput || !enabledInput) {
      throw new Error(`Missing schedule inputs: ${schedule.jobKey}`);
    }

    try {
      return {
        jobKey: schedule.jobKey,
        cronExpression: validateCronExpression(cronInput.value),
        enabled: enabledInput.checked,
      };
    } catch (error) {
      cronInput.classList.add("invalid");
      throw new Error(`${schedule.jobName}: ${error instanceof Error ? error.message : "配置无效"}`);
    }
  });
}

async function loadAdminData(): Promise<void> {
  setLoading(true);
  setStatus("statusText", "加载中...");
  setStatus("scheduleStatus", "");
  setStatus("predictionStatus", "");

  const [scheduleResult, predictionResult] = await Promise.allSettled([
    fetchScheduleConfigs(),
    fetchPredictionConfig(),
  ]);

  if (scheduleResult.status === "fulfilled") {
    schedules = scheduleResult.value;
    renderScheduleRows(schedules);
    setStatus("scheduleStatus", `${schedules.length} 个任务`, "success");
  } else {
    schedules = [];
    renderScheduleRows([]);
    setStatus("scheduleStatus", "加载失败", "error");
  }

  if (predictionResult.status === "fulfilled") {
    predictionConfig = predictionResult.value;
    renderPredictionConfig(predictionConfig);
    setStatus("predictionStatus", "已加载", "success");
  } else {
    predictionConfig = null;
    setStatus("predictionStatus", "加载失败", "error");
  }

  renderSummary();
  const failures = [scheduleResult, predictionResult].filter((result) => result.status === "rejected");
  if (failures.length) {
    const firstFailure = failures[0];
    const message = firstFailure && firstFailure.status === "rejected" && firstFailure.reason instanceof Error
      ? firstFailure.reason.message
      : "配置加载失败";
    setStatus("statusText", message, "error");
  } else {
    setStatus("statusText", "配置已加载", "success");
  }
  setLoading(false);
}

async function saveAdminData(): Promise<void> {
  let updates: ScheduleUpdate[];
  let horizonDays: number;
  try {
    updates = collectScheduleUpdates();
    horizonDays = validateHorizonDays();
  } catch (error) {
    setStatus("statusText", error instanceof Error ? error.message : "配置无效", "error");
    return;
  }

  const method = elementById<HTMLSelectElement>("predictionMethod").value as PredictionMethod;
  setLoading(true);
  setStatus("statusText", "保存中...");

  const [scheduleResult, predictionResult] = await Promise.allSettled([
    saveScheduleConfigs(updates),
    savePredictionConfig({ method, horizonDays }),
  ]);

  if (scheduleResult.status === "fulfilled") {
    schedules = scheduleResult.value;
    renderScheduleRows(schedules);
    setStatus("scheduleStatus", "已保存", "success");
  } else {
    setStatus("scheduleStatus", "保存失败", "error");
  }

  if (predictionResult.status === "fulfilled") {
    predictionConfig = predictionResult.value;
    renderPredictionConfig(predictionConfig);
    setStatus("predictionStatus", "已保存", "success");
  } else {
    setStatus("predictionStatus", "保存失败", "error");
  }

  renderSummary();
  const failures = [scheduleResult, predictionResult].filter((result) => result.status === "rejected");
  if (failures.length) {
    const firstFailure = failures[0];
    const message = firstFailure && firstFailure.status === "rejected" && firstFailure.reason instanceof Error
      ? firstFailure.reason.message
      : "配置保存失败";
    setStatus("statusText", message, "error");
  } else {
    setStatus("statusText", "配置已保存", "success");
  }
  setLoading(false);
}

function downloadDataExport(): void {
  try {
    const dataset = elementById<HTMLSelectElement>("dataExportDataset").value;
    const currency = elementById<HTMLSelectElement>("dataExportCurrency").value;
    const limit = validateLimit(elementById<HTMLInputElement>("dataExportLimit"));
    const query = new URLSearchParams({ dataset, limit: String(limit) });
    if (currency) {
      query.set("currency", currency);
    }
    window.location.href = `/api/admin/export/data?${query.toString()}`;
  } catch (error) {
    setStatus("statusText", error instanceof Error ? error.message : "导出参数无效", "error");
  }
}

function downloadLogExport(): void {
  try {
    const source = elementById<HTMLSelectElement>("logExportSource").value;
    const level = elementById<HTMLSelectElement>("logExportLevel").value;
    const limit = validateLimit(elementById<HTMLInputElement>("logExportLimit"));
    const query = new URLSearchParams({ limit: String(limit) });
    if (source) {
      query.set("source", source);
    }
    if (level) {
      query.set("level", level);
    }
    window.location.href = `/api/admin/export/logs?${query.toString()}`;
  } catch (error) {
    setStatus("statusText", error instanceof Error ? error.message : "导出参数无效", "error");
  }
}

window.addEventListener("pageshow", () => {
  void loadAdminData();
});

elementById<HTMLButtonElement>("saveButton").addEventListener("click", () => {
  void saveAdminData();
});

elementById<HTMLButtonElement>("reloadButton").addEventListener("click", () => {
  void loadAdminData();
});

elementById<HTMLButtonElement>("exportDataButton").addEventListener("click", downloadDataExport);
elementById<HTMLButtonElement>("exportLogsButton").addEventListener("click", downloadLogExport);
