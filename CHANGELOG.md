# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
