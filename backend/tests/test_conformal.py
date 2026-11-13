import unittest
import numpy as np
from src.services.conformal_algorithm import upper_tail_p,holm_adjust

class TestConformal(unittest.TestCase):
    def test_upper_tail_basic_and_resolution(self):
        cal=[1,2,3,4,5]
        out=upper_tail_p(cal,[5,6,0])
        # cal>=5 有1条 => (1+1)/6；cal>=6 为0 => 1/6；cal>=0 为5 => 6/6
        self.assertEqual(out["p"],[2/6,1/6,1.0])
        self.assertEqual(out["cal_ge_count"],[1,0,5])
        self.assertEqual(out["m"],5)
        self.assertAlmostEqual(out["resolution"],1/6)

    def test_upper_tail_tie_conservative(self):
        # 同值保守：test等于cal分数时计入>=
        out=upper_tail_p([2,2,2],[2])
        self.assertEqual(out["p"],[4/4])

    def test_holm_known_example(self):
        # 经典示例 n=5: p = .005,.01,.03,.04,.10, alpha=.05
        out=holm_adjust([.005,.01,.03,.04,.10])
        # R p.adjust(method="holm"): .025,.04,.09,.09,.10（cummax单调化）
        np.testing.assert_allclose(out["p_adj"],[.025,.04,.09,.09,.10],atol=1e-12)
        self.assertEqual(out["ranks"],[1,2,3,4,5])
        self.assertEqual(out["multipliers"],[5,4,3,2,1])

    def test_holm_tied_p_share_adjustment(self):
        # 并列p：p1=p2=.01 应获得完全相同的校正p（与R p.adjust(method="holm")一致）
        out=holm_adjust([.01,.01,.03,.10])
        self.assertEqual(out["p_adj"][0],out["p_adj"][1])
        # R 参考：holm(c(.01,.01,.03,.10)) -> 0.04 0.04 0.06 0.10
        np.testing.assert_allclose(out["p_adj"],[.04,.04,.06,.10],atol=1e-12)
        # 并列共享竞赛排名；展示乘子取并列组首位(n-r+1)，最保守
        self.assertEqual(out["ranks"][:2],[1,1])
        self.assertEqual(out["multipliers"][:2],[4,4])
        # 第三个并列组从排名3起
        self.assertEqual(out["ranks"][2],3)
        self.assertEqual(out["multipliers"][2],2)

    def test_holm_ties_at_tail(self):
        out=holm_adjust([.005,.02,.02])
        # R: holm(c(.005,.02,.02)) -> .015 .04 .04
        np.testing.assert_allclose(out["p_adj"],[.015,.04,.04],atol=1e-12)
        self.assertEqual(out["ranks"],[1,2,2])

    def test_holm_capped_at_one_and_order_preserved(self):
        out=holm_adjust([.5,.6,.7])
        self.assertTrue(all(0<=x<=1 for x in out["p_adj"]))
        np.testing.assert_allclose(out["p_adj"],[1.0,1.0,1.0])

    def test_holm_reorder_invariance(self):
        p=[.10,.005,.04,.01,.03]
        out=holm_adjust(p)
        ref=holm_adjust([.005,.01,.03,.04,.10])
        got={x:y for x,y in zip(p,out["p_adj"])}
        for x,y in zip([.005,.01,.03,.04,.10],ref["p_adj"]):
            self.assertAlmostEqual(got[x],y)

    def test_holm_single_value(self):
        out=holm_adjust([.04])
        self.assertAlmostEqual(out["p_adj"][0],.04)
        self.assertEqual(out["multipliers"],[1])

if __name__=="__main__":
    unittest.main()
