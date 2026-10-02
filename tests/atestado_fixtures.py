import dataclasses
import typing
from collections import abc

from pdf_rendering import render_pdf

type BuildAtestado = abc.Callable[..., bytes]


@dataclasses.dataclass
class EnrollmentRow:
    # None leaves the element out of the markup; "" keeps it, but empty.
    code: str
    name: str | None
    professors: str | None
    schedule: str
    section: str = "01"
    level: str = "-"
    status: str = "MATRICULADO"
    type_: str | None = "DISCIPLINA"
    location: str | None = "Sala 1"
    # "missing" drops the cell; "merged" joins it to the previous one (colspan).
    component_cell: typing.Literal["own", "merged"] = "own"
    schedule_cell: typing.Literal["own", "missing", "merged"] = "own"


class AtestadoOptions(typing.TypedDict, total=False):
    period_label: str
    period_start: str
    period_end: str
    period_value: str
    student_id: str
    student_name: str
    course: str
    labels: dict[str, str]
    include_table: bool
    include_tbody: bool
    include_level: bool
    renamed_headers: dict[str, str]
    include_schedule_grid: bool


LONG_STUDENT_NAME = (
    "MARIA EDUARDA DOS SANTOS ALBUQUERQUE CAVALCANTI DE OLIVEIRA PEREIRA DA "
    "SILVA NASCIMENTO FERREIRA"
)

# Made-up professor names: real ones are personal data.
COMP388 = EnrollmentRow(
    code="COMP388",
    name="ACE 4:  CONTINUAÇÃO DO PROJETO 2",
    professors="ANA PAULA MOREIRA DOS SANTOS",
    schedule="3T12 (27/07/2026 - 12/12/2026)",
    section="02",
    level="7",
    type_="ATIVIDADE",
    location="IC - A definir",
)
COMP385 = EnrollmentRow(
    code="COMP385",
    name="ACE 5: EVENTO",
    professors="HELENA RIBEIRO GONCALVES CARDOSO DE MEDEIROS",
    schedule="3T56 (27/07/2026 - 12/12/2026)",
    level="8",
    type_="ATIVIDADE",
    location="Auditório CEPETEC",
)
COMP401 = EnrollmentRow(
    code="COMP401",
    name="CIÊNCIA DE DADOS",
    professors="RENATO LIMA FARIAS",
    schedule="24M34",
    location="Laboratório 01 - IC",
)
COMP404 = EnrollmentRow(
    code="COMP404",
    name="CÁLCULO 3",
    professors="JOSE ANTONIO MACHADO DA ROCHA",
    schedule="24T34",
    location="Sala 02 IC",
)
COMP393 = EnrollmentRow(
    code="COMP393",
    name="REDES NEURAIS E APRENDIZADO PROFUNDO",
    professors="OTAVIO FERRAZ NOGUEIRA",
    schedule="35T34",
    section="02",
    location="Sala 04 IC",
)
COMP390 = EnrollmentRow(
    code="COMP390",
    name="APRENDIZAGEM DE MÁQUINA",
    professors="SERGIO PRADO DE CASTRO",
    schedule="35M56",
    section="02",
    location="LCCV",
)
COMP397 = EnrollmentRow(
    code="COMP397",
    name="COMPUTAÇÃO EVOLUCIONÁRIA",
    professors="CESAR AUGUSTO GUIMARAES DE SOUZA e MAURICIO TEIXEIRA GONCALVES DA LUZ",
    schedule="35T12",
    location="",
)
COMP382 = EnrollmentRow(
    code="COMP382",
    name="PROJETO E DESENVOLVIMENTO DE SISTEMAS",
    professors=(
        "CARLOS EDUARDO MENDES, JULIANA TORRES FALCAO DE ANDRADE LIMA, "
        "OSCAR PEDRO DA COSTA e RAFAELA DE MOURA NUNES"
    ),
    schedule="2345M3456",
    location="Auditório CPTEC",
)

# Only with all its rows does the PDF render wrap the long cells.
ROWS_2026_2 = [
    COMP388,
    dataclasses.replace(COMP385, status="INDEFERIDO"),
    dataclasses.replace(COMP385, status="INDEFERIDO"),
    COMP385,
    COMP401,
    COMP404,
    COMP393,
    COMP390,
]

COLUMN_HEADERS = (
    "Cód.",
    "Componentes Curriculares/Docentes",
    "Turma",
    "Nível",
    "Status",
    "Horário",
)

# The rules of the portal's stylesheets that shape the PDF render.
ATESTADO_CSS = """
body { font-size: 70%; font-family: Verdana, sans-serif; }
#identificacao { width: 100%; }
#identificacao td { padding: 0px; }
#matriculas {
    width: 100%;
    border-left: 1px solid #BBB; border-top: 1px solid #BBB;
}
#matriculas td, #matriculas th {
    border-right: 1px solid #BBB; border-bottom: 1px solid #BBB;
}
#matriculas span.componente { font-weight: bold; }
#matriculas span.docente { font-size: 0.8em; display: block; }
#horario { border-left: 1px solid #BBB; border-top: 1px solid #BBB; }
#horario td { border-right: 1px solid #BBB; border-bottom: 1px solid #BBB; }
"""


