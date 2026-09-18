import unittest
from invoice import invoice_total

class InvoiceBehavior(unittest.TestCase):
    def test_shipping_not_discounted(self):
        self.assertEqual(invoice_total([(1000, 2)], 500, 10), 2300)
    def test_merchandise_fraction_rounds_down(self):
        self.assertEqual(invoice_total([(101, 1)], 0, 50), 50)
    def test_shipping_only_is_undiscounted(self):
        self.assertEqual(invoice_total([], 500, 50), 500)
    def test_boundaries(self):
        self.assertEqual(invoice_total([(1000, 2)], 500, 0), 2500)
        self.assertEqual(invoice_total([(1000, 2)], 500, 100), 500)
        self.assertEqual(invoice_total([(0, 1)], 0, 100), 0)
    def test_invalid_inputs(self):
        for items, shipping, discount in [([(-1,1)],0,0), ([(1,0)],0,0), ([(1,-1)],0,0), ([], -1, 0), ([],0,-1), ([],0,101)]:
            with self.subTest(items=items, shipping=shipping, discount=discount):
                with self.assertRaises(ValueError):
                    invoice_total(items, shipping, discount)
    def test_input_is_not_mutated(self):
        items=[(100,2)]
        self.assertEqual(invoice_total(items, 0, 0),200)
        self.assertEqual(items,[(100,2)])

if __name__ == '__main__': unittest.main()
