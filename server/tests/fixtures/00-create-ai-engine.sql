-- 本地 dev：compose mysql 启动时建 cs-engine 自有库 ai_engine + 读写账号。
-- 加载顺序由文件名前缀控制（00 先于 01-seed.sql）。生产用阿里云 RDS，不走此脚本。
CREATE DATABASE IF NOT EXISTS ai_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'ai'@'%' IDENTIFIED BY 'ai_local_pw';
GRANT ALL PRIVILEGES ON ai_engine.* TO 'ai'@'%';
FLUSH PRIVILEGES;
