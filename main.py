"""Main application entry point for the Smart Balance API."""

from fastapi import FastAPI
from application.routers import user_management_router
from application.routers import food_search_router

app = FastAPI()
app.include_router(user_management_router.router)
app.include_router(food_search_router.router)

@app.get("/")
def read_root():
    """Root endpoint providing basic information about the API."""
    return {
        "message": "API running",
        "routes": ["/users/create_User", "/users/get_User/{user_id}"]
    }
