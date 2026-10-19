#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "beautifulsoup4>=4.15.0",
#     "icalendar>=7.3.0",
#     "pymupdf>=1.28.2,<2",
# ]
# ///

import argparse
import dataclasses
import datetime
import enum
import itertools
import json
import re
import sys
import typing
import unicodedata
import uuid
import zoneinfo
from collections import abc

import bs4
import icalendar
import pymupdf

DEFAULT_TIMEZONE = "America/Maceio"
KNOWN_STATUSES = "INDEFERIDO", "MATRICULADO"
NAMESPACE_UID = uuid.UUID("3ce34002-08ef-49ef-a212-ce9c9a503d99")
WEEKDAY_ABBREVS = "MO", "TU", "WE", "TH", "FR", "SA", "SU"

COURSE_RE = re.compile(r"(.+?)\s+-\s", re.DOTALL)
FIELD_LABEL_RE = re.compile(r"^[^\n:]+:(?!\S)", re.MULTILINE)
MULTIPLE_PROFESSORS_RE = re.compile(r",|\be\b")
PERIOD_DATES_RE = re.compile(
    r"(\d{4}\.\d) \((\d{2}/\d{2}/\d{4}) à (\d{2}/\d{2}/\d{4})\)"
)
SCHEDULE_WITH_RANGE_RE = re.compile(r"([^()]+?)\s\(([0-9/]+)\s-\s([0-9/]+)\)")
SIE_DAY_RE = re.compile(r"[1-7] - .+")
TIME_CODE_RE = re.compile(r"([1-7]+)([MTN])([1-9]+)")
WHITESPACE_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"\w+")


class Args:
    print_record: bool
    timezone: zoneinfo.ZoneInfo
    in_path: str


class Columns[T](typing.NamedTuple):
    code: T
    component: T
    section: T
    status: T
    schedule: T


COLUMN_NAMES = Columns(
    code="Cód.",
    component="Componentes Curriculares/Docentes",
    section="Turma",
    status="Status",
    schedule="Horário",
)

CORRECT_CASES = (
    "à",
    "ACE",
    "ao",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "FPGA",
    "IA",
    "II",
    "III",
    "IV",
    "na",
    "no",
    "para",
    "por",
    "sem",
    "TCC",
)

CORRECT_SPELLINGS = (
    "Abraão",
    "André",
    "Antônio",
    "Araújo",
    "Beltrão",
    "César",
    "Cícero",
    "Cláudia",
    "Cláudius",
    "Corrêa",
    "Domínguez",
    "Fábio",
    "Getúlio",
    "Gonçalves",
    "Gregório",
    "Guimarães",
    "Gusmão",
    "Hernández",
    "Hilário",
    "Ícaro",
    "Iván",
    "João",
    "José",
    "Júnior",
    "Luís",
    "Marcílio",
    "Márcio",
    "Mário",
    "Martínez",
    "Maurício",
    "Müller",
    "Nóbrega",
    "Paraguaçu",
    "Perdigão",
    "Petrúcio",
    "Sá",
    "Tenório",
    "Vitório",
)

SHIFTS = {
    "M": (datetime.time(7, 30), 6),
    "T": (datetime.time(13, 30), 6),
    "N": (datetime.time(19, 0), 4),
}

DATE_CORRECTIONS = {datetime.date(2025, 11, 19): datetime.date(2025, 11, 28)}

SIE_PERIOD_DATES = {
    "2023.1": ("26/06/2023", "25/10/2023"),
    "2023.2": ("13/11/2023", "05/04/2024"),
}


