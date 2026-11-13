-- 002: 误报控制模式冻结列（在线迁移 src/models/migrations.py 会自动执行，本文件为归档记录）
-- 旧库升级：补列并把历史运行回填为单窗旧规则，历史档案与下载保持不变。
ALTER TABLE deviation_runs ADD COLUMN IF NOT EXISTS error_control VARCHAR NOT NULL DEFAULT 'single_window';
UPDATE deviation_runs SET error_control='single_window' WHERE error_control IS NULL;
