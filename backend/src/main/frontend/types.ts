export interface LatestRate {
  Date: string;
  Locals: string | null;
  Currency: string;
  Rate: number;
  PredictedRate: number | null;
  PredictionDate: string | null;
}

export interface HistoryRow {
  Date: string;
  Currency: string;
  Rate: number;
  Locals: string | null;
}

export interface ChartPoint {
  datetime: string;
  rate: number | null;
  predicted: number | null;
  prediction_datetime: string | null;
}

export type HistoryChartResponse = Record<string, ChartPoint[]>;

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export interface ScheduleConfig {
  jobKey: string;
  jobName: string;
  cronExpression: string;
  command: string;
  enabled: boolean;
  description: string | null;
  updatedAt: string | null;
}

export interface ScheduleUpdate {
  jobKey: string;
  cronExpression: string;
  enabled: boolean;
}

export type PredictionMethod = "lstm" | "last_observed";

export interface PredictionConfig {
  method: PredictionMethod;
  horizonDays: number;
  availableMethods: PredictionMethod[];
}

export interface PredictionConfigUpdate {
  method: PredictionMethod;
  horizonDays: number;
}
