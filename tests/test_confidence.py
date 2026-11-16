import unittest
from confidence import scale_intervals


class ConfidenceTests(unittest.TestCase):
    def test_mean_t_interval_matches_reference_and_keeps_out_of_scale_limits(self):
        ci=scale_intervals([1,2,3,4,5],4)['mean_ci95']
        self.assertAlmostEqual(ci[0],1.0367568385,places=8)
        self.assertAlmostEqual(ci[1],4.9632431615,places=8)
        ci=scale_intervals([1,5],4)['mean_ci95']
        self.assertLess(ci[0],1)
        self.assertGreater(ci[1],5)

    def test_wilson_half_and_extreme_proportions(self):
        ci=scale_intervals([2,3,4,5],4)['top2_ci95']
        self.assertAlmostEqual(ci[0],15.0038989152,places=8)
        self.assertAlmostEqual(ci[1],84.9961010848,places=8)
        none=scale_intervals([1]*10,4)['top2_ci95']
        all_=scale_intervals([5]*10,4)['top2_ci95']
        self.assertAlmostEqual(none[0],0)
        self.assertAlmostEqual(none[1],27.7532799863,places=8)
        self.assertAlmostEqual(all_[0],72.2467200137,places=8)
        self.assertAlmostEqual(all_[1],100)

    def test_empty_single_constant_and_custom_threshold(self):
        self.assertEqual(scale_intervals([],4),dict(mean_ci95=None,top2_ci95=None))
        one=scale_intervals([5],4)
        self.assertIsNone(one['mean_ci95'])
        self.assertTrue(0<one['top2_ci95'][0]<100)
        constant=scale_intervals([5]*5,4)
        self.assertEqual(constant['mean_ci95'],[5,5])
        self.assertEqual(scale_intervals([2,5,8,9],8)['top2_ci95'],scale_intervals([1,2,4,5],4)['top2_ci95'])
