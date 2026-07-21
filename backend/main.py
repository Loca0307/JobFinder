from fastapi import FastAPI
from mangum import Mangum
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.routes.jobs import router as jobs_router
from api.settings.config import get_settings

load_dotenv()

app = FastAPI(title="Main app")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    # Due to lambda accepting only cloudfront origin
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(jobs_router)


handler = Mangum(app, lifespan="off")
