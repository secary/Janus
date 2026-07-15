package com.janus.api.controller;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.sql.Timestamp;
import java.time.format.DateTimeFormatter;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Pattern;

@RestController
public class ScheduleConfigController {

    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Pattern CRON_FIELD_PATTERN = Pattern.compile("^[0-9A-Za-z*/,-]+$");
    private static final List<String> PREDICTION_METHODS = List.of("lstm", "last_observed");
    private static final List<DefaultSchedule> DEFAULT_SCHEDULES = List.of(
            new DefaultSchedule(
                    "exchange_crawler",
                    "汇率抓取",
                    "*/30 * * * *",
                    "/app/.venv/bin/python /app/main/Janus.py",
                    true,
                    "抓取中国银行汇率并写入 history 表"
            ),
            new DefaultSchedule(
                    "exchange_prediction",
                    "汇率预测",
                    "0 2 * * *",
                    "/app/.venv/bin/python /app/predictor/Jervis.py",
                    true,
                    "生成未来汇率预测并写入 prediction 表"
            ),
            new DefaultSchedule(
                    "model_training",
                    "模型训练",
                    "0 3 1 * *",
                    "/app/.venv/bin/python /app/predictor/tune_lstm.py",
                    true,
                    "周期性训练 LSTM 模型"
            )
    );

    private final JdbcTemplate jdbcTemplate;

    public ScheduleConfigController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping("/api/admin/schedules")
    public List<Map<String, Object>> schedules() {
        ensureScheduleConfigRows();
        return loadSchedules();
    }

    @GetMapping("/api/admin/prediction-config")
    public Map<String, Object> predictionConfig() {
        ensureAppConfigRows();
        return loadPredictionConfig();
    }

