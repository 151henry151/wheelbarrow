import asyncio
import logging
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
# REST
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
async def login(req: LoginRequest):
    username = req.username.strip()
    if not username or len(username) > 32:
        raise HTTPException(400, "Username must be 1–32 characters.")
    if not req.password:
        raise HTTPException(400, "Password is required.")

    player = await queries.login_or_register(username, req.password)
    if player is None:
        raise HTTPException(401, "Incorrect password.")

    token = engine.create_session(player)
    return JSONResponse({"token": token})


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    player = engine.get_player_by_token(token)
    if not player:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    try:
        await websocket.send_json(engine.full_state(player["id"]))
    except Exception:
        logging.exception("wheelbarrow: initial websocket send failed")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
        return

    # out_q: game loop + error notices — drained only by pump_outgoing (single sender task).
    # in_q: non-move client messages. move_q: latest move only (maxsize=1, replace on overflow)
    # so ~60/s rAF move frames cannot build an unbounded asyncio.Queue backlog on the server.
    out_q: asyncio.Queue = asyncio.Queue()
    in_q: asyncio.Queue = asyncio.Queue()
    move_q: asyncio.Queue = asyncio.Queue(maxsize=1)

    def _put_latest_move(msg: dict) -> None:
        try:
            move_q.put_nowait(msg)
        except asyncio.QueueFull:
            try:
                move_q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                move_q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def pump_incoming():
        try:
            while True:
                msg = await websocket.receive_json()
                if msg.get("type") == "move":
                    _put_latest_move(msg)
                else:
                    await in_q.put(msg)
        except WebSocketDisconnect:
            pass
        except Exception:
            logging.exception("wheelbarrow: websocket receive failed")
        finally:
            try:
                await in_q.put(None)
            except Exception:
                pass

    async def pump_outgoing():
        try:
            while True:
                payload = await out_q.get()
                await websocket.send_json(payload)
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            pass
        except Exception:
            logging.exception("wheelbarrow: websocket outbound send failed")

    pump_in_task = asyncio.create_task(pump_incoming())
    pump_out_task = asyncio.create_task(pump_outgoing())

    async def handle_input_safe(msg: dict) -> None:
        try:
            await engine.handle_input(player["id"], msg)
        except Exception:
            logging.exception("handle_input failed")
            try:
                await out_q.put({
                    "type": "notice",
                    "msg": "Server hit an error on that action — try again or refresh the page.",
                })
            except Exception:
                pass

    engine.add_socket(player["id"], websocket, out_q)

    try:
        while True:
            t_move = asyncio.create_task(move_q.get())
            t_in = asyncio.create_task(in_q.get())
            done, pending = await asyncio.wait(
                {t_move, t_in},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p in pending:
                p.cancel()
                try:
                    await p
                except asyncio.CancelledError:
                    pass
            if t_move in done:
                msg = t_move.result()
                await handle_input_safe(msg)
            else:
                msg = t_in.result()
                if msg is None:
                    break
                await handle_input_safe(msg)
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        pass
    finally:
        pump_in_task.cancel()
        pump_out_task.cancel()
        for t in (pump_in_task, pump_out_task):
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        await engine.remove_player(player["id"])


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="client", html=True), name="client")
