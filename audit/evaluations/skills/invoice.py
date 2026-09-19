"""Synthetic invoice API. Amounts are integer cents; quantities must be positive."""
def invoice_total(items, shipping_cents=0, discount_percent=0):
    if shipping_cents < 0:
        raise ValueError("shipping must be nonnegative")
    if not 0 <= discount_percent <= 100:
        raise ValueError("discount must be between 0 and 100")
    subtotal = 0
    for price, quantity in items:
        if price < 0 or quantity <= 0:
            raise ValueError("prices must be nonnegative and quantities positive")
        subtotal += price * quantity
    # Floor merchandise fractional cents before adding undiscounted shipping.
    return subtotal * (100 - discount_percent) // 100 + shipping_cents
