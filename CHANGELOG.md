# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
