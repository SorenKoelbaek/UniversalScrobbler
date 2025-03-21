from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers import (auth_router)
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Serve the React app
app.mount("/ui", StaticFiles(directory="../ui/build", html=True), name="ui")

@app.get("/api")
async def read_api():
    return {"message": "Hello, API with Poetry and React!"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)