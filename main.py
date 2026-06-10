"""Main application entry point for the Smart Balance API."""

from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference, Theme, DocumentDownloadType

from application.controller import user_management_router
from application.controller import food_search_router

app = FastAPI(
    docs_url=None,  # Disable default Swagger UI
    redoc_url=None,  # Disable default ReDoc UI
    title="Smart Balance API",
    description="API for user management and food search functionalities in the Smart Balance application.",
)
app.include_router(user_management_router.router)
app.include_router(food_search_router.router)

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
