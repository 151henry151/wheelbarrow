# Wheelbarrow

A real-time browser-based MMO where you are a wheelbarrow.

You spawn in a field with nothing. You roll around a shared persistent world, gathering resources by parking near them, hauling loads to market, earning money, buying land, building infrastructure, and farming. The world keeps running — and your structures keep earning — even when you're not playing.

Inspired by the spirit of [A Tractor](https://store.steampowered.com/app/779050/A_tractor/) — a semi-serious social-economic simulation — but you're a wheelbarrow.

**Live at:** https://hromp.com/wheelbarrow/

---

## Gameplay

### The basics
- Move with **arrow keys** or **WASD** — speed depends on your load; heavier materials (gravel, stone) slow you significantly; an empty aluminium barrow is faster than a loaded plastic one
- **Other players** only appear while they have an active browser session; when someone disconnects, their wheelbarrow disappears from your view until they log in again (their land and piles stay in the world)
- **Pull up within one tile** (Chebyshev distance) of a **wild resource node** or a **free pile**, then press **`[1]`–`[9]`** as shown in the HUD to **start** loading; stay in range until your barrow is full or press **`[V]`** to stop. Multiple nearby sources list separate number keys.
- **Haul your load** to the NPC market (`50,60`) and press **Space** to sell; on a **large pile of your own** (`E` → **Sell all at NPC market…**), confirm to autopilot load → sell → repeat until the pile is empty (**any key except H** cancels)
- Wild resources **deplete** over time, forcing you to travel further from spawn to find fresh nodes
- The server runs 24/7 — park near resources before logging off and collect the difference when you return

### Key bindings

| Key | Action |
|---|---|
| Arrow keys / **WASD** | Move |
| Space | Sell at NPC market |
| B | Preview parcel under your feet; press B again to confirm purchase |
| P | Open build menu (on own land) |
| U | Unload bucket — resource pile on own land; **wheat** goes into a **completed silo** if you stand on your silo |
| G | Deliver barrow materials to a **construction site** under your feet (your own site); HUD shows remaining foundation/building amounts |
| X | **Cancel construction** on your site — returns deposited materials to piles (starting coins not refunded) |
| K | **Tear down** a completed building on your tile (Town Hall excluded) — partial material refund to piles |
| I | **Improve poor soil** — spread 1 **dirt** from the barrow on a parcel tile that needs it before you can till |
| L | **Fill water** — face an adjacent water tile on **your** land; consumes 1 dirt from the barrow |
| J | **Bridge** — face a water tile; pay coin cost once per tile, then deliver wood until the bridge completes (not on another player’s land) |
| O | Withdraw **wheat** from your **silo** into the barrow |
| E | Context interact — town hall / NPC shop / **pile menu** (set prices, buy, or **Sell all at NPC market** autopilot on your piles) / trade at player market |
| F | Farm action — plant wheat (spring only) / fertilize / harvest / till (not in winter — ground frozen) |
| Drag | Orbit: **horizontal** spin + **vertical** tilt (hold left mouse — up/down looks more top-down or flatter) |
| Mouse wheel | Zoom camera in / out |
| [ | Nudge view more overhead (toward top-down) |
| ] | Nudge view flatter (more horizon) |
| H | Toggle HUD (hidden by default — just press H to see it) |
| 1–9 | **Start loading** from a listed wild node or pile (when no menu is open — HUD shows which number is which), or select an item in an open menu |
| V | **Stop** loading into the barrow (while a load is active) |
| Esc | Cancel parcel preview / close menu |

### The economy ladder
1. **Spawn** — explore outwards to find resources; the starting field is intentionally bare
2. **Sell** at the NPC primary market (about 60 tiles south of spawn); prices drift based on supply
3. **Buy land** — parcels are variable size and price; press B once to preview the outline and price, B again to buy (parcel outlines on the 3D map only show **on the parcel you’re standing on**, or while **previewing** with B)
4. **Pile resources** on your land (`U`), set a sell price (`E`), and let other players buy from you — no market building required
5. **Build structures** — pay the **starting coin** cost to place a **construction site**, then carry **foundation** and **building** materials to the tile and press **`G`** to deliver each load until the building completes (horse stable, gravel pit, compost heap, topsoil mound, **player market**, **town hall**, **grain silo**). Use **`X`** to cancel a site and recover deposited materials (coins spent to start are not refunded).
6. **Build a Player Market** — **2000c** to start the site, then staged stone/wood delivery — set custom buy and sell prices for any goods; the most powerful economic tool in the game
7. **Farm wheat** — buy seeds from the Seed Shop, **plant only in spring** on owned tilled land, optionally **fertilize** within the time window for double yield using **NPC fertilizer**, **compost** (from a compost heap or piles), or **manure** (from a stable); harvest in ~10–20 min; **uncovered wheat piles rot into compost in winter** — store grain in a **silo** to protect it
8. **Build a Grain Silo** — **500c** to start, **60 stone** + **80 wood** delivered in trips; unload wheat with **`U`** on the silo, retrieve with **`O`**
9. **Build a Town Hall** — **5000c** to start the site, then staged foundation and building materials — become a town's founder: name it, set a sales tax (0–30%), and govern which structures and goods are allowed
10. **Upgrade your wheelbarrow** at the General Store — larger bucket (6 tiers), tire type (regular → tubeless → heavy-duty), handle material (wood → steel → fiberglass), and barrow material (plastic → steel → aluminium); material choices affect both speed and maintenance

### Wheelbarrow condition
Your wheelbarrow degrades as you move:
- **Paint** fades — when it drops below 50% on a **steel** barrow, the metal starts to rust
- **Barrow** (structural) — plastic wears physically over time; steel rusts when paint is low (repair paint first); aluminium barely degrades; when below 60%, cargo can spill during long journeys
- **Tyre** wears — random flat tyre when condition is low; flat tyre triples move time until repaired
- **Handle** wears — random snap when condition is low; a snapped handle limits you to **50% of your normal bucket capacity** until you repair it at the Repair Shop (you can still move)

Repair all components at the **Repair Shop** (500, 444). Upgrades reduce wear rates.

### Barrow materials and speed
Your choice of barrow material, handle material, and current load all affect movement speed:
- **Gravel and stone** are the heaviest loads; **wood and wheat** are light
- **Steel** barrow and handle are heavier than plastic/wood — slower even when empty, but more durable
- **Aluminium** barrow and **fiberglass** handle are lighter than plastic/wood — faster and virtually maintenance-free, but expensive

### Towns
The world contains 40 procedurally generated towns with irregular polygon boundaries and names like "Greenford" or "Ironwick". Entering a town shows its name and any sales tax. Town leaders govern through the Town Hall:

- Set sales tax (0–30%) on player-to-player transactions in the town
- Rename the town (founder only, once)
- Withdraw accumulated taxes from the treasury
- (Future: ban structures/goods, hold elections among landowners)

### NPC shops
All NPC shops are ~56 tiles from spawn — not visible at the starting field. Explore to find them.

| Shop | Location | Sells |
|---|---|---|
| Seed Shop | (556, 500) | Wheat seeds, fertilizer |
| General Store | (444, 500) | Wheelbarrow upgrades (bucket: 6 tiers; tire/handle/barrow: 3 named tiers) |
| Repair Shop | (500, 444) | Condition repairs, flat tyre fix |

### Water, bridges, and soil
- **Water** (ponds and streams) blocks movement until you **fill** a tile on land you own (**`L`** with dirt) or build a **wooden bridge** across it (**`J`**, facing the water; coin + wood per tile). You cannot bridge over another player’s parcel.
- Some purchased **parcel tiles** are **poor soil** (patchy, random per plot) — you cannot see which tiles are poor until you **own** the parcel; till then fails with a notice until you deposit **1 dirt** per tile (**`I`**).

### Seasons
The year cycles through **Spring → Summer → Fall → Winter** (15 minutes each). **Planting wheat** is allowed **only in spring**. In **winter** the **ground is frozen** — you cannot **[F]** till untilled soil or clear **frost-killed** stubble until **spring**; tilled plots also wait until spring to plant. **Winter** kills crops still in the field; **wheat** left in **piles** on the ground rots into **compost** — **silos** keep stored wheat safe. You cannot **[F]** till or plant on a tile until **ground piles** on that tile are cleared (load into your barrow), including compost from rotted wheat.

### Resource types
| Resource | Where | NPC price | Notes |
|---|---|---|---|
| Manure | Horse stables (player-built) | 2c | Only from stables — not found in the wild |
| Gravel | Rocky biomes, gravel pits | 3c | Needed for gravel pit build |
| Topsoil | Plains and wetland biomes | 3c | Needed for topsoil mound build |
| Compost | Compost heaps (player-built) | 4c | Only from compost heaps — not found in the wild |
| Wood | Forest biomes (trees only in groves of 3+; ~higher density on fresh worlds) | 3c | Needed for many builds and bridges |
| Stone | Map edges | 4c | Needed for Player Market build; very slow replenish |
| Clay | Mid-map | 2.5c | Moderate replenish |
| Dirt | Widespread | 1c | Low value, fast replenish |
| Wheat | Farmed | 5c | Needs farming skill |

**Fresh database / first seed:** biomes include a wide **forest** band plus **meadow copses** (clustered trees on plains/wetland); the grid is dense and often drops the four base **minerals** (stone, gravel, clay, dirt) in any biome so nearby tiles are not empty. **Existing** live worlds: after upgrading, run `scripts/densify_resource_nodes.py` once (see `deploy/README.md`) to add nodes without resetting the database.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, WebSockets |
| Game loop | asyncio server-side tick |
| Database | MariaDB |
| Frontend | HTML5 Canvas + Three.js (WebGL), vanilla JavaScript — **sky/horizon** via scene background + fog (seasonal tints), not the grass color |
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
│   │   ├── construction.py # Staged building (foundation + materials)
│   │   ├── terrain_features.py # Water, poor-soil marks (world gen + legacy seed)
│   │   ├── seasons.py    # Season clock
│   │   ├── wb_condition.py # Wheelbarrow condition/decay
│   │   └── world_gen.py  # Procedural world generation (runs once at startup)
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

The public game is served at **https://hromp.com/wheelbarrow/** (path on the main `hromp.com` vhost) via a systemd service behind nginx.

See `wheelbarrow.service` for the service unit template. Deployment is handled manually via SSH to `henry@romptele.com`. Additional notes live in `deploy/README.md`.

---

## Version

Current version: **0.10.4** (see `VERSION`, `pyproject.toml`, and cache-bust query on scripts in `client/index.html`). See [CHANGELOG.md](CHANGELOG.md).
