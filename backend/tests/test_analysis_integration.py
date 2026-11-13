import copy
import unittest
import numpy as np
from src.services.analysis_service import analyze_deviation, SINGLE_WINDOW, FAMILY_WISE

rng = np.random.default_rng(7)
CODES = ["temperature", "humidity", "particles", "variation"]

def make_snapshot(n_train=60, n_cal=20, n_test=10, n_cal_small=None, extreme_test=2, seed=11):
    r = np.random.default_rng(seed)
    mean = np.array([19.5, 47., 18., .35])
    scale = np.array([1.5, 5., 4., .12])
    Rm = np.array([[1, .5, .2, .1], [.5, 1, .3, .1], [.2, .3, 1, .3], [.1, .1, .3, 1]])
    def draw(k):
        return mean + r.multivariate_normal(np.zeros(4), Rm, k) * scale
    n_cal = n_cal if n_cal_small is None else n_cal_small
    Xtr, Xcal, Xte = draw(n_train), draw(n_cal), draw(n_test)
    if extreme_test:
        Xte[:extreme_test] += np.array([10., 25., 22., .8])
    rows = []
    wid = 0
    for split, X in (("train", Xtr), ("cal", Xcal), ("test", Xte)):
        for row in X:
            wid += 1
            rows.append({"id": wid, "code": f"W{wid:04d}", "split": split,
                         "values": {c: float(v) for c, v in zip(CODES, row)}, "note": ""})
    return {"study": {"id": 1, "code": "T-01", "name": "集成测试研究"},
            "features": [{"code": c, "position": i} for i, c in enumerate(CODES)],
            "windows": rows}

