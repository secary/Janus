CREATE TABLE IF NOT EXISTS history (
    `Date` DATETIME NOT NULL,
    Currency VARCHAR(20) NOT NULL,
    Rate FLOAT,
    Locals VARCHAR(50),
    PRIMARY KEY (`Date`, Currency),
    INDEX idx_history_currency_date (Currency, `Date`)
);

CREATE TABLE IF NOT EXISTS thresholds (Currency VARCHAR(20) PRIMARY KEY, Upper FLOAT, Lower FLOAT);
CREATE TABLE IF NOT EXISTS auto_switch (`key` VARCHAR(50) PRIMARY KEY, `value` BOOLEAN NOT NULL);

CREATE TABLE IF NOT EXISTS currency_map (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name_cn VARCHAR(20) UNIQUE NOT NULL,
    code_en VARCHAR(10) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS prediction (
    `Date` DATETIME NOT NULL,
    Currency VARCHAR(20) NOT NULL,
    Predicted_rate FLOAT NOT NULL,
    Locals VARCHAR(50),
    PRIMARY KEY (`Date`, Currency)
);

CREATE TABLE IF NOT EXISTS logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME, level VARCHAR(20), trace_id VARCHAR(100), module VARCHAR(100),
    source VARCHAR(50), log_type VARCHAR(20), message TEXT, method VARCHAR(10),
    path VARCHAR(255), ip VARCHAR(50), status_code INT, latency_ms INT,
    job_name VARCHAR(100), script VARCHAR(100), exit_code INT, extra JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO currency_map (code_en, name_cn)
VALUES ('USD', '美元'), ('JPY', '日元'), ('AUD', '澳大利亚元')
ON DUPLICATE KEY UPDATE name_cn = VALUES(name_cn);
