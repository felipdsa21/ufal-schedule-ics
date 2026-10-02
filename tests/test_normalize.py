import dataclasses
import datetime

import pytest
from atestado_fixtures import COMP385, COMP388, COMP393, COMP397, BuildAtestado

from ufal_schedule_ics import (
    CORRECT_CASES,
    CORRECT_SPELLINGS,
    Enrollment,
    Period,
    RawEnrollment,
    RawPeriod,
    RawRecord,
    Record,
    StudentInfo,
    extract_raw_record,
    normalize_name,
    normalize_raw_record,
    normalize_whitespace,
    parse_date,
    strip_accents,
)

BASE_RAW_RECORD = RawRecord(
    period=RawPeriod(label="2026.2", start_date="27/07/2026", end_date="12/12/2026"),
    student=StudentInfo(id=" 12345678", name="TESTE DA SILVA", course=" TESTE"),
    enrollments=[],
)

BASE_RAW_ENROLLMENT = RawEnrollment(
    code=" COMP401 ",
    name=" CIÊNCIA DE DADOS ",
    professors="RENATO LIMA FARIAS",
    section="01",
    status="MATRICULADO",
    schedule=["24M34"],
)


def normalize_enrollment(**overrides: object) -> Enrollment:
    raw_enrollment = dataclasses.replace(BASE_RAW_ENROLLMENT, **overrides)
    record = normalize_raw_record(
        dataclasses.replace(BASE_RAW_RECORD, enrollments=[raw_enrollment])
    )
    return record.enrollments[0]


class TestWhitespace:
    def test_strips_and_collapses_spaces_newlines_and_tabs(self) -> None:
        # NORM-01
        value = "  ACE 4:  CONTINUAÇÃO\n\tDO PROJETO 2 "
        assert normalize_whitespace(value) == "ACE 4: CONTINUAÇÃO DO PROJETO 2"


class TestDates:
    def test_parses_ddmmyyyy(self) -> None:
        # NORM-03
        assert parse_date("27/07/2026") == datetime.date(2026, 7, 27)

    @pytest.mark.parametrize("value", ["2026/07/27", "31/02/2024"])
    def test_malformed_date_raises(self, value: str) -> None:
        # NORM-05
        with pytest.raises(ValueError, match=f"Could not parse date {value!r}"):
            parse_date(value)

    def test_known_correction_applies_to_every_date(self) -> None:
        # NORM-04
        # COMP383 ends with the period; COMP390 has no range of its own.
        record = normalize_raw_record(
            RawRecord(
                period=RawPeriod("2025.1", "07/07/2025", "19/11/2025"),
                student=BASE_RAW_RECORD.student,
                enrollments=[
                    dataclasses.replace(
                        BASE_RAW_ENROLLMENT,
                        code="COMP383",
                        start_date="07/07/2025",
                        end_date="19/11/2025",
                    ),
                    dataclasses.replace(BASE_RAW_ENROLLMENT, code="COMP390"),
                ],
            )
        )
        corrected = datetime.date(2025, 11, 28)
        assert record.period.end_date == corrected
        assert [e.end_date for e in record.enrollments] == [corrected, corrected]

    def test_missing_enrollment_dates_come_from_the_period(self) -> None:
        # NORM-12
        enrollment = normalize_enrollment(start_date=None, end_date=None)
        assert enrollment.start_date == datetime.date(2026, 7, 27)
        assert enrollment.end_date == datetime.date(2026, 12, 12)

    def test_enrollment_dates_override_the_period(self) -> None:
        # NORM-12
        enrollment = normalize_enrollment(
            start_date="03/08/2026", end_date="30/09/2026"
        )
        assert enrollment.start_date == datetime.date(2026, 8, 3)
        assert enrollment.end_date == datetime.date(2026, 9, 30)


