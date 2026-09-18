"""Independent correctness gate for a proposed constant-time summation."""
def proposed_candidate(n):
    return (n - 1) * (n - 2) // 2
assert proposed_candidate(2) == 1, 'candidate(2) must sum 0+1=1; observed %s' % proposed_candidate(2)
