CREATE TABLE IF NOT EXISTS bu (
    bu_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    status TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS user (
    user_id VARCHAR(20) PRIMARY KEY,
    bu_id VARCHAR(20) NOT NULL,
    email VARCHAR(120),
    phone VARCHAR(20),
    status VARCHAR(20),
    INDEX idx_bu (bu_id)
);

CREATE TABLE IF NOT EXISTS card (
    card_id VARCHAR(30) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    bu_id VARCHAR(20) NOT NULL,
    card_no VARCHAR(30),
    status VARCHAR(20),
    lock_reason VARCHAR(200),
    INDEX idx_bu (bu_id)
);

CREATE TABLE IF NOT EXISTS api_call_log (
    uid VARCHAR(40) PRIMARY KEY,
    bu_id VARCHAR(20) NOT NULL,
    endpoint VARCHAR(200) NOT NULL,
    status_code INT NOT NULL,
    error_code VARCHAR(50),
    request_json TEXT,
    response_json TEXT,
    created_at DATETIME,
    INDEX idx_bu_created (bu_id, created_at)
);

INSERT INTO bu(bu_id, name, status) VALUES
  ('BU00243780', '示例合作伙伴', 1),
  ('BU_OTHER', '另一个 BU', 1);

INSERT INTO user(user_id, bu_id, email, phone, status) VALUES
  ('U1', 'BU00243780', 'alice@x.com', '13812345678', 'active'),
  ('U2', 'BU_OTHER',   'bob@x.com',   '13911112222', 'active');

INSERT INTO card(card_id, user_id, bu_id, card_no, status, lock_reason) VALUES
  ('C100', 'U1', 'BU00243780', '4938750672464590', 'locked', 'R-217 风控误判'),
  ('C200', 'U2', 'BU_OTHER',   '1111222233334444', 'active', NULL);

INSERT INTO api_call_log(uid, bu_id, endpoint, status_code, error_code, request_json, response_json, created_at) VALUES
  ('1765348436409', 'BU00243780', '/v2/card/bind', 500, 'DB_TIMEOUT', '{}', '{"error":"DB_TIMEOUT"}', '2026-05-18 10:00:00');
