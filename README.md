# Wheelbarrow

A real-time browser-based MMO where you are a wheelbarrow.

You spawn in a field with nothing. You roll around a shared persistent world, gathering resources by parking near them, hauling loads to market, earning money, buying land, building infrastructure, and farming. The world keeps running — and your structures keep earning — even when you're not playing.

Inspired by the spirit of [A Tractor](https://store.steampowered.com/app/779050/A_tractor/) — a semi-serious social-economic simulation — but you're a wheelbarrow.

**Live at:** https://hromp.com/wheelbarrow/

---

## Gameplay

### The basics
- Move with **arrow keys** (slower when you have a flat tyre)
- **Park near a resource** and your bucket slowly fills — proximity collection is passive
- **Haul your load** to the NPC market (`50,60`) and press **Space** to sell
- Wild resources **deplete** over time, forcing you to travel further from spawn to find fresh nodes
- The server runs 24/7 — park near resources before logging off and collect the difference when you return

### Key bindings

| Key | Action |
|---|---|
| Arrow keys | Move |
| Space | Sell at NPC market |
| B | Buy current land parcel (500c) |
| P | Open build menu (on own land) |
| U | Unload bucket to resource pile (on own land) |
| E | Context interact — open NPC shop / manage pile prices / trade at player market |
| F | Farm action — plant wheat / fertilize / harvest |
| 1–9 | Select item in any open menu |
| Esc | Close menu |

### The economy ladder
1. **Spawn** — collect free resources near spawn (manure, gravel, topsoil, compost)
2. **Sell** at the NPC primary market; prices drift based on supply
3. **Buy land** — 500c per 10×10 parcel
4. **Pile resources** on your land (`U`), set a sell price (`E`), and let other players buy from you — no market building required
5. **Build structures** — horse stable, gravel pit, compost heap; other players pay you a fee when they collect
6. **Build a Player Market** (2000c + 50 wood + 30 stone) — set custom buy and sell prices for any goods; the most powerful economic tool in the game
7. **Farm wheat** — buy seeds from the Seed Shop, plant on owned land, optionally fertilize for double yield, harvest in ~10–20 min
8. **Upgrade your wheelbarrow** at the General Store — larger bucket, better tyres, stronger handle, better barrow material (6 levels each, very expensive at top end)

### Wheelbarrow condition
Your wheelbarrow degrades as you move:
- **Paint** fades — eventual holes cause cargo to spill while moving (buy stainless barrow to slow this)
- **Tyre** wears — random flat tyre when condition is low; flat tyre triples move time until repaired
- **Handle** wears — random break when condition is low; broken handle = immobile until repaired

Repair at the **Repair Shop** (50,44). Upgrades reduce wear rates.

### NPC shops
| Shop | Location | Sells |
|---|---|---|
| Seed Shop | (56,50) | Wheat seeds, fertilizer |
| General Store | (44,50) | Wheelbarrow upgrades (6 levels each) |
| Repair Shop | (50,44) | Condition repairs, flat tyre fix |

### Seasons
The year cycles through **Spring → Summer → Fall → Winter** (15 minutes each). Farming is tuned around the season cycle; the current season and time remaining are shown in the HUD.

### Resource types
| Resource | Where | NPC price | Notes |
|---|---|---|---|
| Manure | Near spawn, horse stables | 2c | Starter resource |
| Gravel | Near spawn, gravel pits | 3c | Needed for gravel pit build |
| Topsoil | Near spawn | 3c | Needed for topsoil mound build |
| Compost | Near spawn | 4c | High replenish cost structure |
| Wood | Forest corners | 3c | Needed for Player Market build |
| Stone | Map edges | 4c | Needed for Player Market build; very slow replenish |
| Clay | Mid-map | 2.5c | Moderate replenish |
| Dirt | Widespread | 1c | Low value, fast replenish |
| Wheat | Farmed | 5c | Needs farming skill |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, WebSockets |
| Game loop | asyncio server-side tick |
| Database | MariaDB |
| Frontend | HTML5 Canvas, vanilla JavaScript |
| Server | Debian 12, nginx reverse proxy |
| Domain | [hromp.com/wheelbarrow/](https://hromp.com/wheelbarrow/) |

---

## Project Structure

```
wheelbarrow/
├── server/
│   ├── main.py           # FastAPI app, REST + WebSocket endpoints
│   ├── config.py         # Settings (env vars)
│   ├── game/
│   │   ├── engine.py     # In-memory game state, all game actions
│   │   ├── tick.py       # Server-side game loop (asyncio)
│   │   ├── constants.py  # Game constants and definitions
│   │   ├── seasons.py    # Season clock
│   │   └── wb_condition.py # Wheelbarrow condition/decay
│   └── db/
│       ├── connection.py # aiomysql connection pool
│       └── queries.py    # All DB queries
├── db/
│   └── init.sql          # MariaDB schema + seed data
├── client/
│   ├── index.html
│   ├── js/
│   │   ├── game.js       # Main client loop, HUD, key bindings
│   │   ├── renderer.js   # Canvas rendering
│   │   ├── input.js      # Arrow key input with speed multiplier
│   │   └── ws.js         # WebSocket client
│   └── css/
│       └── style.css
├── deploy/               # nginx config, deploy README
├── Dockerfile
├── docker-compose.yml
├── wheelbarrow.service   # systemd unit
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## Development Setup

```bash
git clone https://github.com/151henry151/wheelbarrow.git
cd wheelbarrow
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env with your local DB credentials
uvicorn server.main:app --reload
```

Open `http://localhost:8000` in a browser.

---

## Deployment

The game runs on `wheelbarrow.hromp.com` via a systemd service behind nginx.

See `wheelbarrow.service` for the service unit template. Deployment is handled manually via SSH to `henry@romptele.com`.

---

## Version

Current version: **0.4.0**. See [CHANGELOG.md](CHANGELOG.md).
