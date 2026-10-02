# Especificação

Este documento diz o que o `ufal-schedule-ics` deve fazer com cada formato de entrada e por quê. Ele é normativo: quando o código e este texto divergem, um dos dois está errado.

As regras têm IDs (`ROW-18`, `EV-06`…), e os testes citam as regras que verificam num comentário (`# ROW-18`). Os IDs são estáveis: o número de uma regra removida não é reaproveitado.

O documento deve descrever o comportamento sem citar nomes do código, exceto nas seções 1 e 5, que descrevem a estrutura do programa e dos testes.

## 1. Visão geral

```
bytes ─► extract_raw_record ─► RawRecord ─► normalize_raw_record ─► Record ─┬─► record_to_json
         ├─ HTML (atestado)    (strings                             (tipos  └─► build_calendar ─► .ics
         └─ PDF ┬─ atestado     cruas)                               finais)        └─ generate_events
                └─ SIE (comprovante) ─► SieRecord ─► convert_sie_record
```

O comprovante SIE é lido em duas etapas: a primeira lê o documento no modelo do próprio SIE (`SieRecord`), e a segunda o traduz para o do atestado (`RawRecord`), completando o que o comprovante não traz (SIE-02, SIE-10, SIE-11). A separação evita misturar os dois modelos durante a leitura do comprovante.

Contratos entre as etapas:

- **C1** Os extratores interpretam a estrutura do documento, mas não limpam os valores: cada campo sai com o texto da fonte, com espaços de preenchimento e quebras de linha embutidas. O HTML devolve ` COMP388 ` e o PDF devolve `COMP388`; só a normalização os iguala.
- **C2** A normalização não sabe de que formato veio o registro.
- **C3** Só matrículas `MATRICULADO` geram eventos.
- **C4** A saída depende só dos dados, exceto o `DTSTAMP` (EV-08): os UIDs de evento e de calendário são determinísticos, e o UID de evento não muda entre versões do programa (EV-06).

## 2. Formatos de entrada

### 2.1 Origem dos fatos

Os fatos desta seção foram observados em documentos reais: comprovantes SIE e atestados do SIGAA de vários períodos, em PDF (dos dois geradores da seção 2.4) e em HTML (o fonte do servidor e a página salva pelo navegador). Os documentos têm dados pessoais e não ficam no repositório; esta seção é o registro do que eles mostram.

O programa lê todos eles sem erro, e o mesmo atestado em PDF, em HTML-fonte e em HTML salvo produz o mesmo registro.

As regras indicam a base de cada uma:

| Base | Significado |
| --- | --- |
| **R** | Visto em pelo menos um documento real. |
| **P** | Plausível: não aparece nos documentos, mas o formato o produz para outros alunos, cursos ou turnos. |
| **V** | Validação: a entrada foge do formato conhecido e é rejeitada (seção 3). |

### 2.2 Atestado de matrícula (SIGAA)

É a página "Atestado de Matrícula" do portal do SIGAA, em HTML ou impressa em PDF.

**Identificação**
- `Período Letivo:` vale sempre `AAAA.S (dd/mm/aaaa à dd/mm/aaaa)`.
- A matrícula é numérica.
- O curso é longo (`CIÊNCIA DA COMPUTAÇÃO - CAMPUS MACEIÓ - … - M`); o nome do curso é o que vem antes do primeiro ` - `.
- Um nome de aluno longo quebra em duas linhas no PDF.

