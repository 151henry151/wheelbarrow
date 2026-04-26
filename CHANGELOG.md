# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.12.88] - 2026-04-16

### Added
- **Repository** (`LICENSE`): License the project under **GNU GPL version 3** (full license text).
- **Documentation** (`README.md`): Add **License** section pointing to **`LICENSE`**.
- **Packaging** (`pyproject.toml`): Declare **`readme`**, SPDX **`GPL-3.0-only`**, and **`license`** metadata.

### Changed
- **Client** (`client/index.html`): Bump cache-bust query strings to **0.12.88**.

## [0.12.87] - 2026-04-16

### Added
- **Client** (`client/js/game.js`, `client/index.html`, `client/css/style.css`): **Silo menu** — **[E]** on or next to your silo shows stored contents (via **`silo_inventory`** / **`silo_wheat`**), **[1]** load withdrawable resources (wheat today), **[N]** / button **sell all wheat** autopilot (silo ↔ NPC market).
- **Server** (`server/game/engine.py`): **`silo_inventory`** on node wire for extensible multi-type display.
- **Server** (`server/game/ids.py`): **`ids_equal`** helper for id comparisons without pulling in **`engine`**.
- **Tests** (`tests/test_ids_equal.py`): Cover **`ids_equal`** coercion and **`None`** handling.

### Fixed
- **Server** (`server/game/engine.py`, `server/game/ids.py`): Use **`ids_equal`** for silo **withdraw** and **unload** ownership checks so DB/JSON **`owner_id`** types match **`player_id`**.

## [0.12.86] - 2026-04-24

### Fixed
- **Client** (`client/js/renderer.js`): Draw owned-tile highlight using **`floor(player.x/y)`** (same as server **`standing_parcel`**), not smoothed **`rx`/`ry`**; treat as owned when **`world_parcels`** row for **`standing_parcel.id`** matches **id** even if nested **`owner_id`** is wrong.
- **Client** (`client/js/game.js`): Derive **`isOwn`** / buy / land hints from **`world_parcels`** row looked up by **`standing_parcel.id`** first, then **`standing_parcel.owner_id`**, then bbox fallback — restores **[F]** till/plant hints when wire **`owner_id`** and row disagree.

## [0.12.85] - 2026-04-24

### Added
- **Server** (`server/game/engine.py`): **`standing_parcel`** on **`_player_wire`** — **`parcel_at`** tile under the player (same as **`_farm`**).

### Fixed
- **Client** (`client/js/game.js`, `client/js/renderer.js`): Prefer **`standing_parcel`** for HUD ownership, till/plant hints, and owned-tile highlight; merge full row from **`world_parcels`** by id so UI matches server when parcel bbox list order disagrees with **`parcel_at`**.

## [0.12.84] - 2026-04-24

### Fixed
- **Server** (`server/game/engine.py`): Add **`_ids_equal`** for **`_farm`** parcel ownership; coerce **`player_id`** with **`int()`** at **`handle_input`** entry (covers str vs int from the WebSocket path).
- **Client** (`client/js/renderer.js`): Use **`_samePlayerId`** for owned-parcel tint and **`_ownedTileHighlight`**; use **floored tile** (**`ptx`/`pty`**) for parcel overlay “current parcel” tests (align with **`player_tile_xy`**).

## [0.12.83] - 2026-04-24

### Fixed
- **Server** (`server/game/engine.py`): Coerce **`world_parcels`** **`owner_id`** and session **`player["id"]`** to **`int`** after load/login so **`_farm`** ownership checks match the DB.
- **Client** (`client/js/game.js`): Resolve parcel at **integer tile** (**`_parcelAt(tx, ty)`**) for HUD (was float **`p.x`/`p.y`**, diverging from **`parcel_at`** / **`player_tile_xy`**); add **`_sameOwnerId`** for **`owner_id`** vs **`p.id`** comparisons (string vs number from JSON).

## [0.12.82] - 2026-04-19

### Fixed
- **Server** (`server/game/engine.py`): Restore **`_persist_task`** / **`_do_persist()`** — **v0.12.81** had inlined **`await queries.save_*`** in **`tick()`**, blocking the asyncio loop on each **`persist_interval_s`** and freezing movement (same class as **v0.12.71** / **v0.12.76**; see **`docs/ENGINE-TICK-AND-PERSIST.md`**).

## [0.12.81] - 2026-04-19

### Changed
- **Wheat** (`server/game/constants.py`, `server/game/engine.py`): Set harvest **yield** from **fertilizer type** — **5** / **6** / **8** / **10** units for none / manure / compost / store fertilizer (`_crop_harvest_yield`, `crops.fertilizer_type`).
- **Seed shop** (`constants.py`, `client/js/game.js`, `client/index.html`): Store fertilizer **×5** costs **150** coins.
- **NPC market** (`constants.py`, `server/game/engine.py`, `server/db/queries.py`): Remove **fertilizer** from **`MARKET_BASE_PRICES`** and from NPC sell liquidation; migration deletes **`market_prices`** row for fertilizer.

### Added
- **Schema** (`db/init.sql`, `server/db/queries.py`, `server/game/engine.py`): **`crops.fertilizer_type`**; **`fertilize_crop`** records type; legacy **`fertilized_at`** rows without type use **compost-tier** yield (**8**).

## [0.12.80] - 2026-04-19

### Added
- **Docs** (`docs/ENGINE-TICK-AND-PERSIST.md`): Document **v0.12.76** / **`e04ad31`** persist regression vs **WebSocket** starvation; **merge checklist**; history rows for **`7c71ccf`** (**v0.12.79**).
- **README.md**: Link persistence rule and regression versions.
- **Cursor** (`.cursor/rules/engine-tick-persist.mdc`): Note **v0.12.76** / **v0.12.79** and misdiagnosis vs **`move_q`**.

## [0.12.79] - 2026-04-19

### Added
- **Docs** (`docs/ENGINE-TICK-AND-PERSIST.md`): Document why `tick()` must not block on full DB persist (asyncio/event-loop movement freeze; relation to v0.12.71 / v0.12.73); **Cursor** (`.cursor/rules/engine-tick-persist.mdc`)

### Fixed
- **Server** (`server/game/engine.py`): Restore `_persist_task` / `_do_persist()` background-task pattern that was accidentally removed during chat implementation. The chat commit replaced it with inline `await queries.save_*` calls directly in `tick()`, causing the event loop to block on every persist interval and stalling move-message processing — the same movement-freeze bug fixed in v0.12.73.

## [0.12.78] - 2026-04-19

### Fixed
- **Server** (`server/game/engine.py`): Schedule **`chat`** fan-out with **`asyncio.create_task`** so **`handle_input`** does not **`await`** **`_broadcast_all`** on the WebSocket input loop (avoids **move** starvation after chat, same class of issue as **`start_collect`** vs **`move`** in **`main.py`**).
- **Server** (`server/main.py`): **Drain** **`move_q`** with **`get_nowait`** in a **loop** until empty before each **`wait(move_q, in_q)`** (match comment intent; helps when **`in_q`** competes with movement).

## [0.12.77] - 2026-04-19

### Fixed
- **Client** (`client/js/game.js`, `client/js/input.js`): After chat, **`#chat-input`** could stay focused while hidden so **`input.js`** skipped all WASD/keyup — restore movement by **`blur()`** on close/send, **`requestAnimationFrame`** → canvas focus, and gate key capture on **`#chat-input`** only (not every `INPUT`).

## [0.12.76] - 2026-04-19

### Added
- **Global chat**: **[Enter]** opens the composer, **[Enter]** again sends; all connected players receive **`chat`** messages; bottom-left log (**`client/index.html`**, **`client/css/style.css`**, **`client/js/game.js`**, **`client/js/input.js`**).
- **Server** (`server/game/engine.py`): Handle **`chat`** input; broadcast **`{ type: "chat", from, text }`** to every socket; **0.75s** per-player rate limit; **200** character cap.

## [0.12.75] - 2026-04-19

### Changed
- **Client** (`client/js/renderer.js`): Lower default orbit **pitch** so the opening view includes the **horizon** and **sky** instead of a near top-down angle.

## [0.12.74] - 2026-04-16

### Changed
- **Client** (`client/js/renderer.js`): Draw wild **gravel** nodes as a pile of small rocks instead of a single icosahedron (clearer contrast with **stone** nodes).
- **Client** (`client/js/renderer.js`): Tint the wheelbarrow tub **load** by the **dominant** bucket material (largest amount); mixed loads use that material’s color instead of a single green fill.

## [0.12.73] - 2026-04-19

### Fixed
- **Server** (`server/game/engine.py`): Restore background-task persist — `_do_persist()` runs via `asyncio.create_task` so the event loop is never blocked during DB saves, preventing periodic movement freezes that recurred every persist cycle after the fix was accidentally reverted in v0.12.71.

## [0.12.72] - 2026-04-19

### Fixed
- **Server** (`server/main.py`): **Apply** **queued** **`move`** **input** **with** **`get_nowait()`** **before** **each** **`wait(move_q,` **`in_q)`** **—** **prevents** **non-move** **WebSocket** **messages** **(e.g.** **`start_collect`** **key** **repeat)** **from** **starving** **`handle_input`** **for** **`move`** **(wheelbarrow** **stuck** **not** **moving)**
- **Client** (`client/js/input.js`, `client/js/game.js`): **Ignore** **key** **repeat** **for** **`[V]`** **stop** **load** **and** **`[1]`–`[9]`** **start** **load** **—** **fewer** **redundant** **`start_collect`** **messages**

## [0.12.71] - 2026-04-19

