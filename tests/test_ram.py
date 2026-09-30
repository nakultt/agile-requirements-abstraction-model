import json
import tempfile
import unittest
from pathlib import Path

from ram import (Level, Requirement, RequirementSet, Status, classify, metrics, plan_sprints,
                 priority_score, traceability_matrix, validate, workup)

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "campusconnect.json"


def mk(i, level, parent=None, **kw):
    kw.setdefault("title", f"req {i}")
    return Requirement(id=i, level=Level(level), parent=parent, **kw)


class ModelTests(unittest.TestCase):
    def test_hierarchy_navigation(self):
        rs = RequirementSet("t", [mk("P", 1), mk("F", 2, "P"), mk("FN", 3, "F"), mk("C", 4, "FN")])
        self.assertEqual([a.id for a in rs.ancestors("C")], ["FN", "F", "P"])
        self.assertEqual({d.id for d in rs.descendants("P")}, {"F", "FN", "C"})
        self.assertEqual([r.id for r in rs.roots()], ["P"])

    def test_duplicate_id_rejected(self):
        rs = RequirementSet("t", [mk("A", 1)])
        with self.assertRaises(ValueError):
            rs.add(mk("A", 2))

    def test_roundtrip(self):
        rs = RequirementSet.load(SAMPLE)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            rs.save(p)
            again = RequirementSet.load(p)
        self.assertEqual(json.dumps(rs.to_dict(), sort_keys=True), json.dumps(again.to_dict(), sort_keys=True))

    def test_ancestors_survive_cycle(self):
        rs = RequirementSet("t", [mk("A", 2, "B"), mk("B", 2, "A")])
        self.assertLessEqual(len(rs.ancestors("A")), 2)


class ClassifierTests(unittest.TestCase):
    def test_each_level(self):
        cases = {
            Level.PRODUCT: "Reduce the cost to the organization and strengthen our market position.",
            Level.FEATURE: "The app supports a personalised dashboard module.",
            Level.FUNCTION: "The user can select a language from the drop-down list on the screen.",
            Level.COMPONENT: "The API shall return JSON in under 200 ms using an indexed database table.",
        }
        for lvl, text in cases.items():
            self.assertEqual(classify(text).level, lvl, text)

    def test_no_cues_defaults_to_function(self):
        self.assertEqual(classify("xyzzy").level, Level.FUNCTION)

    def test_confidence_bounds(self):
        c = classify("The system shall display a message on the screen.")
        self.assertTrue(0 < c.confidence <= 1)
        self.assertTrue(c.cues)


class ValidationTests(unittest.TestCase):
    def codes(self, rs):
        return {(i.code, i.req_id) for i in validate(rs)}

    def test_orphan(self):
        rs = RequirementSet("t", [mk("FN", 3, acceptance=["x"])])
        self.assertIn(("R001", "FN"), self.codes(rs))

    def test_missing_parent(self):
        rs = RequirementSet("t", [mk("FN", 3, "GHOST", acceptance=["x"])])
        self.assertIn(("R002", "FN"), self.codes(rs))

    def test_level_skip(self):
        rs = RequirementSet("t", [mk("F", 2, "P"), mk("P", 1), mk("C", 4, "F", acceptance=["x"])])
        self.assertIn(("R003", "C"), self.codes(rs))

    def test_cycle(self):
        rs = RequirementSet("t", [mk("A", 2, "B"), mk("B", 2, "A")])
        self.assertTrue({c for c, _ in self.codes(rs)} >= {"R004"})

    def test_duplicates(self):
        t = "The user can select notification categories on the settings screen"
        rs = RequirementSet("t", [mk("P", 1), mk("F", 2, "P"),
                                  mk("A", 3, "F", title=t, acceptance=["x"]),
                                  mk("B", 3, "F", title=t, acceptance=["x"])])
        self.assertIn(("R008", "B"), self.codes(rs))

    def test_new_status_is_info_only(self):
        rs = RequirementSet("t", [mk("N", 3, status=Status.NEW)])
        self.assertEqual({(i.code, i.severity) for i in validate(rs)}, {("R010", "info")})

    def test_sample_has_expected_seeded_defects(self):
        codes = self.codes(RequirementSet.load(SAMPLE))
        self.assertIn(("R001", "FN16"), codes)
        self.assertIn(("R003", "C11"), codes)
        self.assertIn(("R008", "FN17"), codes)


class WorkupTests(unittest.TestCase):
    def test_component_needs_no_refinement(self):
        rs = RequirementSet.load(SAMPLE)
        w = workup(rs, rs.get("N3"))
        self.assertEqual(w.suggested_level, Level.COMPONENT)
        self.assertEqual(w.missing_levels_down, [])

    def test_feature_needs_refinement(self):
        rs = RequirementSet.load(SAMPLE)
        w = workup(rs, rs.get("N2"))
        self.assertEqual(w.missing_levels_down, [Level.FUNCTION])

    def test_product_has_no_parent(self):
        rs = RequirementSet.load(SAMPLE)
        r = Requirement("X", "Strengthen the brand", "Improve the market position of the organization.", Level.PRODUCT)
        w = workup(rs, r)
        self.assertIsNone(w.suggested_parent)
        self.assertEqual(w.missing_levels_up, [])


class AnalysisTests(unittest.TestCase):
    def test_priority_formula(self):
        self.assertAlmostEqual(priority_score(mk("A", 3, value=9, cost=3, risk=2)), 9 / 4, places=3)

    def test_traceability_rows_are_full_chains(self):
        rs = RequirementSet("t", [mk("P", 1), mk("F", 2, "P"), mk("FN", 3, "F"), mk("C", 4, "FN")])
        self.assertEqual(traceability_matrix(rs), [["P", "F", "FN", "C"]])

    def test_metrics_on_sample(self):
        m = metrics(RequirementSet.load(SAMPLE))
        self.assertEqual(m["new_unprocessed"], 4)
        self.assertEqual(m["per_level"]["Product"], 4)
        self.assertLess(m["traceability_coverage"], 1.0)   # FN16 is an orphan

    def test_plan_ties_use_natural_id_order(self):
        rs = RequirementSet("t", [mk("P", 1), mk("F", 2, "P")] +
                            [mk(f"FN{n}", 3, "F", value=4, cost=2, risk=0) for n in (12, 5, 1)])
        self.assertEqual(plan_sprints(rs, 4, 1)[0]["items"], ["FN1", "FN5"])

    def test_plan_respects_capacity_and_excludes_orphans(self):
        rs = RequirementSet.load(SAMPLE)
        plan = plan_sprints(rs, 14, 3)
        planned = [i for s in plan for i in s["items"]]
        self.assertNotIn("FN16", planned)
        self.assertEqual(len(planned), len(set(planned)))
        for s in plan[:-1]:
            self.assertLessEqual(s["used"], 14)


if __name__ == "__main__":
    unittest.main()
