import dataclasses

import pymupdf
import pytest
from atestado_fixtures import (
    COMP382,
    COMP388,
    COMP393,
    COMP397,
    COMP401,
    LONG_STUDENT_NAME,
    ROWS_2026_2,
    BuildAtestado,
    EnrollmentRow,
    build_atestado_html,
    build_atestado_pdf,
)

from ufal_schedule_ics import RawPeriod, extract_raw_record, normalize_whitespace


class TestIdentification:
    def test_period_and_student_fields(self, build_atestado: BuildAtestado) -> None:
        # IDENT-01, IDENT-02, IDENT-03
        record = extract_raw_record(
            build_atestado(
                [],
                period_label="2026.2",
                period_start="27/07/2026",
                period_end="12/12/2026",
                student_id="12345678",
                student_name="TESTE DA SILVA",
                course=(
                    "CIÊNCIA DA COMPUTAÇÃO - CAMPUS MACEIÓ - PRESENCIAL - Maceió - "
                    "BACHARELADO - Regular - Semestral (13216) - M"
                ),
            )
        )
        assert record.period == RawPeriod("2026.2", "27/07/2026", "12/12/2026")
        assert normalize_whitespace(record.student.id) == "12345678"
        assert normalize_whitespace(record.student.name) == "TESTE DA SILVA"
        assert normalize_whitespace(record.student.course) == "CIÊNCIA DA COMPUTAÇÃO"

    def test_unspaced_hyphen_is_part_of_the_course_name(
        self, build_atestado: BuildAtestado
    ) -> None:
        # IDENT-04
        record = extract_raw_record(
            build_atestado([], course="LETRAS-LIBRAS - CAMPUS MACEIÓ")
        )
        assert normalize_whitespace(record.student.course) == "LETRAS-LIBRAS"

    def test_long_student_name_wrapped_in_the_pdf_is_captured_in_full(self) -> None:
        # IDENT-07
        record = extract_raw_record(
            build_atestado_pdf([], student_name=LONG_STUDENT_NAME)
        )
        assert "\n" in record.student.name
        assert normalize_whitespace(record.student.name) == LONG_STUDENT_NAME

    def test_course_without_separator_raises(
        self, build_atestado: BuildAtestado
    ) -> None:
        # IDENT-09
        data = build_atestado([], course="CIÊNCIA DA COMPUTAÇÃO")
        with pytest.raises(ValueError, match="course"):
            extract_raw_record(data)

    def test_page_without_identification_raises(self) -> None:
        # IDENT-10
        data = b"<html><body><h2>Portal do Discente</h2><p>Turmas</p></body></html>"
        with pytest.raises(ValueError, match="#identificacao"):
            extract_raw_record(data)

    def test_renamed_identification_label_raises(
        self, build_atestado: BuildAtestado
    ) -> None:
        # IDENT-10
        data = build_atestado([], labels={"Matrícula:": "Número de matrícula:"})
        with pytest.raises(ValueError, match="'Matrícula:'"):
            extract_raw_record(data)

    @pytest.mark.parametrize(
        "value",
        [
            "2026-2 (27/07/2026 à 12/12/2026)",
            "2026 (27/07/2026 à 12/12/2026)",
            "2026.2 (27/07/2026 a 12/12/2026)",
            "2026.2",
        ],
    )
    def test_period_in_another_notation_raises(
        self, build_atestado: BuildAtestado, value: str
    ) -> None:
        # IDENT-12
        data = build_atestado([], period_value=value)
        with pytest.raises(ValueError, match="period"):
            extract_raw_record(data)