def build_component_cell(row: EnrollmentRow) -> str:
    parts = []
    if row.name is not None:
        parts.append(f'<span class="componente"> {row.name} </span>')
    if row.professors is not None:
        parts.append(f'<span class="docente">{row.professors}</span>')
    if row.type_ is not None:
        parts.append(f"""<span class="tipoComponente">
                    <b>Tipo:</b>
                    {row.type_}
                </span>""")
    if row.location is not None:
        parts.append(f'<span class="local"><b>Local:</b> {row.location}</span>')

    return "\n                ".join(parts)


def build_code_and_component_cells(row: EnrollmentRow) -> str:
    match row.component_cell:
        case "own":
            return f"""<td class="codigo"> {row.code} </td>
            <td>
                {build_component_cell(row)}
            </td>"""
        case "merged":
            return f'<td class="codigo" colspan="2"> {row.code} </td>'


def build_status_and_schedule_cells(row: EnrollmentRow) -> str:
    match row.schedule_cell:
        case "own":
            return f"""<td class="status">{row.status}</td>
            <td class="horario">{row.schedule} </td>"""
        case "missing":
            return f'<td class="status">{row.status}</td>'
        case "merged":
            return f'<td class="status" colspan="2">{row.status}</td>'


def build_enrollments_table(
    rows: list[EnrollmentRow],
    *,
    include_tbody: bool = True,
    include_level: bool = True,
    renamed_headers: dict[str, str] | None = None,
) -> str:
    # The cell whitespace is the real markup's. The heading keeps
    # find_tables() from taking the text above for the header row.
    renamed_headers = renamed_headers or {}
    headers = "".join(
        f"\n                <th>{renamed_headers.get(header, header)}</th>"
        for header in COLUMN_HEADERS
        if include_level or header != "Nível"
    )
    table_body = "".join(
        f"""
        <tr>
            {build_code_and_component_cells(row)}
            <td class="turma">{row.section}</td>
            {f'<td class="turma">{row.level}</td>' if include_level else ""}
            {build_status_and_schedule_cells(row)}
        </tr>"""
        for row in rows
    )
    if include_tbody:
        table_body = f"<tbody>{table_body}\n        </tbody>"

    return f"""
    <h4>Turmas Matriculadas: {len(rows)}</h4>
    <table id="matriculas">
        <thead>
            <tr>{headers}
            </tr>
        </thead>
        {table_body}
    </table>"""


def build_schedule_grid() -> str:
    # The real page ends with this grid, which the PDF path must skip.
    return """
    <h4>Tabela de Horários:</h4>
    <table id="horario">
        <tr>
            <td>Horários</td>
            <td>Dom</td><td>Seg</td><td>Ter</td><td>Qua</td>
            <td>Qui</td><td>Sex</td><td>Sab</td>
        </tr>
        <tr>
            <td>07:30 - 08:20</td>
            <td>---</td><td>---</td><td>---</td><td>---</td>
            <td>---</td><td>---</td><td>---</td>
        </tr>
    </table>"""


def build_atestado_html(
    rows: list[EnrollmentRow],
    *,
    period_label: str = "2026.2",
    period_start: str = "27/07/2026",
    period_end: str = "12/12/2026",
    period_value: str | None = None,
    student_id: str = "12345678",
    student_name: str = "TESTE DA SILVA",
    course: str = (
        "CIÊNCIA DA COMPUTAÇÃO - CAMPUS MACEIÓ - PRESENCIAL - Maceió - "
        "BACHARELADO - Regular - Semestral (13216) - M"
    ),
    labels: dict[str, str] | None = None,
    include_table: bool = True,
    include_tbody: bool = True,
    include_level: bool = True,
    renamed_headers: dict[str, str] | None = None,
    include_schedule_grid: bool = True,
) -> bytes:
    labels = labels or {}
    period_cell = (
        period_value
        if period_value is not None
        else f"""
                <strong>
                    {period_label}
                </strong>
                ({period_start} à {period_end})
            """
    )
    enrollments_table = (
        build_enrollments_table(
            rows,
            include_tbody=include_tbody,
            include_level=include_level,
            renamed_headers=renamed_headers,
        )
        if include_table
        else ""
    )
    schedule_grid = build_schedule_grid() if include_schedule_grid else ""

    # As in the real page: the period label spans two lines, and the Nível
    # and Vínculo cells set the width the name and course wrap within.
    html = f"""<html>
<head><style>{ATESTADO_CSS}</style></head>
<body>
    <table id="identificacao">
        <tr>
            <td>
                {labels.get("Período Letivo:", "Período\n                Letivo:")}
            </td>
            <td>{period_cell}</td>
            <td>Nível:</td>
            <td><strong>GRADUAÇÃO</strong></td>
        </tr>
        <tr>
            <td>{labels.get("Matrícula:", "Matrícula:")}</td>
            <td> <strong>{student_id}</strong></td>
            <td> Vínculo: </td>
            <td> <strong>REGULAR</strong> </td>
        </tr>
        <tr>
            <td>{labels.get("Nome:", "Nome:")} </td>
            <td colspan="3"><strong>{student_name}</strong></td>
        </tr>
        <tr>
            <td>{labels.get("Curso:", "Curso:")} </td>
            <td colspan="3"><strong> {course} </strong></td>
        </tr>
    </table>
    {enrollments_table}
    {schedule_grid}
</body>
</html>"""
    return html.encode("utf-8")


def build_atestado_pdf(
    rows: list[EnrollmentRow], **options: typing.Unpack[AtestadoOptions]
) -> bytes:
    # The real PDF is the browser's print of this same page, in A4.
    html = build_atestado_html(rows, **options).decode("utf-8")
    return render_pdf(html, width=595, height=842, margin=58)