### Changed
- **Server** (`server/game/engine.py`): **Require** **an** **explicit** **`start_collect`** **target** **(and** **`stop_collect`)** **before** **moving** **materials** **from** **wild** **nodes** **or** **free** **piles** **into** **the** **barrow;** **continue** **only** **while** **the** **player** **tile** **stays** **within** **Chebyshev** **distance** **≤** **1** **of** **that** **source** **—** **tile-based** **range** **checks** **(no** **float** **position** **vs** **node** **tile** **mismatch);** **paid** **pile** **purchases** **auto-set** **the** **active** **pile** **key** **and** **still** **require** **the** **same** **proximity** **rules**
- **Client** (`client/js/game.js`): **HUD** **lists** **`[1]`–`[9]`** **per** **nearby** **load** **target** **and** **`[V]`** **to** **stop;** **send** **`start_collect`** **/** **`stop_collect`;** **sell** **autopilot** **sends** **`start_collect`** **on** **the** **owner** **pile** **when** **parked** **so** **the** **loop** **still** **fills** **the** **barrow**
- **Docs** (`README.md`): **Document** **manual** **load** **keys** **and** **`V`**

## [0.12.70] - 2026-04-19

### Changed
- **Client** (`client/js/renderer.js`): **Stop** **drawing** **owner** **names** **above** **each** **player** **structure** **and** **player** **market** **—** **parcel** **overlay** **already** **shows** **who** **owns** **the** **plot**

## [0.12.69] - 2026-04-19

### Changed
- **Server** (`server/game/movement.py`): **Lower** **`TURN_RADIANS_PER_SEC`** **from** **2.8** **to** **1.6** **—** **slower** **maximum** **yaw** **rate** **so** **keyboard** **steering** **is** **less** **twitchy** **and** **easier** **to** **correct**
- **Client** (`client/js/game.js`): **Raise** **sell-autopilot** **heading** **gain** **in** **proportion** **to** **the** **old** **/** **new** **turn** **rate** **so** **autopilot** **paths** **still** **converge** **in** **reasonable** **time**

## [0.12.68] - 2026-04-19

### Changed
- **Client** (`client/js/game.js`): **Show** **remaining** **resource** **amount** **(and** **max** **when** **available)** **in** **the** **HUD** **while** **collecting** **from** **a** **wild** **node;** **prefer** **the** **node** **on** **the** **tile** **underfoot** **when** **multiple** **nodes** **are** **in** **range**

## [0.12.67] - 2026-04-16

### Fixed
- **Client** (`client/js/game.js`): **Show** **`[G]`** **construction** **hints** **when** **standing** **on** **or** **adjacent** **(Chebyshev** **≤** **1)** **to** **your** **active** **site** **using** **the** **same** **`_pick_adjacent_structure`** **rules** **as** **the** **server** **—** **matches** **`deposit_build`** **/** **`cancel_construction`** **so** **the** **HUD** **no** **longer** **requires** **standing** **exactly** **on** **the** **structure** **tile**

## [0.12.66] - 2026-04-19

### Fixed
- **Client** (`client/js/game.js`): **Use** **`Math.floor`** **for** **player** **tile** **coordinates** **in** **HUD** **hints** **and** **menus** **(piles,** **crops,** **soil,** **poor** **soil,** **structures,** **shops)** **—** **matches** **integer** **tile** **data** **from** **the** **server** **so** **till** **/** **plant** **/** **poor-soil** **messages** **apply** **to** **the** **square** **you** **stand** **on**
- **Client** (`client/js/renderer.js`): **Draw** **a** **cyan** **tile** **outline** **and** **tint** **on** **the** **tile** **under** **the** **player** **when** **that** **tile** **is** **on** **owned** **parcel** **land**

## [0.12.64] - 2026-04-16

### Fixed
- **Client** (`client/js/game.js`): **Treat** **NPC** **market** **sell** **range** **as** **Chebyshev** **distance** **≤** **1** **from** **market** **tile** **using** **floored** **player** **coords** **—** **matches** **server** **`_at_any_npc_market`** **so** **the** **`[Space]`** **sell** **hint** **shows** **when** **the** **sell** **action** **works**
- **Client** (`client/js/input.js`, `client/js/game.js`, `client/js/renderer.js`): **Snap** **follow-camera** **yaw** **to** **the** **barrow** **heading** **while** **A/D** **or** **left/right** **turn** **keys** **are** **held;** **keep** **frame** **lerp** **when** **not** **steering** **so** **orbit→drive** **recenters** **smoothly**

## [0.12.59] - 2026-04-16

### Fixed
- **Server** (`server/game/engine.py`): **Index** **soil** **tiles,** **crops,** **resource** **piles,** **and** **poor-soil** **tiles** **by** **64×64** **chunks** **for** **viewport** **queries** **in** **`_broadcast_state`** **and** **`full_state`** **—** **avoids** **O(|world|)** **Python** **loops** **per** **connected** **player** **each** **tick** **that** **blocked** **the** **asyncio** **event** **loop** **(matches** **multi-second** **movement** **freezes** **while** **the** **camera** **still** **orbits;** **often** **misread** **as** **~5s** **aligned** **with** **`resource_tick_s`)**
- **Server** (`server/game/engine.py`): **`await asyncio.sleep(0)`** **after** **each** **player** **tick** **payload** **in** **`_broadcast_state`** **and** **at** **the** **start** **of** **each** **connected** **player** **in** **`_do_resource_tick`** **—** **yield** **so** **WebSocket** **`receive`** **/** **`handle_input`** **can** **run** **during** **heavy** **ticks**

## [0.12.58] - 2026-04-18

### Fixed
- **Server** (`server/main.py`, `server/game/engine.py`): **Deliver** **`tick`** **WebSocket** **payloads** **via** **`asyncio.Queue(maxsize=1)`** **with** **replace-on-overflow** **—** **only** **the** **latest** **tick** **is** **queued** **for** **send;** **stops** **unbounded** **`out_q`** **growth** **when** **`send_json`** **lags** **the** **game** **loop** **(matches** **~10–15s** **“stuck** **until** **it** **clears”** **after** **~15** **tiles)**

## [0.12.57] - 2026-04-18

### Fixed
- **Server** (`server/main.py`): **Route** **`move`** **frames** **through** **`asyncio.Queue(maxsize=1)`** **with** **replace-on-overflow** **—** **never** **enqueue** **unbounded** **`move`** **JSON** **on** **`in_q`** **(matches** **15–20s** **“queue** **drains** **after** **pause”** **behavior)**
- **Client** (`client/js/input.js`): **Revert** **continuous** **`face_angle`** **(v0.12.56);** **throttle** **steady** **`fwd`/`turn`** **to** **≥** **50ms** **between** **sends** **when** **input** **unchanged** **(~20/s)** **;** **still** **send** **immediately** **when** **`fwd`/`turn`** **changes**

## [0.12.56] - 2026-04-18

### Fixed
- **Client** (`client/js/input.js`): **Send** **`face_angle`** **on** **every** **`move`** **while** **`fwd`** **≠** **0** **and** **no** **turn** **keys** **—** **keeps** **server** **heading** **aligned** **with** **orbit** **camera** **view** **(not** **only** **on** **first** **press** **from** **rest);** **avoids** **desync** **where** **velocity** **no** **longer** **matches** **“into** **the** **screen”** **until** **rest** **+** **camera** **orbit** **resends** **`face_angle`**

## [0.12.55] - 2026-04-18

### Fixed
- **Server** (`server/main.py`): **Coalesce** **consecutive** **WebSocket** **`move`** **messages** **to** **the** **latest** **frame** **before** **`handle_input`** **—** **when** **the** **inbound** **queue** **backs** **up,** **processing** **stale** **`move`** **frames** **in** **FIFO** **order** **could** **briefly** **set** **`_input_fwd`** **/** **`_input_turn`** **to** **older** **values** **and** **match** **stop-go** **movement** **while** **the** **camera** **still** **orbits**

## [0.12.54] - 2026-04-18

### Changed
- **Server** (`server/game/world_gen.py`): **Restore** **pre–0.9.3** **wild** **spawn** **density** **—** **biome** **thresholds** **0.25/0.50/0.75;** **forest** **clusters** **`FOREST_CLUSTER_TARGET`** **92** **/** **`FOREST_CLUSTER_MIN_SPACING`** **13** **/** **`max_attempts`** **22000** **with** **direct** **tree** **placement** **`placed`** **≥** **4;** **grid** **`RESOURCE_GRID_STEP`** **25** **and** **`GRID_CELL_HIT_PROB`** **0.35;** **biome-only** **`_pick_resource_for_grid`** **(no** **`MINERAL_QUAD`** **sprinkle);** **`_boost_mineral_nodes`** **1.5×** **and** **biome** **mineral** **opts** **only;** **`MEADOW_COPSE_TARGET`** **0;** **starter** **nodes** **match** **the** **old** **single-tile** **shop** **ring** **layout**

## [0.12.53] - 2026-04-18

### Fixed
- **Server** (`server/main.py`): **Dedicated** **`pump_outgoing`** **task** **`await out_q.get()`** **`+`** **`send_json`** **so** **`tick`** **payloads** **are** **not** **starved** **by** **the** **inbound** **`move`** **loop** **(previous** **single-task** **`asyncio.wait`** **+** **drain** **could** **delay** **or** **block** **ticks** **when** **sending** **~60** **move** **frames/s)**
- **Server** (`server/main.py`): **Route** **`handle_input`** **error** **notices** **through** **`out_q`** **so** **only** **the** **outbound** **pump** **calls** **`send_json`**
- **Client** (`client/js/ws.js`): **Warn** **in** **console** **when** **`send`** **is** **skipped** **because** **the** **socket** **is** **not** **OPEN**

## [0.12.52] - 2026-04-18

### Fixed
- **Server** (`server/game/engine.py`): **Chunk-index** **`water_tiles`** **and** **`bridge_tiles`** **for** **viewport** **wire** **lists** **—** **stop** **full-table** **scans** **each** **`tick`** **(major** **event-loop** **stall** **after** **rivers** **/** **ponds** **scale-up)**
- **Client** (`client/js/input.js`): **Send** **`move`** **every** **animation** **frame** **while** **keys** **are** **held** **;** **use** **`performance.now()`** **when** **`now`** **is** **not** **finite**

