CREATE TABLE IF NOT EXISTS mock_users (
    user_id TEXT PRIMARY KEY,
    bu_id TEXT NOT NULL,
    email TEXT,
    status TEXT
);
CREATE TABLE IF NOT EXISTS mock_cards (
    card_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    bu_id TEXT NOT NULL,
    status TEXT NOT NULL,
    lock_reason TEXT
);
CREATE TABLE IF NOT EXISTS mock_api_calls (
    uid TEXT PRIMARY KEY,
    bu_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    error_code TEXT,
    request_json TEXT,
    response_json TEXT,
    created_at TEXT
);

INSERT OR IGNORE INTO mock_users(user_id, bu_id, email, status) VALUES
  ('U1', 'BU00243780', 'a@x.com', 'active'),
  ('U2', 'BU_OTHER',   'b@x.com', 'active');

INSERT OR IGNORE INTO mock_cards(card_id, user_id, bu_id, status, lock_reason) VALUES
  ('4938750672464590', 'U1', 'BU00243780', 'locked', '风控规则 R-217 命中'),
  ('1111222233334444', 'U2', 'BU_OTHER',   'active', NULL);

INSERT OR IGNORE INTO mock_api_calls(uid, bu_id, endpoint, status_code, error_code, request_json, response_json, created_at) VALUES
  ('1765348436409', 'BU00243780', '/v2/card/bind', 500, 'DB_TIMEOUT', '{}', '{"error":"DB_TIMEOUT"}', '2026-05-18T10:00:00');