**Tabela de matrículas**
- As colunas são `Cód.`, `Componentes Curriculares/Docentes`, `Turma`, `Nível`, `Status` e `Horário`.
- A célula do componente tem o nome (em negrito), os docentes, `Tipo:` e `Local:`. `Local:` pode vir vazio.
- Vários docentes são separados por `, ` e por ` e ` minúsculo. Os docentes vêm sem acento (`JOSE`, `GONCALVES`); as disciplinas, com acento.
- Toda linha tem exatamente um código de horário. Só as atividades (ACE) têm intervalo de datas, sempre igual ao do período.
- O atestado mostra os status `MATRICULADO` e `INDEFERIDO`. A mesma disciplina e turma pode aparecer mais de uma vez, com status diferentes (por exemplo, duas `INDEFERIDO` e uma `MATRICULADO`).
- As turmas são `01` e `02`.
- O mesmo código aparece em períodos diferentes, quando uma disciplina é cursada de novo.
- O cabeçalho da tabela traz `Turmas Matriculadas: N` e, quando há atividades, `Atividades Matriculadas: M`.
- A página termina com uma grade semanal de horários (`#horario`), que o programa não lê.

### 2.3 Atestado em HTML

- As células vêm preenchidas com espaços: código (` COMP388 `), nome da disciplina, horário (`3T12 (…) `), matrícula (` 12345678`) e curso. Status, turma e nome do aluno vêm sem preenchimento. Um nome pode ter espaço duplo, como `ACE 4:  CONTINUAÇÃO DO PROJETO 2`.
- No HTML, o rótulo `Período Letivo:` e o valor ficam espalhados em várias linhas indentadas.
- O HTML-fonte do servidor escreve os acentos como entidades numéricas (`Per&#237;odo`). A página salva pelo navegador está em windows-1252, com `<meta charset>`.
- As linhas da tabela ficam num `<tbody>`, e o `<th>` de `Nível` está cercado da indentação típica de um bloco condicional do template.
- O NBSP (`&nbsp;`) aparece só na linha espaçadora da grade de horários, fora de qualquer campo lido.

### 2.4 Atestado em PDF

O PDF é a impressão da mesma página HTML. Há dois geradores:

| Gerador | Fontes |
| --- | --- |
| "Salvar como PDF" do Chrome | `Verdana`, `Verdana-Bold` |
| "Microsoft Print to PDF" | `CIDFont+F1`, `CIDFont+F2` |

- No "Microsoft Print to PDF", as minúsculas em `font-variant: small-caps` (o título, os cabeçalhos `h4` e o cabeçalho do portal) não têm texto recuperável. O gerador desenha glifos próprios (IDs 0x3FB–0x410) sem dizer a que caracteres eles correspondem, e o PyMuPDF usa o ID do glifo como caractere, o que produz letras de outros alfabetos no lugar das minúsculas. Maiúsculas, dígitos e pontuação saem certos. Rótulos, valores e tabela não usam small-caps.
- No mesmo gerador, o nome da fonte não diz se ela é negrito; o negrito só aparece no indicador de negrito que o PyMuPDF dá para cada trecho.
- Na célula do componente, os trechos são: nome em negrito, docentes, `Tipo:` em negrito, o tipo, `Local:` em negrito e o local.
- Há quebras de linha na lista de docentes, no nome de uma disciplina longa e no intervalo de datas, sempre logo depois do `-`.
- Um atestado pode ocupar duas páginas, mas a tabela cabe inteira na primeira. O limite de horas por período e o espaço da grade tornam improvável uma tabela maior.

### 2.5 Comprovante de matrícula (SIE)

É o documento do sistema anterior ao SIGAA. O formato está encerrado: só existem comprovantes de semestres anteriores à migração.

- A 1ª página traz `Departamento de Registro e Controle Acadêmico - DRCA`, que nenhum atestado tem.
- A identificação está em duas tabelas: `[período, matrícula, nome]`, com o período escrito `2023/1`, e `[curso, turno]`.
- O comprovante não traz as datas do período.
- A grade lista, dia a dia (`2 - Segunda-feira`, `3 - Terça-feira`…), cada aula de 50 minutos numa linha `CÓDIGO-TURMA NOME`, seguida da linha `hh:mm - hh:mm`. Só aparecem os dias com aula.
- Depois vêm as seções `Disciplinas Matriculadas` e `Professores`, ambas com o nome numa linha e o código completo (`COMP359-M`) na seguinte.
- As turmas são letras (`M`, `A`).
- Nenhum comprovante tem linhas vazias.

