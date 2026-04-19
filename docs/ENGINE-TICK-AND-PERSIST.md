# Wheelbarrow server: `tick()` must not block on DB persist

## Symptom

Players report the wheelbarrow **cannot move** (or movement **freezes for seconds** on a regular interval). WebSocket input may appear ignored; the issue is often misattributed to message queues or `start_collect` spam.

## Actual cause

`GameEngine.tick()` runs on the **asyncio event loop**. If persist (saving all players, nodes, structures, towns to MariaDB) runs **inline** inside `tick()` as a series of `await queries.save_*` calls **without** yielding for long stretches, the event loop is **blocked for ~1–5+ seconds per persist cycle**.

While the loop is stuck in DB I/O:

- `integrate_player_movement` does not run on schedule.
- WebSocket `move` handling and tick broadcasts stall.
- The game looks like “no movement” or periodic freezes **aligned with `persist_interval_s`** (default 10s).

This is **not** primarily fixed by reordering WebSocket `move_q` vs `in_q` (though that can help a different class of input lag). The **durable** fix is **never** running full-world persist synchronously on the hot path of `tick()`.

## Correct pattern (required)

1. **`_do_persist()`** — async method that iterates players / nodes / structures / towns and awaits DB writes.
2. **`asyncio.create_task(self._do_persist())`** — schedule persist from `tick()` when the persist interval elapses.
3. **Guard** — e.g. `self._persist_task` set to `None` or checked with `.done()`; if a persist is still running, **skip** starting another (log a warning). Prevents overlapping persists.
4. **Iterate copies** — `list(self.players.values())` etc., so mutations during await do not corrupt iterators.
5. **Exceptions** — wrap body in try/except and `logging.exception` so a failed persist does not kill the task silently in a bad way.

## History (do not revert)

| Commit    | What happened |
|-----------|----------------|
| `39fe5d7` | **Fix movement freeze:** introduce background-task persist (`create_task` + `_do_persist`). |
| `50596b6` | Fix `NameError` in `_do_persist` (logging). |
| v0.12.71  | **Regression:** background persist removed; persist ran **inside** `tick()` again → freeze **reintroduced**. |
| `8b37e22` (v0.12.73) | **Restore** background `_do_persist` + `_persist_task` guard. |

## Agent / developer checklist

When editing `server/game/engine.py` around **`tick`**, **`_do_persist`**, or **persistence**:

- [ ] Persist is **not** a long synchronous block in `tick()` without a background task.
- [ ] If you add new await-heavy work on every tick, consider **background tasks** or **chunking** + `await asyncio.sleep(0)` so the loop stays responsive.

## Related files

- `server/game/engine.py` — `tick`, `_do_persist`, `_persist_task`
- `server/config.py` — `persist_interval_s`
