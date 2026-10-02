import pathlib
import re

TESTS = pathlib.Path(__file__).parent
SPEC = (TESTS.parent / "docs" / "especificacao.md").read_text(encoding="utf-8")

ROW_ID_RE = re.compile(r"^\| ([A-Z]+-\d+) \|", re.MULTILINE)
CITATION_RE = re.compile(r"^\s*# ((?:[A-Z]+-\d+(?:, )?)+)$", re.MULTILINE)

# The spec gives each of these rules a reason for having no test of its own.
UNTESTED = {"CAL-02", "DISP-02", "DISP-05", "DISP-06", "SIE-13"}


def section(start: str, end: str) -> str:
    begin = re.search(rf"^{re.escape(start)} ", SPEC, re.MULTILINE)
    finish = re.search(rf"^{re.escape(end)} ", SPEC, re.MULTILINE)
    assert begin is not None
    assert finish is not None
    return SPEC[begin.start() : finish.start()]


LIMITATIONS = ROW_ID_RE.findall(section("### 3.1", "## 4."))
RULES = ROW_ID_RE.findall(section("## 4.", "## 5."))


def cited_ids() -> set[str]:
    return {
        rule_id
        for path in TESTS.glob("test_*.py")
        for citation in CITATION_RE.findall(path.read_text(encoding="utf-8"))
        for rule_id in citation.split(", ")
    }


def test_ids_are_unique() -> None:
    ids = LIMITATIONS + RULES
    assert sorted(ids) == sorted(set(ids))


def test_tests_cite_only_existing_rules() -> None:
    assert cited_ids() <= set(RULES)


def test_every_rule_has_a_test() -> None:
    assert set(RULES) - cited_ids() == UNTESTED
