import datetime

import pytest
from comprovante_fixtures import FRIDAY, MONDAY, SATURDAY, THURSDAY, TUESDAY, WEDNESDAY

from ufal_schedule_ics import (
    SLOT_TIMES,
    SLOTS_BY_TIME_RANGE,
    TIME_CODE_RE,
    SieSubjectSchedule,
    parse_schedule_and_dates,
    parse_time_code,
    schedule_to_time_codes,
)

OFFICIAL_GRID = {
    ("M", 1): "07:30 - 08:20",
    ("M", 2): "08:20 - 09:10",
    ("M", 3): "09:20 - 10:10",
    ("M", 4): "10:10 - 11:00",
    ("M", 5): "11:10 - 12:00",
    ("M", 6): "12:00 - 12:50",
    ("T", 1): "13:30 - 14:20",
    ("T", 2): "14:20 - 15:10",
    ("T", 3): "15:20 - 16:10",
    ("T", 4): "16:10 - 17:00",
    ("T", 5): "17:10 - 18:00",
    ("T", 6): "18:00 - 18:50",
    ("N", 1): "19:00 - 19:50",
    ("N", 2): "19:50 - 20:40",
    ("N", 3): "20:50 - 21:40",
    ("N", 4): "21:40 - 22:30",
}

M1, M2, M3, M4, M5, M6 = (OFFICIAL_GRID["M", slot] for slot in range(1, 7))
T3, T4 = OFFICIAL_GRID["T", 3], OFFICIAL_GRID["T", 4]


class TestScheduleCell:
    def test_code_without_date_range(self) -> None:
        # SCHED-01
        assert parse_schedule_and_dates("24M34") == (["24M34"], None, None)

    def test_code_with_date_range(self) -> None:
        # SCHED-02
        assert parse_schedule_and_dates("3T12 (27/07/2026 - 12/12/2026)") == (
            ["3T12"],
            "27/07/2026",
            "12/12/2026",
        )

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            # HTML: trailing space in the cell.
            ("3T12 (27/07/2026 - 12/12/2026) ", (["3T12"], "27/07/2026", "12/12/2026")),
            # PDF: wrap after the "-".
            ("6T23 (07/07/2025 -\n19/11/2025)", (["6T23"], "07/07/2025", "19/11/2025")),
        ],
    )
    def test_real_cell_whitespace_yields_no_empty_codes(
        self, value: str, expected: tuple[list[str], str, str]
    ) -> None:
        # SCHED-03
        assert parse_schedule_and_dates(value) == expected

    def test_multiple_codes(self) -> None:
        # SCHED-04
        assert parse_schedule_and_dates("2M56 2T12") == (["2M56", "2T12"], None, None)

    def test_empty_cell_yields_no_codes(self) -> None:
        # SCHED-07
        assert parse_schedule_and_dates(" ") == ([], None, None)

    @pytest.mark.parametrize(
        "value",
        [
            "3T12(27/07/2026-12/12/2026)",
            "2M12 (03/08/2026 - 30/09/2026) 4T34 (01/10/2026 - 12/12/2026)",
            "3T12 (27/07/2026 - 12/12/2026) 24M34",
        ],
    )
    def test_unrecognized_format_is_rejected_downstream(self, value: str) -> None:
        # SCHED-06
        codes, start_date, end_date = parse_schedule_and_dates(value)
        assert (start_date, end_date) == (None, None)
        with pytest.raises(ValueError, match="time code"):
            list(map(parse_time_code, codes))


