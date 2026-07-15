-- Only creates Janus runtime configuration tables.
-- For a full database bootstrap, use scripts/init_db_schema.sql.

CREATE TABLE IF NOT EXISTS schedule_config (
    job_key VARCHAR(50) PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    cron_expression VARCHAR(100) NOT NULL,
    `command` VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    description VARCHAR(255),
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS app_config (
    config_key VARCHAR(80) PRIMARY KEY,
    config_value VARCHAR(255) NOT NULL,
    description VARCHAR(255),
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT IGNORE INTO app_config
    (config_key, config_value, description)
VALUES
    ('prediction_method', 'lstm', '当前预测方法：lstm 或 last_observed'),
    ('prediction_horizon_days', '7', '预测未来天数');
