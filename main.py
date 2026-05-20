from fastapi import FastAPI
from application.routers import user_management_router

app = FastAPI()
app.include_router(user_management_router.router)

@app.get("/")
def read_root():
    return {
        "message": "API running",
        "routes": ["/users/create_User", "/users/get_User/{user_id}"]
    }