### 2.6 Horários

- A grade oficial tem os turnos M (6 aulas, a partir das 07:30), T (6 aulas, a partir das 13:30) e N (4 aulas, a partir das 19:00). Cada aula dura 50 minutos, com 10 minutos de intervalo a cada duas.
- Um código de horário é `<dias><turno><aulas>`: `35T34` é terça e quinta, da 3ª à 4ª aula da tarde. Os dias vão de 1 (domingo) a 7 (sábado).
- Nos documentos, os dias vão de 2 a 6 e as aulas, de M1 a M6 e de T1 a T6. Não há sábado, domingo nem turno noturno.
- Uma disciplina do SIE tem aula na terça e na quinta das 08:20 às 11:00 e na sexta das 07:30 às 09:10. É a única com mais de um código: `35M234` e `6M12`.
- Uma aula que atravessasse o almoço viria como dois códigos (`2M56 2T12`).
- Todos os períodos começam numa segunda-feira.
- O fim do período 2025.1 aparece como `19/11/2025`, e o programa o corrige para `28/11/2025`. A mesma data aparece no fim do intervalo da atividade COMP383.
- O calendário acadêmico chegou a ficar meses atrasado em relação ao ano civil (2024.2, por exemplo, foi todo em 2025). O atraso foi corrigido pulando o período 2025.2. Por isso o nome de um período não diz o ano das suas aulas, e um período pode atravessar o ano. Não se pode deduzir datas do nome: usar sempre as do documento ou, no SIE, as pré-definidas no programa.

## 3. Validação

O programa valida os formatos que lê. Uma mudança no SIGAA ou no SIE, ou uma variante ainda não vista, interrompe a execução com um erro que diz **o que** não foi reconhecido e **onde** (campo, coluna, linha). Ele nunca produz um registro parcial ou errado em silêncio. A mensagem chega ao usuário como traceback.

A validação é sobre o **formato**, não sobre o **conteúdo**:

- Um arquivo sem a estrutura esperada é rejeitado: outra página do portal, tabela ausente, coluna ou rótulo renomeado, notação diferente, status fora dos conhecidos (NORM-16). Isso protege contra o arquivo errado e contra mudanças de formato.
- Um arquivo com a estrutura certa e conteúdo vazio ou inútil é aceito: tabela sem linhas, só linhas `INDEFERIDO`, célula de horário vazia, docente vazio. O resultado é um registro ou calendário vazio, ou com o campo vazio.
- O conteúdo dos dados descartados de propósito não é validado: o tipo, o local e a coluna `Nível`. O rótulo `Tipo:` só é exigido no PDF, porque marca o fim do nome e dos docentes (ROW-13).

### 3.1 Limitações conhecidas

Riscos que ficam sem proteção:

| ID | Situação | Efeito | Por que não é tratado |
| --- | --- | --- | --- |
| ROW-17 | Tabela que continua na 2ª página do PDF. | As linhas da 2ª página se perdem. | Improvável, pelo limite de horas por período e pelo espaço da grade. |
| ROW-20 | Linhas do atestado que deixam de ser reconhecidas sem erro. | O registro sai com menos matrículas. | A conferência com `Turmas Matriculadas` não é possível: esse texto não é recuperável nos PDFs do "Microsoft Print to PDF" (2.4). Toda linha lida já é validada. |
| ROW-23 | Docentes impressos em negrito no PDF. | Os docentes entram no nome, e a matrícula fica sem docentes, sem erro. | No PDF, o nome e os docentes só se distinguem pelo negrito, e um único grupo em negrito é o caso de docente vazio (ROW-18). Tamanho da fonte e posição da linha também os separariam, mas exigiriam uma verificação a mais para uma mudança que nunca aconteceu. O HTML não é afetado: usa o elemento `.docente`. |
| SIE-15 | Cabeçalho de dia do comprovante numa notação nova. | Se todos os cabeçalhos mudarem, a grade inteira é ignorada como se fosse o cabeçalho do documento, e o registro sai sem matrículas, sem erro. | O formato SIE está encerrado. |

