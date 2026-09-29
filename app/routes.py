from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from app.db import session_scope
from app.events import emit
from app.models import Disciplina, Turma, Reserva
from app.schemas import DisciplinaInput, TurmaInput, ReservaInput, conflitam

router = APIRouter()


def turma_view(session, turma):
    disciplina = session.get(Disciplina, turma.disciplina_codigo)
    ocupadas = session.scalar(select(func.count()).select_from(Reserva).where(Reserva.turma_id == turma.id, Reserva.ativa.is_(True)))
    return {'id': turma.id, 'disciplina_codigo': turma.disciplina_codigo, 'periodo': turma.periodo,
            'capacidade': turma.capacidade, 'vagas_disponiveis': turma.capacidade - ocupadas,
            'horarios': turma.horarios, 'pre_requisitos': disciplina.pre_requisitos}


@router.post('/disciplinas', status_code=201)
def criar_disciplina(data: DisciplinaInput, session: Session = Depends(session_scope)):
    session.execute(text('SELECT pg_advisory_xact_lock(101)'))
    if session.get(Disciplina, data.codigo):
        raise HTTPException(409, 'Codigo ja cadastrado')
    if any(session.get(Disciplina, codigo) is None for codigo in data.pre_requisitos):
        raise HTTPException(404, 'Pre-requisito nao cadastrado')
    session.add(Disciplina(**data.model_dump()))
    session.commit()
    return data.model_dump()


@router.get('/disciplinas')
def listar_disciplinas(session: Session = Depends(session_scope)):
    return [{'codigo': d.codigo, 'nome': d.nome, 'pre_requisitos': d.pre_requisitos} for d in session.scalars(select(Disciplina).order_by(Disciplina.codigo))]


@router.post('/turmas', status_code=201)
def criar_turma(data: TurmaInput, session: Session = Depends(session_scope)):
    if session.get(Disciplina, data.disciplina_codigo) is None:
        raise HTTPException(404, 'Disciplina nao encontrada')
    turma = Turma(**data.model_dump())
    session.add(turma)
    session.commit()
    return turma_view(session, turma)


@router.get('/turmas')
def listar_turmas(periodo: str | None = None, session: Session = Depends(session_scope)):
    query = select(Turma).order_by(Turma.id)
    if periodo:
        query = query.where(Turma.periodo == periodo)
    return [turma_view(session, t) for t in session.scalars(query)]


@router.get('/turmas/{turma_id}')
def obter_turma(turma_id: str, session: Session = Depends(session_scope)):
    turma = session.get(Turma, turma_id)
    if turma is None:
        raise HTTPException(404, 'Turma nao encontrada')
    return turma_view(session, turma)


@router.post('/turmas/{turma_id}/reservas')
def reservar(turma_id: str, data: ReservaInput, session: Session = Depends(session_scope)):
    # Lock the student before the class: concurrent conflicting reservations cannot both pass.
    session.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:aluno, 0))'), {'aluno': data.aluno_id})
    turma = session.scalar(select(Turma).where(Turma.id == turma_id).with_for_update())
    if turma is None:
        raise HTTPException(404, 'Turma nao encontrada')
    existing = session.get(Reserva, data.solicitacao_id)
    if existing:
        if existing.turma_id != turma_id or existing.aluno_id != data.aluno_id:
            raise HTTPException(409, 'SOLICITACAO_DIVERGENTE')
        if not existing.ativa:
            raise HTTPException(409, 'RESERVA_CANCELADA')
        return {'solicitacao_id': existing.solicitacao_id, 'turma_id': turma_id, 'reservada': True}
    outras = session.scalars(select(Turma).join(Reserva).where(Reserva.aluno_id == data.aluno_id, Reserva.ativa.is_(True), Turma.periodo == turma.periodo))
    for outra in outras:
        if outra.disciplina_codigo == turma.disciplina_codigo:
            raise HTTPException(409, 'DISCIPLINA_JA_MATRICULADA')
        if conflitam(turma.horarios, outra.horarios):
            raise HTTPException(409, 'CHOQUE_HORARIO')
    if turma_view(session, turma)['vagas_disponiveis'] <= 0:
        raise HTTPException(409, 'SEM_VAGAS')
    session.add(Reserva(solicitacao_id=data.solicitacao_id, aluno_id=data.aluno_id, turma_id=turma_id))
    session.commit()
    return {'solicitacao_id': data.solicitacao_id, 'turma_id': turma_id, 'reservada': True}


@router.delete('/turmas/{turma_id}/reservas/{solicitacao_id}', status_code=204)
def liberar(turma_id: str, solicitacao_id: str, session: Session = Depends(session_scope)):
    turma = session.scalar(select(Turma).where(Turma.id == turma_id).with_for_update())
    if turma is None:
        raise HTTPException(404, 'Turma nao encontrada')
    reserva = session.get(Reserva, solicitacao_id)
    if reserva and reserva.turma_id != turma_id:
        raise HTTPException(409, 'SOLICITACAO_DIVERGENTE')
    if reserva and reserva.ativa:
        reserva.ativa = False
        emit(session, 'vaga.liberada', {'turma_id': turma_id, 'solicitacao_id': solicitacao_id})
        session.commit()
    return Response(status_code=204)
