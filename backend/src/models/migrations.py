"""轻量在线迁移：为旧库 deviation_runs 补 error_control 列。

首次建表由 SQLAlchemy metadata 完成；已存在的旧库不会自动加列，
因此在应用与 worker 启动时显式 ADD COLUMN（IF NOT EXISTS），
并把历史行回填为 single_window——旧数据仍按原单窗规则展示，档案与下载不变。
"""
from sqlalchemy import text
from ..config.database import engine
from .deviation_run import SINGLE_WINDOW

def ensure_schema():
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            cols=[r[1] for r in conn.exec_driver_sql("PRAGMA table_info(deviation_runs)").fetchall()]
            if "error_control" not in cols:
                conn.exec_driver_sql(f"ALTER TABLE deviation_runs ADD COLUMN error_control VARCHAR DEFAULT '{SINGLE_WINDOW}'")
        else:
            conn.execute(text(f"ALTER TABLE deviation_runs ADD COLUMN IF NOT EXISTS error_control VARCHAR NOT NULL DEFAULT '{SINGLE_WINDOW}'"))
            conn.execute(text(f"UPDATE deviation_runs SET error_control='{SINGLE_WINDOW}' WHERE error_control IS NULL"))