## 4. Regras

### 4.1 Entrada (`DISP`)

| ID | Regra | Base |
| --- | --- | --- |
| DISP-01 | Um arquivo que começa com `%PDF-` é lido como PDF; qualquer outro, como HTML. | R |
| DISP-02 | Um PDF cuja 1ª página contém `Departamento de Registro e Controle Acadêmico - DRCA` é lido como comprovante SIE; os demais, como atestado. Coberto pelos testes do SIE. | R |
| DISP-03 | O caminho `-` lê o arquivo da entrada padrão. | R |
| DISP-05 | O HTML é passado ao BeautifulSoup como **bytes**, para que a codificação declarada no `<meta charset>` da página salva pelo navegador seja respeitada. Sem teste: a decodificação é da biblioteca. | R |
| DISP-06 | Acentos em entidades numéricas, como no HTML-fonte do servidor, são convertidos pelo `html.parser`. Sem teste, pelo mesmo motivo. | R |

### 4.2 Atestado: identificação (`IDENT`)

HTML e PDF procuram os rótulos de jeitos diferentes, mas interpretam os valores com o mesmo código.

| ID | Regra | Base |
| --- | --- | --- |
| IDENT-01 | O período (nome, início e fim) vem de `Período Letivo:`, inclusive quando o rótulo HTML ocupa várias linhas. | R |
| IDENT-02 | A matrícula e o nome são o texto que segue o rótulo: a célula seguinte no HTML, ou até o próximo rótulo no PDF. | R |
| IDENT-03 | O curso é o texto antes do primeiro espaço-hífen-espaço. | R |
| IDENT-04 | Um hífen sem espaços faz parte do nome do curso (`LETRAS-LIBRAS`). | P |
| IDENT-07 | Um nome de aluno quebrado em duas linhas no PDF é lido inteiro. | R |
| IDENT-09 | Um curso sem o separador ` - ` é rejeitado (`course`). | V |
| IDENT-10 | Uma identificação ausente é rejeitada: HTML sem `#identificacao` (outra página do portal), rótulo ausente ou renomeado no HTML (`table cell for 'Matrícula:'`) ou no PDF (`'Matrícula:'`). | V |
| IDENT-12 | O valor de `Período Letivo:`, com os espaços normalizados, segue exatamente `AAAA.S (dd/mm/aaaa à dd/mm/aaaa)`; qualquer outro é rejeitado (`period`). Uma leitura mais tolerante transformaria `2026-2 (…)` no período `2`, que iria para o título e o UID de todos os eventos. | V |

### 4.3 Atestado: linhas de matrícula (`ROW`)