def slot_to_time(shift_start: datetime.time, slot: int, is_end: bool) -> datetime.time:
    minutes = 60 * shift_start.hour + shift_start.minute
    minutes += 50 * (slot - (0 if is_end else 1))  # Slots
    minutes += 10 * ((slot - 1) // 2)  # Pauses
    return datetime.time(minutes // 60, minutes % 60)


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


CASE_CORRECTIONS = {word.title(): word for word in CORRECT_CASES}

SLOT_TIMES = {
    (shift, slot): (slot_to_time(start, slot, False), slot_to_time(start, slot, True))
    for shift, (start, count) in SHIFTS.items()
    for slot in range(1, count + 1)
}

SLOTS_BY_TIME_RANGE = {
    f"{start:%H:%M} - {end:%H:%M}": key for key, (start, end) in SLOT_TIMES.items()
}

SPELLING_CORRECTIONS = {strip_accents(word): word for word in CORRECT_SPELLINGS}


@dataclasses.dataclass(slots=True)
class RawRecord:
    period: RawPeriod
    student: StudentInfo
    enrollments: list[RawEnrollment]


@dataclasses.dataclass(slots=True)
class RawPeriod:
    label: str
    start_date: str
    end_date: str


@dataclasses.dataclass(slots=True)
class RawEnrollment:
    code: str
    name: str
    professors: str
    section: str
    status: str
    schedule: list[str]
    start_date: str | None = None
    end_date: str | None = None


@dataclasses.dataclass(slots=True)
class SieRecord:
    period: str
    student: StudentInfo
    enrollments: list[SieEnrollment]


type SieSchedulesBySubject = dict[str, SieSubjectSchedule]


class SiePdfSection(enum.Enum):
    SCHEDULE = enum.auto()
    SUBJECTS = enum.auto()
    PROFESSORS = enum.auto()


@dataclasses.dataclass(slots=True)
class SieEnrollment:
    code: str
    name: str
    professor: str
    section: str
    schedule: SieSubjectSchedule


type SieSubjectSchedule = dict[str, list[str]]


@dataclasses.dataclass(slots=True)
class Record:
    period: Period
    student: StudentInfo
    enrollments: list[Enrollment]


@dataclasses.dataclass(slots=True)
class Period:
    label: str
    start_date: datetime.date
    end_date: datetime.date


@dataclasses.dataclass(slots=True)
class StudentInfo:
    id: str
    name: str
    course: str


@dataclasses.dataclass(slots=True)
class Enrollment:
    period: str
    code: str
    name: str
    professors: str
    multiple_professors: bool
    section: str
    status: str
    schedule: list[str]
    start_date: datetime.date
    end_date: datetime.date


def require[T](value: T | None, what: str) -> T:
    if value is None:
        raise ValueError(f"Could not extract {what}")

    return value


def split_once(value: str, sep: str, what: str) -> tuple[str, str]:
    head, found, tail = value.partition(sep)
    if not found:
        raise ValueError(f"Could not extract {what} from {value!r}")

    return head, tail


def normalize_whitespace(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value.strip())


def read_input(path: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()

    with open(path, mode="rb", buffering=0) as file:
        return file.read()


def extract_raw_record(data: bytes) -> RawRecord:
    if data.startswith(b"%PDF-"):
        return extract_raw_record_pdf_dispatch(data)
    else:
        return extract_raw_record_html(data)


def extract_raw_record_pdf_dispatch(data: bytes) -> RawRecord:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        page = doc[0]
        text = page.get_text()
        if not isinstance(text, str):
            raise TypeError(f"Expected str from get_text, got {type(text).__name__}")

        if "Departamento de Registro e Controle Acadêmico - DRCA" in text:
            sie_record = extract_sie_record(page, text)
            return convert_sie_record(sie_record)
        else:
            return extract_raw_record_pdf(page, text)


def extract_sie_record(page: pymupdf.Page, text: str) -> SieRecord:
    tabs = list(page.find_tables())
    if len(tabs) < 2:
        raise ValueError("Could not extract tables")

    first_row = tabs[0].extract()[0]
    period = first_row[0]
    student = StudentInfo(first_row[1], first_row[2], tabs[1].extract()[0][0])

    schedules_by_subject, professors = parse_sie_text(text)
    enrollments: list[SieEnrollment] = []

    for subject, subject_schedule in schedules_by_subject.items():
        full_code, name = split_once(subject, " ", "subject code and name")
        code, section = split_once(full_code, "-", "subject code and section")

        enrollment = SieEnrollment(
            code=code,
            name=name,
            professor=require(
                professors.get(full_code), f"professor for {full_code!r}"
            ),
            section=section,
            schedule=subject_schedule,
        )
        enrollments.append(enrollment)

    return SieRecord(period, student, enrollments)


def parse_sie_text(text: str) -> tuple[SieSchedulesBySubject, dict[str, str]]:
    schedules_by_subject: SieSchedulesBySubject = {}
    professors: dict[str, str] = {}

    lines = iter(text.splitlines())
    pdf_section = SiePdfSection.SCHEDULE
    current_day: str | None = None

    for line in lines:
        if line == "Disciplinas Matriculadas":
            pdf_section = SiePdfSection.SUBJECTS

        elif line == "Professores":
            pdf_section = SiePdfSection.PROFESSORS

        elif pdf_section == SiePdfSection.SCHEDULE:
            if SIE_DAY_RE.fullmatch(line):
                current_day = line
            elif current_day:
                class_time = require(next(lines, None), f"class time for {line!r}")
                subject_schedule = schedules_by_subject.setdefault(line, {})
                subject_schedule.setdefault(current_day, []).append(class_time)

        elif pdf_section == SiePdfSection.PROFESSORS:
            full_code = require(next(lines, None), f"subject code for {line!r}")
            professors[full_code] = line

    return schedules_by_subject, professors


def convert_sie_record(sie_record: SieRecord) -> RawRecord:
    year, semester = split_once(sie_record.period, "/", "year and semester")

    label = f"{year}.{semester}"
    dates = require(SIE_PERIOD_DATES.get(label), f"dates for period {label}")
    period = RawPeriod(label, *dates)

    enrollments = [
        RawEnrollment(
            code=enrollment.code,
            name=enrollment.name,
            professors=enrollment.professor,
            section=enrollment.section,
            status="MATRICULADO",
            schedule=schedule_to_time_codes(enrollment.schedule),
        )
        for enrollment in sie_record.enrollments
    ]

    return RawRecord(period, sie_record.student, enrollments)


def schedule_to_time_codes(schedule: SieSubjectSchedule) -> list[str]:
    days_by_shift_slots: dict[str, str] = {}

    for day, day_schedule in schedule.items():
        day_digit = day.split(" - ", 1)[0]
        slots_by_shift: dict[str, set[int]] = {}

        for class_time in day_schedule:
            shift, slot = require(
                SLOTS_BY_TIME_RANGE.get(class_time), f"slot for {class_time!r}"
            )
            slots_by_shift.setdefault(shift, set()).add(slot)

        for shift, slots in slots_by_shift.items():
            for run in split_contiguous_runs(slots):
                shift_slots = shift + "".join(map(str, run))
                days = days_by_shift_slots.get(shift_slots, "")
                days_by_shift_slots[shift_slots] = days + day_digit

    return [days + shift_slots for shift_slots, days in days_by_shift_slots.items()]


def split_contiguous_runs(values: abc.Iterable[int]) -> abc.Generator[list[int]]:
    runs = itertools.groupby(enumerate(sorted(values)), key=lambda p: p[1] - p[0])
    for _, run in runs:
        yield [value for _, value in run]


def extract_raw_record_pdf(page: pymupdf.Page, text: str) -> RawRecord:
    fields = split_labeled_fields(text)
    period, student = parse_identification(
        lambda label: require(fields.get(label), repr(label))
    )

    tab = require(next(iter(page.find_tables()), None), "tables")
    columns = get_column_indexes(tab.header.names)
    enrollments: list[RawEnrollment] = []

    for i, row in enumerate(tab.extract()[1:], 1):
        code, section, status, raw_schedule = (
            require(row[col], f"{tab.header.names[col]!r} in row {i}")
            for col in (columns.code, columns.section, columns.status, columns.schedule)
        )
        bbox = require(tab.rows[i].cells[columns.component], f"component in row {i}")
        name, professors = require(
            split_component_cell(page, bbox), f"name and professors in row {i}"
        )
        schedule, start_date, end_date = parse_schedule_and_dates(raw_schedule)

        enrollment = RawEnrollment(
            code=code,
            name=name,
            professors=professors,
            section=section,
            status=status,
            schedule=schedule,
            start_date=start_date,
            end_date=end_date,
        )
        enrollments.append(enrollment)

    return RawRecord(period, student, enrollments)


def split_labeled_fields(text: str) -> dict[str, str]:
    labels = list(FIELD_LABEL_RE.finditer(text))
    ends = [label.start() for label in labels[1:]] + [len(text)]
    fields: dict[str, str] = {}

    for label, end in zip(labels, ends, strict=True):
        key = normalize_whitespace(label.group())
        fields.setdefault(key, text[label.end() : end].strip())

    return fields


def parse_identification(
    field: abc.Callable[[str], str],
) -> tuple[RawPeriod, StudentInfo]:
    period_value = normalize_whitespace(field("Período Letivo:"))
    match = require(PERIOD_DATES_RE.fullmatch(period_value), "period")
    period = RawPeriod(match.group(1), match.group(2), match.group(3))

    id_ = field("Matrícula:")
    name = field("Nome:")
    course = require(COURSE_RE.search(field("Curso:")), "course").group(1)
    return period, StudentInfo(id_, name, course)


def get_column_indexes(header: abc.Sequence[str]) -> Columns[int]:
    columns = {name: i for i, name in enumerate(header)}
    return Columns(
        *(require(columns.get(name), f"column {name!r}") for name in COLUMN_NAMES)
    )


def split_component_cell(
    page: pymupdf.Page, bbox: tuple[float, float, float, float]
) -> tuple[str, str] | None:
    text_dict = page.get_text("dict", clip=bbox)
    if not isinstance(text_dict, dict):
        raise TypeError(f"Expected dict from get_text, got {type(text_dict).__name__}")

    spans = [
        span
        for block in text_dict["blocks"]
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span["text"].strip()
    ]

    end = next(
        (
            i
            for i, span in enumerate(spans)
            if is_bold_span(span) and span["text"].strip() == "Tipo:"
        ),
        None,
    )
    if end is None:
        return None

    groups = [
        (bold, " ".join(span["text"] for span in group))
        for bold, group in itertools.groupby(spans[:end], key=is_bold_span)
    ]
    match groups:
        case [(True, name)]:
            return name, ""
        case [(True, name), (False, professors)]:
            return name, professors
        case _:
            return None


def is_bold_span(span: dict) -> bool:
    return (
        bool(span["flags"] & pymupdf.TEXT_FONT_BOLD) or "bold" in span["font"].lower()
    )


def parse_schedule_and_dates(value: str) -> tuple[list[str], str | None, str | None]:
    if match := SCHEDULE_WITH_RANGE_RE.fullmatch(value.strip()):
        return match.group(1).split(), match.group(2), match.group(3)

    return value.split(), None, None


def extract_raw_record_html(data: bytes) -> RawRecord:
    soup = bs4.BeautifulSoup(data, "html.parser")
    identification = require(soup.select_one("#identificacao"), "#identificacao")

    period, student = parse_identification(
        lambda label: extract_next_cell_text(identification, label)
    )

    table = require(soup.select_one("#matriculas"), "#matriculas")
    body = require(table.select_one(":scope > tbody"), "#matriculas > tbody")
    header = tuple(normalize_whitespace(th.get_text()) for th in table.select("th"))
    columns = get_column_indexes(header)
    enrollments: list[RawEnrollment] = []

    for i, row in enumerate(body.select(":scope > tr"), 1):
        cells = row.select(":scope > td")
        if len(cells) <= max(columns):
            raise ValueError(f"Could not extract all columns in row {i}")

        component = cells[columns.component]
        raw_schedule = cells[columns.schedule].get_text()
        schedule, start_date, end_date = parse_schedule_and_dates(raw_schedule)

        enrollment = RawEnrollment(
            code=cells[columns.code].get_text(),
            name=extract_tag_text(component, ".componente"),
            professors=extract_tag_text(component, ".docente"),
            section=cells[columns.section].get_text(),
            status=cells[columns.status].get_text(),
            schedule=schedule,
            start_date=start_date,
            end_date=end_date,
        )
        enrollments.append(enrollment)

    return RawRecord(period, student, enrollments)


def extract_next_cell_text(tag: bs4.Tag, label: str) -> str:
    for subtag in tag.select("td"):
        text = normalize_whitespace(subtag.get_text())
        if text == label and (sibling := subtag.find_next_sibling("td")):
            return sibling.get_text()

    raise ValueError(f"Could not find table cell for {label!r}")


def extract_tag_text(tag: bs4.Tag, selector: str) -> str:
    return require(tag.select_one(selector), f"{selector!r}").get_text()


def normalize_raw_record(raw_record: RawRecord) -> Record:
    period = Period(
        raw_record.period.label,
        parse_date(raw_record.period.start_date),
        parse_date(raw_record.period.end_date),
    )

    student = StudentInfo(
        normalize_whitespace(raw_record.student.id),
        normalize_name(raw_record.student.name),
        normalize_name(raw_record.student.course),
    )

    enrollments: list[Enrollment] = []

    for raw_enrollment in raw_record.enrollments:
        professors = raw_enrollment.professors
        section = normalize_whitespace(raw_enrollment.section)
        status = normalize_whitespace(raw_enrollment.status)

        if status not in KNOWN_STATUSES:
            raise ValueError(f"Unknown status {status!r}")

        start_date = parse_date_or_default(raw_enrollment.start_date, period.start_date)
        end_date = parse_date_or_default(raw_enrollment.end_date, period.end_date)

        enrollment = Enrollment(
            period=period.label,
            code=normalize_whitespace(raw_enrollment.code),
            name=normalize_name(raw_enrollment.name),
            professors=normalize_name(professors, fix_spellings=True),
            multiple_professors=bool(MULTIPLE_PROFESSORS_RE.search(professors)),
            section=section.lstrip("0") or section[:1],
            status=status,
            schedule=raw_enrollment.schedule,
            start_date=start_date,
            end_date=end_date,
        )
        enrollments.append(enrollment)

    return Record(period, student, enrollments)


def parse_date(value: str) -> datetime.date:
    try:
        parsed = datetime.date.strptime(value, "%d/%m/%Y")
    except ValueError as e:
        raise ValueError(f"Could not parse date {value!r}") from e

    return DATE_CORRECTIONS.get(parsed, parsed)


def normalize_name(name: str, fix_spellings: bool = False) -> str:
    def fix_word(match: re.Match[str]) -> str:
        word = match.group()

        fixed = CASE_CORRECTIONS.get(word)
        if fixed and (match.start() > 0 or fixed.isupper()):
            return fixed

        return SPELLING_CORRECTIONS.get(word, word) if fix_spellings else word

    return WORD_RE.sub(fix_word, normalize_whitespace(name).title())


def parse_date_or_default(value: str | None, default: datetime.date) -> datetime.date:
    return default if value is None else parse_date(value)


def record_to_json(record: Record) -> str:
    fields = dataclasses.asdict(record)
    return json.dumps(fields, ensure_ascii=False, default=str)


def build_calendar(
    enrollments: list[Enrollment], tz: zoneinfo.ZoneInfo
) -> icalendar.Calendar:
    events = tuple(
        event
        for enrollment in enrollments
        if enrollment.status == "MATRICULADO"
        for event in generate_events(enrollment, tz)
    )

    calendar_uid = uuid.uuid5(NAMESPACE_UID, ";".join(event.uid for event in events))
    calendar = icalendar.Calendar.new(uid=calendar_uid)

    for event in events:
        calendar.add_component(event)

    calendar.add_missing_timezones()
    return calendar


def generate_events(
    enrollment: Enrollment, tz: zoneinfo.ZoneInfo
) -> abc.Generator[icalendar.Event]:
    summary = f"{enrollment.name} {enrollment.period}"
    professor_label = "Professores" if enrollment.multiple_professors else "Professor"
    description = "\n".join((
        f"Código: {enrollment.code}",
        f"Turma: {enrollment.section}",
        f"{professor_label}: {enrollment.professors}",
    ))

    now = datetime.datetime.now(datetime.UTC)
    last_instant = datetime.datetime.combine(enrollment.end_date, datetime.time.max, tz)
    until = last_instant.astimezone(datetime.UTC)

    for time_code in enrollment.schedule:
        uid_parts = enrollment.period, enrollment.code, enrollment.section, time_code
        start_time, end_time, days = parse_time_code(time_code)
        first_date = min(on_or_after_weekday(enrollment.start_date, d) for d in days)
        by_days = [WEEKDAY_ABBREVS[d] for d in days]

        event = icalendar.Event.new(
            summary=summary,
            start=datetime.datetime.combine(first_date, start_time, tz),
            end=datetime.datetime.combine(first_date, end_time, tz),
            stamp=now,
            uid=uuid.uuid5(NAMESPACE_UID, ";".join(uid_parts)),
            description=description,
        )
        event.add("rrule", {"freq": "weekly", "until": until, "byday": by_days})

        yield event


def parse_time_code(value: str) -> tuple[datetime.time, datetime.time, tuple[int, ...]]:
    match = require(TIME_CODE_RE.fullmatch(value), f"time code from {value!r}")
    days_str, shift, slots_str = match.groups()

    slots = tuple(map(int, slots_str))
    if slots != tuple(range(slots[0], slots[0] + len(slots))):
        raise ValueError(f"Non-contiguous slots in time code {value!r}")

    days = tuple((int(day) - 2) % 7 for day in days_str)
    start_time, _ = require(
        SLOT_TIMES.get((shift, slots[0])), f"slot {shift}{slots[0]}"
    )
    _, end_time = require(
        SLOT_TIMES.get((shift, slots[-1])), f"slot {shift}{slots[-1]}"
    )
    return start_time, end_time, days


def on_or_after_weekday(date: datetime.date, weekday: int) -> datetime.date:
    return date + datetime.timedelta((weekday - date.weekday()) % 7)


def parse_timezone(value: str) -> zoneinfo.ZoneInfo:
    try:
        return zoneinfo.ZoneInfo(value)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError) as e:
        raise argparse.ArgumentTypeError(f"unknown time zone {value!r}") from e


def parse_args() -> Args:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r",
        "--print-record",
        action="store_true",
        help="print the parsed record as JSON instead of generating a calendar",
    )
    parser.add_argument(
        "-t",
        "--timezone",
        type=parse_timezone,
        default=DEFAULT_TIMEZONE,
        help=f"IANA time zone of the class times (default: {DEFAULT_TIMEZONE})",
    )
    parser.add_argument(
        "in_path", metavar="input_file", help="input file (use '-' for standard input)"
    )
    return parser.parse_args(namespace=Args())


def main() -> None:
    args = parse_args()

    pymupdf.no_recommend_layout()

    raw_record = extract_raw_record(read_input(args.in_path))
    record = normalize_raw_record(raw_record)

    if args.print_record:
        print(record_to_json(record))
    else:
        calendar = build_calendar(record.enrollments, args.timezone)
        sys.stdout.buffer.write(calendar.to_ical())


if __name__ == "__main__":
    main()
