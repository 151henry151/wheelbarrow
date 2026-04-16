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

## Resetting the database (destroys all data)

```bash
sudo docker compose down -v
sudo docker compose up -d
```