    @PostMapping("/api/admin/schedules")
    @Transactional
    public List<Map<String, Object>> updateSchedules(@RequestBody List<ScheduleUpdateRequest> requests) {
        ensureScheduleConfigRows();
        if (requests == null || requests.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请求中缺少调度配置");
        }

        for (ScheduleUpdateRequest request : requests) {
            if (request.jobKey() == null || request.jobKey().isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请求中缺少 jobKey");
            }
            if (request.enabled() == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请求中缺少 enabled");
            }

            String cronExpression = validateCronExpression(request.cronExpression());
            int updated = jdbcTemplate.update(
                    """
                    UPDATE schedule_config
                    SET cron_expression = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_key = ?
                    """,
                    cronExpression,
                    request.enabled(),
                    request.jobKey()
            );
            if (updated == 0) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "未知调度任务: " + request.jobKey());
            }
        }

        return loadSchedules();
    }

    @PostMapping("/api/admin/prediction-config")
    @Transactional
    public Map<String, Object> updatePredictionConfig(@RequestBody PredictionConfigRequest request) {
        ensureAppConfigRows();
        if (request == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请求中缺少预测配置");
        }

        String method = validatePredictionMethod(request.method());
        int horizonDays = validateHorizonDays(request.horizonDays());
        upsertAppConfig("prediction_method", method, "当前预测方法：lstm 或 last_observed");
        upsertAppConfig("prediction_horizon_days", String.valueOf(horizonDays), "预测未来天数");
        return loadPredictionConfig();
    }

    @GetMapping("/api/admin/export/data")
    public ResponseEntity<byte[]> exportData(
            @RequestParam(defaultValue = "history") String dataset,
            @RequestParam(required = false) String currency,
            @RequestParam(defaultValue = "1000") Integer limit
    ) {
        String normalizedDataset = validateDataset(dataset);
        int normalizedLimit = validateLimit(limit);
        String sql = switch (normalizedDataset) {
            case "prediction" -> """
                    SELECT Date, Currency, Predicted_rate AS Rate, Locals
                    FROM prediction
                    WHERE (? IS NULL OR Currency = ?)
                    ORDER BY Date DESC
                    LIMIT ?
                    """;
            case "history" -> """
                    SELECT Date, Currency, Rate, Locals
                    FROM history
                    WHERE (? IS NULL OR Currency = ?)
                    ORDER BY Date DESC
                    LIMIT ?
                    """;
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "不支持的数据集");
        };

        String normalizedCurrency = normalizeCurrency(currency);
        List<Map<String, Object>> rows = jdbcTemplate.query(
                sql,
                (rs, rowNum) -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("Date", format(rs.getTimestamp("Date")));
                    item.put("Currency", rs.getString("Currency"));
                    item.put("Rate", rs.getObject("Rate"));
                    item.put("Locals", rs.getString("Locals"));
                    return item;
                },
                normalizedCurrency,
                normalizedCurrency,
                normalizedLimit
        );

        String filename = "janus-" + normalizedDataset + ".csv";
        return csvResponse(filename, toCsv(List.of("Date", "Currency", "Rate", "Locals"), rows));
    }

    @GetMapping("/api/admin/export/logs")
    public ResponseEntity<byte[]> exportLogs(
            @RequestParam(required = false) String source,
            @RequestParam(required = false) String level,
            @RequestParam(defaultValue = "1000") Integer limit
    ) {
        int normalizedLimit = validateLimit(limit);
        String normalizedSource = normalizeText(source);
        String normalizedLevel = normalizeText(level);
        List<Map<String, Object>> rows = jdbcTemplate.query(
                """
                SELECT timestamp, level, source, module, log_type, message
                FROM logs
                WHERE (? IS NULL OR source = ?)
                  AND (? IS NULL OR level = ?)
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (rs, rowNum) -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("timestamp", format(rs.getTimestamp("timestamp")));
                    item.put("level", rs.getString("level"));
                    item.put("source", rs.getString("source"));
                    item.put("module", rs.getString("module"));
                    item.put("log_type", rs.getString("log_type"));
                    item.put("message", rs.getString("message"));
                    return item;
                },
                normalizedSource,
                normalizedSource,
                normalizedLevel,
                normalizedLevel,
                normalizedLimit
        );

        return csvResponse(
                "janus-logs.csv",
                toCsv(List.of("timestamp", "level", "source", "module", "log_type", "message"), rows)
        );
    }

    private void ensureScheduleConfigRows() {
        if (!scheduleConfigTableExists()) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "缺少 schedule_config 表，请先使用数据库管理员账号执行 scripts/schedule_config_schema.mysql"
            );
        }

        for (DefaultSchedule schedule : DEFAULT_SCHEDULES) {
            jdbcTemplate.update(
                    """
                    INSERT IGNORE INTO schedule_config
                    (job_key, job_name, cron_expression, `command`, enabled, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    schedule.jobKey(),
                    schedule.jobName(),
                    schedule.cronExpression(),
                    schedule.command(),
                    schedule.enabled(),
                    schedule.description()
            );
        }
    }

    private void ensureAppConfigRows() {
        if (!appConfigTableExists()) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "缺少 app_config 表，请先使用数据库管理员账号执行 scripts/schedule_config_schema.mysql"
            );
        }

        upsertAppConfig("prediction_method", "lstm", "当前预测方法：lstm 或 last_observed", true);
        upsertAppConfig("prediction_horizon_days", "7", "预测未来天数", true);
    }

    private boolean scheduleConfigTableExists() {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name = 'schedule_config'
                """,
                Integer.class
        );
        return count != null && count > 0;
    }

    private boolean appConfigTableExists() {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name = 'app_config'
                """,
                Integer.class
        );
        return count != null && count > 0;
    }

    private List<Map<String, Object>> loadSchedules() {
        return jdbcTemplate.query(
                """
                SELECT job_key, job_name, cron_expression, `command` AS command_text,
                       enabled, description, updated_at
                FROM schedule_config
                ORDER BY job_key ASC
                """,
                (rs, rowNum) -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("jobKey", rs.getString("job_key"));
                    item.put("jobName", rs.getString("job_name"));
                    item.put("cronExpression", rs.getString("cron_expression"));
                    item.put("command", rs.getString("command_text"));
                    item.put("enabled", rs.getBoolean("enabled"));
                    item.put("description", rs.getString("description"));
                    item.put("updatedAt", format(rs.getTimestamp("updated_at")));
                    return item;
                }
        );
    }

    private Map<String, Object> loadPredictionConfig() {
        Map<String, String> values = jdbcTemplate.query(
                """
                SELECT config_key, config_value
                FROM app_config
                WHERE config_key IN ('prediction_method', 'prediction_horizon_days')
                """,
                rs -> {
                    Map<String, String> items = new LinkedHashMap<>();
                    while (rs.next()) {
                        items.put(rs.getString("config_key"), rs.getString("config_value"));
                    }
                    return items;
                }
        );

        String method = validatePredictionMethod(values.getOrDefault("prediction_method", "lstm"));
        int horizonDays = validateHorizonDays(toInteger(values.get("prediction_horizon_days"), 7));
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("method", method);
        response.put("horizonDays", horizonDays);
        response.put("availableMethods", PREDICTION_METHODS);
        return response;
    }

    private void upsertAppConfig(String key, String value, String description) {
        upsertAppConfig(key, value, description, false);
    }

    private void upsertAppConfig(String key, String value, String description, boolean keepExisting) {
        String sql = keepExisting
                ? """
                INSERT IGNORE INTO app_config (config_key, config_value, description)
                VALUES (?, ?, ?)
                """
                : """
                INSERT INTO app_config (config_key, config_value, description)
                VALUES (?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    config_value = VALUES(config_value),
                    description = VALUES(description),
                    updated_at = CURRENT_TIMESTAMP
                """;
        jdbcTemplate.update(sql, key, value, description);
    }

    private String validateCronExpression(String value) {
        if (value == null || value.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "cron 表达式不能为空");
        }

        String expression = value.trim().replaceAll("\\s+", " ");
        String[] fields = expression.split(" ");
        if (fields.length != 5) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "cron 表达式必须包含 5 个字段");
        }

        for (String field : fields) {
            if (!CRON_FIELD_PATTERN.matcher(field).matches()) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "cron 字段不支持: " + field);
            }
        }

        return expression;
    }

    private String validatePredictionMethod(String value) {
        String method = Objects.toString(value, "").trim();
        if (!PREDICTION_METHODS.contains(method)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "不支持的预测方法: " + method);
        }
        return method;
    }

    private int validateHorizonDays(Integer value) {
        int days = value == null ? 7 : value;
        if (days < 1 || days > 30) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "预测天数必须在 1 到 30 之间");
        }
        return days;
    }

    private int validateLimit(Integer value) {
        int limit = value == null ? 1000 : value;
        if (limit < 1 || limit > 10000) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "导出条数必须在 1 到 10000 之间");
        }
        return limit;
    }

    private String validateDataset(String value) {
        String dataset = Objects.toString(value, "history").trim();
        if (!List.of("history", "prediction").contains(dataset)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "不支持的数据集: " + dataset);
        }
        return dataset;
    }

    private Integer toInteger(String value, int fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private String normalizeCurrency(String value) {
        String text = normalizeText(value);
        return text == null ? null : text.toUpperCase();
    }

    private String normalizeText(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private String format(Timestamp timestamp) {
        return timestamp == null ? null : DATE_TIME_FORMATTER.format(timestamp.toLocalDateTime());
    }

    private ResponseEntity<byte[]> csvResponse(String filename, String csv) {
        byte[] bytes = csv.getBytes(StandardCharsets.UTF_8);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(new MediaType("text", "csv", StandardCharsets.UTF_8))
                .body(bytes);
    }

    private String toCsv(List<String> headers, List<Map<String, Object>> rows) {
        StringBuilder csv = new StringBuilder();
        csv.append(String.join(",", headers)).append("\n");
        for (Map<String, Object> row : rows) {
            for (int i = 0; i < headers.size(); i++) {
                if (i > 0) {
                    csv.append(",");
                }
                csv.append(csvValue(row.get(headers.get(i))));
            }
            csv.append("\n");
        }
        return csv.toString();
    }

    private String csvValue(Object value) {
        String text = Objects.toString(value, "");
        boolean escaped = text.contains(",") || text.contains("\"") || text.contains("\n") || text.contains("\r");
        String normalized = text.replace("\"", "\"\"");
        return escaped ? "\"" + normalized + "\"" : normalized;
    }

    private record DefaultSchedule(
            String jobKey,
            String jobName,
            String cronExpression,
            String command,
            boolean enabled,
            String description
    ) {
    }

    private record ScheduleUpdateRequest(String jobKey, String cronExpression, Boolean enabled) {
    }

    private record PredictionConfigRequest(String method, Integer horizonDays) {
    }
}