| ID | Regra | Base |
| --- | --- | --- |
| ROW-01 | Cada linha da tabela vira uma matrícula, na ordem, com código, nome, docentes, turma, status, horário e datas. | R |
| ROW-02 | O nome vem de `.componente` (HTML) ou do trecho em negrito antes dos docentes (PDF); os docentes, de `.docente` ou dos trechos regulares antes de `Tipo:`. `Tipo:` e `Local:` são descartados; o local frequentemente está desatualizado ou incompleto. | R |
| ROW-03 | Um nome de disciplina quebrado em várias linhas no PDF é juntado com espaço. | R |
| ROW-04 | Vários docentes ficam numa única string; a quebra de linha do PDF é juntada. | R |
| ROW-06 | Linhas repetidas (mesma disciplina e turma, status diferentes) são todas mantidas, cada uma com seu status cru. | R |
| ROW-07 | As colunas são localizadas pelo texto do cabeçalho, não pela posição, porque a coluna `Nível` parece condicional. | P |
| ROW-09 | A célula de horário é interpretada pelas regras `SCHED`. | R |
| ROW-10 | Uma coluna renomeada ou removida é rejeitada (`column '<nome>'`). | V |
| ROW-11 | Uma linha HTML com menos células que o cabeçalho é rejeitada (`all columns in row N`). | V |
| ROW-12 | Uma célula mesclada no PDF é rejeitada (`'<coluna>' in row N`, ou `component in row N` para a célula do componente). | V |
| ROW-13 | Uma célula de componente no PDF fora da forma "nome em negrito, docentes, `Tipo:`" é rejeitada (`name and professors in row N`): sem `Tipo:` ou sem o nome em negrito antes dos docentes. | V |
| ROW-14 | Uma página sem a tabela de matrículas é rejeitada: HTML sem `#matriculas`; PDF sem nenhuma tabela, ou cuja 1ª tabela é a grade de horários (`column 'Cód.'`). | V |
| ROW-16 | Um `Local:` vazio é aceito e não afeta o nome nem os docentes. | R |
| ROW-18 | Uma linha com o docente vazio é aceita, com o mesmo resultado nos dois formatos: nome correto e docentes vazios. A descrição do evento fica com `Professor: ` sem nome. | P |
| ROW-19 | Uma linha HTML sem o elemento `.componente` ou `.docente` é rejeitada com o seletor ausente. A falta do elemento é formato; o elemento vazio é conteúdo (ROW-18). | V |
| ROW-21 | Uma tabela de matrículas sem linhas é aceita e gera um registro sem matrículas. | P |
| ROW-22 | O `<tbody>` é obrigatório no HTML; uma `#matriculas` sem ele é rejeitada (`tbody`). Sem essa regra, a tabela sairia vazia em silêncio. | V |

### 4.4 Comprovante SIE (`SIE`)

| ID | Regra | Base |
| --- | --- | --- |
| SIE-01 | A identificação vem das duas tabelas: `[período, matrícula, nome]` e `[curso, turno]`. | R |
| SIE-02 | O período `AAAA/S` vira `AAAA.S`, com as datas pré-definidas no programa para cada período (2023.1 e 2023.2). | R |
| SIE-03 | Um período fora da tabela é rejeitado (`dates for period X`); comprovantes de outros semestres existem. | P, V |
| SIE-04 | Um período sem `/` é rejeitado (`year and semester`). | V |
| SIE-05 | Um nome de aluno quebrado em duas linhas é lido inteiro. | P |
| SIE-06 | Um comprovante com menos de duas tabelas é rejeitado (`tables`). | V |
| SIE-07 | Na grade, uma linha `N - Dia` abre um dia, e cada linha `CÓDIGO-TURMA NOME` é seguida da linha de horário. Linhas vazias não têm tratamento especial. | R |
| SIE-08 | O primeiro token se divide em código e turma no `-`; o resto da linha é o nome. | R |
| SIE-09 | O docente é encontrado pelo código completo na seção `Professores`. | R |
| SIE-10 | O status é sempre `MATRICULADO`, e não há datas por matrícula. | R |
| SIE-11 | A agenda de cada disciplina vira códigos de horário: cada horário vira uma aula pela grade oficial, as aulas seguidas de um dia se juntam, e os dias com o mesmo turno e as mesmas aulas compartilham um código. Os códigos saem na ordem em que os dias aparecem, que importa para o UID do calendário (CAL-07). A agenda de 2.6 com dois códigos dá `["35M234", "6M12"]`. | R |
| SIE-12 | Sábado é reconhecido como dia (`7 - Sábado`). Como só aparecem os dias com aula, uma linha de sábado logo depois das aulas de sexta precisa abrir um dia novo, e não ser lida como disciplina da sexta. | P |
| SIE-13 | A seção `Disciplinas Matriculadas` é ignorada. Coberto por todos os testes do SIE, porque a fixture a inclui. | R |
| SIE-14 | São rejeitados: rótulo de disciplina sem nome ou sem turma, disciplina cujo código não aparece em `Professores` (`professor for`) e texto que termina antes do horário ou do código esperado. | V |
| SIE-16 | Um comprovante sem disciplinas é aceito e gera um registro sem matrículas. | P |

