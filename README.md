# ufal-schedule-ics

Converte um horário de aulas da UFAL (exportado do SIGAA) em um arquivo `.ics`, que pode ser importado em qualquer aplicativo de calendário.

Recebe como entrada um PDF ou uma página HTML do "Atestado de Matrícula" emitido pelo SIGAA.

## Requisitos

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (recomendado) ou `pip`

## Instalação

Com o [uv](https://docs.astral.sh/uv/):

```sh
uv sync
```

## Uso

### Com uv

Execute o script diretamente. Não é preciso instalar nada à parte, pois o `uv` resolve as dependências automaticamente a partir dos metadados incluídos no próprio script:

```sh
uv run src/ufal_schedule_ics.py <arquivo_de_entrada> > schedule.ics
```

Ou, após rodar `uv sync`, usando o comando instalado:

```sh
uv run ufal-schedule-ics <arquivo_de_entrada> > schedule.ics
```

### Entrada

- `<arquivo_de_entrada>` pode ser um arquivo PDF ou HTML exportado do SIGAA.
- Use `-` para ler a partir da entrada padrão:

```sh
uv run ufal-schedule-ics - < atestado.pdf > schedule.ics
```

### Saída

Por padrão, o calendário (`.ics`) é escrito na saída padrão. Redirecione-o para um arquivo, como no exemplo acima, e depois importe esse arquivo no seu aplicativo de calendário.

Os horários das aulas são gravados no fuso `America/Maceio`, então aparecem corretamente mesmo em um aparelho configurado em outro fuso. Para usar outro fuso, passe um nome IANA com `-t`/`--timezone`:

```sh
uv run ufal-schedule-ics --timezone America/Recife <arquivo_de_entrada> > schedule.ics
```

Para conferir os dados identificados em vez de gerar um calendário, use `-r`/`--print-record`, que imprime um único objeto JSON com o período letivo (`period`), os dados do aluno (`student`) e a lista de matrículas (`enrollments`):

```sh
uv run ufal-schedule-ics --print-record <arquivo_de_entrada>
```

## Desenvolvimento

O comportamento esperado do programa está descrito em [docs/especificacao.md](docs/especificacao.md): os formatos de entrada, a política de validação e as regras, cada uma com um ID que os testes citam.

Para rodar os testes com a verificação de cobertura, que exige 100% de linhas e de ramos:

```sh
uv run pytest --cov
```
