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

    # Game loop enqueues JSON via put_nowait; we send from this same task so send/receive obey
    # ASGI websocket expectations. Multiplex with asyncio.wait so we never block only on receive
    # while ticks pile up (separate outbound task can deadlock with receive on some servers).
    out_q: asyncio.Queue = asyncio.Queue()

    engine.add_socket(player["id"], websocket, out_q)

    try:
        while True:
            # If receive_json and out_q.get() both complete in the same turn, FIRST_COMPLETED
            # can pick receive every time while ticks stay queued — client move spam then starves
            # tick delivery. Flush any queued server→client payloads before waiting on input.
            while True:
                try:
                    queued = out_q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                await websocket.send_json(queued)

            out_task = asyncio.create_task(out_q.get())
            in_task = asyncio.create_task(websocket.receive_json())
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
                # If both out_task and in_task completed in the same loop turn, only one
                # "wins" asyncio.wait; process the inbound move so it is not dropped.
                if in_task.done():
                    _disconnect = False
                    try:
                        msg2 = in_task.result()
                    except asyncio.CancelledError:
                        pass
                    except WebSocketDisconnect:
                        _disconnect = True
                    except Exception:
                        pass
                    else:
                        try:
                            await engine.handle_input(player["id"], msg2)
                        except Exception:
                            logging.exception("handle_input failed")
                            try:
                                await websocket.send_json({
                                    "type": "notice",
                                    "msg": "Server hit an error on that action — try again or refresh the page.",
                                })
                            except Exception:
                                pass
                        await asyncio.sleep(0)
                    if _disconnect:
                        break
                continue

            try:
                msg = in_task.result()
            except asyncio.CancelledError:
                continue
            except WebSocketDisconnect:
                break
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
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        pass
    finally:
        await engine.remove_player(player["id"])


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="client", html=True), name="client")