### 4.5 Célula de horário (`SCHED`)

| ID | Regra | Base |
| --- | --- | --- |
| SCHED-01 | Um código sem intervalo dá o código, sem datas. | R |
| SCHED-02 | Um código seguido de ` (dd/mm/aaaa - dd/mm/aaaa)` dá o código e as duas datas. | R |
| SCHED-03 | O espaço final do HTML e a quebra depois do `-` no PDF não geram códigos vazios. | R |
| SCHED-04 | Vários códigos separados por espaço são aceitos (`2M56 2T12`). | P |
| SCHED-06 | Um texto fora desses formatos (sem espaços, vários intervalos, texto depois do intervalo) é dividido em palavras, sem datas, para que o código de horário o rejeite depois (TC-05), em vez de o excesso ser descartado. | V |
| SCHED-07 | Uma célula vazia não gera códigos; a matrícula fica sem eventos. | P |

### 4.6 Grade e códigos de horário (`TC`)

| ID | Regra | Base |
| --- | --- | --- |
| TC-01 | A grade é: M1–M6 das 07:30 às 12:50, T1–T6 das 13:30 às 18:50 e N1–N4 das 19:00 às 22:30, com aulas de 50 minutos e 10 minutos de intervalo a cada duas. A tabela inversa (horário → aula) é a mesma grade. | R (M, T), P (N) |
| TC-04 | Num código, os dígitos de dia vão de 1 (domingo) a 7 (sábado), na ordem em que aparecem; o horário vai do início da primeira aula ao fim da última. | R |
| TC-05 | São rejeitados: código fora da notação (inclusive dois turnos, como `2M56T12`), aulas não contíguas e aula que o turno não tem. | V |
| TC-06 | Aulas contíguas de um turno viram um código; dias com o mesmo turno e as mesmas aulas se juntam; o dígito vem do prefixo do dia. | R |
| TC-08 | Um horário fora da grade é rejeitado (`slot for`). | V |
| TC-09 | Expandir os códigos gerados recupera exatamente a agenda original, para as disciplinas de comprovantes inteiros. | R |

### 4.7 Normalização (`NORM`)

| ID | Regra | Base |
| --- | --- | --- |
| NORM-01 | Espaços, quebras de linha e tabs são colapsados, e as pontas aparadas. | R |
| NORM-03 | As datas são `dd/mm/aaaa`. | R |
| NORM-04 | As correções de data conhecidas (`19/11/2025` → `28/11/2025`) valem para toda data lida: as do período e as do intervalo de cada matrícula. | R |
| NORM-05 | Uma data em outra ordem (`2026/07/27`) ou inexistente (`31/02/2024`) é rejeitada. | V |
| NORM-08 | Nomes ficam em title case, com conectivos em minúsculas no meio e as palavras de uma lista pré-definida (siglas, numerais romanos, conectivos) na grafia da lista. A primeira palavra fica maiúscula mesmo sendo conectivo (`De Souza`). | R, P |
| NORM-09 | A grafia é corrigida por uma lista pré-definida de nomes, só nos docentes. A lista é de nomes de docentes, viável de manter; uma de alunos não seria. Os acentos são só visuais. | R |
| NORM-10 | A turma perde os zeros à esquerda (`01` → `1`); letras do SIE ficam como estão. | R |
| NORM-11 | Há vários docentes quando o texto tem `,` ou ` e ` minúsculo; um `E` maiúsculo dentro de um nome não conta. | R, P |
| NORM-12 | As datas de uma matrícula sem intervalo são as do período; um intervalo próprio prevalece. | R |
| NORM-13 | Os docentes ficam numa única string, com a grafia corrigida. | R |
| NORM-14 | A matrícula do aluno é aparada; nome e curso ficam em title case. | R |
| NORM-15 | O código é aparado, para que HTML e PDF gerem o mesmo UID; sem isso, importar um e depois o outro duplicaria os eventos. | R |
| NORM-16 | O status é `MATRICULADO` ou `INDEFERIDO`; qualquer outro, inclusive outra grafia de um desses, é rejeitado (`Unknown status`). Sem essa regra, uma grafia nova de `MATRICULADO` descartaria todas as matrículas e o calendário sairia vazio, sem erro. | V |
| NORM-17 | O mesmo atestado, em HTML ou em PDF, dá exatamente o mesmo registro normalizado. | R |

