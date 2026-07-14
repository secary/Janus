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
