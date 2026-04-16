from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Wheelbarrow MMO")

app.mount("/", StaticFiles(directory="client", html=True), name="client")