## [0.12.51] - 2026-04-18

### Fixed
- **Server** (`server/game/engine.py`): **Chunk-index** **`world_roads`** **for** **`tick`** **/** **`init`** **viewport** **lists** **—** **stop** **O(|all road tiles|)** **scans** **every** **tick** **that** **starved** **the** **asyncio** **loop** **and** **stopped** **WebSocket** **`tick`** **delivery**
- **Server** (`server/game/tick.py`): **Log** **warning** **when** **a** **`tick`** **takes** **>200ms**

## [0.12.50] - 2026-04-18

### Fixed
- **Server** (`server/game/engine.py`): **Omit** **node** **/** **structure** **footprints** **from** **`_movement_blocked_tiles`** **when** **the** **tile** **is** **in** **`road_tiles`** **so** **road∩node** **cells** **do** **not** **block** **movement** **along** **paths**
- **Server** (`server/game/engine.py`): **Invalidate** **`_movement_blocked_cache`** **after** **intra-town** **road** **INSERTs** **and** **spring** **road** **growth**

## [0.12.49] - 2026-04-18

### Fixed
- **Server** (`server/game/movement.py`): **Treat** **`world_roads`** **tiles** **as** **walkable** **before** **water** **checks** **so** **road** **cells** **that** **also** **appear** **in** **`water_tiles`** **(e.g.** **intra-town** **paths** **without** **water** **removal)** **do** **not** **block** **all** **movement**

### Added
- **Scripts** (`scripts/diagnose_tile_overlaps.py`): **Report** **`road`** **∩** **`water_tiles`** **and** **`road`** **∩** **`resource_nodes`** **counts** **(run** **inside** **`docker compose run --rm app python scripts/diagnose_tile_overlaps.py`**)**

## [0.12.48] - 2026-04-18

### Changed
- **Server** (`server/game/movement.py`): **Remove** **`_road_snap_angle`** **cardinal** **heading** **lock** **on** **road** **path** **tiles** **—** **keep** **`ROAD_SPEED_MULT`** **only**

## [0.12.47] - 2026-04-18

### Fixed
- **Server** (`server/main.py`): **Pump** **inbound** **WebSocket** **JSON** **into** **`asyncio.Queue`** **so** **`receive_json`** **is** **never** **cancelled** **by** **`asyncio.wait`** **—** **avoids** **stranding** **`move`** **payloads** **while** **still** **multiplexing** **with** **`out_q`**
- **Client** (`client/js/input.js`): **Duplicate-send** **the** **first** **`move`** **after** **rest** **via** **`queueMicrotask`** **and** **tighten** **`MOVE_RESEND_MS`** **to** **33** **—** **reduces** **chance** **`_input_fwd`** **stays** **zero** **when** **the** **HUD** **already** **shows** **camera-snapped** **rotation** **(optimistic** **`face_angle`** **in** **`game.js`**)**

## [0.12.46] - 2026-04-18

### Fixed
- **Server** (`server/game/engine.py`): **Cache** **`_movement_blocked_tiles()`** **and** **invalidate** **when** **structures** **/** **piles** **change** **—** **rebuilding** **~24k** **blocked** **tiles** **every** **100ms** **tick** **starved** **the** **asyncio** **loop** **and** **prevented** **timely** **`tick`** **/** **`move`** **handling**
- **Server** (`server/game/engine.py`): **Chunk-index** **wild** **resource** **nodes** **for** **viewport** **`tick`** **/** **`full_state`** **queries** **instead** **of** **scanning** **every** **node** **each** **time**
- **Server** (`server/main.py`): **Process** **`receive_json`** **result** **when** **both** **outbound** **and** **inbound** **complete** **in** **the** **same** **scheduler** **turn** **(do** **not** **drop** **`move`**
- **Client** (`client/js/input.js`): **Re-send** **`move`** **every** **50ms** **while** **movement** **keys** **are** **held** **so** **a** **dropped** **message** **does** **not** **leave** **`_input_fwd`** **at** **zero**
- **Client** (`client/index.html`, `client/js/game.js`): **Show** **build** **version** **in** **HUD** **`#hud-version`**

## [0.12.44] - 2026-04-16

### Fixed
- **Client** (`client/js/input.js`): **Send** **`move`** **only** **when** **`fwd`** **/** **`turn`** **changes** **from** **the** **last** **sent** **command** **—** **stop** **~30×/s** **idle** **`{fwd:0,turn:0}`** **spam** **that** **flooded** **the** **WebSocket** **and** **contributed** **to** **`tick`** **starvation** **and** **disconnects**

## [0.12.43] - 2026-04-16

### Fixed
- **Server** (`server/main.py`): **Drain** **`out_q`** **with** **`get_nowait`** **before** **each** **`asyncio.wait`** **on** **outbound** **vs** **`receive_json`** **—** **when** **both** **complete** **in** **the** **same** **scheduler** **turn** **the** **race** **could** **favor** **buffered** **move** **messages** **repeatedly** **and** **starve** **`tick`** **delivery**

## [0.12.42] - 2026-04-16

### Fixed
- **Server** (`server/main.py`): **Multiplex** **outbound** **queue** **`get`** **with** **`websocket.receive_json`** **via** **`asyncio.wait`** **in** **the** **same** **task** **that** **calls** **`send_json`** **—** **removes** **the** **separate** **outbound** **pump** **task** **that** **could** **deadlock** **with** **receive** **on** **ASGI** **and** **leave** **`tick`** **messages** **undelivered** **(wheelbarrow** **stuck** **in** **place)**

## [0.12.41] - 2026-04-18

### Fixed
- **Server** (`server/main.py`): **Await** **`asyncio.sleep(0)`** **after** **each** **`handle_input`** **so** **the** **game** **loop** **is** **not** **starved** **when** **the** **browser** **sends** **many** **WebSocket** **messages** **per** **second** **(movement** **looked** **dead** **because** **`tick`** **broadcasts** **were** **delayed** **by** **asyncio** **scheduling)**

## [0.12.40] - 2026-04-18

### Fixed
- **Client** (`client/js/renderer.js`): **Focus** **the** **game** **canvas** **on** **each** **primary** **mousedown** **so** **keyboard** **events** **reach** **movement** **after** **focus** **moves** **to** **Firefox** **Developer** **Tools** **or** **other** **UI**
- **Client** (`client/js/input.js`): **Clear** **held** **movement** **keys** **and** **send** **a** **zero** **move** **on** **`window` `blur`** **so** **stuck** **keys** **do** **not** **persist** **when** **switching** **away**

## [0.12.39] - 2026-04-18

### Fixed
- **Server** (`server/game/engine.py`): **Reset** **`_last_resource_tick`** **/** **`_last_market_drift`** **/** **`_last_election_check`** **/** **`_last_persist`** **to** **`time.monotonic()`** **at** **end** **of** **`load()`** **so** **the** **first** **`tick()`** **does** **not** **treat** **the** **whole** **load** **window** **as** **one** **catch-up** **interval** **before** **broadcasting** **`tick`** **messages**
- **Server** (`server/game/engine.py`): **Cap** **resource-tick** **`elapsed`** **at** **120s** **when** **catching** **up** **after** **long** **pauses**
- **Server** (`server/game/engine.py`, `server/main.py`): **Remove** **`asyncio.wait_for`** **around** **WebSocket** **`send_json`** **(restore** **direct** **`await`)** **and** **remove** **`WS_SEND_TIMEOUT_S`**
- **Server** (`server/game/tick.py`): **Re-raise** **`asyncio.CancelledError`** **from** **the** **game** **loop** **task** **so** **shutdown** **cancellation** **is** **not** **swallowed** **by** **the** **generic** **`except`**

## [0.12.38] - 2026-04-18

### Fixed
- **Client** (`client/js/ws.js`): **Remove** **`queueMicrotask`** **around** **`tick`** **handlers** **—** **it** **queued** **a** **growing** **microtask** **backlog** **and** **delayed** **frame** **processing,** **which** **paired** **with** **server** **send** **timeouts** **could** **drop** **the** **connection** **and** **freeze** **movement**

## [0.12.37] - 2026-04-18

### Fixed
- **Server** (`server/game/constants.py`, `server/game/engine.py`, `server/main.py`): **Bound** **WebSocket** **`send_json`** **with** **`asyncio.wait_for`** **(`WS_SEND_TIMEOUT_S`);** **drop** **and** **close** **stalled** **clients** **so** **one** **browser** **that** **stops** **reading** **ticks** **cannot** **block** **the** **game** **loop** **for** **everyone**
- **Client** (`client/js/ws.js`): **Defer** **`tick`** **handlers** **with** **`queueMicrotask`**, **catch** **`JSON.parse`** **and** **handler** **errors** **so** **the** **socket** **keeps** **draining**

## [0.12.36] - 2026-04-18

### Fixed
- **Server** (`server/game/engine.py`): **Run** **intra-town** **NPC** **road** **seeding** **whenever** **the** **world** **loads** **(not** **only** **when** **`world_roads`** **was** **empty);** **inter-town** **roads** **had** **prevented** **shop** **paths** **from** **ever** **being** **inserted** **on** **most** **live** **databases**
- **Server** (`server/game/roads_util.py`): **Connect** **NPC** **district** **sites** **with** **a** **Prim-style** **shortest-path** **network** **inside** **the** **town** **polygon** **instead** **of** **a** **single** **ring** **order** **that** **could** **omit** **segments**

### Changed
- **Server** (`server/game/engine.py`): **Replace** **`_seed_initial_npc_roads`** **/** **`_merge_npc_roads_for_town`** **with** **`_ensure_intratown_npc_road_paths`** **(covers** **re-placed** **districts** **and** **existing** **worlds)**

