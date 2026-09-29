from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_engine
from app.events import Outbox
from app.schemas import conflitam

pytestmark = pytest.mark.integration


def turma(client, codigo='CAL', capacidade=1, inicio='08:00', fim='10:00', periodo='2026-2'):
    client.post('/disciplinas', json={'codigo': codigo, 'nome': codigo})
    r = client.post('/turmas', json={'disciplina_codigo': codigo, 'capacidade': capacidade, 'periodo': periodo,
        'horarios': [{'dia_semana': 0, 'inicio': inicio, 'fim': fim}]})
    assert r.status_code == 201
    return r.json()['id']


def reservar(client, tid, sid='s1', aluno='a1'):
    return client.post(f'/turmas/{tid}/reservas', json={'solicitacao_id': sid, 'aluno_id': aluno})


def test_catalogo_filtro_e_pre_requisitos(client):
    assert client.post('/disciplinas', json={'codigo':'B','nome':'B','pre_requisitos':['A']}).status_code == 404
    turma(client, 'A')
    assert client.post('/disciplinas', json={'codigo':'B','nome':'B','pre_requisitos':['A']}).status_code == 201
    assert len(client.get('/disciplinas').json()) == 2
    assert len(client.get('/turmas?periodo=2026-2').json()) == 1
    assert client.get('/turmas?periodo=2027-1').json() == []
    assert len(client.get('/turmas').json()) == 1
    assert client.post('/disciplinas', json={'codigo':'A','nome':'A'}).status_code == 409


@pytest.mark.parametrize('payload', [
    {'codigo':'','nome':'A'}, {'codigo':'A','nome':' '},
    {'codigo':'A','nome':'A','pre_requisitos':['A']},
    {'codigo':'A','nome':'A','pre_requisitos':['B','B']},
])
def test_disciplina_invalida(client, payload):
    assert client.post('/disciplinas', json=payload).status_code == 422


@pytest.mark.parametrize('horarios', [[], [{'dia_semana':7,'inicio':'08:00','fim':'09:00'}],
    [{'dia_semana':0,'inicio':'25:00','fim':'09:00'}],
    [{'dia_semana':0,'inicio':'09:00','fim':'09:00'}],
    [{'dia_semana':0,'inicio':'10:00','fim':'09:00'}],
    [{'dia_semana':0,'inicio':'08:00','fim':'10:00'}, {'dia_semana':0,'inicio':'09:00','fim':'11:00'}]])
def test_horarios_invalidos(client, horarios):
    assert client.post('/turmas', json={'disciplina_codigo':'A','capacidade':1,'periodo':'2026-2','horarios':horarios}).status_code == 422


def test_reserva_idempotente_capacidade_e_liberacao(client):
    tid = turma(client)
    assert reservar(client, tid).status_code == 200
    assert reservar(client, tid).status_code == 200
    assert client.get(f'/turmas/{tid}').json()['vagas_disponiveis'] == 0
    assert reservar(client, tid, 's2', 'a2').json()['detail'] == 'SEM_VAGAS'
    assert reservar(client, tid, 's1', 'a2').json()['detail'] == 'SOLICITACAO_DIVERGENTE'
    assert client.delete(f'/turmas/{tid}/reservas/s1').status_code == 204
    assert client.delete(f'/turmas/{tid}/reservas/s1').status_code == 204
    assert reservar(client, tid).json()['detail'] == 'RESERVA_CANCELADA'
    assert client.get(f'/turmas/{tid}').json()['vagas_disponiveis'] == 1
    with Session(get_engine()) as session:
        events = list(session.scalars(select(Outbox)))
        assert len(events) == 1
        assert events[0].topic == 'vaga.liberada'


def test_conflitos_sao_limitados_ao_periodo(client):
    a = turma(client, 'A', capacidade=2)
    b = turma(client, 'B')
    c = turma(client, 'C', inicio='10:00', fim='12:00')
    d = turma(client, 'D', periodo='2027-1')
    assert reservar(client, a).status_code == 200
    assert reservar(client, a, 's2').json()['detail'] == 'DISCIPLINA_JA_MATRICULADA'
    assert reservar(client, b, 's3').json()['detail'] == 'CHOQUE_HORARIO'
    assert reservar(client, c, 's4').status_code == 200
    assert reservar(client, d, 's5').status_code == 200
    assert client.delete(f'/turmas/{b}/reservas/s1').status_code == 409


def test_ultima_vaga_em_concorrencia(client):
    tid = turma(client)
    with ThreadPoolExecutor(max_workers=5) as pool:
        codes = list(pool.map(lambda n: reservar(client, tid, f's{n}', f'a{n}').status_code, range(5)))
    assert codes.count(200) == 1
    assert codes.count(409) == 4
    assert client.get(f'/turmas/{tid}').json()['vagas_disponiveis'] == 0


def test_mesmo_aluno_nao_reserva_horarios_concorrentes(client):
    tids = [turma(client, 'A'), turma(client, 'B')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda n: reservar(client, tids[n], f's{n}').status_code, range(2)))
    assert sorted(codes) == [200, 409]


def test_nao_encontrados(client):
    assert client.get('/turmas/inexistente').status_code == 404
    assert reservar(client, 'inexistente').status_code == 404
    assert client.delete('/turmas/inexistente/reservas/s1').status_code == 404
    assert client.post('/turmas', json={'disciplina_codigo':'X','capacidade':1,'periodo':'2026',
        'horarios':[{'dia_semana':0,'inicio':'08:00','fim':'10:00'}]}).status_code == 404


@pytest.mark.unit
def test_intervalos_adjacentes_nao_conflitam():
    a = [{'dia_semana':0,'inicio':'08:00','fim':'10:00'}]
    assert not conflitam(a, [{'dia_semana':0,'inicio':'10:00','fim':'12:00'}])
    assert not conflitam(a, [{'dia_semana':1,'inicio':'08:00','fim':'10:00'}])
    assert conflitam(a, [{'dia_semana':0,'inicio':'09:00','fim':'12:00'}])
