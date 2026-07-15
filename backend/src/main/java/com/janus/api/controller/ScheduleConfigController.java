package com.janus.api.controller;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.sql.Timestamp;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

@RestController
public class ScheduleConfigController {

    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Pattern CRON_FIELD_PATTERN = Pattern.compile("^[0-9A-Za-z*/,-]+$");
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
        ensureScheduleConfig();
        return loadSchedules();
    }

    @PostMapping("/api/admin/schedules")
    @Transactional
    public List<Map<String, Object>> updateSchedules(@RequestBody List<ScheduleUpdateRequest> requests) {
        ensureScheduleConfig();
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

    private void ensureScheduleConfig() {
        jdbcTemplate.execute(
                """
                CREATE TABLE IF NOT EXISTS schedule_config (
                    job_key VARCHAR(50) PRIMARY KEY,
                    job_name VARCHAR(100) NOT NULL,
                    cron_expression VARCHAR(100) NOT NULL,
                    `command` VARCHAR(255) NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    description VARCHAR(255),
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """
        );

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

    private String format(Timestamp timestamp) {
        return timestamp == null ? null : DATE_TIME_FORMATTER.format(timestamp.toLocalDateTime());
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
}
