from pdf_rendering import render_pdf

from ufal_schedule_ics import SieSubjectSchedule

MONDAY = "2 - Segunda-feira"
TUESDAY = "3 - Terça-feira"
WEDNESDAY = "4 - Quarta-feira"
THURSDAY = "5 - Quinta-feira"
FRIDAY = "6 - Sexta-feira"
SATURDAY = "7 - Sábado"


def build_comprovante_pdf(
    schedules: dict[str, SieSubjectSchedule],
    professors: dict[str, str] | None = None,
    *,
    period: str = "2023/1",
    student_id: str = "99999999",
    student_name: str = "TESTE DA SILVA",
    course: str = "CIÊNCIA DA COMPUTAÇÃO",
    shift: str = "MATUTINO",
    include_subjects: bool = True,
    include_course_table: bool = True,
) -> bytes:
    # Without professors, each subject gets one named after its full code.
    if professors is None:
        professors = {
            subject.split(" ", 1)[0]: f"DOCENTE DE {subject.split(' ', 1)[0]}"
            for subject in schedules
        }

    parts = [
        (
            f"<table><tr><td>{period}</td><td>{student_id}</td>"
            f"<td>{student_name}</td></tr></table>"
        ),
        "<p>&#160;</p>",
    ]
    if include_course_table:
        parts.append(f"<table><tr><td>{course}</td><td>{shift}</td></tr></table>")
    parts.append("<p>Departamento de Registro e Controle Acadêmico - DRCA</p>")

    classes = sorted(
        (day, class_time, subject)
        for subject, schedule in schedules.items()
        for day, class_times in schedule.items()
        for class_time in class_times
    )
    previous_day = None
    for day, class_time, subject in classes:
        if day != previous_day:
            parts.append(f"<p>{day}</p>")
            previous_day = day
        parts.extend((f"<p>{subject}</p>", f"<p>{class_time}</p>"))

    if include_subjects:
        parts.append("<p>Disciplinas Matriculadas</p>")
        for subject in schedules:
            full_code, name = subject.split(" ", 1)
            parts.extend((f"<p>{name}</p>", f"<p>{full_code}</p>"))

    parts.append("<p>Professores</p>")
    for full_code, professor in professors.items():
        parts.extend((f"<p>{professor}</p>", f"<p>{full_code}</p>"))

    css = """
    table { border-collapse: collapse; }
    td, th { border: 1px solid black; padding: 2px 4px; }
    """

    return render_pdf("".join(parts), css)