### Notes
- **Seasonal** **road** **growth** **toward** **player** **buildings** **(`_grow_roads_new_year`**, **spring** **transition)** **is** **unchanged** **—** **see** **`ROAD_GROWTH_TILES_MIN`** **/** **`MAX`** **in** **`server/game/constants.py`**

## [0.12.35] - 2026-04-18

### Fixed
- **Server** (`server/game/tick.py`): **Catch** **exceptions** **per** **`engine.tick`** **so** **a** **single** **failed** **tick** **does** **not** **terminate** **the** **background** **game** **loop** **(without** **loop** **`tick`** **messages** **never** **reach** **clients)**
- **Server** (`server/game/engine.py`): **Log** **failures** **when** **sending** **`tick`** **over** **the** **WebSocket** **instead** **of** **ignoring** **them**
- **Client** (`client/js/game.js`): **Blur** **focused** **login** **fields** **and** **focus** **the** **game** **canvas** **after** **login** **so** **arrow** **/** **WASD** **input** **is** **delivered** **reliably**
- **Client** (`client/js/input.js`): **Map** **movement** **via** **`KeyboardEvent.code`** **`KeyW`/`KeyA`/`KeyS`/`KeyD`** **in** **addition** **to** **`key`** **characters**

## [0.12.34] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Stop** **resetting** **mesh** **pools** **each** **frame;** **re-attach** **pooled** **groups** **to** **`dynamicRoot`;** **cache** **wheelbarrow** **geometry** **by** **quantized** **yaw/load;** **throttle** **grass** **terrain** **rebuilds** **(~9** **Hz);** **widen** **road** **overlap,** **disable** **road** **cast** **shadow,** **slight** **emissive** **—** **fixes** **severe** **FPS** **stutter** **and** **jerky** **camera**
- **Client** (`client/js/input.js`): **Send** **movement** **samples** **every** **33** **ms**
- **Server** (`server/game/constants.py`): **Add** **`VIEWPORT_WATER_RADIUS`** **(100)** **for** **water** **/** **bridge** **payloads**
- **Server** (`server/game/engine.py`): **Use** **`player_tile_xy`** **for** **viewport** **culling** **(init** **+** **tick);** **send** **water** **/** **bridges** **in** **the** **larger** **water** **radius**

## [0.12.33] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Increase** **road** **tile** **overlap** **and** **draw** **order** **so** **dirt** **paths** **read** **as** **continuous** **ribbons** **instead** **of** **separated** **squares**

## [0.12.32] - 2026-04-18

### Added
- **`server/game/intertown_roads.py`**: **Plan** **MST+redundant** **inter-town** **roads** **with** **bridge** **tiles** **where** **paths** **cross** **water**
- **`tests/test_movement_blocked.py`**: **Cover** **leaving** **vs** **entering** **blocked** **tiles**
- **`requirements.txt`**: **List** **`pytest`** **for** **running** **`tests/`**

### Changed
- **`server/game/engine.py`**: **Block** **movement** **onto** **nodes,** **structures,** **and** **non-empty** **piles;** **load** **`protected`** **road** **tiles;** **extend** **many** **interactions** **to** **Chebyshev** **distance** **≤** **1;** **forbid** **building** **/** **farming** **/** **unloading** **on** **protected** **roads**
- **`server/game/movement.py`**: **Pass** **water,** **bridges,** **blocked** **set,** **and** **roads;** **multiply** **speed** **on** **roads** **(fix** **inverted** **multiplier);** **treat** **blocked** **tiles** **as** **entry-only** **so** **players** **can** **drive** **off** **structures** **(e.g.** **NPC** **market)**
- **`server/game/world_gen.py`**: **Insert** **inter-town** **protected** **roads** **and** **generated** **bridges** **after** **water**
- **`server/db/queries.py`**: **`load_all_roads_with_protected`,** **`delete_water_tiles_bulk`,** **`insert_bridge_tiles_bulk`**
- **`db/init.sql`**: **Add** **`world_roads.protected`**
- **`client/js/renderer.js`**: **Draw** **roads** **as** **flat** **planes;** **omit** **road** **quads** **on** **bridge** **tiles**

## [0.12.31] - 2026-04-16

