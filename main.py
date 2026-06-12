"""Main application entry point for the Smart Balance API."""

from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request
from scalar_fastapi import get_scalar_api_reference, Theme, DocumentDownloadType

from application.controller import user_controller, food_controller
from application.models.return_models import ReturnException

app = FastAPI(
    docs_url=None,  # Disable default Swagger UI
    redoc_url=None,  # Disable default ReDoc UI
    title="Smart Balance API",
    description="API for user management and food search functionalities in the Smart Balance application.",
)
app.include_router(user_controller.router)
app.include_router(food_controller.router)

@app.exception_handler(ReturnException)
async def return_exception_handler(request: Request, exc: ReturnException):
    """Custom exception handler for ReturnException, returning a standardized JSON response."""

    # Monta o corpo da resposta com os campos da sua dataclass
    response_body = {"success": exc.success, "message": exc.message, "data": exc.data, "status_code": exc.status_code, "url": str(request.url)}

    # Inclui o campo data apenas se ele foi preenchido
    if exc.data is not None:
        response_body["data"] = exc.data

    return JSONResponse(status_code=exc.status_code, content=response_body)

@app.get("/docs", include_in_schema=False)
async def scalar_html():
    """Endpoint to serve the Scalar API reference documentation."""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Smart Balance API",
        dark_mode=True,                 # Habilita o modo escuro por padrão

        # Tema
        theme=Theme.DEFAULT,           # Theme.DEFAULT ou Theme.NONE
        force_dark_mode_state="dark",  # força "dark" ou "light"
        hide_dark_mode_toggle=False,   # esconde o botão de alternar tema

        # Fontes e CSS
        with_default_fonts=True,       # usa Inter + JetBrains Mono
        custom_css=".scalar-app { --scalar-color-accent: #7c3aed; }",

        # Download do schema
        document_download_type=DocumentDownloadType.BOTH,  # JSON, YAML, BOTH ou NONE

        # Ordenação de propriedades
        order_required_properties_first=True,
        order_schema_properties_by="alpha",  # "alpha" ou "preserve"

        # Servidor base
        base_server_url="https://api.meusite.com",

        # Botões da sidebar
        hide_client_button=False,  # esconde o botão de gerar código cliente
    )

@app.get("/")
def read_root():
    """Root endpoint providing basic information about the API."""
    return {
        "message": "API running",
        "routes": ["/users/create_User", "/users/get_User/{user_id}"]
    }


# Exemplo de como usar o query parameters

# from fastapi import Depends
# from typing import Annotated
# from pydantic import BaseModel, Field

# class FilterParams(BaseModel):
#     limit: int = Field(100, gt=0, le=100)
#     offset: int = Field(0, ge=0)
#     order_by: str = "id"

# @app.get("/v1/items/")
# async def get_all_items(params: Annotated[FilterParams, Depends()]):
#     """Retrieve items using query parameters described by FilterParams.

#     Using Depends() here lets FastAPI populate the Pydantic model from query
#     parameters. `params` is a FilterParams instance, so access attributes
#     directly or call `model_dump()` to return a dict.
#     """
#     # return a dict of the parsed parameters
#     return params.offset
