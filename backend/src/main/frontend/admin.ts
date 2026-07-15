import { fetchScheduleConfigs, saveScheduleConfigs } from "./api.js";
import type { ScheduleConfig, ScheduleUpdate } from "./types";

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

function setStatus(message: string, tone: "idle" | "success" | "error" = "idle"): void {
  const status = elementById<HTMLSpanElement>("statusText");
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

function findScheduleRow(jobKey: string): HTMLTableRowElement {
  const rows = Array.from(document.querySelectorAll<HTMLTableRowElement>("#scheduleTable tbody tr"));
  const row = rows.find((item) => item.dataset.jobKey === jobKey);
  if (!row) {
    throw new Error(`Missing schedule row: ${jobKey}`);
  }
  return row;
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
    presetSelect.className = "preset-select";
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
        setStatus("");
      }
      presetSelect.value = "";
    });

    cronGroup.replaceChildren(cronInput, presetSelect);
    cronCell.appendChild(cronGroup);

    const commandCell = appendCell(row);
    const command = document.createElement("code");
    command.textContent = schedule.command;
    commandCell.appendChild(command);

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

async function loadSchedules(): Promise<void> {
  setLoading(true);
  setStatus("加载中...");
  try {
    schedules = await fetchScheduleConfigs();
    renderScheduleRows(schedules);
    setStatus(`已加载 ${schedules.length} 个任务`, "success");
  } catch {
    renderScheduleRows([]);
    setStatus("调度配置加载失败", "error");
  } finally {
    setLoading(false);
  }
}

async function saveSchedules(): Promise<void> {
  let updates: ScheduleUpdate[];
  try {
    updates = collectScheduleUpdates();
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "配置无效", "error");
    return;
  }

  setLoading(true);
  setStatus("保存中...");
  try {
    schedules = await saveScheduleConfigs(updates);
    renderScheduleRows(schedules);
    setStatus("配置已保存", "success");
  } catch {
    setStatus("配置保存失败", "error");
  } finally {
    setLoading(false);
  }
}

window.addEventListener("pageshow", () => {
  void loadSchedules();
});

elementById<HTMLButtonElement>("saveButton").addEventListener("click", () => {
  void saveSchedules();
});

elementById<HTMLButtonElement>("reloadButton").addEventListener("click", () => {
  void loadSchedules();
});
