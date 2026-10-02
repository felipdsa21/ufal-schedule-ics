import dataclasses
import datetime
import zoneinfo

import icalendar

from ufal_schedule_ics import Enrollment, build_calendar, generate_events

TZ = zoneinfo.ZoneInfo("America/Maceio")

# 2026.2 starts on a Monday.
BASE_ENROLLMENT = Enrollment(
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


def make_enrollment(**overrides: object) -> Enrollment:
    return dataclasses.replace(BASE_ENROLLMENT, **overrides)


def local(day: int, month: int, hour: int, minute: int) -> datetime.datetime:
    return datetime.datetime(2026, month, day, hour, minute, tzinfo=TZ)


class TestEvents:
    def test_one_event_per_time_code(self) -> None:
        # EV-01
        enrollment = make_enrollment(schedule=["35M234", "6M12"])
        assert len(list(generate_events(enrollment, TZ))) == 2
        assert list(generate_events(make_enrollment(schedule=[]), TZ)) == []

    def test_summary_is_name_and_period(self) -> None:
        # EV-02
        (event,) = generate_events(BASE_ENROLLMENT, TZ)
        assert event.summary == "Ciência de Dados 2026.2"

    def test_description(self) -> None:
        # EV-03
        (event,) = generate_events(BASE_ENROLLMENT, TZ)
        assert event.description == (
            "Código: COMP401\nTurma: 1\nProfessor: Renato Lima Farias"
        )

    def test_professor_label_follows_the_flag_not_the_text(self) -> None:
        # EV-03
        (several,) = generate_events(
            make_enrollment(
                professors="Ana Lima e Rui Costa", multiple_professors=True
            ),
            TZ,
        )
        (single,) = generate_events(
            make_enrollment(professors="João da Silva e Souza"), TZ
        )
        assert "Professores: Ana Lima e Rui Costa" in several.description
        assert "Professor: João da Silva e Souza" in single.description

    def test_first_occurrence_is_the_first_class_day_from_the_start(self) -> None:
        # EV-04
        first, second = generate_events(make_enrollment(schedule=["24M34", "3T12"]), TZ)
        assert (first.start, first.end) == (local(27, 7, 9, 20), local(27, 7, 11, 0))
        assert (second.start, second.end) == (
            local(28, 7, 13, 30),
            local(28, 7, 15, 10),
        )

    def test_class_times_are_wall_clock_times_in_the_given_zone(self) -> None:
        # EV-05
        rio_branco = zoneinfo.ZoneInfo("America/Rio_Branco")
        (event,) = generate_events(BASE_ENROLLMENT, rio_branco)
        assert event.start == datetime.datetime(2026, 7, 27, 9, 20, tzinfo=rio_branco)
        assert isinstance(event.start, datetime.datetime)
        assert event.start.tzinfo is rio_branco

    def test_uid_is_fixed_across_versions(self) -> None:
        # EV-06
        uids = [
            event.uid
            for period in ("2025.1", "2026.1")
            for event in generate_events(
                make_enrollment(period=period, code="COMP397", schedule=["35T12"]), TZ
            )
        ]
        assert uids == [
            "28a02e8c-dc97-5eba-9e0d-013b4aa080c8",
            "3f7c40da-00ad-589e-96cd-8fc89eac099d",
        ]

    def test_weekly_recurrence_until_the_end_date(self) -> None:
        # EV-07
        # 23:59:59 in Maceió (UTC-3) is 02:59:59 UTC the next day.
        (event,) = generate_events(make_enrollment(schedule=["35T34"]), TZ)
        (rrule,) = event.rrules
        assert rrule["FREQ"] == "weekly"
        assert rrule["BYDAY"] == ["TU", "TH"]
        assert rrule["UNTIL"].replace(microsecond=0) == datetime.datetime(
            2026, 12, 13, 2, 59, 59, tzinfo=datetime.UTC
        )

    def test_byday_follows_the_order_of_the_code(self) -> None:
        # EV-07
        (event,) = generate_events(make_enrollment(schedule=["246M12"]), TZ)
        (rrule,) = event.rrules
        assert rrule["BYDAY"] == ["MO", "WE", "FR"]

    def test_dtstamp_is_the_generation_time_in_utc(self) -> None:
        # EV-08
        before = datetime.datetime.now(datetime.UTC)
        (event,) = generate_events(BASE_ENROLLMENT, TZ)
        after = datetime.datetime.now(datetime.UTC)
        assert event.stamp.utcoffset() == datetime.timedelta(0)
        assert before <= event.stamp <= after


class TestCalendar:
    def test_only_the_matriculado_row_of_a_repeated_subject_is_kept(self) -> None:
        # CAL-01, CAL-03
        # The three rows share the UID key.
        comp385 = make_enrollment(code="COMP385", schedule=["3T56"])
        enrollments = [
            dataclasses.replace(comp385, status="INDEFERIDO"),
            dataclasses.replace(comp385, status="INDEFERIDO"),
            comp385,
        ]

        (event,) = build_calendar(enrollments, TZ).walk("VEVENT")
        assert "Código: COMP385" in str(event["DESCRIPTION"])

    def test_no_matriculado_rows_yield_an_empty_calendar(self) -> None:
        # CAL-04
        for enrollments in ([], [make_enrollment(status="INDEFERIDO")]):
            calendar = build_calendar(enrollments, TZ)
            assert calendar.name == "VCALENDAR"
            assert calendar.walk("VEVENT") == []

    def test_output_round_trips_through_icalendar(self) -> None:
        # CAL-05
        output = build_calendar([BASE_ENROLLMENT], TZ).to_ical()

        (event,) = icalendar.Calendar.from_ical(output).walk("VEVENT")
        assert str(event["SUMMARY"]) == "Ciência de Dados 2026.2"

    def test_events_reference_an_included_vtimezone(self) -> None:
        # CAL-06
        output = build_calendar([BASE_ENROLLMENT], TZ).to_ical()

        calendar = icalendar.Calendar.from_ical(output)
        (timezone,) = calendar.walk("VTIMEZONE")
        (event,) = calendar.walk("VEVENT")
        assert timezone["TZID"] == "America/Maceio"
        assert event["DTSTART"].params["TZID"] == "America/Maceio"

    def test_calendar_uid_is_deterministic_and_depends_on_the_events(self) -> None:
        # CAL-07
        other = make_enrollment(code="COMP404")

        first_run = build_calendar([BASE_ENROLLMENT], TZ)
        second_run = build_calendar([BASE_ENROLLMENT], TZ)
        other_events = build_calendar([BASE_ENROLLMENT, other], TZ)

        assert first_run["UID"] == second_run["UID"]
        assert first_run["UID"] != other_events["UID"]
