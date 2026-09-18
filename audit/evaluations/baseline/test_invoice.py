import unittest
from invoice import invoice_total


class InvoiceTests(unittest.TestCase):
    def test_promotion_leaves_shipping_unchanged(self):
        self.assertEqual(invoice_total([(1000, 1)], 200, 10), 1100)
        self.assertEqual(invoice_total([(101, 1)], 7, 50), 57)

    def test_rounds_aggregate_merchandise_down_once(self):
        self.assertEqual(invoice_total([(1, 1), (1, 1)], 7, 50), 8)
        self.assertEqual(invoice_total([(101, 1)], 0, 50), 50)

    def test_boundaries_defaults_and_multiple_quantities(self):
        self.assertEqual(invoice_total([(150, 2), (99, 3)]), 597)
        self.assertEqual(invoice_total([(150, 2), (99, 3)], 20, 0), 617)
        self.assertEqual(invoice_total([(150, 2), (99, 3)], 20, 100), 20)
        self.assertEqual(invoice_total([], 20, 50), 20)
        self.assertEqual(invoice_total([(0, 1)]), 0)

    def test_generator_input(self):
        self.assertEqual(invoice_total(((p, q) for p, q in [(200, 2), (100, 1)]), 10, 20), 410)

    def test_invalid_inputs(self):
        cases = [
            ([(-1, 1)], 0, 0),
            ([(10, 0)], 0, 0),
            ([(10, -1)], 0, 0),
            ([(10, 1)], -1, 0),
            ([(10, 1)], 0, -1),
            ([(10, 1)], 0, 101),
            ([(100, 1), (-1, 1)], 0, 100),
            ([(0, 0)], 0, 0),
            ([], -1, 50),
        ]
        for args in cases:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    invoice_total(*args)

    def test_shipping_is_an_additive_invariant(self):
        for cents in range(0, 101):
            for discount in range(0, 101):
                with self.subTest(cents=cents, discount=discount):
                    merchandise = invoice_total([(cents, 1)], 0, discount)
                    self.assertEqual(invoice_total([(cents, 1)], 37, discount), merchandise + 37)
                    # Integer inequalities characterize floor without duplicating it.
                    numerator = cents * (100 - discount)
                    self.assertLessEqual(100 * merchandise, numerator)
                    self.assertLess(numerator, 100 * (merchandise + 1))

    def test_large_integer_amounts_remain_exact(self):
        self.assertEqual(invoice_total([(10**30 + 1, 1)], 7, 50), 5 * 10**29 + 7)


if __name__ == '__main__':
    unittest.main()
