"""QOJ 适配器单元测试（normalize + HTML 解析）。"""


from datetime import UTC

from adapters.base import Verdict
from adapters.qoj import QOJAdapter
from adapters.qoj.normalize import map_verdict


class TestMapVerdict:
    """verdict 归一化测试。"""

    def test_ac_with_checkmark(self):
        assert map_verdict("AC ✓") == Verdict.AC
        assert map_verdict("100 ✓") == Verdict.AC
        assert map_verdict("110 ✓") == Verdict.AC

    def test_explicit_status(self):
        assert map_verdict("AC") == Verdict.AC
        assert map_verdict("WA") == Verdict.WA
        assert map_verdict("RE") == Verdict.RE
        assert map_verdict("TL") == Verdict.TLE
        assert map_verdict("ML") == Verdict.MLE
        assert map_verdict("CE") == Verdict.CE
        assert map_verdict("OLE") == Verdict.OLE
        assert map_verdict("UKE") == Verdict.UKE
        assert map_verdict("JG") == Verdict.JG

    def test_subtask_score_full(self):
        """满分通过（data-score == data-full）→ AC。"""
        assert map_verdict("50", score=50.0, full_score=50.0) == Verdict.AC
        assert map_verdict("100", score=100.0, full_score=100.0) == Verdict.AC

    def test_subtask_score_partial(self):
        """部分得分 → UNAC。"""
        assert map_verdict("72", score=72.0, full_score=100.0) == Verdict.UNAC
        assert map_verdict("0", score=0.0, full_score=100.0) == Verdict.UNAC
        assert map_verdict("1.5", score=1.5, full_score=100.0) == Verdict.UNAC

    def test_subtask_score_no_full_info(self):
        """无 full_score 信息时，纯数字保守归 UNAC。"""
        assert map_verdict("50") == Verdict.UNAC
        assert map_verdict("0") == Verdict.UNAC

    def test_unknown(self):
        assert map_verdict("???") == Verdict.UKE
        assert map_verdict("") == Verdict.UKE


class TestParseRows:
    """HTML 解析测试。"""

    def test_parse_sample_row(self):
        """解析单条典型提交记录。"""
        html = """
        <table>
        <tr><th>ID</th><th>Problem</th><th>Submitter</th><th>Result</th><th>Time</th><th>Memory</th><th>Language</th><th>File size</th><th>Submit time</th></tr>
        <tr>
            <td><a href="#/submission/2600866">#2600866</a></td>
            <td><a href="#/contest/123/problem/14809">#14809. Chi Fan</a></td>
            <td>Inkyo</td>
            <td><span class="uoj-result" data-score="100" data-full="100">AC ✓</span></td>
            <td>843ms</td>
            <td>5640kb</td>
            <td><a>C++20</a></td>
            <td>2.2kb</td>
            <td><a>2026-07-09 15:26:29</a></td>
        </tr>
        </table>
        """
        rows = QOJAdapter._parse_rows(html)
        assert len(rows) == 1
        row = rows[0]
        assert row.submission_id == "2600866"
        assert row.problem_id == "14809"
        assert row.problem_name == "Chi Fan"
        assert row.result_text == "AC ✓"
        assert row.score == 100.0
        assert row.full_score == 100.0
        assert row.language == "C++20"
        assert row.submitted_at_str == "2026-07-09 15:26:29"

    def test_parse_subtask_score(self):
        """解析子任务评分行。"""
        html = """
        <table>
        <tr><th>ID</th><th>Problem</th><th>Submitter</th><th>Result</th><th>Time</th><th>Memory</th><th>Language</th><th>File size</th><th>Submit time</th></tr>
        <tr>
            <td><a href="#/submission/123">#123</a></td>
            <td><a href="#/contest/1/problem/100">#100. Test</a></td>
            <td>user</td>
            <td><span class="uoj-result" data-score="72" data-full="100">72</span></td>
            <td>-</td>
            <td>-</td>
            <td><a>Python3</a></td>
            <td>1kb</td>
            <td><a>2026-06-01 10:00:00</a></td>
        </tr>
        </table>
        """
        rows = QOJAdapter._parse_rows(html)
        assert len(rows) == 1
        row = rows[0]
        assert row.result_text == "72"
        assert row.score == 72.0
        assert row.full_score == 100.0

    def test_parse_multiple_rows(self):
        """解析多行，跳过表头。"""
        html = """
        <table>
        <tr><th>ID</th><th>Problem</th><th>Submitter</th><th>Result</th><th>Time</th><th>Memory</th><th>Language</th><th>File size</th><th>Submit time</th></tr>
        <tr>
            <td><a href="#/submission/1">#1</a></td>
            <td><a href="#/contest/1/problem/100">#100. A</a></td>
            <td>u1</td>
            <td><span class="uoj-result">AC ✓</span></td>
            <td>1ms</td>
            <td>1kb</td>
            <td><a>C++</a></td>
            <td>1kb</td>
            <td><a>2026-01-01 00:00:01</a></td>
        </tr>
        <tr>
            <td><a href="#/submission/2">#2</a></td>
            <td><a href="#/contest/1/problem/101">#101. B</a></td>
            <td>u1</td>
            <td><span class="uoj-result">WA</span></td>
            <td>2ms</td>
            <td>2kb</td>
            <td><a>Java</a></td>
            <td>2kb</td>
            <td><a>2026-01-01 00:00:02</a></td>
        </tr>
        </table>
        """
        rows = QOJAdapter._parse_rows(html)
        assert len(rows) == 2
        assert rows[0].submission_id == "1"
        assert rows[1].submission_id == "2"

    def test_parse_empty_table(self):
        """空表格返回空列表。"""
        html = "<table><tr><th>A</th></tr></table>"
        rows = QOJAdapter._parse_rows(html)
        assert rows == []

    def test_parse_skips_malformed_rows(self):
        """跳过格式不正确的行（不阻断整批）。"""
        html = """
        <table>
        <tr><th>ID</th><th>Problem</th><th>Submitter</th><th>Result</th><th>Time</th><th>Memory</th><th>Language</th><th>File size</th><th>Submit time</th></tr>
        <tr>
            <td>bad</td>
            <td>no link</td>
            <td>user</td>
            <td>WA</td>
            <td>-</td>
            <td>-</td>
            <td>C++</td>
            <td>1kb</td>
            <td>2026-01-01 00:00:00</td>
        </tr>
        <tr>
            <td><a href="#/submission/1">#1</a></td>
            <td><a href="#/contest/1/problem/100">#100. A</a></td>
            <td>u1</td>
            <td><span class="uoj-result">AC ✓</span></td>
            <td>1ms</td>
            <td>1kb</td>
            <td><a>C++</a></td>
            <td>1kb</td>
            <td><a>2026-01-01 00:00:01</a></td>
        </tr>
        </table>
        """
        rows = QOJAdapter._parse_rows(html)
        assert len(rows) == 1
        assert rows[0].submission_id == "1"


