import datetime
import io
import json
import pathlib
import types
import zoneinfo

import pytest
from atestado_fixtures import (
    COMP401,
    BuildAtestado,
    build_atestado_html,
    build_atestado_pdf,
)

from ufal_schedule_ics import (
    Enrollment,
    Period,
    Record,
    StudentInfo,
    extract_raw_record,
    main,
    normalize_whitespace,
    parse_args,
    record_to_json,
)

RECORD = Record(
    period=Period("2026.2", datetime.date(2026, 7, 27), datetime.date(2026, 12, 12)),
    student=StudentInfo(id="12345678", name="João da Silva", course="Computação"),
    enrollments=[
        Enrollment(
            period="2026.2",
            code="COMP401",
            name="Ciência de Dados",
            professors="Renato Lima Farias",
            multiple_professors=False,
            section="1",
            status="MATRICULADO",
            schedule=["24M34"],
            start_date=datetime.date(2026, 7, 27),
            end_date=datetime.date(2026, 12, 12),
        )
    ],
)


class TestInput:
    def test_both_formats_are_recognized_from_their_bytes(
        self, build_atestado: BuildAtestado
    ) -> None:
        # DISP-01
        (enrollment,) = extract_raw_record(build_atestado([COMP401])).enrollments
        assert normalize_whitespace(enrollment.code) == "COMP401"


class TestJson:
    def test_serializes_the_record(self) -> None:
        # JSON-01
        payload = json.loads(record_to_json(RECORD))
        assert payload["period"] == {
            "label": "2026.2",
            "start_date": "2026-07-27",
            "end_date": "2026-12-12",
        }
        assert payload["student"]["id"] == "12345678"
        assert payload["enrollments"][0]["code"] == "COMP401"
        assert payload["enrollments"][0]["end_date"] == "2026-12-12"

    def test_keeps_non_ascii_characters(self) -> None:
        # JSON-02
        assert "João" in record_to_json(RECORD)


class TestArguments:
    def test_input_file_is_required(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # CLI-01
        monkeypatch.setattr("sys.argv", ["prog"])
        with pytest.raises(SystemExit) as exc_info:
            parse_args()

        assert exc_info.value.code == 2
        assert "input_file" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("flags", "print_record"),
        [([], False), (["-r"], True), (["--print-record"], True)],
    )
    def test_print_record_flag(
        self, monkeypatch: pytest.MonkeyPatch, flags: list[str], print_record: bool
    ) -> None:
        # CLI-02
        monkeypatch.setattr("sys.argv", ["prog", *flags, "file.pdf"])
        args = parse_args()
        assert args.print_record is print_record
        assert args.in_path == "file.pdf"

    def test_default_timezone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # CLI-03
        monkeypatch.setattr("sys.argv", ["prog", "file.pdf"])
        assert parse_args().timezone == zoneinfo.ZoneInfo("America/Maceio")

    @pytest.mark.parametrize("flag", ["-t", "--timezone"])
    def test_timezone_option(self, monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
        # CLI-03
        monkeypatch.setattr(
            "sys.argv", ["prog", flag, "America/Rio_Branco", "file.pdf"]
        )
        assert parse_args().timezone == zoneinfo.ZoneInfo("America/Rio_Branco")

    def test_unknown_timezone_is_a_usage_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # CLI-03
        monkeypatch.setattr("sys.argv", ["prog", "-t", "Foo/Bar", "file.pdf"])
        with pytest.raises(SystemExit) as exc_info:
            parse_args()

        assert exc_info.value.code == 2
        assert "unknown time zone 'Foo/Bar'" in capsys.readouterr().err


class TestRun:
    def test_print_record_flag_outputs_json(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # CLI-04
        path = tmp_path / "atestado.html"
        path.write_bytes(build_atestado_html([COMP401]))
        monkeypatch.setattr("sys.argv", ["prog", "--print-record", str(path)])

        main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["enrollments"][0]["code"] == "COMP401"

    def test_default_mode_outputs_a_calendar(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # CLI-04
        path = tmp_path / "atestado.pdf"
        path.write_bytes(build_atestado_pdf([COMP401]))
        monkeypatch.setattr("sys.argv", ["prog", str(path)])

        main()

        output = capsys.readouterr().out
        assert "BEGIN:VCALENDAR" in output
        assert "BEGIN:VEVENT" in output
        assert "DTSTART;TZID=America/Maceio:" in output

    def test_timezone_option_reaches_the_calendar(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # CLI-04
        path = tmp_path / "atestado.pdf"
        path.write_bytes(build_atestado_pdf([COMP401]))
        monkeypatch.setattr("sys.argv", ["prog", "-t", "America/Rio_Branco", str(path)])

        main()

        output = capsys.readouterr().out
        assert "TZID:America/Rio_Branco" in output
        assert "DTSTART;TZID=America/Rio_Branco:" in output

    def test_reads_from_stdin_when_path_is_dash(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # DISP-03, CLI-04
        data = build_atestado_html([COMP401])
        monkeypatch.setattr("sys.stdin", types.SimpleNamespace(buffer=io.BytesIO(data)))
        monkeypatch.setattr("sys.argv", ["prog", "--print-record", "-"])

        main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["enrollments"][0]["code"] == "COMP401"
