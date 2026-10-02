import pytest
from atestado_fixtures import BuildAtestado, build_atestado_html, build_atestado_pdf


@pytest.fixture(params=[build_atestado_html, build_atestado_pdf], ids=["html", "pdf"])
def build_atestado(request: pytest.FixtureRequest) -> BuildAtestado:
    return request.param