class TestEnrollmentRows:
    def test_row_fields(self, build_atestado: BuildAtestado) -> None:
        # ROW-01, ROW-02, ROW-09
        # Only the whole table makes the PDF wrap COMP388's date range.
        enrollment = extract_raw_record(build_atestado(ROWS_2026_2)).enrollments[0]
        assert normalize_whitespace(enrollment.code) == "COMP388"
        assert (
            normalize_whitespace(enrollment.name) == "ACE 4: CONTINUAÇÃO DO PROJETO 2"
        )
        assert normalize_whitespace(enrollment.professors) == COMP388.professors
        assert normalize_whitespace(enrollment.section) == "02"
        assert normalize_whitespace(enrollment.status) == "MATRICULADO"
        assert enrollment.schedule == ["3T12"]
        assert enrollment.start_date == "27/07/2026"
        assert enrollment.end_date == "12/12/2026"

    def test_schedule_without_date_range_leaves_dates_unset(
        self, build_atestado: BuildAtestado
    ) -> None:
        # ROW-09
        (enrollment,) = extract_raw_record(build_atestado([COMP401])).enrollments
        assert enrollment.schedule == ["24M34"]
        assert enrollment.start_date is None
        assert enrollment.end_date is None

    def test_rows_keep_their_order_and_fields(
        self, build_atestado: BuildAtestado
    ) -> None:
        # ROW-01, ROW-03
        enrollments = extract_raw_record(build_atestado(ROWS_2026_2)).enrollments
        assert [normalize_whitespace(e.code) for e in enrollments] == [
            row.code for row in ROWS_2026_2
        ]
        assert [normalize_whitespace(e.name) for e in enrollments] == [
            normalize_whitespace(row.name or "") for row in ROWS_2026_2
        ]
        assert [normalize_whitespace(e.professors) for e in enrollments] == [
            row.professors for row in ROWS_2026_2
        ]

    def test_repeated_rows_are_all_kept_with_their_status(
        self, build_atestado: BuildAtestado
    ) -> None:
        # ROW-06
        enrollments = extract_raw_record(build_atestado(ROWS_2026_2)).enrollments
        assert [normalize_whitespace(e.status) for e in enrollments] == [
            row.status for row in ROWS_2026_2
        ]

    def test_multiple_professors_stay_one_string(
        self, build_atestado: BuildAtestado
    ) -> None:
        # ROW-04
        (enrollment,) = extract_raw_record(build_atestado([COMP382])).enrollments
        assert normalize_whitespace(enrollment.professors) == COMP382.professors

    def test_empty_location_is_accepted(self, build_atestado: BuildAtestado) -> None:
        # ROW-16
        # In the PDF, "Local:" with nothing after it ends the cell.
        (enrollment,) = extract_raw_record(build_atestado([COMP397])).enrollments
        assert normalize_whitespace(enrollment.name) == "COMPUTAÇÃO EVOLUCIONÁRIA"
        assert normalize_whitespace(enrollment.professors) == COMP397.professors

    def test_empty_professor_is_accepted(self, build_atestado: BuildAtestado) -> None:
        # ROW-18
        row = dataclasses.replace(COMP401, professors="")
        (enrollment,) = extract_raw_record(build_atestado([row])).enrollments
        assert normalize_whitespace(enrollment.name) == "CIÊNCIA DE DADOS"
        assert normalize_whitespace(enrollment.professors) == ""

    def test_columns_are_found_by_header(self, build_atestado: BuildAtestado) -> None:
        # ROW-07
        data = build_atestado([COMP393], include_level=False)
        (enrollment,) = extract_raw_record(data).enrollments
        assert normalize_whitespace(enrollment.section) == "02"
        assert normalize_whitespace(enrollment.status) == "MATRICULADO"

    def test_empty_table_yields_no_enrollments(
        self, build_atestado: BuildAtestado
    ) -> None:
        # ROW-21
        assert extract_raw_record(build_atestado([])).enrollments == []

    def test_renamed_column_raises(self, build_atestado: BuildAtestado) -> None:
        # ROW-10
        data = build_atestado([COMP401], renamed_headers={"Turma": "Turma nº"})
        with pytest.raises(ValueError, match="column 'Turma'"):
            extract_raw_record(data)

    def test_html_without_enrollments_table_raises(self) -> None:
        # ROW-14
        data = build_atestado_html([], include_table=False)
        with pytest.raises(ValueError, match="#matriculas"):
            extract_raw_record(data)

    def test_pdf_without_enrollments_table_raises(self) -> None:
        # ROW-14
        # The schedule grid becomes the first table instead.
        data = build_atestado_pdf([], include_table=False)
        with pytest.raises(ValueError, match=r"column 'Cód\.'"):
            extract_raw_record(data)

    def test_pdf_without_any_table_raises(self) -> None:
        # ROW-14
        data = build_atestado_pdf([], include_table=False, include_schedule_grid=False)
        with pytest.raises(ValueError, match="tables"):
            extract_raw_record(data)

    def test_html_table_without_tbody_raises(self) -> None:
        # ROW-22
        data = build_atestado_html([COMP401], include_tbody=False)
        with pytest.raises(ValueError, match="tbody"):
            extract_raw_record(data)

    def test_html_row_with_a_missing_cell_raises(self) -> None:
        # ROW-11
        row = dataclasses.replace(COMP401, schedule_cell="missing")
        with pytest.raises(ValueError, match="all columns in row 1"):
            extract_raw_record(build_atestado_html([row]))

    @pytest.mark.parametrize(
        ("change", "selector"),
        [({"name": None}, ".componente"), ({"professors": None}, ".docente")],
    )
    def test_html_component_without_an_element_raises(
        self, change: dict[str, None], selector: str
    ) -> None:
        # ROW-19
        row = dataclasses.replace(COMP401, **change)
        with pytest.raises(ValueError, match=f"'{selector}'"):
            extract_raw_record(build_atestado_html([row]))

    @pytest.mark.parametrize(
        ("change", "message"),
        [
            ({"schedule_cell": "merged"}, "'Horário' in row 1"),
            ({"component_cell": "merged"}, "component in row 1"),
        ],
    )
    def test_pdf_merged_cell_raises(self, change: dict[str, str], message: str) -> None:
        # ROW-12
        # A cell covered by a colspan comes out of find_tables() as None.
        row = dataclasses.replace(COMP401, **change)
        with pytest.raises(ValueError, match=message):
            extract_raw_record(build_atestado_pdf([row]))

    @pytest.mark.parametrize(
        "change",
        [
            {"professors": None, "type_": None, "location": None},  # No Tipo:
            {"name": None},  # No bold name before the professors
        ],
    )
    def test_pdf_component_out_of_shape_raises(self, change: dict[str, None]) -> None:
        # ROW-13
        row = dataclasses.replace(COMP401, **change)
        with pytest.raises(ValueError, match="name and professors in row 1"):
            extract_raw_record(build_atestado_pdf([row]))


class TestPdfFixture:
    @pytest.mark.parametrize(
        ("rows", "column", "wrapped"),
        [
            (ROWS_2026_2, 1, "REDES NEURAIS E APRENDIZADO\nPROFUNDO"),
            ([COMP382], 1, "LIMA,\nOSCAR"),
            (ROWS_2026_2, 5, "3T12 (27/07/2026 -\n12/12/2026)"),
        ],
    )
    def test_render_wraps_the_cells_the_extraction_tests_rely_on(
        self, rows: list[EnrollmentRow], column: int, wrapped: str
    ) -> None:
        # ROW-03, ROW-04, ROW-09
        with pymupdf.open(stream=build_atestado_pdf(rows)) as doc:
            table = next(iter(doc[0].find_tables()))
            cells = [row[column] or "" for row in table.extract()[1:]]
        assert any(wrapped in cell for cell in cells)
