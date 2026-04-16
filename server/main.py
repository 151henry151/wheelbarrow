import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.db.connection import close_pool
from server.db import queries
from server.game.engine import engine
from server.game.tick import run_game_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    await engine.load()
    asyncio.create_task(run_game_loop())
    yield
    await close_pool()


app = FastAPI(title="Wheelbarrow MMO", lifespan=lifespan)


# ---------------------------------------------------------------------------
# REST — login / session
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str

@app.post("/api/login")
async def login(req: LoginRequest):
    username = req.username.strip()
    if not username or len(username) > 32:
        raise HTTPException(400, "Invalid username")
    player = await queries.get_or_create_player(username)
    token = engine.create_session(player)
    return JSONResponse({"token": token, "player_id": player["id"]})


# ---------------------------------------------------------------------------
# WebSocket — game connection
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    player = engine.get_player_by_token(token)
    if not player:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    engine.add_socket(player["id"], websocket)

    try:
        await websocket.send_json(engine.full_state(player["id"]))
        while True:
            msg = await websocket.receive_json()
            await engine.handle_input(player["id"], msg)
    except WebSocketDisconnect:
        pass
    finally:
        await engine.remove_player(player["id"])


# ---------------------------------------------------------------------------
# Static — serve the client
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="client", html=True), name="client")