class TestTimeCodes:
    def test_slot_times_match_the_official_grid(self) -> None:
        # TC-01
        actual = {
            key: f"{start:%H:%M} - {end:%H:%M}"
            for key, (start, end) in SLOT_TIMES.items()
        }
        assert actual == OFFICIAL_GRID
        assert SLOTS_BY_TIME_RANGE == {
            class_time: key for key, class_time in OFFICIAL_GRID.items()
        }

    @pytest.mark.parametrize(
        ("digit", "weekday"),
        [("1", 6), ("2", 0), ("3", 1), ("4", 2), ("5", 3), ("6", 4), ("7", 5)],
    )
    def test_day_digits_map_to_weekdays(self, digit: str, weekday: int) -> None:
        # TC-04
        _, _, days = parse_time_code(f"{digit}M1")
        assert days == (weekday,)

    def test_days_keep_the_order_of_the_code(self) -> None:
        # TC-04
        _, _, days = parse_time_code("246M12")
        assert days == (0, 2, 4)

    @pytest.mark.parametrize(
        ("code", "start", "end"),
        [
            ("24T12", datetime.time(13, 30), datetime.time(15, 10)),
            ("6M3456", datetime.time(9, 20), datetime.time(12, 50)),
            ("2N34", datetime.time(20, 50), datetime.time(22, 30)),
        ],
    )
    def test_span_goes_from_the_first_to_the_last_slot(
        self, code: str, start: datetime.time, end: datetime.time
    ) -> None:
        # TC-04
        assert parse_time_code(code)[:2] == (start, end)

    @pytest.mark.parametrize(
        "code",
        [
            "M12",  # Missing days
            "2M",  # Missing slots
            "2X1",  # Unknown shift letter
            "0M1",  # Day digit below Sunday
            "8M1",  # Day digit above Saturday
            "2M56T12",  # Two shifts in one code
        ],
    )
    def test_malformed_code_raises(self, code: str) -> None:
        # TC-05
        with pytest.raises(ValueError, match="time code"):
            parse_time_code(code)

    @pytest.mark.parametrize("code", ["2M13", "2M21", "2M1224"])
    def test_non_contiguous_slots_raise(self, code: str) -> None:
        # TC-05
        with pytest.raises(ValueError, match="Non-contiguous"):
            parse_time_code(code)

    @pytest.mark.parametrize(
        ("code", "slot"), [("2M7", "M7"), ("2T67", "T7"), ("2N5", "N5"), ("2N9", "N9")]
    )
    def test_slot_outside_the_shift_raises(self, code: str, slot: str) -> None:
        # TC-05
        with pytest.raises(ValueError, match=f"slot {slot}"):
            parse_time_code(code)


class TestTimeCodesFromClassTimes:
    @pytest.mark.parametrize(
        ("schedule", "expected"),
        [
            ({MONDAY: [M1]}, ["2M1"]),
            ({MONDAY: [M1, M2]}, ["2M12"]),
            ({MONDAY: [M1, M2], WEDNESDAY: [M1, M2]}, ["24M12"]),
            ({THURSDAY: [M1, OFFICIAL_GRID["T", 1]]}, ["5M1", "5T1"]),
            ({MONDAY: [M1, M2, M5, M6]}, ["2M12", "2M56"]),
            ({SATURDAY: [M1]}, ["7M1"]),
        ],
    )
    def test_groups_slots_and_days(
        self, schedule: SieSubjectSchedule, expected: list[str]
    ) -> None:
        # TC-06
        assert schedule_to_time_codes(schedule) == expected

    @pytest.mark.parametrize(
        "class_time",
        [
            "06:00 - 06:50",  # Before any shift
            "07:30 - 08:30",  # Known start, wrong end
            "13:50 - 14:40",  # Inside a slot, not at its start
        ],
    )
    def test_class_time_outside_the_grid_raises(self, class_time: str) -> None:
        # TC-08
        with pytest.raises(ValueError, match="slot for"):
            schedule_to_time_codes({MONDAY: [class_time]})

    # The schedules of two whole comprovantes.
    @pytest.mark.parametrize(
        "schedule",
        [
            {MONDAY: [M1, M2], WEDNESDAY: [M1, M2]},
            {MONDAY: [M3, M4], WEDNESDAY: [M3, M4]},
            {MONDAY: [M5, M6], WEDNESDAY: [M5, M6]},
            {TUESDAY: [M2, M3, M4], THURSDAY: [M2, M3, M4], FRIDAY: [M1, M2]},
            {FRIDAY: [M3, M4, M5, M6]},
            {MONDAY: [T3, T4], WEDNESDAY: [T3, T4]},
            {TUESDAY: [M3, M4], THURSDAY: [M3, M4]},
            {TUESDAY: [M5, M6], THURSDAY: [M5, M6]},
        ],
    )
    def test_expanding_the_codes_recovers_the_schedule(
        self, schedule: SieSubjectSchedule
    ) -> None:
        # TC-09
        expected = {
            (day[0], class_time)
            for day, class_times in schedule.items()
            for class_time in class_times
        }

        actual: set[tuple[str, str]] = set()
        for code in schedule_to_time_codes(schedule):
            parse_time_code(code)  # Must have contiguous slots
            match = TIME_CODE_RE.fullmatch(code)
            assert match is not None
            days, shift, slots = match.groups()
            actual.update(
                (day, OFFICIAL_GRID[shift, int(slot)]) for day in days for slot in slots
            )

        assert actual == expected
