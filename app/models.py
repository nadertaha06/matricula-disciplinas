from sqlalchemy import String, Integer, JSON, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base, new_id


class Disciplina(Base):
    __tablename__ = 'disciplina'
    codigo: Mapped[str] = mapped_column(String(30), primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    pre_requisitos: Mapped[list] = mapped_column(JSON, default=list)


class Turma(Base):
    __tablename__ = 'turma'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    disciplina_codigo: Mapped[str] = mapped_column(ForeignKey('disciplina.codigo'))
    periodo: Mapped[str] = mapped_column(String(20), index=True)
    capacidade: Mapped[int] = mapped_column(Integer)
    horarios: Mapped[list] = mapped_column(JSON)


class Reserva(Base):
    __tablename__ = 'reserva_vaga'
    solicitacao_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    turma_id: Mapped[str] = mapped_column(ForeignKey('turma.id'), index=True)
    aluno_id: Mapped[str] = mapped_column(String(150), index=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