class TestNames:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("ACE 2: CONTINUIDADE DO PROJETO I", "ACE 2: Continuidade do Projeto I"),
            ("ACE 4:  CONTINUAÇÃO DO PROJETO 2", "ACE 4: Continuação do Projeto 2"),
            ("PROJETO E ANÁLISE DE ALGORITMOS", "Projeto e Análise de Algoritmos"),
            ("INTERAÇÃO HOMEM-MÁQUINA", "Interação Homem-Máquina"),
            (
                "REDES NEURAIS E APRENDIZADO\nPROFUNDO",
                "Redes Neurais e Aprendizado Profundo",
            ),
            (" CIÊNCIA DA COMPUTAÇÃO ", "Ciência da Computação"),
            ("DE SOUZA PEREIRA", "De Souza Pereira"),
            ("TCC EM IA", "TCC em IA"),
        ],
    )
    def test_examples(self, name: str, expected: str) -> None:
        # NORM-08
        assert normalize_name(name) == expected

    def test_spelling_corrections_are_opt_in(self) -> None:
        # NORM-09
        assert normalize_name("ANDRE SILVA", fix_spellings=True) == "André Silva"
        assert normalize_name("ANDRE SILVA") == "Andre Silva"

    @pytest.mark.parametrize("word", CORRECT_CASES)
    def test_every_entry_in_correct_cases_is_restored_mid_name(self, word: str) -> None:
        # NORM-08
        assert normalize_name(f"TESTE {word.upper()} TESTE") == f"Teste {word} Teste"

    @pytest.mark.parametrize("word", CORRECT_SPELLINGS)
    def test_every_entry_in_correct_spellings_is_restored(self, word: str) -> None:
        # NORM-09
        misspelled = strip_accents(word).upper()
        assert (
            normalize_name(f"TESTE {misspelled} TESTE", fix_spellings=True)
            == f"Teste {word} Teste"
        )


class TestEnrollmentFields:
    @pytest.mark.parametrize(
        ("section", "expected"), [("01", "1"), ("02", "2"), ("10", "10"), ("M", "M")]
    )
    def test_section_loses_leading_zeros(self, section: str, expected: str) -> None:
        # NORM-10
        assert normalize_enrollment(section=section).section == expected

    @pytest.mark.parametrize(
        ("professors", "expected"),
        [
            ("RENATO LIMA FARIAS", False),
            ("JOÃO DA SILVA E SOUSA", False),
            ("CESAR AUGUSTO GUIMARAES e MAURICIO TEIXEIRA", True),
            ("CARLOS MENDES, JULIANA TORRES e RAFAELA DE MOURA NUNES", True),
        ],
    )
    def test_multiple_professors(self, professors: str, expected: bool) -> None:
        # NORM-11
        assert (
            normalize_enrollment(professors=professors).multiple_professors is expected
        )

    @pytest.mark.parametrize("status", ["Matriculado", "MATRICULADA", "CANCELADO"])
    def test_unknown_status_raises(self, status: str) -> None:
        # NORM-16
        with pytest.raises(ValueError, match=f"Unknown status {status!r}"):
            normalize_enrollment(status=status)


START_2026_2 = datetime.date(2026, 7, 27)
END_2026_2 = datetime.date(2026, 12, 12)

EXPECTED_ENROLLMENT = Enrollment(
    period="2026.2",
    code="",
    name="",
    professors="",
    multiple_professors=False,
    section="1",
    status="MATRICULADO",
    schedule=[],
    start_date=START_2026_2,
    end_date=END_2026_2,
)


class TestSameRecordFromHtmlAndPdf:
    def test_normalizes_to_the_expected_record(
        self, build_atestado: BuildAtestado
    ) -> None:
        # NORM-13, NORM-14, NORM-15, NORM-17
        rows = [
            COMP388,
            dataclasses.replace(COMP385, status="INDEFERIDO"),
            COMP397,
            COMP393,
        ]
        expected = Record(
            period=Period("2026.2", START_2026_2, END_2026_2),
            student=StudentInfo("12345678", "Teste da Silva", "Ciência da Computação"),
            enrollments=[
                dataclasses.replace(
                    EXPECTED_ENROLLMENT,
                    code="COMP388",
                    name="ACE 4: Continuação do Projeto 2",
                    professors="Ana Paula Moreira dos Santos",
                    section="2",
                    schedule=["3T12"],
                ),
                dataclasses.replace(
                    EXPECTED_ENROLLMENT,
                    code="COMP385",
                    name="ACE 5: Evento",
                    professors="Helena Ribeiro Gonçalves Cardoso de Medeiros",
                    status="INDEFERIDO",
                    schedule=["3T56"],
                ),
                dataclasses.replace(
                    EXPECTED_ENROLLMENT,
                    code="COMP397",
                    name="Computação Evolucionária",
                    professors=(
                        "César Augusto Guimarães de Souza e "
                        "Maurício Teixeira Gonçalves da Luz"
                    ),
                    multiple_professors=True,
                    schedule=["35T12"],
                ),
                dataclasses.replace(
                    EXPECTED_ENROLLMENT,
                    code="COMP393",
                    name="Redes Neurais e Aprendizado Profundo",
                    professors="Otavio Ferraz Nogueira",
                    section="2",
                    schedule=["35T34"],
                ),
            ],
        )

        assert (
            normalize_raw_record(extract_raw_record(build_atestado(rows))) == expected
        )
