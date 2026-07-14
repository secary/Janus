package com.janus.api.controller;

import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

@RestController
public class JanusApiController {

    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbcTemplate;

    public JanusApiController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/api/history")
    public List<Map<String, Object>> history(@RequestParam(required = false) String currency) {
        String baseSql = """
                SELECT Date, Currency, Rate, Locals
                FROM history
                """;
        String sql = currency == null || currency.isBlank()
                ? baseSql + " ORDER BY Date DESC LIMIT 100"
                : baseSql + " WHERE Currency = ? ORDER BY Date DESC LIMIT 100";

        List<HistoryRow> rows = currency == null || currency.isBlank()
                ? jdbcTemplate.query(sql, this::mapHistoryRow)
                : jdbcTemplate.query(sql, this::mapHistoryRow, currency);

        return rows.stream()
                .map(row -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("Date", format(row.date()));
                    item.put("Currency", row.currency());
                    item.put("Rate", row.rate());
                    item.put("Locals", row.locals());
                    return item;
                })
                .toList();
    }

    @GetMapping("/api/logs/latest")
    public List<Map<String, Object>> latestLogs() {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT timestamp, level, message
                FROM logs
                WHERE source = 'janus'
                ORDER BY timestamp DESC
                LIMIT 50
                """, (rs, rowNum) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("timestamp", format(getLocalDateTime(rs, "timestamp")));
            item.put("level", rs.getString("level"));
            item.put("message", rs.getString("message"));
            return item;
        });

        Collections.reverse(rows);
        return rows;
    }

    @GetMapping("/api/config")
    public List<Map<String, Object>> getConfig() {
        return jdbcTemplate.query("""
                SELECT Currency, Upper, Lower
                FROM thresholds
                ORDER BY Currency ASC
                """, (rs, rowNum) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("Currency", rs.getString("Currency"));
            item.put("Upper", getNullableDouble(rs, "Upper"));
            item.put("Lower", getNullableDouble(rs, "Lower"));
            return item;
        });
    }

    @PostMapping("/api/config")
    @Transactional
    public Map<String, Object> updateConfig(@RequestBody Map<String, Object> request) {
        Object currencyValue = request.get("Currency");
        if (currencyValue == null || currencyValue.toString().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请求中缺少 Currency 字段");
        }

        String currency = currencyValue.toString();
        ThresholdRow existing = findThreshold(currency);
        Double upper = request.containsKey("Upper") ? toNullableDouble(request.get("Upper")) : existing == null ? null : existing.upper();
        Double lower = request.containsKey("Lower") ? toNullableDouble(request.get("Lower")) : existing == null ? null : existing.lower();

        if (existing == null) {
            jdbcTemplate.update(
                    "INSERT INTO thresholds (Currency, Upper, Lower) VALUES (?, ?, ?)",
                    currency,
                    upper,
                    lower
            );
        } else {
            jdbcTemplate.update(
                    "UPDATE thresholds SET Upper = ?, Lower = ? WHERE Currency = ?",
                    upper,
                    lower,
                    currency
            );
        }

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "配置已更新");
        response.put("Currency", currency);
        response.put("Upper", upper);
        response.put("Lower", lower);
        return response;
    }

    @GetMapping("/api/latest")
    public List<Map<String, Object>> latestRates() {
        List<HistoryRow> latestHistory = jdbcTemplate.query("""
                SELECT h.Date, h.Currency, h.Rate, h.Locals
                FROM history h
                INNER JOIN (
                    SELECT Currency, MAX(Date) AS Date
                    FROM history
                    GROUP BY Currency
                ) latest
                  ON h.Currency = latest.Currency
                 AND h.Date = latest.Date
                ORDER BY h.Date DESC, h.Currency ASC
                """, this::mapHistoryRow);

        List<Map<String, Object>> response = new ArrayList<>();
        for (HistoryRow row : latestHistory) {
            LocalDateTime anchor = parseLocalTime(row.locals());
            if (anchor == null) {
                anchor = row.date();
            }
            LocalDateTime predictionDate = floorToHalfHour(anchor);
            PredictionRow prediction = findPrediction(row.currency(), predictionDate);

            Map<String, Object> item = new LinkedHashMap<>();
            item.put("Date", format(row.date()));
            item.put("Locals", row.locals());
            item.put("Currency", row.currency());
            item.put("Rate", row.rate());
            item.put("PredictedRate", prediction == null ? null : prediction.predictedRate());
            item.put("PredictionDate", prediction == null ? null : format(predictionDate));
            response.add(item);
        }

        return response;
    }

    @GetMapping("/api/history/chart")
    public Map<String, List<Map<String, Object>>> historyChart() {
        List<HistoryRow> historyRows = jdbcTemplate.query("""
                SELECT Date, Currency, Rate, Locals
                FROM history
                ORDER BY Date DESC
                """, this::mapHistoryRow);

        List<PredictionRow> predictionRows = jdbcTemplate.query("""
                SELECT Date, Currency, Predicted_rate, Locals
                FROM prediction
                ORDER BY Date DESC
                """, this::mapPredictionRow);

        Map<String, Map<LocalDateTime, Double>> historyMap = new HashMap<>();
        for (HistoryRow row : historyRows) {
            LocalDateTime anchor = parseLocalTime(row.locals());
            if (anchor == null) {
                anchor = row.date();
            }
            LocalDateTime timestamp = floorToHalfHour(anchor);
            historyMap.computeIfAbsent(row.currency(), ignored -> new HashMap<>())
                    .putIfAbsent(timestamp, row.rate());
        }

        Map<String, Map<LocalDateTime, Double>> predictionMap = new HashMap<>();
        for (PredictionRow row : predictionRows) {
            LocalDateTime timestamp = floorToHalfHour(row.date());
            predictionMap.computeIfAbsent(row.currency(), ignored -> new HashMap<>())
                    .putIfAbsent(timestamp, row.predictedRate());
        }

        Set<String> currencies = new TreeSet<>();
        currencies.addAll(historyMap.keySet());
        currencies.addAll(predictionMap.keySet());

        Map<String, List<Map<String, Object>>> response = new LinkedHashMap<>();
        for (String currency : currencies) {
            List<LocalDateTime> historyTimes = new ArrayList<>(historyMap.getOrDefault(currency, Map.of()).keySet());
            Collections.sort(historyTimes);
            if (historyTimes.isEmpty()) {
                continue;
            }

            List<LocalDateTime> latestHistoryTimes = historyTimes.subList(Math.max(0, historyTimes.size() - 20), historyTimes.size());
            LocalDateTime latestHistoryDate = latestHistoryTimes.get(latestHistoryTimes.size() - 1);

            List<LocalDateTime> futurePredictionTimes = predictionMap.getOrDefault(currency, Map.of()).keySet().stream()
                    .filter(date -> date.isAfter(latestHistoryDate))
                    .sorted()
                    .limit(1)
                    .toList();

            Set<LocalDateTime> chartTimes = new TreeSet<>();
            chartTimes.addAll(latestHistoryTimes);
            chartTimes.addAll(futurePredictionTimes);

            List<Map<String, Object>> merged = new ArrayList<>();
            for (LocalDateTime date : chartTimes) {
                Double predictionValue = predictionMap.getOrDefault(currency, Map.of()).get(date);
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("datetime", format(date));
                item.put("rate", historyMap.getOrDefault(currency, Map.of()).get(date));
                item.put("predicted", predictionValue);
                item.put("prediction_datetime", predictionValue == null ? null : format(date));
                merged.add(item);
            }
            response.put(currency, merged);
        }

        return response;
    }

    private HistoryRow mapHistoryRow(ResultSet rs, int rowNum) throws SQLException {
        return new HistoryRow(
                getLocalDateTime(rs, "Date"),
                rs.getString("Currency"),
                getNullableDouble(rs, "Rate"),
                rs.getString("Locals")
        );
    }

    private PredictionRow mapPredictionRow(ResultSet rs, int rowNum) throws SQLException {
        return new PredictionRow(
                getLocalDateTime(rs, "Date"),
                rs.getString("Currency"),
                getNullableDouble(rs, "Predicted_rate"),
                rs.getString("Locals")
        );
    }

    private ThresholdRow findThreshold(String currency) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT Currency, Upper, Lower FROM thresholds WHERE Currency = ?",
                    (rs, rowNum) -> new ThresholdRow(
                            rs.getString("Currency"),
                            getNullableDouble(rs, "Upper"),
                            getNullableDouble(rs, "Lower")
                    ),
                    currency
            );
        } catch (EmptyResultDataAccessException ignored) {
            return null;
        }
    }

    private PredictionRow findPrediction(String currency, LocalDateTime predictionDate) {
        try {
            return jdbcTemplate.queryForObject(
                    "SELECT Date, Currency, Predicted_rate, Locals FROM prediction WHERE Currency = ? AND Date = ?",
                    this::mapPredictionRow,
                    currency,
                    Timestamp.valueOf(predictionDate)
            );
        } catch (EmptyResultDataAccessException ignored) {
            return null;
        }
    }

    private LocalDateTime floorToHalfHour(LocalDateTime date) {
        int minute = date.getMinute() < 30 ? 0 : 30;
        return date.withMinute(minute).withSecond(0).withNano(0);
    }

    private LocalDateTime parseLocalTime(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }

        String text = value.length() > 19 ? value.substring(0, 19) : value;
        try {
            return LocalDateTime.parse(text, DATE_TIME_FORMATTER);
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    private String format(LocalDateTime dateTime) {
        return dateTime == null ? null : DATE_TIME_FORMATTER.format(dateTime);
    }

    private LocalDateTime getLocalDateTime(ResultSet rs, String column) throws SQLException {
        Timestamp timestamp = rs.getTimestamp(column);
        return timestamp == null ? null : timestamp.toLocalDateTime();
    }

    private Double getNullableDouble(ResultSet rs, String column) throws SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }

    private Double toNullableDouble(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        String text = Objects.toString(value, "").trim();
        if (text.isEmpty()) {
            return null;
        }
        try {
            return Double.parseDouble(text);
        } catch (NumberFormatException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Upper/Lower 必须是数字");
        }
    }

    private record HistoryRow(LocalDateTime date, String currency, Double rate, String locals) {
    }

    private record PredictionRow(LocalDateTime date, String currency, Double predictedRate, String locals) {
    }

    private record ThresholdRow(String currency, Double upper, Double lower) {
    }
}
