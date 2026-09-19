"""Small disposable CPU projects with independent literal expectations."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agentkit.pack import render, select
from agentkit.validation import ROOT


class FixtureTests(unittest.TestCase):
    def run_project(self, source, probe):
        with tempfile.TemporaryDirectory(prefix="agentkit-fixture-") as tmp:
            path = Path(tmp)
            (path / "subject.py").write_text(source)
            # The check lives outside the implementation file and uses a fixed oracle.
            (path / "verify.py").write_text(probe)
            return subprocess.run([sys.executable, "verify.py"], cwd=path,
                                  capture_output=True, text=True, timeout=10)

    def red_green(self, buggy, fixed, oracle):
        red = self.run_project(buggy, oracle)
        green = self.run_project(fixed, oracle)
        self.assertNotEqual(red.returncode, 0, "planted defect escaped independent oracle")
        self.assertNotIn("ModuleNotFoundError", red.stderr)
        self.assertEqual(green.returncode, 0, green.stderr)

    def test_eighteen_explicit_triggers_and_domain_loading(self):
        tasks = json.loads((ROOT / "tests/fixtures/tasks.json").read_text())
        self.assertEqual(len(tasks), 18)
        for task in tasks:
            with self.subTest(task=task["id"]):
                entry = select(task["intent"])
                self.assertEqual(entry["id"], task["expected_skill"])
                self.assertIn("# " + task["domain"].replace("-", " ").capitalize(),
                              render(entry["id"], task["domain"]))

    def test_invoice_discount_does_not_apply_to_shipping(self):
        self.red_green(
            "def total(): return (1000 + 200) * 90 // 100\n",
            "def total(): return 1000 * 90 // 100 + 200\n",
            "from subject import total\nassert total() == 1100, 'invoice total'\n")

    def test_split_leakage_detects_cross_split_entities(self):
        self.red_green(
            "def split(): return ([1, 2, 3], [3, 4])\n",
            "def split(): return ([1, 2], [3, 4])\n",
            "from subject import split\na,b=split()\nassert not set(a) & set(b), 'entity leakage'\nassert sorted(a+b) == [1,2,3,4]\n")

    def test_scalar_gradient_matches_independent_worked_example(self):
        # For (w*x-y)^2 at w=3,x=2,y=1: derivative = 20.
        self.red_green(
            "def gradient(w,x,y): return 2*(w*x-y)\n",
            "def gradient(w,x,y): return 2*x*(w*x-y)\n",
            "from subject import gradient\nassert gradient(3,2,1) == 20, 'gradient'\nassert gradient(3,0,1) == 0\n")

    def test_inference_cache_identity_includes_model_version(self):
        common = "cache={}\ndef infer(version,x):\n    key=KEY\n    if key not in cache: cache[key]=x+version\n    return cache[key]\n"
        self.red_green(common.replace("KEY", "x"), common.replace("KEY", "(version,x)"),
                       "from subject import infer\nassert infer(1,3)==4\nassert infer(2,3)==5, 'stale model result'\n")

    def test_stable_softmax_cpu_reference_only(self):
        common = "import math\ndef softmax(xs):\n    ys=[math.exp(x-OFFSET) for x in xs]\n    return [y/sum(ys) for y in ys]\n"
        self.red_green(common.replace("OFFSET", "0"), common.replace("OFFSET", "max(xs)"),
                       "from subject import softmax\nassert softmax([1000,1000]) == [0.5,0.5]\n")

    def test_sqlite_public_retry_behavior(self):
        common = '''import sqlite3
class Orders:
    def __init__(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('create table orders (request text UNIQUE, amount integer)')
    def submit(self, key, amount):
        EXISTING
        self.db.execute('insert into orders values (?,?)', (key,amount))
    def total(self):
        return self.db.execute('select coalesce(sum(amount),0) from orders').fetchone()[0]
'''
        fixed = "row=self.db.execute('select amount from orders where request=?',(key,)).fetchone()\n        if row:\n            if row[0]!=amount: raise ValueError('conflicting request')\n            return"
        self.red_green(common.replace("EXISTING", "pass"), common.replace("EXISTING", fixed),
                       "from subject import Orders\no=Orders()\no.submit('r1',500)\no.submit('r1',500)\nassert o.total()==500\ntry:\n o.submit('r1',600)\nexcept ValueError:\n pass\nelse:\n raise AssertionError('conflicting key accepted')\nassert o.total()==500\n")


if __name__ == "__main__":
    unittest.main()
