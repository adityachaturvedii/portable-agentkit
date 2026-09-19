"""Controller-owned disposable Phase 4 engineering fixtures."""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class FixtureSubtask:
    subtask_id: str
    objective: str
    allowed_paths: Tuple[str, ...]
    request_terms: Tuple[str, ...] = ()
    dependencies: Tuple[str, ...] = ()
    interfaces: Tuple[str, ...] = ()
    acceptance: Tuple[dict, ...] = ()
    acceptance_test: str = ''


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

    def acceptance_test_for(self, acceptance_ids):
        requested = set(acceptance_ids)
        if requested == {item['id'] for item in self.acceptance}:
            return self.acceptance_test
        selected = [item.acceptance_test for item in self.subtasks
                    if item.acceptance_test and
                    {criterion['id'] for criterion in item.acceptance} <= requested]
        if not selected:
            raise ValueError('project scenario has no controller-owned test for selected acceptance')
        return '\n'.join(selected)


CALCULATOR = FixtureSpec(
    'calculator', 'Repair a small arithmetic function.', 'routine', 'routine', 'backend-database',
    {'calculator.py': 'def total(left, right):\n    """Return the arithmetic sum."""\n    return left - right\n',
     'README.md': '# Disposable calculator fixture\n'},
    {'calculator.py': 'def total(left, right):\n    """Return the arithmetic sum."""\n    return left + right\n'},
    '''import unittest\nfrom calculator import total\n\nclass Acceptance(unittest.TestCase):\n    def test_total(self):\n        self.assertEqual(total(17, 25), 42)\n        self.assertEqual(total(-4, 9), 5)\n        self.assertEqual(total(0, 0), 0)\n''',
    ({'id': 'total', 'expected': 'total returns arithmetic sum for positive, negative, and zero inputs'},),
    (FixtureSubtask('calculator-core', 'Correct total without changing its public interface.',
                    ('calculator.py',), ('total', 'sum', 'calculator'),
                    interfaces=('total(left, right) -> number',),
                    acceptance=({'id': 'total', 'expected': 'total returns arithmetic sum for positive, negative, and zero inputs'},),
                    acceptance_test='''import unittest\nfrom calculator import total\n\nclass TotalAcceptance(unittest.TestCase):\n    def test_total(self):\n        self.assertEqual(total(17, 25), 42)\n'''),))


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
    (FixtureSubtask('word-metric', 'Correct word_count semantics.', ('words.py',),
                    ('word', 'words'), interfaces=('word_count(text) -> int',),
                    acceptance=({'id': 'word-count', 'expected': 'word_count counts whitespace-separated words'},),
                    acceptance_test='''import unittest\nfrom words import word_count\n\nclass WordAcceptance(unittest.TestCase):\n    def test_words(self):\n        self.assertEqual(word_count("one two\\nthree"), 3)\n        self.assertEqual(word_count(""), 0)\n'''),
     FixtureSubtask('line-metric', 'Correct line_count semantics.', ('lines.py',),
                    ('line', 'lines'), interfaces=('line_count(text) -> int',),
                    acceptance=({'id': 'line-count', 'expected': 'line_count follows splitlines semantics'},),
                    acceptance_test='''import unittest\nfrom lines import line_count\n\nclass LineAcceptance(unittest.TestCase):\n    def test_lines(self):\n        self.assertEqual(line_count("one\\ntwo"), 2)\n        self.assertEqual(line_count(""), 0)\n''')))


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
    (FixtureSubtask('pricing', 'Correct subtotal arithmetic.', ('pricing.py',),
                    ('price', 'pricing', 'subtotal'), interfaces=('subtotal(unit_price, quantity) -> number',),
                    acceptance=({'id': 'pricing', 'expected': 'subtotal multiplies unit price and quantity'},),
                    acceptance_test='''import unittest\nfrom pricing import subtotal\n\nclass PricingAcceptance(unittest.TestCase):\n    def test_subtotal(self):\n        self.assertEqual(subtotal(7, 3), 21)\n'''),
     FixtureSubtask('availability', 'Correct available stock arithmetic.', ('stock.py',),
                    ('stock', 'availability', 'available'),
                    interfaces=('available(on_hand, reserved) -> number',),
                    acceptance=({'id': 'stock', 'expected': 'available subtracts reserved units from on-hand units'},),
                    acceptance_test='''import unittest\nfrom stock import available\n\nclass StockAcceptance(unittest.TestCase):\n    def test_available(self):\n        self.assertEqual(available(10, 4), 6)\n''')))


