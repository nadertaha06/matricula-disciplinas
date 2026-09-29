from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Codigo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
Hora = Annotated[str, Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')]


class DisciplinaInput(BaseModel):
    codigo: Codigo
    nome: Texto
    pre_requisitos: list[Codigo] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def validar(self):
        if self.codigo in self.pre_requisitos or len(set(self.pre_requisitos)) != len(self.pre_requisitos):
            raise ValueError('Pre-requisitos duplicados ou referencia a propria disciplina')
        return self


class Horario(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    inicio: Hora
    fim: Hora

    @model_validator(mode='after')
    def validar(self):
        if self.inicio >= self.fim:
            raise ValueError('Inicio deve ser anterior ao fim')
        return self


def conflitam(a, b):
    return any(x['dia_semana'] == y['dia_semana'] and x['inicio'] < y['fim'] and y['inicio'] < x['fim'] for x in a for y in b)


class TurmaInput(BaseModel):
    disciplina_codigo: Codigo
    periodo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    capacidade: int = Field(ge=1, le=10000)
    horarios: list[Horario] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def validar(self):
        horarios = [h.model_dump() for h in self.horarios]
        if any(conflitam([h], horarios[i+1:]) for i, h in enumerate(horarios)):
            raise ValueError('Horarios da propria turma se sobrepoem')
        return self


class ReservaInput(BaseModel):
    solicitacao_id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    aluno_id: Texto