class TestToUtcSeconds:
    """时区转换测试。"""

    def test_china_time_to_utc(self):
        """中国时间（UTC+8）→ UTC 秒级时间戳。"""
        ts = QOJAdapter.to_utc_seconds("2026-07-09 15:26:29")
        # 2026-07-09 15:26:29 UTC+8 = 2026-07-09 07:26:29 UTC
        from datetime import datetime
        expected = int(datetime(2026, 7, 9, 7, 26, 29, tzinfo=UTC).timestamp())
        assert ts == expected


class TestExtractNickname:
    """昵称提取测试。"""

    def test_extract_nickname(self):
        html = '<div data-nickname="TestUser">content</div>'
        assert QOJAdapter._extract_nickname(html) == "TestUser"

    def test_extract_nickname_empty(self):
        assert QOJAdapter._extract_nickname("<div>no nickname</div>") is None


class TestToSubmission:
    """提交记录归一化测试。"""

    def test_to_submission_ac(self):
        from adapters.qoj.api_models import QojSubmissionRow
        row = QojSubmissionRow(
            submission_id="123",
            problem_id="100",
            problem_name="Test Problem",
            result_text="AC ✓",
            language="C++20",
            submitted_at_str="2026-01-01 12:00:00",
            score=100.0,
            full_score=100.0,
        )
        sub = QOJAdapter.to_submission(row, 1735723200)
        assert sub.submission_id == "123"
        assert sub.problem_key == "100"
        assert sub.problem_name == "Test Problem"
        assert sub.verdict == Verdict.AC
        assert sub.submitted_at == 1735723200
        assert sub.language == "C++20"
        assert sub.difficulty is None

    def test_to_submission_unac(self):
        from adapters.qoj.api_models import QojSubmissionRow
        row = QojSubmissionRow(
            submission_id="456",
            problem_id="101",
            problem_name="Another",
            result_text="72",
            language="Python3",
            submitted_at_str="2026-01-01 12:00:00",
            score=72.0,
            full_score=100.0,
        )
        sub = QOJAdapter.to_submission(row, 1735723200)
        assert sub.verdict == Verdict.UNAC
