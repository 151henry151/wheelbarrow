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

    # Game loop enqueues JSON via put_nowait; we send from this same task.
    # Inbound messages are pumped into in_q so we never cancel receive_json() mid-flight:
    # cancelling the old asyncio.wait "loser" could strand a decoded move before it was read.
    out_q: asyncio.Queue = asyncio.Queue()
    in_q: asyncio.Queue = asyncio.Queue()

    async def pump_incoming():
        try:
            while True:
                msg = await websocket.receive_json()
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

    pump_task = asyncio.create_task(pump_incoming())

    async def handle_input_safe(msg: dict) -> None:
        try:
            await engine.handle_input(player["id"], msg)
        except Exception:
            logging.exception("handle_input failed")
            try:
                await websocket.send_json({
                    "type": "notice",
                    "msg": "Server hit an error on that action — try again or refresh the page.",
                })
            except Exception:
                pass

    engine.add_socket(player["id"], websocket, out_q)

    try:
        while True:
            while True:
                try:
                    queued = out_q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                await websocket.send_json(queued)

            while True:
                try:
                    msg = in_q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if msg is None:
                    return
                await handle_input_safe(msg)
                await asyncio.sleep(0)

            out_task = asyncio.create_task(out_q.get())
            in_task = asyncio.create_task(in_q.get())
            _, pending = await asyncio.wait(
                {out_task, in_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p in pending:
                p.cancel()
            for p in pending:
                try:
                    await p
                except asyncio.CancelledError:
                    pass

            payload = None
            try:
                payload = out_task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logging.exception("wheelbarrow: outbound queue get failed")
                break

            if payload is not None:
                await websocket.send_json(payload)
                while True:
                    try:
                        p2 = out_q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    await websocket.send_json(p2)
                continue

            try:
                msg = in_task.result()
            except asyncio.CancelledError:
                continue
            if msg is None:
                break
            await handle_input_safe(msg)
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        try:
            await pump_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        await engine.remove_player(player["id"])


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="client", html=True), name="client")
