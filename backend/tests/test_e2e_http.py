import csv
import io
import json
import os
import tempfile
import threading
import time
import unittest

_TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "e2e.db")
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET"] = "e2e-secret"
os.environ["SEED_DEMO"] = "false"
os.environ["ARTIFACTS_DIR"] = os.path.join(_TMP, "artifacts")

import fakeredis
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.config import database as dbmod
# sqlite 跨线程（HTTP主线程 + worker线程）共用引擎
_engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
dbmod.engine = _engine
dbmod.SessionLocal.configure(bind=_engine)

from src.services import run_service
run_service.queue = fakeredis.FakeRedis(decode_responses=True)

from src.config.database import Base, SessionLocal
from src.models import DeviationRun, ReviewNote
from src.models.deviation_run import SINGLE_WINDOW, FAMILY_WISE


def _worker_loop():
    import src.worker  # noqa: F401  导入即进入真实 worker 循环


class TestHttpEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(_engine)
        from scripts.seed_demo import seed
        seed()
        cls.worker = threading.Thread(target=_worker_loop, daemon=True)
        cls.worker.start()
        from src.main import app
        cls.client = TestClient(app)
        cls.tokens = {}
        for role, email in [("analyst", "analyst@shuangleng.demo"),
                            ("admin", "admin@shuangleng.demo"),
                            ("viewer", "viewer@shuangleng.demo")]:
            r = cls.client.post("/auth/login", json={"email": email, "password": "Shuangleng2026!"})
            assert r.status_code == 200, r.text
            cls.tokens[role] = r.json()["token"]

    def _h(self, role):
        return {"Authorization": "Bearer " + self.tokens[role]}

    def _wait_completed(self, rid, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.client.get(f"/runs/{rid}", headers=self._h("viewer"))
            data = r.json()
            if data["status"] in ("completed", "failed"):
                return data
            time.sleep(0.2)
        raise TimeoutError("run did not finish")

    def test_01_invalid_mode_rejected_422(self):
        r = self.client.post("/runs", headers=self._h("analyst"),
                             json={"name": "非法模式研究", "study_id": 1, "alpha": .05, "seed": 2026,
                                   "error_control": "bonferroni"})
        self.assertEqual(r.status_code, 422)

    def test_02_viewer_cannot_create_403(self):
        r = self.client.post("/runs", headers=self._h("viewer"),
                             json={"name": "阅读者越权研究", "study_id": 1, "alpha": .05, "seed": 1,
                                   "error_control": FAMILY_WISE})
        self.assertEqual(r.status_code, 403)

    def test_03_create_family_wise_run_full_pipeline_and_artifact(self):
        r = self.client.post("/runs", headers=self._h("analyst"),
                             json={"name": "E2E整批Holm研究", "study_id": 1, "alpha": .05,
                                   "seed": 2026, "error_control": FAMILY_WISE})
        self.assertEqual(r.status_code, 202)
        rid = r.json()["id"]
        # 模式在创建时冻结到行上
        self.assertEqual(r.json()["error_control"], FAMILY_WISE)
        run = self._wait_completed(rid)
        self.assertEqual(run["status"], "completed", run.get("error"))
        res = run["result"]
        self.assertEqual(res["error_control"], FAMILY_WISE)
        self.assertEqual(res["algorithm_version"], "train-mcd-split-conformal-v2")
        n = res["counts"]["test"]
        # 完整测试集合一次性判定，且前端展示字段齐备
        self.assertEqual(res["selected_count"], sum(x["p_adj"] <= .05 for x in res["test"]))
        for x in res["test"]:
            self.assertIn("p", x); self.assertIn("p_adj", x); self.assertIn("selection_reason", x)
            self.assertGreaterEqual(x["p_adj"], x["p"] - 1e-15)
            self.assertEqual(x["selected"], x["p_adj"] <= .05)
        # 整批100窗在 m=150、alpha=.05 下分辨率不足，无人入选且有说明
        self.assertEqual(n, 100)
        self.assertEqual(res["selected_count"], 0)
        self.assertIn("分辨率", res["no_selection_note"])
        # worker 写出完整结果 JSON 产物
        with open(os.path.join(os.environ["ARTIFACTS_DIR"], f"run-{rid}.json"), encoding="utf-8") as f:
            artifact = json.load(f)
        self.assertEqual(artifact["input_hash"], res["input_hash"])
        self.__class__._holm_rid = rid

    def test_04_single_window_run_keeps_legacy_rule(self):
        r = self.client.post("/runs", headers=self._h("analyst"),
                             json={"name": "E2E单窗研究", "study_id": 1, "alpha": .05,
                                   "seed": 2026, "error_control": SINGLE_WINDOW})
        rid = r.json()["id"]
        self.assertEqual(r.json()["error_control"], SINGLE_WINDOW)
        run = self._wait_completed(rid)
        res = run["result"]
        for x in res["test"]:
            self.assertAlmostEqual(x["p_adj"], x["p"])
            self.assertEqual(x["selected"], x["p"] <= .05)
        self.assertEqual(res["selected_count"], sum(x["p"] <= .05 for x in res["test"]))
        self.__class__._single_rid = rid

    def test_05_unapproved_export_403_and_analyst_cannot_approve_403(self):
        rid = self.__class__._holm_rid
        r = self.client.get(f"/runs/{rid}/export", headers=self._h("viewer"))
        self.assertEqual(r.status_code, 403)
        # 研究员提交补测建议
        r = self.client.post("/notes", headers=self._h("analyst"),
                             json={"run_id": rid, "title": "E2E补测说明",
                                   "interpretation": "整批Holm校正后无窗入选，记录分辨率原因。",
                                   "proposal": "保持冻结配置，独立窗口补测，不重算筛选。"})
        self.assertEqual(r.status_code, 201)
        nid = r.json()["id"]
        # 研究员审批 403
        r = self.client.patch(f"/notes/{nid}/review", headers=self._h("analyst"),
                              json={"status": "approved", "review_note": "越权批准应被拒绝的长意见"})
        self.assertEqual(r.status_code, 403)
        # 负责人批准
        r = self.client.patch(f"/notes/{nid}/review", headers=self._h("admin"),
                              json={"status": "approved", "review_note": "批准归档，按完整测试集合判定不变。"})
        self.assertEqual(r.status_code, 200)
        # 重复审批 409
        r = self.client.patch(f"/notes/{nid}/review", headers=self._h("admin"),
                              json={"status": "rejected", "review_note": "重复审批应冲突的长意见"})
        self.assertEqual(r.status_code, 409)
        self.__class__._note_id = nid

    def test_06_approved_holm_export_has_new_columns(self):
        rid = self.__class__._holm_rid
        r = self.client.get(f"/runs/{rid}/export", headers=self._h("viewer"))
        self.assertEqual(r.status_code, 200)
        rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
        self.assertIn("holm_adjusted_p", rows[0])
        self.assertIn("holm_rank", rows[0])
        self.assertIn("holm_multiplier", rows[0])
        self.assertIn("error_control", rows[0])
        self.assertIn("selection_reason", rows[0])
        idx = {h: i for i, h in enumerate(rows[0])}
        self.assertEqual(len(rows) - 1, 100)  # 完整测试集合，不随筛选裁剪
        self.assertTrue(all(row[idx["error_control"]] == FAMILY_WISE for row in rows[1:]))
        self.assertTrue(all("Holm" in row[idx["selection_reason"]] for row in rows[1:]))

    def test_07_legacy_v1_archive_exports_old_format_unchanged(self):
        # 手工植入升级前 v1 结果（无 error_control/p_adj），模拟旧库回读
        v1 = {
            "algorithm_version": "train-mcd-split-conformal-v1",
            "study": {"id": 1, "code": "SL-01", "name": "旧档"},
            "features": [{"code": c, "position": i} for i, c in
                         enumerate(["temperature", "humidity", "particles", "variation"])],
            "counts": {"train": 200, "cal": 150, "test": 2},
            "fit": {"warnings": []}, "fit_hash": "oldfit", "input_hash": "oldin",
            "calibration": [],
            "test": [
                {"window": {"code": "OLD-W1", "split": "test", "values": {c: 1.0 for c in
                            ["temperature", "humidity", "particles", "variation"]}},
                 "d2": 9.0, "cal_ge_count": 0, "p": .01, "selected": True},
                {"window": {"code": "OLD-W2", "split": "test", "values": {c: 2.0 for c in
                            ["temperature", "humidity", "particles", "variation"]}},
                 "d2": 1.0, "cal_ge_count": 100, "p": .8, "selected": False}],
            "calibration_ecdf": [], "alpha": .05, "seed": 2026, "selected_count": 1,
            "resolution": 1 / 151, "tail": "", "input_snapshot": {"windows": []},
            "assumptions": "", "protocol": ""}
        with SessionLocal() as db:
            run = DeviationRun(name="升级前v1旧档", study_id=1, alpha=.05, seed=2026,
                               error_control=SINGLE_WINDOW, input_snapshot={}, status="completed",
                               result=v1, owner="旧分析员")
            db.add(run); db.flush()
            db.add(ReviewNote(run_id=run.id, title="旧档批注", interpretation="历史说明足够长",
                              proposal="历史方案足够长", status="approved", owner="o",
                              reviewer="r", review_note="历史批准意见足够长"))
            db.commit()
            legacy_rid = run.id
        r = self.client.get(f"/runs/{legacy_rid}/export", headers=self._h("viewer"))
        self.assertEqual(r.status_code, 200)
        rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
        # 旧档下载列与升级前完全一致
        self.assertEqual(rows[0], ["window", "split", "temperature", "humidity", "particles",
                                   "variation", "D_squared", "cal_ge_count", "upper_tail_p",
                                   "preset_alpha", "selected", "cal_m", "seed", "fit_hash",
                                   "input_hash"])
        self.assertEqual(len(rows), 3)
        # 旧档经 API 回读仍带单窗冻结标记，结果体保持原样
        got = self.client.get(f"/runs/{legacy_rid}", headers=self._h("viewer")).json()
        self.assertEqual(got["error_control"], SINGLE_WINDOW)
        self.assertNotIn("error_control", got["result"])


if __name__ == "__main__":
    unittest.main()
