"""Controller-owned disposable Phase 4 engineering fixtures."""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class FixtureSubtask:
    subtask_id: str
    objective: str
    allowed_paths: Tuple[str, ...]


@dataclass(frozen=True)
class FixtureSpec:
    fixture_id: str
    description: str
    difficulty: str
    risk: str
    domain: str
    files: Dict[str, str]
    final_files: Dict[str, str]
    acceptance_test: str
    acceptance: Tuple[dict, ...]
    subtasks: Tuple[FixtureSubtask, ...]

    @property
    def scope(self):
        return tuple(sorted(self.final_files))


CALCULATOR = FixtureSpec(
    'calculator', 'Repair a small arithmetic function.', 'routine', 'routine', 'backend-database',
    {'calculator.py': 'def total(left, right):\n    """Return the arithmetic sum."""\n    return left - right\n',
     'README.md': '# Disposable calculator fixture\n'},
    {'calculator.py': 'def total(left, right):\n    """Return the arithmetic sum."""\n    return left + right\n'},
    '''import unittest\nfrom calculator import total\n\nclass Acceptance(unittest.TestCase):\n    def test_total(self):\n        self.assertEqual(total(17, 25), 42)\n        self.assertEqual(total(-4, 9), 5)\n        self.assertEqual(total(0, 0), 0)\n''',
    ({'id': 'total', 'expected': 'total returns arithmetic sum for positive, negative, and zero inputs'},),
    (FixtureSubtask('calculator-core', 'Correct total without changing its public interface.',
                    ('calculator.py',)),))


TEXT_METRICS = FixtureSpec(
    'text-metrics', 'Repair independent word and line metrics and integrate them.',
    'substantial', 'routine', 'backend-database',
    {'words.py': 'def word_count(text):\n    return len(text)\n',
     'lines.py': 'def line_count(text):\n    return 0\n',
     'summary.py': ('from lines import line_count\nfrom words import word_count\n\n'
                    'def summarize(text):\n    return {"words": word_count(text), "lines": line_count(text)}\n'),
     'README.md': '# Disposable text metrics fixture\n'},
    {'words.py': 'def word_count(text):\n    return len(text.split())\n',
     'lines.py': 'def line_count(text):\n    return len(text.splitlines())\n'},
    '''import unittest\nfrom summary import summarize\n\nclass Acceptance(unittest.TestCase):\n    def test_summary(self):\n        self.assertEqual(summarize("one two\\nthree"), {"words": 3, "lines": 2})\n        self.assertEqual(summarize(""), {"words": 0, "lines": 0})\n''',
    ({'id': 'word-count', 'expected': 'word_count counts whitespace-separated words'},
     {'id': 'line-count', 'expected': 'line_count follows splitlines semantics'},
     {'id': 'integration', 'expected': 'summarize returns both independently corrected metrics'}),
    (FixtureSubtask('word-metric', 'Correct word_count semantics.', ('words.py',)),
     FixtureSubtask('line-metric', 'Correct line_count semantics.', ('lines.py',))))


INVENTORY = FixtureSpec(
    'inventory', 'Repair independent price and availability calculations.',
    'substantial', 'material', 'backend-database',
    {'pricing.py': 'def subtotal(unit_price, quantity):\n    return unit_price - quantity\n',
     'stock.py': 'def available(on_hand, reserved):\n    return on_hand + reserved\n',
     'inventory.py': ('from pricing import subtotal\nfrom stock import available\n\n'
                      'def quote(unit_price, quantity, on_hand, reserved):\n'
                      '    return {"subtotal": subtotal(unit_price, quantity), '
                      '"available": available(on_hand, reserved)}\n'),
     'README.md': '# Disposable inventory fixture\n'},
    {'pricing.py': 'def subtotal(unit_price, quantity):\n    return unit_price * quantity\n',
     'stock.py': 'def available(on_hand, reserved):\n    return on_hand - reserved\n'},
    '''import unittest\nfrom inventory import quote\n\nclass Acceptance(unittest.TestCase):\n    def test_quote(self):\n        self.assertEqual(quote(7, 3, 10, 4), {"subtotal": 21, "available": 6})\n        self.assertEqual(quote(0, 5, 2, 2), {"subtotal": 0, "available": 0})\n''',
    ({'id': 'pricing', 'expected': 'subtotal multiplies unit price and quantity'},
     {'id': 'stock', 'expected': 'available subtracts reserved units from on-hand units'},
     {'id': 'quote', 'expected': 'quote integrates the corrected calculations'}),
    (FixtureSubtask('pricing', 'Correct subtotal arithmetic.', ('pricing.py',)),
     FixtureSubtask('availability', 'Correct available stock arithmetic.', ('stock.py',))))


FIXTURES = {item.fixture_id: item for item in (CALCULATOR, TEXT_METRICS, INVENTORY)}


def fixture_catalog():
    return [{'id': item.fixture_id, 'description': item.description,
             'difficulty': item.difficulty, 'risk': item.risk,
             'subtasks': len(item.subtasks), 'scope': list(item.scope)}
            for item in FIXTURES.values()]


def get_fixture(fixture_id):
    try:
        return FIXTURES[fixture_id]
    except KeyError as exc:
        raise ValueError('unsupported execution target; choose a controller-created fixture') from exc
