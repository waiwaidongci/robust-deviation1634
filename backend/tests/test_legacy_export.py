import csv
import io
import os
import tempfile
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "legacy.db"))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("SEED_DEMO", "false")

from sqlalchemy import inspect
from src.config.database import Base, engine, SessionLocal
from src.models import DeviationRun, ReviewNote
from src.models.deviation_run import SINGLE_WINDOW, FAMILY_WISE
from src.models.migrations import ensure_schema
from src.services.run_service import export_run

V1_RESULT = {
    "algorithm_version": "train-mcd-split-conformal-v1",
    "features": [{"code": "temperature"}, {"code": "humidity"}, {"code": "particles"}, {"code": "variation"}],
    "counts": {"train": 20, "cal": 4, "test": 2},
    "fit": {},
    "fit_hash": "fitold",
    "input_hash": "inold",
    "calibration": [],
    "test": [
        {"window": {"code": "W1", "split": "test", "values": {"temperature": 1.0, "humidity": 2.0, "particles": 3.0, "variation": 4.0}},
         "d2": 9.1, "cal_ge_count": 0, "p": 0.2, "selected": True},
        {"window": {"code": "W2", "split": "test", "values": {"temperature": 1.1, "humidity": 2.1, "particles": 3.1, "variation": 4.1}},
         "d2": 7.3, "cal_ge_count": 1, "p": 0.4, "selected": False},
    ],
    "alpha": 0.05,
    "seed": 2026,
}

V2_RESULT = {
    "algorithm_version": "train-mcd-split-conformal-v2",
    "error_control": FAMILY_WISE,
    "features": [{"code": "temperature"}, {"code": "humidity"}, {"code": "particles"}, {"code": "variation"}],
    "counts": {"train": 20, "cal": 4, "test": 2},
    "fit": {},
    "fit_hash": "fitnew",
    "input_hash": "innew",
    "calibration": [],
    "test": [
        {"window": {"code": "W1", "split": "test", "values": {"temperature": 1.0, "humidity": 2.0, "particles": 3.0, "variation": 4.0}},
         "d2": 9.1, "cal_ge_count": 0, "p": 0.2, "p_adj": 0.4, "holm_rank": 1, "holm_multiplier": 2,
         "selected": False, "selection_reason": "整批Holm模式：校正p=0.4>α=0.05，未入选"},
        {"window": {"code": "W2", "split": "test", "values": {"temperature": 1.1, "humidity": 2.1, "particles": 3.1, "variation": 4.1}},
         "d2": 7.3, "cal_ge_count": 1, "p": 0.4, "p_adj": 0.4, "holm_rank": 2, "holm_multiplier": 1,
         "selected": False, "selection_reason": "整批Holm模式：校正p=0.4>α=0.05，未入选"},
    ],
    "alpha": 0.05,
    "seed": 2026,
}


class TestLegacyAndExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)
        ensure_schema()

    def test_migration_adds_column_with_default(self):
        cols = {c["name"] for c in inspect(engine).get_columns("deviation_runs")}
        self.assertIn("error_control", cols)

    def test_legacy_row_reads_back_single_window_and_exports_old_format(self):
        with SessionLocal() as db:
            run = DeviationRun(name="旧档单窗基线", study_id=1, alpha=.05, seed=2026,
                               error_control=SINGLE_WINDOW, input_snapshot={}, status="completed",
                               result=V1_RESULT, owner="旧分析员")
            db.add(run); db.flush()
            note = ReviewNote(run_id=run.id, title="t", interpretation="i", proposal="p",
                              status="approved", owner="o", reviewer="r", review_note="批准归档")
            db.add(note); db.commit()
            rid = run.id
            # 旧结果无 error_control 键：仍按原单窗规则回读
            self.assertNotIn("error_control", run.result)
            csv_text = export_run(db, rid)
        rows = list(csv.reader(io.StringIO(csv_text.lstrip("﻿"))))
        self.assertEqual(rows[0], ["window", "split", "temperature", "humidity", "particles", "variation",
                                   "D_squared", "cal_ge_count", "upper_tail_p", "preset_alpha", "selected",
                                   "cal_m", "seed", "fit_hash", "input_hash"])
        self.assertEqual(rows[1][0], "W1")
        self.assertEqual(rows[1][8], "0.2")
        self.assertEqual(rows[1][10], "True")
        self.assertEqual(len(rows), 3)

    def test_new_run_exports_holm_columns(self):
        with SessionLocal() as db:
            run = DeviationRun(name="整批Holm新档", study_id=1, alpha=.05, seed=2026,
                               error_control=FAMILY_WISE, input_snapshot={}, status="completed",
                               result=V2_RESULT, owner="新分析员")
            db.add(run); db.flush()
            db.add(ReviewNote(run_id=run.id, title="t", interpretation="i", proposal="p",
                              status="approved", owner="o", reviewer="r", review_note="批准归档"))
            db.commit()
            csv_text = export_run(db, run.id)
        rows = list(csv.reader(io.StringIO(csv_text.lstrip("﻿"))))
        self.assertIn("holm_adjusted_p", rows[0])
        self.assertIn("error_control", rows[0])
        self.assertIn("selection_reason", rows[0])
        idx = {h: i for i, h in enumerate(rows[0])}
        self.assertEqual(rows[1][idx["error_control"]], FAMILY_WISE)
        self.assertEqual(rows[1][idx["holm_adjusted_p"]], "0.4")
        self.assertEqual(rows[1][idx["holm_multiplier"]], "2")


if __name__ == "__main__":
    unittest.main()