### 4.8 Eventos (`EV`)

| ID | Regra | Base |
| --- | --- | --- |
| EV-01 | Cada código de horário gera um evento recorrente; uma matrícula sem códigos não gera nenhum. | R |
| EV-02 | O título é `<nome> <período>`. | R |
| EV-03 | A descrição tem três linhas: `Código`, `Turma` e `Professor` ou `Professores`, conforme NORM-11, e não conforme o texto. | R |
| EV-04 | A primeira ocorrência cai no primeiro dia do código a partir do início da matrícula, do início da primeira aula ao fim da última. Cada código tem a sua. | R |
| EV-05 | Os horários são de parede no fuso escolhido: trocar o fuso muda o instante, não as 07:30. | R |
| EV-06 | O UID é um UUID v5, num namespace fixo do programa, de `período;código;turma;código-de-horário`, e não muda entre versões do programa; se mudasse, quem reimportasse o calendário teria os eventos duplicados. O período entra porque o mesmo código se repete em períodos diferentes. Uma mudança de horário gera um UID novo, e o evento antigo continua na agenda de quem reimportar: evitar isso exigiria conhecer os calendários anteriores. | R |
| EV-07 | A recorrência é semanal, nos dias do código, na ordem do código, até o último instante local da data final, expresso em UTC (RFC 5545). | R |
| EV-08 | O `DTSTAMP` de cada evento é o instante em que ele foi gerado, em UTC, como exige o RFC 5545. Ele indica quando o evento foi revisado pela última vez. É o único valor da saída que muda a cada execução. | R |

### 4.9 Calendário (`CAL`)

| ID | Regra | Base |
| --- | --- | --- |
| CAL-01 | Só matrículas `MATRICULADO` geram eventos; as `INDEFERIDO` são descartadas sem erro. | R |
| CAL-02 | Um código de horário inválido numa matrícula descartada tem comportamento indefinido: pode ou não ser rejeitado. Nenhum teste o fixa. | — |
| CAL-03 | Da mesma disciplina e turma repetida com status diferentes, só a linha `MATRICULADO` gera evento, e os UIDs não colidem. | R |
| CAL-04 | Sem matrículas `MATRICULADO`, o resultado é um calendário sem eventos, sem erro. | P |
| CAL-05 | A saída é iCalendar válido. | R |
| CAL-06 | O `VTIMEZONE` do fuso é incluído e referenciado pelos eventos. | R |
| CAL-07 | O UID do calendário depende só da lista de eventos, em ordem. | R |

### 4.10 Saída JSON (`JSON`)

| ID | Regra | Base |
| --- | --- | --- |
| JSON-01 | O objeto tem `period`, `student` e `enrollments`, com datas ISO. | R |
| JSON-02 | Caracteres não-ASCII saem sem escape. | R |

### 4.11 Linha de comando (`CLI`)

