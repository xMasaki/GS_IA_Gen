from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..schemas import Health

router = APIRouter(tags=["Saúde"])


@router.get("/health", response_model=Health, summary="Saúde da aplicação",
            responses={503: {"model": Health, "description": "Banco de dados indisponível"}})
def health(request: Request):
    st = request.app.state
    banco_ok = st.db.ping()
    corpo = {
        "status": "ok" if banco_ok else "degradado",
        "versao": st.settings.versao,
        "ambiente": st.settings.app_env,
        "componentes": {
            "banco": "ok" if banco_ok else "erro",
            "visao": "ok" if st.servicos.visao.disponivel else "indisponivel",
            "assistente": st.servicos.assistente.modo,
        },
    }
    return JSONResponse(corpo, status_code=200 if banco_ok else 503)
