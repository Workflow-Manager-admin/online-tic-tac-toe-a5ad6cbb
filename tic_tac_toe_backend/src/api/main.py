from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router

app = FastAPI(
    title="Tic Tac Toe Backend",
    description="API backend for a simple online Tic Tac Toe game.",
    version="0.1.0",
    openapi_tags=[
        {"name": "Game", "description": "Game creation, moves, and listing endpoints."},
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Main API router for all core endpoints
app.include_router(router)

@app.get("/", tags=["General"])
def health_check():
    """Health Check endpoint for backend"""
    return {"message": "Healthy"}
