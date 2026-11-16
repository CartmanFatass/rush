"""Regression checks for observed contamination, source and time-boundary bugs."""
import tempfile
import unittest
import contextlib
import io
from pathlib import Path

from source_layers import sublayer_of
from relate import parse_exams, first_answers, pre_exam, Tfidf
from poltheory import parse_poltheory
import dynamics


class SourceClassificationTests(unittest.TestCase):
    def test_collection_prefix_does_not_make_a_publisher_official(self):
        for source in ("osint-yicai_news", "osint-21jingji_news", "osint-stcn_news",
                       "osint-gmw", "osint-people_daily", "osint-economic_daily"):
            self.assertEqual(sublayer_of(source), "B_主流媒体")
        self.assertEqual(sublayer_of("osint-ndrc_news"), "A1_部委发布")
        self.assertEqual(sublayer_of("osint-cass_news"), "D_学术智库")
        self.assertEqual(sublayer_of("osint-drc_news"), "D_学术智库")
        self.assertEqual(sublayer_of("osint-unknown"), "Z_其他")
        self.assertEqual(sublayer_of("_web"), "Z_其他")

    def test_primary_source_path_must_be_a_component(self):
        self.assertEqual(sublayer_of("other", "/tmp/_primary-sources/file.txt"), "A0_中央文件")
        self.assertEqual(sublayer_of("other", "/tmp/not_primary-sources/file.txt"), "Z_其他")


class ExamBoundaryTests(unittest.TestCase):
    def test_instructions_and_answers_are_not_last_material(self):
        for heading in ("## 三、作答要求\n", ""):
            with self.subTest(heading=heading), tempfile.TemporaryDirectory() as tmp:
                body = ("## 给定材料\n### 材料 1\n短材料也应保留。\n" + heading +
                        "### 第一题\n只属于题干的指令。\n## 参考答案\n只属于答案。")
                for year, paper in ((2026, "地市级"), (2026, "行政执法"), (2021, "地市级")):
                    (Path(tmp) / f"{year}国考申论（{paper}）.md").write_text(body)
                exams = parse_exams(exam_dir=tmp)
                self.assertEqual(len(exams), 1)
                self.assertEqual(exams[0]["materials"][0]["text"], "短材料也应保留。")
                self.assertEqual(exams[0]["questions"], ["只属于题干的指令。"])

    def test_first_reference_answer_excludes_prompt_alternatives_and_notes(self):
        text = ("## 参考答案\n### 第一题\n重复的题干\n**【参考答案一】**\n第一份答案\n"
                "参考答案说明：机构解释\n**【参考答案二】**\n第二份答案\n")
        self.assertEqual(first_answers(text), [{"question": "一", "text": "第一份答案"}])

    def test_actual_primary_scope_is_complete_and_clean(self):
        exams = parse_exams()
        self.assertEqual(len(exams), 10)
        self.assertEqual(sum(len(e["materials"]) for e in exams), 47)
        for e in exams:
            self.assertEqual(len(e["questions"]), 5)
            for m in e["materials"]:
                self.assertNotIn("### 第一题", m["text"])
                self.assertNotIn("## 三、作答要求", m["text"])

    def test_actual_answer_projection_has_fifty_answers(self):
        from relate import EXAM_DIR
        for exam in parse_exams():
            answers = first_answers((EXAM_DIR / exam["file"]).read_text())
            self.assertEqual(len(answers), 5)
            for answer in answers:
                self.assertNotIn("参考答案说明：", answer["text"])
                self.assertNotIn("**【参考答案", answer["text"])

    def test_political_dedup_preserves_city_and_province_appearances(self):
        questions = parse_poltheory()
        self.assertEqual(len(questions), 74)
        self.assertEqual(sum(len(q["appearances"]) for q in questions), 124)
        self.assertEqual(len(parse_poltheory(papers=("地市级",))), 62)
        self.assertEqual(len(parse_poltheory(papers=("副省级",))), 62)
        self.assertTrue(all(2022 <= q["year"] <= 2026 for q in questions))


class TimeBoundaryTests(unittest.TestCase):
    def test_reading_inventory_includes_october_without_prediction_score(self):
        docs = [{"date": "2026-10-20", "text": "科技创新", "sublayer": "B_主流媒体"},
                {"date": "2026-11-01", "text": "科技创新", "sublayer": "B_主流媒体"}]
        previous = dynamics.OUT
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            try:
                dynamics.OUT = Path(tmp)
                rows = dynamics.candidates(docs, [])
            finally:
                dynamics.OUT = previous
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["docs"], 1)
        self.assertEqual(rows[0]["share"], 1.0)
        self.assertNotIn("score", rows[0])

    def test_same_month_after_exam_is_not_pre_exam(self):
        self.assertFalse(pre_exam("2025-11-30", "2025-11-30"))
        self.assertFalse(pre_exam("2025-11-28", "2025-11-27"))
        self.assertTrue(pre_exam("2025-11-26", "2025-11-27"))
        self.assertFalse(pre_exam("", "2025-11-30"))
        self.assertFalse(pre_exam("2025-02-30", "2025-11-30"))

    def test_filter_precedes_top_k(self):
        tf = Tfidf.__new__(Tfidf)
        tf.vecs = [{"共同": 1.0}, {"共同": 0.9}, {"共同": 0.2}]
        self.assertEqual(tf.top({"共同": 1.0}, k=1, allowed_indices={2}), [(0.2, 2)])


if __name__ == "__main__":
    unittest.main()