| ID | Regra | Base |
| --- | --- | --- |
| CLI-01 | O arquivo de entrada é obrigatório (saída 2). | R |
| CLI-02 | `-r`/`--print-record` imprime o registro em JSON; sem a opção, o calendário. | R |
| CLI-03 | `-t`/`--timezone` recebe um nome IANA, com padrão `America/Maceio`; um nome desconhecido é erro de uso (saída 2). | R |
| CLI-04 | O resultado vai para a saída padrão: o registro em JSON com `-r`, senão o calendário, no fuso escolhido. | R |

## 5. Testes

### 5.1 Convenções

- Cada teste cita as regras que verifica (`# ROW-18`). Um teste sem regra é sinal de regra faltando neste documento ou de teste sobrando. A exceção é `test_spec.py`, que verifica esta convenção: os IDs citados existem, e toda regra tem teste ou está entre as que este documento diz não ter.
- Além do ID, um teste só tem comentário se o valor esperado ou a montagem precisarem de explicação; o porquê da regra fica neste documento.
- Cada ponto do código que rejeita uma entrada tem um teste, que parte de uma fixture válida e aplica **uma** mudança plausível de formato. A mensagem é verificada pelo trecho que identifica o problema.
- O oráculo é independente da implementação: tabelas literais (a grade, o mapeamento de dias, os UIDs, o registro esperado), nunca a mesma fórmula recalculada.
- Os testes chamam as funções que ligam as etapas do fluxo da seção 1 (`extract_raw_record`, `normalize_raw_record`, `generate_events`, `build_calendar` e `main`), e não as auxiliares que elas usam por dentro. As funções de horário (`parse_schedule_and_dates`, `parse_time_code` e `schedule_to_time_codes`) também são chamadas diretamente, porque concentram as regras SCHED e TC. A exceção é o texto truncado do SIE (SIE-14), que não tem caminho pela fixture e usa `parse_sie_text`.
- Um cenário do atestado roda nos dois formatos: a fixture `build_atestado` do `conftest.py` parametriza o teste com o HTML e o PDF.
- Os testes de extração do atestado comparam os valores depois de `normalize_whitespace` (C1), porque o HTML e o PDF trazem espaços diferentes. A normalização do programa é verificada por NORM-17.
- Nenhum teste lê documentos reais. Um fato novo visto num documento real entra primeiro na seção 2 e depois numa fixture.

### 5.2 Fixtures

As fixtures ficam em `tests/atestado_fixtures.py` e `tests/comprovante_fixtures.py` e reproduzem os fatos da seção 2. Os detalhes de uso estão no próprio código.

Elas não usam dados pessoais reais (nomes, matrícula, histórico de matrículas) nem citam os documentos reais; os nomes de docentes são inventados, de tamanho parecido.

Diferenças conhecidas entre as fixtures e os documentos reais:

| Aspecto | Documento real | Fixture |
| --- | --- | --- |
| Codificação do HTML | entidades ou windows-1252 | UTF-8 literal (DISP-05) |
| Gerador do PDF | Chrome ou "Microsoft Print to PDF" | PyMuPDF: sem o small-caps sem texto e com "Bold" no nome da fonte. O negrito só nos flags não é exercitado. Se o programa deixar de reconhecê-lo, os PDFs reais falham com ROW-13, porque nenhum `Tipo:` em negrito é encontrado; se passar a ver negrito em tudo, os testes de extração falham, porque os docentes saem vazios. |
| Páginas | uma ou duas | sempre uma |

### 5.3 Cobertura

`uv run pytest --cov` exige 100% de cobertura de linhas e de ramos. Ficam de fora só as verificações de tipo contra o PyMuPDF (`raise TypeError`) e o `if __name__ == "__main__":`, declaradas em `exclude_also` no `pyproject.toml`. Para rodar um arquivo só com cobertura, o caminho vem antes do `--cov`; sozinho, ele fica abaixo do mínimo.
