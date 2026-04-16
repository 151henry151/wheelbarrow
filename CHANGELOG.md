# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
