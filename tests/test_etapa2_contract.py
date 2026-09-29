from fastapi.testclient import TestClient
from app.main import app


def test_catalogo_aceita_disciplina():
    response = TestClient(app).post('/disciplinas', json={'codigo': 'MAT101', 'nome': 'Calculo', 'pre_requisitos': []})
    assert response.status_code == 201