TEXT_PIPELINE = FixtureSpec(
    'text-pipeline', 'Repair an ordered normalization and reporting pipeline.',
    'substantial', 'routine', 'backend-database',
    {'normalize.py': 'def normalize(text):\n    return text\n',
     'report.py': ('from normalize import normalize\n\n'
                   'def report(text):\n    return {"normalized": text, "length": 0}\n'),
     'README.md': '# Disposable ordered text pipeline\n'},
    {'normalize.py': 'def normalize(text):\n    return " ".join(text.lower().split())\n',
     'report.py': ('from normalize import normalize\n\n'
                   'def report(text):\n    value = normalize(text)\n'
                   '    return {"normalized": value, "length": len(value)}\n')},
    '''import unittest\nfrom report import report\n\nclass Acceptance(unittest.TestCase):\n    def test_report(self):\n        self.assertEqual(report("  Hello   WORLD "), {"normalized": "hello world", "length": 11})\n''',
    ({'id': 'normalize', 'expected': 'normalization lowercases and collapses whitespace'},
     {'id': 'report', 'expected': 'report uses normalized text and reports its length'},
     {'id': 'ordered-integration', 'expected': 'report consumes the normalize interface'}),
    (FixtureSubtask('normalize', 'Implement the normalization interface.', ('normalize.py',),
                    ('normalize', 'lowercase', 'whitespace'),
                    interfaces=('normalize(text) -> str',),
                    acceptance=({'id': 'normalize', 'expected': 'normalization lowercases and collapses whitespace'},),
                    acceptance_test='''import unittest\nfrom normalize import normalize\n\nclass NormalizeAcceptance(unittest.TestCase):\n    def test_normalize(self):\n        self.assertEqual(normalize("  Hello   WORLD "), "hello world")\n'''),
     FixtureSubtask('report', 'Consume normalize when building the report.', ('report.py',),
                    ('report', 'length'), dependencies=('normalize',),
                    interfaces=('report(text) -> {normalized: str, length: int}',),
                    acceptance=({'id': 'report', 'expected': 'report uses normalized text and reports its length'},),
                    acceptance_test='''import unittest\nfrom report import report\n\nclass ReportAcceptance(unittest.TestCase):\n    def test_report(self):\n        self.assertEqual(report("Hello"), {"normalized": "hello", "length": 5})\n''')))


CASE_POLICY = FixtureSpec(
    'case-policy', 'Resolve and implement one explicit text case policy.', 'routine', 'routine',
    'backend-database',
    {'case_policy.py': 'def apply_case(text):\n    return text\n',
     'README.md': '# Disposable case-policy fixture\n'},
    {'case_policy.py': 'def apply_case(text):\n    return text.lower()\n'},
    '''import unittest\nfrom case_policy import apply_case\n\nclass Acceptance(unittest.TestCase):\n    def test_policy(self):\n        self.assertEqual(apply_case("MiXeD"), "mixed")\n''',
    ({'id': 'case-policy', 'expected': 'apply_case follows the explicitly selected case policy'},),
    (FixtureSubtask('case-policy', 'Implement the selected case policy.', ('case_policy.py',),
                    ('case', 'lowercase', 'uppercase'), interfaces=('apply_case(text) -> str',),
                    acceptance=({'id': 'case-policy', 'expected': 'apply_case follows the explicitly selected case policy'},),
                    acceptance_test='''import unittest\nfrom case_policy import apply_case\n\nclass CaseAcceptance(unittest.TestCase):\n    def test_case(self):\n        self.assertEqual(apply_case("MiXeD"), "mixed")\n'''),))


FIXTURES = {item.fixture_id: item for item in
            (CALCULATOR, TEXT_METRICS, INVENTORY, TEXT_PIPELINE, CASE_POLICY)}


def fixture_catalog():
    return [{'id': item.fixture_id, 'description': item.description,
             'difficulty': item.difficulty, 'risk': item.risk,
             'subtasks': len(item.subtasks), 'scope': list(item.scope),
             'planning': 'request-driven from bounded project inventory'}
            for item in FIXTURES.values()]


def get_fixture(fixture_id):
    try:
        return FIXTURES[fixture_id]
    except KeyError as exc:
        raise ValueError('unsupported execution target; choose a controller-created fixture') from exc
