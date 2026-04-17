# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
