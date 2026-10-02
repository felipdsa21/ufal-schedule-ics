import pytest
from atestado_fixtures import LONG_STUDENT_NAME
from comprovante_fixtures import (
    FRIDAY,
    MONDAY,
    SATURDAY,
    THURSDAY,
    TUESDAY,
    WEDNESDAY,
    build_comprovante_pdf,
)

from ufal_schedule_ics import (
    SieSubjectSchedule,
    extract_raw_record,
    normalize_whitespace,
    parse_sie_text,
)

M1, M2, M3, M4 = "07:30 - 08:20", "08:20 - 09:10", "09:20 - 10:10", "10:10 - 11:00"

PROGRAMACAO = "COMP359-M PROGRAMAÇÃO 1"
LOGICA = "COMP360-M LÓGICA PARA COMPUTAÇÃO"


class TestIdentification:
    def test_period_and_student_fields(self) -> None:
        # SIE-01, SIE-02
        record = extract_raw_record(
            build_comprovante_pdf(
                {PROGRAMACAO: {MONDAY: [M1]}},
                period="2023/2",
                student_id="12345678",
                student_name="TESTE DA SILVA",
                course="CIÊNCIA DA COMPUTAÇÃO",
            )
        )
        assert record.period.label == "2023.2"
        assert normalize_whitespace(record.student.id) == "12345678"
        assert normalize_whitespace(record.student.name) == "TESTE DA SILVA"
        assert normalize_whitespace(record.student.course) == "CIÊNCIA DA COMPUTAÇÃO"

    @pytest.mark.parametrize(
        ("period", "start_date", "end_date"),
        [
            ("2023/1", "26/06/2023", "25/10/2023"),
            ("2023/2", "13/11/2023", "05/04/2024"),
        ],
    )
    def test_period_dates_come_from_the_known_sie_periods(
        self, period: str, start_date: str, end_date: str
    ) -> None:
        # SIE-02
        record = extract_raw_record(build_comprovante_pdf({}, period=period))
        assert (record.period.start_date, record.period.end_date) == (
            start_date,
            end_date,
        )

    def test_long_student_name_is_captured_in_full(self) -> None:
        # SIE-05
        record = extract_raw_record(
            build_comprovante_pdf({}, student_name=LONG_STUDENT_NAME)
        )
        assert "\n" in record.student.name
        assert normalize_whitespace(record.student.name) == LONG_STUDENT_NAME

    def test_unknown_period_raises(self) -> None:
        # SIE-03
        data = build_comprovante_pdf({}, period="2022/2")
        with pytest.raises(ValueError, match=r"dates for period 2022\.2"):
            extract_raw_record(data)

    def test_period_in_another_notation_raises(self) -> None:
        # SIE-04
        data = build_comprovante_pdf({}, period="2023.1")
        with pytest.raises(ValueError, match="year and semester"):
            extract_raw_record(data)

    def test_missing_course_table_raises(self) -> None:
        # SIE-06
        data = build_comprovante_pdf({}, include_course_table=False)
        with pytest.raises(ValueError, match="tables"):
            extract_raw_record(data)


class TestSubjects:
    def test_subject_fields(self) -> None:
        # SIE-07, SIE-08, SIE-09, SIE-10
        (enrollment,) = extract_raw_record(
            build_comprovante_pdf({PROGRAMACAO: {MONDAY: [M1]}})
        ).enrollments
        assert enrollment.code == "COMP359"
        assert enrollment.name == "PROGRAMAÇÃO 1"
        assert enrollment.section == "M"
        assert enrollment.professors == "DOCENTE DE COMP359-M"
        assert enrollment.status == "MATRICULADO"
        assert enrollment.schedule == ["2M1"]
        assert enrollment.start_date is None
        assert enrollment.end_date is None

    def test_each_subject_keeps_its_own_schedule_and_professor(self) -> None:
        # SIE-09, SIE-11
        enrollments = extract_raw_record(
            build_comprovante_pdf({
                PROGRAMACAO: {MONDAY: [M1, M2]},
                LOGICA: {MONDAY: [M3, M4], FRIDAY: [M3, M4]},
            })
        ).enrollments
        by_code = {e.code: e for e in enrollments}
        assert by_code["COMP359"].schedule == ["2M12"]
        assert by_code["COMP359"].professors == "DOCENTE DE COMP359-M"
        assert by_code["COMP360"].schedule == ["26M34"]
        assert by_code["COMP360"].professors == "DOCENTE DE COMP360-M"

    @pytest.mark.parametrize(
        ("schedule", "expected"),
        [
            ({MONDAY: [M1, M2]}, ["2M12"]),
            ({MONDAY: [M1], WEDNESDAY: [M1]}, ["24M1"]),
            (
                {TUESDAY: [M2, M3, M4], THURSDAY: [M2, M3, M4], FRIDAY: [M1, M2]},
                ["35M234", "6M12"],
            ),
        ],
    )
    def test_class_times_become_time_codes(
        self, schedule: SieSubjectSchedule, expected: list[str]
    ) -> None:
        # SIE-11
        (enrollment,) = extract_raw_record(
            build_comprovante_pdf({PROGRAMACAO: schedule})
        ).enrollments
        assert enrollment.schedule == expected

    def test_saturday_is_a_day(self) -> None:
        # SIE-12
        enrollments = extract_raw_record(
            build_comprovante_pdf({
                PROGRAMACAO: {FRIDAY: [M1]},
                LOGICA: {SATURDAY: [M2]},
            })
        ).enrollments
        by_code = {e.code: e for e in enrollments}
        assert by_code["COMP359"].schedule == ["6M1"]
        assert by_code["COMP360"].schedule == ["7M2"]
        assert by_code["COMP360"].professors == "DOCENTE DE COMP360-M"

    def test_no_subjects_yields_no_enrollments(self) -> None:
        # SIE-16
        assert extract_raw_record(build_comprovante_pdf({})).enrollments == []

    @pytest.mark.parametrize(
        ("label", "message"),
        [
            ("COMP359-M", "subject code and name from 'COMP359-M'"),
            ("COMP359 PROGRAMAÇÃO 1", "subject code and section from 'COMP359'"),
        ],
    )
    def test_malformed_subject_label_raises(self, label: str, message: str) -> None:
        # SIE-14
        data = build_comprovante_pdf({label: {MONDAY: [M1]}}, include_subjects=False)
        with pytest.raises(ValueError, match=message):
            extract_raw_record(data)

    def test_subject_missing_from_the_professors_section_raises(self) -> None:
        # SIE-14
        data = build_comprovante_pdf({PROGRAMACAO: {MONDAY: [M1]}}, professors={})
        with pytest.raises(ValueError, match="professor for 'COMP359-M'"):
            extract_raw_record(data)

    # A truncated text can't come from the fixture.
    def test_subject_without_class_time_at_the_end_raises(self) -> None:
        # SIE-14
        with pytest.raises(ValueError, match="class time for 'COMP359-M"):
            parse_sie_text(f"{MONDAY}\n{PROGRAMACAO}")

    def test_professor_without_subject_code_at_the_end_raises(self) -> None:
        # SIE-14
        with pytest.raises(ValueError, match="subject code for 'DOCENTE'"):
            parse_sie_text("Professores\nDOCENTE")