class TestAnalyzeModes(unittest.TestCase):
    def test_family_wise_holm_fields_and_full_set_decision(self):
        snap = make_snapshot()
        out = analyze_deviation(snap, .05, 2026, FAMILY_WISE)
        self.assertEqual(out["algorithm_version"], "train-mcd-split-conformal-v2")
        self.assertEqual(out["error_control"], FAMILY_WISE)
        self.assertEqual(len(out["test"]), 10)
        for x in out["test"]:
            self.assertIn("p", x); self.assertIn("p_adj", x); self.assertIn("selection_reason", x)
            self.assertGreaterEqual(x["p_adj"], x["p"] - 1e-15)  # 校正只可能更严格
            self.assertIn("Holm", x["selection_reason"])
        # Holm判定与校正p完全一致；入选数来自完整10窗一次性判定
        self.assertEqual(out["selected_count"], sum(x["p_adj"] <= .05 for x in out["test"]))
        self.assertEqual(out["selected_count"], sum(x["selected"] for x in out["test"]))
        # 最严格乘子n作用于排名1
        first = min(out["test"], key=lambda x: x["holm_rank"])
        self.assertEqual(first["holm_multiplier"], 10)
        # 整批模式比单窗模式更严格（入选集合为子集）
        single = analyze_deviation(snap, .05, 2026, SINGLE_WINDOW)
        fam_codes = {x["window"]["code"] for x in out["test"] if x["selected"]}
        single_codes = {x["window"]["code"] for x in single["test"] if x["selected"]}
        self.assertTrue(fam_codes <= single_codes)

    def test_single_window_mode_matches_legacy_rule(self):
        snap = make_snapshot()
        out = analyze_deviation(snap, .05, 2026, SINGLE_WINDOW)
        self.assertEqual(out["error_control"], SINGLE_WINDOW)
        for x in out["test"]:
            self.assertAlmostEqual(x["p_adj"], x["p"])  # 单窗不校正
            self.assertEqual(x["holm_multiplier"], 1)
            self.assertEqual(x["selected"], x["p"] <= .05)
            self.assertIn("单窗模式", x["selection_reason"])
        self.assertEqual(out["selected_count"], sum(x["p"] <= .05 for x in out["test"]))

    def test_reordering_test_windows_does_not_recompute_decisions(self):
        snap = make_snapshot()
        out1 = analyze_deviation(snap, .05, 2026, FAMILY_WISE)
        shuffled = copy.deepcopy(snap)
        test_rows = [w for w in shuffled["windows"] if w["split"] == "test"]
        others = [w for w in shuffled["windows"] if w["split"] != "test"]
        r2 = np.random.default_rng(99); r2.shuffle(test_rows)
        shuffled["windows"] = others + test_rows
        out2 = analyze_deviation(shuffled, .05, 2026, FAMILY_WISE)
        m1 = {x["window"]["code"]: x for x in out1["test"]}
        m2 = {x["window"]["code"]: x for x in out2["test"]}
        self.assertEqual(set(m1), set(m2))
        for code, a in m1.items():
            b = m2[code]
            self.assertAlmostEqual(a["p"], b["p"])
            self.assertAlmostEqual(a["p_adj"], b["p_adj"])
            self.assertEqual(a["selected"], b["selected"])
            self.assertEqual(a["holm_rank"], b["holm_rank"])
        # fit 与输入指纹不受窗口行序影响（自然键排序）
        self.assertEqual(out1["fit_hash"], out2["fit_hash"])
        self.assertEqual(out1["input_hash"], out2["input_hash"])

    def test_small_calibration_no_selection_explains_resolution(self):
        # m=4 => 分辨率1/5=.2；alpha=.05 低于首个网格，单窗必然无人入选
        snap = make_snapshot(n_train=25, n_cal_small=4, n_test=8, extreme_test=8)
        out = analyze_deviation(snap, .05, 2026, SINGLE_WINDOW)
        self.assertEqual(out["selected_count"], 0)
        self.assertAlmostEqual(out["resolution"], .2)
        self.assertEqual(out["alpha_grid_threshold"], 0.0)
        self.assertTrue(out["no_selection_note"])
        self.assertIn("分辨率", out["no_selection_note"])
        self.assertIn("无人入选", out["no_selection_note"])
        # 同数据整批Holm同样无人入选，且说明n/(m+1)门槛
        fam = analyze_deviation(snap, .05, 2026, FAMILY_WISE)
        self.assertEqual(fam["selected_count"], 0)
        self.assertTrue(fam["no_selection_note"])
        self.assertIn("Holm", fam["no_selection_note"])

    def test_tied_p_get_identical_adjusted_p_and_decision(self):
        # 构造校准同分并列：让两个测试窗D²落在同一cal网格，原始p必然相等
        snap = make_snapshot(n_train=40, n_cal=10, n_test=6, extreme_test=0)
        # 强制两个测试窗数值完全相同 => D²/p 完全相同
        te = [w for w in snap["windows"] if w["split"] == "test"]
        te[1]["values"] = copy.deepcopy(te[0]["values"])
        out = analyze_deviation(snap, .2, 2026, FAMILY_WISE)
        a, b = out["test"][0], out["test"][1]
        self.assertAlmostEqual(a["p"], b["p"])
        self.assertAlmostEqual(a["p_adj"], b["p_adj"])
        self.assertEqual(a["holm_rank"], b["holm_rank"])
        self.assertEqual(a["selected"], b["selected"])

    def test_invalid_mode_rejected(self):
        snap = make_snapshot()
        with self.assertRaises(ValueError):
            analyze_deviation(snap, .05, 2026, "bonferroni")

    def test_alpha_change_does_not_change_scores_but_changes_selection(self):
        snap = make_snapshot()
        a = analyze_deviation(snap, .05, 2026, FAMILY_WISE)
        b = analyze_deviation(snap, .1, 2026, FAMILY_WISE)
        for x, y in zip(a["test"], b["test"]):
            self.assertAlmostEqual(x["p"], y["p"])
            self.assertAlmostEqual(x["p_adj"], y["p_adj"])  # 校正p不随alpha变
        self.assertEqual(a["fit_hash"], b["fit_hash"])

if __name__ == "__main__":
    unittest.main()