### Changed
- **Client** (`client/js/terrain.js`): **Expose** **`elevationRawFloat`** **/** **`worldYFloat`** **for** **continuous** **height** **(same** **formula** **as** **integers)**
- **Client** (`client/js/renderer.js`): **Replace** **instanced** **flat** **grass** **quads** **with** **an** **indexed** **terrain** **mesh** **—** **vertices** **sample** **`worldYFloat`;** **optional** **2×** **subdivision** **per** **tile** **when** **the** **loaded** **patch** **is** **small** **enough**
- **Server** (`server/game/terrain_elevation.py`): **Add** **`elevation_raw_float`** **and** **delegate** **`elevation_raw`**
- **Tests** (`tests/test_terrain_elevation.py`): **Cover** **float** **elevation**

## [0.12.30] - 2026-04-16

### Changed
- **Client** (`client/js/input.js`): **Treat** **WASD** **as** **movement** **with** **arrow** **keys** **(camera** **follow** **unchanged)**
- **Client** (`client/js/game.js`): **Map** **tear-down** **to** **`K`** **instead** **of** **`D`** **so** **it** **does** **not** **conflict** **with** **strafe** **right**
- **Docs** (`README.md`): **Document** **WASD** **and** **`K`** **for** **demolish**

## [0.12.29] - 2026-04-16

### Changed
- **Client** (`client/js/terrain.js`): **Increase** **hill** **visibility** **—** **scale** **world** **Y** **from** **×12** **to** **×48,** **add** **medium-frequency** **elevation** **octave,** **clamp** **`elevationRaw`** **to** **[-1,** **1]**
- **Server** (`server/game/terrain_elevation.py`): **Match** **client** **formula** **and** **`WORLD_Y_SCALE`**
- **Tests** (`tests/test_terrain_elevation.py`): **Add** **checks** **for** **elevation** **field**

## [0.12.28] - 2026-04-16

### Changed
- **Server** (`server/game/terrain_features.py`): **Add** **long** **multi-town** **rivers** **(4–8** **tiles** **wide,** **1–2** **systems** **per** **map)** **as** **thick** **polylines** **through** **8–10** **town** **centers** **per** **river** **—** **avoid** **NPC** **shop** **tiles** **and** **resource** **nodes;** **include** **in** **`generate_water_features`**
- **Server** (`server/game/world_gen.py`): **Clarify** **world_gen** **log** **line** **for** **water** **count**
- **Scripts** (`scripts/add_major_rivers.py`): **Add** **idempotent** **migration** **for** **existing** **worlds** **(skips** **bridge** **tiles)**
- **Tests** (`tests/test_terrain_rivers.py`): **Add** **coverage** **for** **river** **geometry** **helpers**

## [0.12.27] - 2026-04-16

### Changed
- **Client** (`client/js/renderer.js`): **Remove** **L-corner** **quarter-cylinder** **road** **meshes** **—** **they** **rendered** **as** **vertical** **fins** **at** **some** **junctions;** **rely** **on** **overlapping** **road** **tiles** **instead**

## [0.12.26] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Reduce** **loaded** **tile** **footprint** **—** **tighter** **`_expandTileRangeForGroundLayers`** **span/pad,** **smaller** **frustum** **margin,** **capped** **fallback** **span,** **`MAX_GRASS`** **65536→10000** **with** **matching** **fade** **band**
- **Client** (`client/js/renderer.js`): **Lerp** **`_renderSmoothX/Y`** **toward** **server** **position** **each** **frame** **for** **camera,** **grass,** **and** **local** **wheelbarrow** **mesh** **(snap** **if** **teleport** **>10** **tiles)** **to** **ease** **stop-go** **between** **ticks**
- **Server** (`server/game/constants.py`): **Lower** **`VIEWPORT_RADIUS`** **120→72** **so** **tick** **payloads** **cover** **less** **world** **around** **the** **player**

## [0.12.25] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Wheelbarrow** **—** **shorten** **axle** **to** **~10** **units** **(rail** **track)** **and** **move** **wheel** **to** **z≈** **rail** **tips** **so** **the** **tire** **sits** **in** **the** **V** **with** **axle** **ends** **at** **the** **frame**

## [0.12.24] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Do** **not** **draw** **the** **local** **player’s** **username** **sprite** **above** **their** **wheelbarrow** **—** **other** **players’** **names** **unchanged**

## [0.12.23] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Simplify** **wheelbarrow** **to** **a** **classic** **V-frame** **—** **two** **straight** **wood** **rails** **(narrow** **at** **the** **axle,** **wider** **at** **the** **handles)** **with** **inline** **rounded** **ends;** **remove** **cross-braces** **under** **the** **bucket,** **perpendicular** **grip** **cylinders,** **straps,** **lug** **bolts,** **and** **rim** **beads;** **single** **front** **nose** **brace,** **open** **bucket,** **one** **sloped** **front** **lip,** **metal** **legs** **with** **a** **cross-brace**

## [0.12.22] - 2026-04-18

### Changed
- **Client** (`client/js/input.js`, `client/js/renderer.js`, `client/js/game.js`): **When** **starting** **forward** **or** **backward** **from** **a** **full** **stop** **with** **no** **turn** **keys,** **send** **`face_angle`** **from** **`getCameraFacingAngle()`** **(orbit** **view)** **and** **apply** **it** **optimistically** **so** **the** **barrow** **faces** **into** **the** **screen** **before** **moving**
- **Server** (`server/game/engine.py`): **On** **`move`**, **apply** **optional** **`face_angle`** **to** **the** **player** **`angle`** **when** **present**

## [0.12.21] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Wheelbarrow** **mesh** — **open** **tub** **(sloped** **floor,** **left/right/back** **walls,** **rim** **beads,** **front** **lip** **+** **under** **panel** **over** **the** **wheel),** **wood** **rails** **with** **outward** **yaw** **toward** **handles,** **axle** **blocks,** **larger** **tire,** **and** **rear** **legs** **—** **so** **the** **shape** **reads** **as** **a** **classic** **single-wheel** **barrow** **from** **most** **camera** **angles**

## [0.12.20] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Road** **tiles** **use** **`T + ROAD_TILE_OVERLAP`** **instead** **of** **`T − ε`** **so** **adjacent** **road** **boxes** **overlap** **and** **grass** **does** **not** **show** **through** **seams**; **tighten** **`polygonOffset`** **slightly** **for** **the** **road** **material**

## [0.12.19] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Replace** **primitive** **wheelbarrow** **(box** **tub** **+** **flat** **torus)** **with** **a** **classic** **single-wheel** **layout** **—** **upright** **cylinder** **tire** **on** **a** **horizontal** **axle** **at** **the** **front** **(+Z),** **steel** **tray** **with** **flared** **rim** **and** **forward** **lip** **over** **the** **wheel,** **two** **wooden** **side** **rails** **from** **the** **axle** **zone** **to** **cylindrical** **handles** **at** **the** **rear,** **metal** **straps,** **cross** **braces,** **rear** **legs** **with** **foot** **pads,** **and** **diagonal** **stiffeners**

## [0.12.18] - 2026-04-18

### Changed
- **Client** (`client/js/renderer.js`): **Water** — **replace** **inner** **L-corner** **`smin`** **union** **(convex** **caps** **into** **grass)** **with** **`smax`** **subtraction** **so** **the** **shore** **is** **a** **concave** **arc**; **place** **disk** **centers** **on** **each** **corner** **bisector** **at** **`B+Rf/√2`** **with** **`B=1.028`**

## [0.12.17] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — **blend** **inner** **fillet** **disks** **into** **the** **main** **`sdRoundBox`** **with** **`smin`** **instead** **of** **`min`**, **and** **remove** **the** **`p.x>1 && p.y>1`** **quadrant** **masks** **so** **the** **arc** **meets** **straight** **edges** **without** **slivers**

## [0.12.16] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — **inner** **(concave)** **L-corners** **use** **the** **same** **radius** **as** **outer** **corners** **by** **unioning** **quarter-disk** **SDFs** **(center** **`(±(1+Rf),±(1+Rf))`,** **`Rf=1`**) **past** **each** **tile** **corner** **in** **normalized** **space** **so** **water** **bleeds** **onto** **grass** **with** **a** **rounded** **inner** **bend**
- **Client** (`client/js/renderer.js`): **Water** — **larger** **`PlaneGeometry`** **`(T×WATER_QUAD_SCALE)`** **+** **`aInnerFillet`** **instance** **attribute** **so** **fragments** **can** **cover** **past** **`|p|=1`**

## [0.12.15] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — **concave** **inner** **vertices** **(one** **cardinal** **grass,** **opposite** **cardinal** **water,** **diagonal** **water)** **now** **force** **`r=0`** **on** **each** **corner** **(symmetric** **NE/SE/NW/SW)** **so** **L-shaped** **ponds** **do** **not** **get** **V-notches** **from** **leftover** **`Rc`**
- **Client** (`client/js/renderer.js`): **Water** — **stronger** **tile** **overlap** **`sdRoundBox`** **`b=vec2(1.028)`** **and** **larger** **SDF** **margin** **to** **hide** **grid** **seams** **(acceptable** **grass** **bleed)**

## [0.12.14] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — set **outer** **corner** **radius** **`Rc`** **to** **`1.0`** **in** **normalized** **`sdRoundBox`** **space** **(matches** **shader** **`b`** **=** **`vec2(1.0)`**)** so **a** **lone** **water** **tile** **is** **a** **full** **circle** **and** **convex** **shore** **corners** **use** **maximum** **quarter-circle** **arcs**

## [0.12.13] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — treat **small** **positive** **`sdRoundBox`** **distance** **as** **inside** **water** (**`WATER_SDF_MARGIN`**) so **adjacent** **tiles** **overlap** **slightly** **and** **grass** **seams** **disappear**; enable **`polygonOffset`** **on** **the** **water** **material** **to** **reduce** **z-fighting** **with** **grass**

## [0.12.12] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — pass **`vWaterUv`** from vertex **`uv`** for the **rounded-rect** `discard`; **`MeshBasicMaterial`** without a map **does not declare** **`vUv`** in the fragment shader, which **broke** **fragment** **compilation** and **disabled** **rounded** **corners** / **correct** **color**

## [0.12.11] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — inject **Inigo `sdRoundBox`** `discard` into the **default** `MeshBasicMaterial` fragment shader instead of replacing the whole shader, so **`colorspace_fragment`** / **`linearToOutputTexel`** run on **`diffuse`** and water reads **blue** again (full custom fragment had skipped output color handling)

## [0.12.10] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — compute **per-corner** **`sdRoundBox`** radii with **diagonal** neighbor checks so **straight** **shorelines** stay **straight** (no per-tile scallops); apply **full** **outer** **convex** **quarter-circles** (**radius** **0.5** in UV space) only at **true** **90°** **outer** **corners** of the water mask

## [0.12.9] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — restore **Inigo Quilez `sdRoundBox`** rounded masks per tile with **`vec4` (NE, SE, NW, SW)**; **`p = (vUv-0.5)*2`** in UV space; **hardcoded** blue **after** `discard` (**no** `linearToOutputTexel`) so ponds/rivers use **smooth curved** outer edges instead of stair-stepped square union

## [0.12.8] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — remove **rounded-rect SDF / `discard`** path; use **plain `MeshBasicMaterial`** full-tile planes, **`toneMapped: false`**, **`colorSpace: SRGBColorSpace`**, bright **`0x4ec8ff`**, **`renderOrder` 2** so rivers/ponds render as **reliable blue** (rounded corners deferred until a safer approach)

## [0.12.7] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — fix **Inigo `sdRoundBox` vec4 layout** (east `NE,SE` + west `NW,SW`); use **`p = (vUv-0.5)*2` without Y flip**; drop **`linearToOutputTexel`** on this pass; solid **blue** `gl_FragColor` after discard
- **Client** (`client/js/renderer.js`): **Roads** — **`T - 0.06`** tile coverage (was **`T - 0.5`**) + **`polygonOffset`** to hide grass seams between road tiles

## [0.12.6] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — fragment color is **hardcoded linear** `vec3` (no `diffuse` uniform); bias **B** over **G** so water reads **blue** after tone/color output
- **Client** (`client/js/renderer.js`): **Lighting** — fixed **high-noon** levels: brighter **hemisphere** (sky/ground colors + intensity), **ambient**, **directional** (white, **~1.82**); **sun** Y **1250**; **toneMappingExposure** **~1.32**; **fog** base density lowered; season **no longer** dims hemi/amb/sun

## [0.12.5] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — replace MeshBasic fragment with a **minimal shader** (rounded `discard`, then `gl_FragColor = vec4(diffuse,1)`, `logdepthbuf`, `linearToOutputTexel`) so color is not pulled green by the default basic indirect/envmap path; brighter blue **0x4cb8f2**
- **Client** (`client/js/renderer.js`): **Ground tile cull** — **`_expandTileRangeForGroundLayers`** unions the frustum tile rect with a **player-centered footprint** (scale with camera distance) + padding so **roads/water** and other ground layers are not dropped at shallow orbit angles
- **Client** (`client/js/renderer.js`): **Nodes** — remove the **green/orange “amount” progress bar** meshes on wild resources and structures (trees, rocks, etc.)

## [0.12.4] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — override `opaque_fragment` so **`gl_FragColor` uses `uniform diffuse` only** (skips `outgoingLight` from MeshBasic’s indirect/envmap path in Three r160); remove **`fog_fragment`** for water; set **`toneMapped: false`**; slightly brighter blue **0x3aa6e8**

## [0.12.3] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Water** — use **`MeshBasicMaterial`** (unlit) so **HemisphereLight** ground tint does not turn blue water **dark green**; slightly brighter base blue **0x2f88d0**; **`receiveShadow: false`** (Basic does not shade)

## [0.12.2] - 2026-04-16

### Changed
- **Client** (`client/js/renderer.js`): **Water** — use **opaque** surface (`opacity: 1`, `transparent: false`) so color does not blend with green grass tiles below; set **`fog: false`** on water for stable blue at distance (shape still uses fragment `discard` for rounded corners)

## [0.12.1] - 2026-04-16

### Changed
- **Client** (`client/js/renderer.js`): **Grass** — sample base color and micro-shade from **continuous world XZ** so adjacent tiles do not show faint grid lines at boundaries
- **Client** (`client/js/renderer.js`): **Water** — full-tile quads with **per-corner rounded-rectangle** fragment clipping (neighbor-aware radii: circular isolated cells, straight shared edges between water tiles, rounded outer corners toward grass); clip runs before `#include <color_fragment>` for reliable compilation

## [0.12.0] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Ground rendering** — grass limited to a **circle** around the player (no square corner artifact); **radial blend** of instance grass color toward a matching **horizon tint** at the outer ring; huge **grass-colored backdrop plane** under the world (`fog: false`, `depthWrite: false`) so distance reads as continuous green; **grass** material uses **`fog: false`** so it stays green with the backdrop; **water/roads** still use the full **camera frustum** tile rect (not the grass circle)

## [0.11.8] - 2026-04-17

### Fixed
- **Client** (`client/js/renderer.js`): when grass tile count exceeds budget, clamp the square to the **player tile** instead of the frustum bounding-box center — shallow views skew the AABB toward the horizon and had been dropping **near** ground while a distant patch still drew

## [0.11.7] - 2026-04-17

### Fixed
- **Client** (`client/js/renderer.js`): **ground vanishing when zoomed out + low pitch** — raise grass/water/road instance caps (**65536** / **12000** / **12000**); **clamp** visible tile rect to a frustum-centered square when over budget (was filling only the first **16k** tiles of a huge rect); **ease fog** further when **zoomed out** so long view rays do not wash terrain away

## [0.11.6] - 2026-04-17

### Fixed
- **Client** (`client/js/input.js`): **invert tank steer** — **Left** decreases turn, **Right** increases it (matches server `angle` integration and sell autopilot)

## [0.11.5] - 2026-04-17

### Added
- **Script** (`scripts/seed_spawn_ring_water.py`): optional **spawn-ring ponds** for existing worlds (INSERT IGNORE; idempotent)

### Changed
- **Server** (`server/game/terrain_features.py`): reduce **spawn dry zone** for wild water from **42** to **30** tiles (Chebyshev); add **`extra_ponds_outside_spawn_ring()`** for migration; **town at `PLAYER_SPAWN`** no longer applies the full **92**-tile water exclusion (only a **22**-tile core + NPC pads), so ponds/streams can exist near the starting hub
- **Server** (`server/game/engine.py`): one-time **water + poor-soil** seed when `water_tiles` is empty if **towns** exist (no longer gated on `world_gen_state.done` alone)
- **Client** (`client/js/renderer.js`): **omit grass** on **water** tiles so ponds/streams read clearly
- **Client** (`client/js/terrain.js`) / **Server** (`server/game/terrain_elevation.py`): stronger **rolling hill** visual (**×12** vs ×8 world units; slope math unchanged)

## [0.11.4] - 2026-04-17

### Changed
- **Client** (`client/js/input.js`, `client/js/game.js`, `client/js/renderer.js`): **Behind-barrow camera** while **any** arrow key is held (forward, back, or turn) or **sell autopilot** is active; **mouse yaw** only when **fully stationary** (no arrows); slightly faster yaw snap when re-locking behind the barrow

## [0.11.3] - 2026-04-17

### Fixed
- **Client** (`client/js/renderer.js`): **Horizontal / low-pitch view** — scale **FogExp2** density by orbit pitch (weaker fog near the horizon) so terrain does not wash out to sky when tilting toward a driving angle; **frustum → ground** tile bounds use a **ray–plane hit or horizon fallback** when `intersectPlane` misses at shallow angles

## [0.11.2] - 2026-04-17

### Changed
- **Client** (`client/js/game.js`, `client/js/input.js`, `client/js/renderer.js`): **Driving camera** — while **ArrowUp/ArrowDown** or **sell autopilot** is active, **orbit yaw** smoothly follows the wheelbarrow **`angle`** (behind-the-barrow view); **horizontal drag** only affects yaw when **not** driving; **pitch** (drag up/down, wheel zoom, **[** / **]**) unchanged

## [0.11.1] - 2026-04-17

### Fixed
- **Client** (`client/js/renderer.js`): **NPC shop loop** renamed ground-height `const sy` to **`shopGy`** — it shadowed the viewport **`sy`** parameter and triggered a temporal dead zone on `shop.y < sy - 2`, freezing **`draw()`**

## [0.11.0] - 2026-04-17

### Added
- **Server** (`server/game/movement.py`): **continuous movement** — float `x`/`y`, heading **`angle`**, tank controls via `_input_fwd` / `_input_turn`; terrain and load speed on server; wheel wear accumulates per ~1 tile travelled
- **Server** (`server/db/queries.py`): **`ensure_player_movement_columns()`** — add **`angle`** and widen **`x`/`y`** to **DOUBLE** when missing (existing DBs)
- **DB** (`db/migration_0_11_continuous_movement.sql`, `db/init.sql`): **`angle`** column; **DOUBLE** positions for new installs

### Changed
- **Server** (`server/game/engine.py`): **`move`** WebSocket message uses **`fwd`** and **`turn`** (-1…1); physics integrated each **tick**; tile-scoped actions use **`player_tile_xy()`**; **`fill_water`** / **`bridge_deposit`** infer cardinal from **`angle`** when **`dir`** omitted
- **Client** (`client/js/input.js`): **Up/Down** = forward/back, **Left/Right** = **rotate** (no strafe); input sampled every **50ms**
- **Client** (`client/js/game.js`, `client/js/renderer.js`): **`angle`** for wheelbarrow **yaw**; facing hints from **`_facingFromAngle`**; **sell autopilot** steers with **fwd/turn** toward tile center
- **Client** (`client/js/renderer.js`): **roads** use nearly **full-tile** slabs (**`T - 0.5`**); **quarter-cylinder** fillets at **inner L junctions** (three road neighbors, missing diagonal)

## [0.10.5] - 2026-04-17

### Added
- **Client** (`client/js/terrain.js`): rolling elevation field, `Terrain.worldY` / `Terrain.moveIntervalMult` for mild hills (uphill slower, downhill faster)
- **Server** (`server/game/terrain_elevation.py`): mirror elevation math for documentation and future server use

### Changed
- **Client** (`client/js/input.js`, `client/js/renderer.js`): **arrow keys** move **camera-relative** (up/down along view toward/away from camera; left/right strafe); `Renderer.getCameraMoveBasis()` supplies forward/right from orbit yaw/pitch/distance
- **Client** (`client/js/game.js`): **sell autopilot** step pacing uses the same interval formula as keyboard (load, flat tyre, terrain)
- **Client** (`client/js/renderer.js`): **frustum-based tile culling** for grass/water/roads/entities — fixes diagonal “empty wedge” from old canvas-pixel bounds; raise **max zoom-out** (`DIST_MAX` 720 → 1600); increase **instanced mesh caps** for larger visible area; slightly **reduce exponential fog** density so distance reads clearer

## [0.10.4] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **Sky / horizon** — `scene.background` uses **blue–gray seasonal sky** colors (not grass green); **fog** color matches sky so distance reads as atmosphere; slightly lower fog density
- **Client** (`client/js/renderer.js`): **Parcel overlays** (fill, edge lines, labels) render only when the player is **on** that parcel or **previewing** it with **[B]** — no outlines for distant parcels

## [0.10.3] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): **camera pitch** — drag **up/down** while orbiting to tilt between **near top-down** and **flat**; widen pitch limits; **mouse wheel** zoom; **[** / **]** nudge pitch with new range

## [0.10.2] - 2026-04-17

### Fixed
- **Client** (`client/js/renderer.js`): call **`_applySeasonAtmosphere()`** only **after** **Ambient** / **Hemisphere** lights exist — **`init()`** had invoked it first, leaving **`hemi` undefined** and throwing in the browser (black screen)

## [0.10.1] - 2026-04-16

### Fixed
- **Client** (`client/js/renderer.js`): **WebGL draw** no longer fails silently — remove **`vertexColors: true`** from grass `InstancedMesh` material (conflicts with **`setColorAt`** instance colors), defer **`THREE`** helpers to **`init()`**, guard **`resize`/`draw`**, wrap **`draw`** in **try/catch**, optional **`SRGBColorSpace`** when present

## [0.10.0] - 2026-04-16

### Added
- **Client** (`client/vendor/three.min.js`, `client/js/renderer.js`): **Three.js WebGL** renderer — perspective camera, follow + **mouse-drag orbit**, **[** / **]** pitch, shadows, fog, instanced grass/water/roads, **tilled-soil furrow lines**, 3D meshes for resources, structures, piles, crops, wheelbarrows, and **sprite labels** for names and UI text

### Changed
- **Server** (`server/game/engine.py`): **block tilling in winter** (frozen ground), including clearing **frost-killed** crops — **spring** required for till and plant (planting was already spring-only)
- **Client** (`client/js/game.js`): HUD hints for **winter** farming (frozen soil, wait for spring)
- **README**: document **winter till** rules and **3D camera** controls
- **Client** (`client/css/style.css`): canvas styling for **WebGL** (drag orbit, no pixelated scaling)

## [0.9.10] - 2026-04-16

### Changed
- **Client** (`client/js/renderer.js`): replace **checkerboard ground** with **smooth grass color** (low-frequency variation) and subtle **radial shading** per tile so the field blends without a visible grid
- **Client** (`client/js/game.js`): **HUD hints** when a **resource pile** blocks tilling or planting on an owned parcel (and when a frosted crop blocks till)

## [0.9.9] - 2026-04-17

### Changed
- **Client** (`client/js/renderer.js`): wheelbarrow tub **tints and wear scratches** scale with low **`wb_paint`** — looks distressed when paint is in poor condition; other players’ `wb_paint` included in tick payload (`server/game/engine.py` **`_connected_players_wire`**)

## [0.9.8] - 2026-04-17

### Added
- **`scripts/densify_resource_nodes.py`**: run against an existing database to insert extra wild nodes via `densify_nodes_for_existing_world()` (meadow copses + grid + mineral boost on unoccupied tiles; does not duplicate forest-cluster groves)

### Changed
- **`server/game/world_gen.py`**: commit the density work outlined in 0.9.5 — wider **forest** biome; **`RESOURCE_GRID_STEP`** / **`GRID_CELL_HIT_PROB`**; **`MINERAL_QUAD`** and **`_pick_resource_for_grid`**; **meadow copses** on plains/wetland; stronger **`_boost_mineral_nodes`**; **`densify_nodes_for_existing_world`** helper for migrations
- **`deploy/README.md`**: document **terrain migrations** (rebuild image, `regenerate_poor_soil`, `densify_resource_nodes`, restart)

## [0.9.7] - 2026-04-17

### Changed
- **Farming**: allow **compost** in the barrow (or pocket) to fertilize wheat like **fertilizer** and **manure** — same growth boost and yield; update HUD hint and README

## [0.9.6] - 2026-04-16

### Changed
- **Farming**: allow **planting wheat** only during **spring** — server rejects `[F]` plant otherwise; HUD hints on tilled soil reflect spring-only planting; update README till/plant copy

## [0.9.5] - 2026-04-16

### Changed
- **Design intent** (implementation and migration script committed in **[0.9.8]**): denser wild resources — wider forest biome, meadow copses, mineral grid sprinkle, `densify_resource_nodes` migration for existing worlds

## [0.9.4] - 2026-04-16

### Added
- **`scripts/regenerate_poor_soil.py`**: clear `poor_soil_tiles` and refill with the current patchy algorithm (fixed RNG seed) for existing worlds
- **`queries.clear_all_poor_soil_tiles`**: truncate `poor_soil_tiles` before bulk insert

### Changed
- **Water placement** (`server/game/terrain_features.py`): exclude water only near town **centers** and **NPC district** tiles — not whole Voronoi polygons (which covered the map and prevented any ponds/streams)
- **Poor soil** (`server/game/terrain_features.py`): replace good/full-bad/i.i.d. modes with **Gaussian blob patches** and per-parcel strength so plots vary organically without being entirely poor or entirely good by fiat
- **`server/game/engine.py`**: send `poor_soil_tiles` only for tiles on **parcels the player owns** (no scouting via wire)
- **`client/js/renderer.js`**: remove dashed poor-soil overlay — quality is learned by owning land and tilling / `[I]`, not by map art

## [0.9.3] - 2026-04-16

### Changed
- **World generation** (`server/game/world_gen.py`): increase biome grid density (~3× non-wood wild nodes vs prior step-25 grid); increase forest grove target (~6× wood placement vs prior cluster count); commit a grove only when at least three trees place (no lone wild trees); starter tutorial wood near shops as two three-tree groves; tighten spacing between grove centers and raise placement attempt budget for the larger forest target

## [0.9.2] - 2026-04-16

### Changed
- **Documentation**: update README (version, key bindings for construction/terrain, multiplayer visibility, project file list); align `pyproject.toml` project version with `VERSION`

## [0.9.1] - 2026-04-16

### Changed
- **Other players’ wheelbarrows**: only players with an active WebSocket are included in `init` and tick payloads; on disconnect the client clears the other-players list so wheelbarrows do not linger on screen until reconnect

## [0.9.0] - 2026-04-16

### Added
- **Construction**: `[X]` cancels an active site and returns deposited materials to piles (start coins not refunded); HUD and sprite show remaining foundation/building quantities
- **Demolish**: `[D]` tears down a completed building on your tile (Town Hall excluded); partial refund to piles (75% stone/gravel/clay/dirt, 40% wood; other types use defaults); silo wheat and half of market inventory go to piles
- **Terrain**: water tiles (ponds/streams), wooden bridges, and poor-soil parcel tiles; legacy worlds get water/poor-soil seeded once if tables were empty
- **Movement**: deep water blocks travel until filled or bridged
- **Poor soil**: some parcel tiles require `[I]` with 1 dirt before tilling; **fill water** `[L]` on your land with dirt (facing); **bridges** `[J]` toward water — coin cost plus wood deposit per tile (wilderness or your land; blocked on another player’s parcel)

### Changed
- **World gen**: ~2.5× more stone/gravel/clay/dirt nodes via an extra mineral scatter pass; water and poor-soil generation integrated with fresh installs

## [0.8.1] - 2026-04-16

### Added
- **`resource_nodes.tree_variant`**: persisted tinyint for wild wood sprite choice (deciduous vs conifer families, eight shapes each); migration for existing databases
- **Forest wood clusters**: procedural groves in forest biomes (deciduous and conifer stands), higher wood caps and replenish rates than the old scattered forest grid nodes

### Changed
- **`server/game/world_gen.py`**: remove wood from the generic biome grid in forests; add `_add_forest_clusters` with jittered positions and minimum spacing between groves
- **`client/js/renderer.js`**: draw wild wood as varied tree sprites; draw **wood ground piles** as small log cross-sections (pile icon), not standing trees
- **`server/game/engine.py`**: include `tree_variant` on node wire payloads for wood nodes

## [0.8.0] - 2026-04-16

### Added
- **Sell all at NPC market (autopilot)**: on your own pile in the pile menu (`E`), use **Sell all at NPC market…** — confirm to loop: load from the pile, path to the nearest NPC market tile (Manhattan steps), sell, return to the pile until the pile is empty, then stand on the tile. A banner shows while autopilot runs; **any key except H** stops it (H still toggles HUD). Movement uses the same tick cadence as normal play; manual arrow input is blocked while autopilot runs (`Input` autopilot block + tick-aligned steps)

### Changed
- **Broken handle**: when the handle snaps (`wb_handle` = 0), you remain mobile but effective barrow capacity is **50%** of your upgraded bucket until you repair the handle at the Repair Shop; excess cargo is dropped with a dedicated notice (`bucket_cap_effective` on the wire for HUD/load speed)

## [0.7.0] - 2026-04-16

### Added
- **Staged construction** for all player-placed buildings: pay **init coins** to place a construction site, then deliver **foundation** materials (stone/gravel), then **building** materials from the barrow in multiple trips; press **[G]** on the tile to deposit whatever matches the current phase
- **`server/game/construction.py`**: shared helpers (`init_construction_state`, `deposit_all_from_bucket`, `construction_is_complete`) for foundation-then-building delivery
- **Grain silo** build: **500c** to start, **60 stone** foundation, **80 wood** building; completed silo stores **wheat** in structure inventory (capacity **5000**); **[U]** on your silo unloads wheat from the barrow into storage; **[O]** withdraws wheat from the silo into the barrow
- **Winter pile spoilage**: at the start of **winter**, **wheat** left in **ground piles** (not in a silo) rots into **compost** on the same tile; field crops still freeze as before
- **Client**: construction-site and silo sprites; build menu lists silo and updated cost copy for staged builds; `tick` / `notice` payloads can carry **structure** updates for in-progress sites

### Changed
- **Player Market**, **Town Hall**, and production structures (**stable**, **gravel pit**, **compost heap**, **topsoil mound**) now use the same staged construction rules (per-structure **init_coins**, **foundation**, and **building** tables in `STRUCTURE_DEFS`) instead of deducting full coin + material costs at once
- Game persist interval now writes **all structures** to the database (inventory/config), not only players and wild resource nodes

## [0.6.0] - 2026-04-16

### Added
- **Load-based movement speed**: empty wheelbarrow moves at full speed; heavier loads slow you down proportionally — a full load of gravel is 3× slower than an empty barrow; wood and wheat are light, stone and gravel are heavy; chassis material also contributes (steel barrow/handle adds drag, aluminium/fiberglass reduces it)
- **Named material tiers** for barrow, tire, and handle (3 tiers each, replacing the old 6-level numbered system):
  - Barrow: plastic (default) → steel (700c) → aluminium (6000c); plastic is light and doesn't rust; steel is heavier and rusts without paint; aluminium is lightest, never rusts, and barely degrades
  - Tire: regular (default) → tubeless (400c) → heavy-duty (4000c)
  - Handle: wood (default) → steel (500c) → fiberglass (4500c); steel handle is heavier; fiberglass is lightest
- **Barrow structural health** (`wb_barrow` stat, 100 = pristine): decay varies by barrow material — steel rusts when paint < 50%; plastic wears physically over time; aluminium barely degrades; shown in WB condition HUD alongside paint/tire/handle
- **`RUST` indicator** (orange) in WB HUD next to paint bar — shown only when barrow is steel and paint has dropped below 50%
- **Cargo spillage from barrow damage**: when barrow health drops below 60%, there is a small per-move chance of losing 0.5 units of cargo through a hole — scales with how degraded the barrow is; a heavily damaged barrow can lose ~10% of a full load on a long journey
- **Barrow repair at Repair Shop**: new "Repair Barrow (45c per 10%)" option; for steel barrows, repair paint first to stop the rusting, then repair structural damage
- **Market-contextual prices**: resource prices in the HUD are hidden while roaming; they appear only when standing at the NPC market or adjacent to a player market, since different markets pay different prices

### Fixed
- **Town borders crossing**: world generation now uses a two-pass Voronoi approach — all town centres are placed first, then each polygon is clipped to its Voronoi cell so boundaries never overlap
- **Wild manure and compost removed**: these resources are now exclusively produced by player-built structures (Stables and Compost Heaps)
- **Repair shop costs corrected**: cost constants now match the labels in-game (paint 30c/10%, tire 50c/10%, handle 60c/10%)

## [0.5.0] - 2026-04-16

### Added
- **Procedural world generation**: 1000×1000 tile world generated deterministically (seed 42) at first startup; never re-generated on restart; guarded by `world_gen_state` DB flag
- **Biome system**: four biomes (forest, rocky, plains, wetland) determined by smooth sinusoidal noise; each biome produces different resource types with different rates
- **~500 resource nodes** scattered via biome-aware grid, with freshness falloff — nodes farther from spawn start more depleted; guaranteed starter resources placed 50–70 tiles from spawn near NPC shops
- **40 procedurally named towns** with irregular polygon boundaries (10–18 vertices, Voronoi-like shapes, radius 80–150 tiles); names generated from adjective+noun word lists
- **~700 variable-size land parcels** (5–20 wide × 5–15 tall tiles); parcels near resource nodes cost more (`PARCEL_RESOURCE_BONUS = 150c` per node inside); wilderness parcels available outside towns
- **Parcel purchase preview**: press `B` once to highlight the parcel under your feet and see its price; press `B` again to confirm; `Esc` cancels — no blind purchases
- **Town boundary rendering**: polygon outlines drawn on the map in per-town colours with faint interior tint; town name label near each centre
- **Town crossing notification**: notice bar announces the town name (and tax rate if non-zero) when the player crosses a town boundary; persistent `in: TownName` indicator shown at bottom-left while inside a town
- **Town Hall building** (5000c + 50 stone + 50 wood + 100 dirt): establishes the player as town founder; enables town governance
- **Town governance**: town founder/leader interact with Town Hall (`E`) to set tax rate (0–30%), rename the town (once, founder only), or withdraw from treasury
- **Town sales tax**: configurable 0–30% tax applied to all player-to-player transactions (pile sales, player market trades) within a town that has a Town Hall; tax accumulates in the town treasury
- **HUD hidden by default**: game starts with a bare field view; small `[H] open hud` indicator always visible at top-left; `H` key toggles the full HUD and WB condition panels
- **Viewport culling**: tick broadcasts only send resource nodes and piles within 120 tiles of the player; all parcels and towns sent once at connection init

### Changed
- World expanded from 100×100 to 1000×1000 tiles; NPC market at (500, 560) — about 60 tiles south of spawn and not visible on screen at start
- NPC shops moved to ~56 tiles from spawn: Seed Shop (556, 500), General Store (444, 500), Repair Shop (500, 444)
- `land_parcels` table replaced by `world_parcels` with `x`, `y`, `w`, `h` columns for variable-size parcels; `town_id` FK ties parcels to towns
- `buy_parcel` action now requires `parcel_id` parameter; player must be standing on the parcel
- Parcel rendering completely rewritten: variable-size rectangles replace the old fixed 10×10 tile grid
- Server tick no longer broadcasts parcel data; clients receive all parcels once at `init` and update incrementally via `parcel_update` / `parcel_bought` events
- DB reset required (new schema, world content generated on first startup)

### Fixed
- Player username now preserved across tick updates (was being dropped since `_player_wire` omits it)

## [0.4.0] - 2026-04-15

### Added
- **Procedural world resources**: 50+ resource nodes (wood, stone, clay, dirt) scattered across the full 100×100 world; wild nodes have slow replenish rates (0.02–0.07/s) so they deplete and force players to explore further
- **Resource piling**: press `U` to unload your bucket onto owned land; piles persist in DB (`resource_piles` table)
- **Player-to-player selling**: pile owners press `E` to set a per-unit price; other players press `E` to buy up to their bucket capacity (carry limit enforced)
- **Season system**: 4 seasons × 15 min real-time = 60-min cycle; HUD shows current season and time remaining; season change broadcasts to all clients
- **Farming**: buy wheat seeds from Seed Shop (`E` near shop) → plant on owned land (`F`) → optional fertilize during growth window → harvest (`F` when ready); yields 8–16 wheat
- **NPC shops**: Seed Shop (56,50), General Store (44,50), Repair Shop (50,44) rendered on map; `E` to open shop overlay; number keys to buy
- **Wheelbarrow condition**: paint, tire, handle degrade per move; random events: flat tyre (3× slower), handle break (immobile), cargo spill through holes; all shown in new WB condition HUD (top-right)
- **Wheelbarrow upgrades** (6 levels each): barrow size (bucket 10→85), tire quality (flat chance ×0.11), handle quality (break chance ×0.10), barrow material (rust/paint decay ×0.12); bought at General Store; costs scale to 45,000–50,000c for max level — long grind for small incremental edge
- **Repair Shop**: repair paint/tire/handle by percentage at per-point cost; fix flat tyre for flat 40c fee
- **Player Market building** (2000c + 50 wood + 30 stone): owner sets buy/sell prices; other players trade at market with `E`; market holds its own inventory
- **New resource types in NPC market**: wood, stone, clay, dirt, wheat with baseline prices; market drift applies to all types
- **WB condition HUD**: top-right panel shows paint/tire/handle bars (green→yellow→red), flat tyre indicator, and current upgrade levels
- **Pocket**: separate from bucket; holds seeds and fertilizer; shown in HUD
- **Flat-tyre movement**: client-side move interval ×3 when tyre is flat (enforced via `Input.setSpeedMult`)

### Changed
- `players` table: added `pocket`, `wb_paint`, `wb_tire`, `wb_handle`, `flat_tire`, `wb_bucket_level`, `wb_tire_level`, `wb_handle_level`, `wb_barrow_level` columns (DB reset required from v0.3.x)
- `structures` table: added `inventory` and `config` JSON columns (for player market)
- NPC primary market now named distinctly from player-built markets; can never be purchased

### Fixed
- `save_player` now persists all new WB condition and upgrade fields

## [0.3.1] - 2026-04-16

### Fixed
- Replaced `passlib` with direct `bcrypt` usage to fix bcrypt 5.x compatibility error on startup
- Client API and WebSocket URLs now derived from `window.location.pathname` so the game works correctly when served from a subpath (e.g. `hromp.com/wheelbarrow/`)

### Changed
- Deployment target changed from `wheelbarrow.hromp.com` (subdomain) to `hromp.com/wheelbarrow/` (subpath) — no new DNS record or TLS certificate required
- Deploy config updated: replaced standalone nginx server block with a location block snippet to add to the existing `00-hromp.com.conf`

## [0.3.0] - 2026-04-15

### Added
- **Auth**: password-based accounts using bcrypt; new username+password = new account, returning players verify on login; legacy accounts (no password) adopt the first password used
- **Land system**: world divided into 10×10 tile parcels; players buy parcels for 500 coins with `[B]`; owned parcels rendered with colored overlay and owner name; faint parcel grid lines across the whole world
- **Building system**: players build structures on owned land with `[P]` build menu + number keys; four structure types: Horse Stable, Gravel Pit, Compost Heap, Topsoil Mound; each has coin + resource costs and produces a specific resource type; other players collect from structures, earning the owner 1 coin per collection
- **Market price drift**: prices adjust every 60 seconds based on sales volume; high supply pushes prices down, low supply lets them recover toward baseline
- **Notice bar**: transient on-screen messages for sell confirmations, land purchases, build results, and error feedback
- **Deploy config**: `deploy/wheelbarrow.hromp.com.nginx.conf` nginx vhost with WebSocket proxy headers; `deploy/README.md` with full step-by-step deployment instructions for `romptele.com`
- `passlib[bcrypt]` dependency

### Changed
- Login form now requires a password field
- `players` table: added `password_hash` column (requires DB volume reset from v0.2.0)
- HUD: added market prices panel, contextual hints now cover buy/build/collect/sell states
- `wheelbarrow.service`: updated to run via `docker compose` rather than direct uvicorn

## [0.2.0] - 2026-04-15

### Added
- Docker containerization: `Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`
- `wheelbarrow.service` updated to run via `docker compose` instead of direct uvicorn
- MariaDB schema (`db/init.sql`): players, resource_nodes, land_parcels, structures, market_prices tables
- Seeded 8 starting resource nodes (manure, gravel, topsoil, compost) and starting market prices
- Full FastAPI server: `/api/login` endpoint, `/ws` WebSocket endpoint, async game loop
- In-memory `GameEngine`: player sessions, movement, proximity-based resource collection, selling at market
- Server-side game tick (100ms movement, 5s resource accumulation, 10s DB persist)
- HTML5 Canvas client: login screen, real-time tile-based world renderer, arrow key movement
- HUD: coins, bucket contents, fill bar, contextual hints (collecting / sell prompt)
- WebSocket protocol: `init`, `tick`, `move`, `sell`, `sold` message types
- `requirements.txt` and `pydantic-settings` dependency

## [0.1.0] - 2026-04-15

### Added
- Initial project scaffold: FastAPI backend, WebSocket support, HTML5 Canvas frontend structure
- Core Python domain model: `Wheelbarrow`, `Wheel`, `Bucket`, `Handle`, `SupportFrame`, `Cargo`, `Component` classes with full behavior (loading, unloading, pushing, tipping, wear, repair)
- `Condition` and `Material` enums with condition degradation progression
- `build_my_wheelbarrow()` factory function
- Project structure: `server/`, `client/`, `wheelbarrow/` layout
- `pyproject.toml` with version tracking
- `wheelbarrow.service` systemd unit template for deployment on `romptele.com`
- `.env.example` for environment configuration
- `README.md` with gameplay description, tech stack, project structure, and setup instructions
