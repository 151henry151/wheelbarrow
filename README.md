# Wheelbarrow

A real-time browser-based MMO where you are a wheelbarrow.

You spawn in a field with nothing. You roll around a shared persistent world, gathering resources by parking near them, hauling loads to market, earning money, buying land, and slowly building up infrastructure that other players depend on. The world keeps running — and your structures keep earning — even when you're not playing.

Inspired by the spirit of [A Tractor](https://store.steampowered.com/app/779050/A_tractor/) — a semi-serious social-economic simulation — but you're a wheelbarrow.

---

## Gameplay

### The basics
- Move your wheelbarrow around the world with the **arrow keys**
- **Park near a resource** (a manure patch, a gravel pile, loose soil) and your bucket slowly fills up over time
- **Haul your load** to a market stall and sell it for coins
- The world keeps ticking on the server whether you're logged in or not — park strategically before you log off

### The economy ladder
1. **Spawn** in an open field with an empty bucket and no money
2. **Find free resources** — wild manure patches, loose gravel, and scattered soil exist in the starting zone so new players can always bootstrap
3. **Sell at the market** — prices fluctuate based on supply and demand from all players
4. **Buy land** — save up enough coins to purchase a parcel; you can only build on land you own
5. **Build structures** — a horse stable generates manure; a gravel pit generates gravel; a compost heap generates compost. Building takes time and resources
6. **Earn passive income** — other players park next to your structures to collect resources and pay you a small fee. Your infrastructure serves the whole server

### Key mechanics
- **Proximity collection** — you don't click to collect; you just roll up and wait. The closer and longer you stay, the more you gather
- **Bucket capacity** — your wheelbarrow has limited carrying capacity; upgrade it to haul more per trip
- **Offline persistence** — the server runs the world 24/7. Log in after a long absence and collect everything that accumulated while you were away (up to your bucket cap)
- **Player-driven world** — early players build the infrastructure new players depend on. The map fills up organically over time

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, WebSockets |
| Game loop | asyncio server-side tick |
| Database | MariaDB |
| Frontend | HTML5 Canvas, vanilla JavaScript |
| Server | Debian 12, nginx reverse proxy |
| Domain | [wheelbarrow.hromp.com](https://wheelbarrow.hromp.com) |

---

## Project Structure

```
wheelbarrow/
├── server/
│   ├── main.py          # FastAPI app entry point
│   ├── game/
│   │   ├── world.py     # World map, tiles, resource nodes
│   │   ├── player.py    # Player/wheelbarrow state
│   │   ├── tick.py      # Server-side game loop
│   │   └── economy.py   # Market prices, transactions, land
│   └── db/
│       └── models.py    # MariaDB schema and queries
├── client/
│   ├── index.html       # Game shell
│   ├── js/
│   │   ├── game.js      # Main client game loop
│   │   ├── renderer.js  # Canvas rendering
│   │   ├── input.js     # Arrow key / input handling
│   │   └── ws.js        # WebSocket client
│   └── css/
│       └── style.css
├── wheelbarrow/
│   └── wheelbarrow.py   # Python model of a wheelbarrow (core domain objects)
├── pyproject.toml
├── requirements.txt
├── .env.example
└── wheelbarrow.service  # systemd service template
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

Current version: **0.1.0** — initial project scaffold. See [CHANGELOG.md](CHANGELOG.md).
