# Deploying Wheelbarrow to romptele.com

Live at: **https://hromp.com/wheelbarrow/**

Runs as a Docker container on `henry@romptele.com`, proxied by the existing
nginx vhost for `hromp.com`. No new DNS record or TLS certificate needed.

## 1. Clone the repo on the server

```bash
cd /home/henry
git clone https://github.com/151henry151/wheelbarrow.git
cd wheelbarrow
```

## 2. Create the .env file

```bash
cp .env.example .env
nano .env   # set strong DB_PASSWORD, DB_ROOT_PASSWORD, SECRET_KEY
chmod 600 .env
```

## 3. Add the nginx location block

Open `/etc/nginx/conf.d/00-hromp.com.conf` and paste the contents of
`deploy/wheelbarrow.nginx.location.conf` inside the existing HTTPS server block
(anywhere alongside the other `location` blocks):

```bash
sudo nano /etc/nginx/conf.d/00-hromp.com.conf
# paste the two location blocks from deploy/wheelbarrow.nginx.location.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 4. Install and start the systemd service

```bash
sudo cp wheelbarrow.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wheelbarrow
sudo systemctl start wheelbarrow
```

## 5. Verify

```bash
sudo systemctl status wheelbarrow
sudo docker ps
curl -s https://hromp.com/wheelbarrow/api/login \
  -X POST -H 'Content-Type: application/json' \
  -d '{"username":"test","password":"test"}' | python3 -m json.tool
```

Then open **https://hromp.com/wheelbarrow/** in a browser.

## Updating

```bash
cd /home/henry/wheelbarrow
git pull
sudo systemctl restart wheelbarrow
```

The MariaDB volume (`db_data`) persists across restarts — player data is safe.

### Terrain migrations (poor soil / water)

After pulling a release that changes **water** or **poor-soil** logic:

1. **Rebuild** the app image if the Dockerfile or dependencies changed; otherwise a restart loads new Python:
   ```bash
   cd /home/henry/wheelbarrow
   docker compose build
   ```

2. **Poor soil** (replace all tiles with the current algorithm — run once per upgrade that needs it):
   ```bash
   docker compose run --rm app python scripts/regenerate_poor_soil.py
   ```

3. **Resource nodes** (add wild nodes on top of an existing world — run when world gen density was increased; safe to skip on fresh installs):
   ```bash
   docker compose run --rm app python scripts/densify_resource_nodes.py
   ```

4. **Spawn-ring water** (optional — adds ponds just outside the spawn exclusion so water appears sooner when exploring; idempotent `INSERT IGNORE`):
   ```bash
   docker compose run --rm app python scripts/seed_spawn_ring_water.py
   ```

5. **Major rivers** (optional — long 4–8-tile-wide rivers through many towns; idempotent `INSERT IGNORE`; run once after upgrading from worlds that only had ponds/streams):
   ```bash
   docker compose run --rm app python scripts/add_major_rivers.py
   ```

6. **Restart** the service so the game process reloads terrain from the database:
   ```bash
   sudo systemctl restart wheelbarrow
   ```

**Water:** If `water_tiles` was empty (e.g. older bug), a normal restart after upgrading the server code seeds ponds/streams automatically. If you already have water and only changed unrelated code, skip re-seeding.

Run steps 2–5 only when the release notes require them; always end with **step 6** (restart).

## Resetting the database (destroys all data)

```bash
sudo docker compose down -v
sudo docker compose up -d
```
