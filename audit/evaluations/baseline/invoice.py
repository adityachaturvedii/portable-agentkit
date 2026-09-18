"""Synthetic invoice API. Amounts are integer cents; quantities must be positive."""


def invoice_total(items, shipping_cents=0, discount_percent=0):
    """Discount merchandise, round its total down, then add shipping.

    Raise ValueError for negative amounts, nonpositive quantities, or a
    percentage outside the inclusive range 0..100.
    """
    if shipping_cents < 0:
        raise ValueError("shipping_cents must be nonnegative")
    if not 0 <= discount_percent <= 100:
        raise ValueError("discount_percent must be between 0 and 100")

    subtotal = 0
    for price, quantity in items:
        if price < 0:
            raise ValueError("prices must be nonnegative")
        if quantity <= 0:
            raise ValueError("quantities must be positive")
        subtotal += price * quantity

    return subtotal * (100 - discount_percent) // 100 + shipping_cents
