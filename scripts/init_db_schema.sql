-- Janus database bootstrap SQL.
-- Defines Janus runtime tables and default seed data.
-- Run this after selecting the target database, for example: USE exchange;

CREATE TABLE IF NOT EXISTS history (
    `Date` DATETIME NOT NULL,
    Currency VARCHAR(20) NOT NULL,
    Rate DOUBLE,
    Locals VARCHAR(50),
    PRIMARY KEY (`Date`, Currency)
);

CREATE TABLE IF NOT EXISTS thresholds (
    Currency VARCHAR(20) PRIMARY KEY,
    Upper DOUBLE,
    Lower DOUBLE
);

CREATE TABLE IF NOT EXISTS auto_switch (
    `key` VARCHAR(50) PRIMARY KEY,
    value BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_config (
    job_key VARCHAR(50) PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    cron_expression VARCHAR(100) NOT NULL,
    `command` VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    description VARCHAR(255),
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_config (
    config_key VARCHAR(80) PRIMARY KEY,
    config_value VARCHAR(255) NOT NULL,
    description VARCHAR(255),
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS currency_map (
    id INT NOT NULL AUTO_INCREMENT,
    name_cn VARCHAR(20) NOT NULL,
    code_en VARCHAR(10) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_currency_map_name_cn (name_cn),
    UNIQUE KEY uq_currency_map_code_en (code_en)
);

CREATE TABLE IF NOT EXISTS prediction (
    `Date` DATETIME NOT NULL,
    Currency VARCHAR(20) NOT NULL,
    Predicted_rate DOUBLE NOT NULL,
    Locals VARCHAR(50),
    PRIMARY KEY (`Date`, Currency)
);

CREATE TABLE IF NOT EXISTS logs (
    id BIGINT NOT NULL AUTO_INCREMENT,
    timestamp DATETIME,
    level VARCHAR(20),
    trace_id VARCHAR(100),
    module VARCHAR(100),
    source VARCHAR(50),
    log_type VARCHAR(20),
    message TEXT,
    method VARCHAR(10),
    path VARCHAR(255),
    ip VARCHAR(50),
    status_code INT,
    latency_ms INT,
    job_name VARCHAR(100),
    script VARCHAR(100),
    exit_code INT,
    extra JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

SET @history_index_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'history'
      AND INDEX_NAME = 'idx_history_currency_date'
);
SET @history_index_sql = IF(
    @history_index_exists = 0,
    'CREATE INDEX idx_history_currency_date ON history (Currency, `Date`)',
    'SELECT 1'
);
PREPARE history_index_stmt FROM @history_index_sql;
EXECUTE history_index_stmt;
DEALLOCATE PREPARE history_index_stmt;

INSERT IGNORE INTO currency_map (code_en, name_cn)
VALUES
    ('USD', '美元'),
    ('JPY', '日元'),
    ('AUD', '澳大利亚元');

INSERT IGNORE INTO schedule_config
    (job_key, job_name, cron_expression, `command`, enabled, description)
VALUES
    (
        'exchange_crawler',
        '汇率抓取',
        '*/30 * * * *',
        '/app/.venv/bin/python /app/main/Janus.py',
        TRUE,
        '抓取中国银行汇率并写入 history 表'
    ),
    (
        'exchange_prediction',
        '汇率预测',
        '0 2 * * *',
        '/app/.venv/bin/python /app/predictor/Jervis.py',
        TRUE,
        '生成未来汇率预测并写入 prediction 表'
    ),
    (
        'model_training',
        '模型训练',
        '0 3 1 * *',
        '/app/.venv/bin/python /app/predictor/tune_lstm.py',
        TRUE,
        '周期性训练 LSTM 模型'
    );

INSERT IGNORE INTO app_config
    (config_key, config_value, description)
VALUES
    ('prediction_method', 'lstm', '当前预测方法：lstm 或 last_observed'),
    ('prediction_horizon_days', '7', '预测未来天数');
