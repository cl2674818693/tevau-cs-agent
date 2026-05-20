-- MVP-2 迁移：仅用于已存在的 MVP-1 数据库（新装库的 CREATE TABLE 已含这些列）。
-- SQLite ALTER 不支持 IF NOT EXISTS / CHECK；mode 取值在应用层校验（spec §13.2）。
ALTER TABLE conversations ADD COLUMN mode TEXT NOT NULL DEFAULT 'ai';
ALTER TABLE conversations ADD COLUMN assigned_staff_id TEXT;
ALTER TABLE conversations ADD COLUMN assigned_at TEXT;
ALTER TABLE messages ADD COLUMN sender_staff_id TEXT;

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('agent','senior','engineer')),
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
