# Deploying Wheelbarrow to romptele.com

Target: `wheelbarrow.hromp.com` → Docker container on `henry@romptele.com`

## 1. Clone the repo on the server

```bash
cd /home/henry
git clone https://github.com/151henry151/wheelbarrow.git
cd wheelbarrow
```

## 2. Create the .env file

```bash
cp .env.example .env
nano .env   # set strong passwords for DB_PASSWORD and DB_ROOT_PASSWORD, and SECRET_KEY
```

## 3. Get a TLS certificate

The existing `hromp.com` cert does not cover `wheelbarrow.hromp.com`. Issue a new one:

```bash
sudo certbot certonly --nginx -d wheelbarrow.hromp.com
```

Certbot will write the cert to `/etc/letsencrypt/live/wheelbarrow.hromp.com/`.

## 4. Install the nginx vhost

```bash
sudo cp deploy/wheelbarrow.hromp.com.nginx.conf /etc/nginx/conf.d/wheelbarrow.hromp.com.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 5. Install the systemd service

```bash
sudo cp wheelbarrow.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wheelbarrow
sudo systemctl start wheelbarrow
```

## 6. Verify

```bash
sudo systemctl status wheelbarrow
sudo docker ps
curl -s https://wheelbarrow.hromp.com/api/login -X POST \
  -H 'Content-Type: application/json' \
  -d '{"username":"test","password":"test"}' | python3 -m json.tool
```

## Updating

```bash
cd /home/henry/wheelbarrow
git pull
sudo systemctl restart wheelbarrow
```

Docker will rebuild and restart the containers. The MariaDB volume (`db_data`) persists across restarts — player data is safe.

## Resetting the database (dev only)

**This destroys all game data:**
```bash
sudo docker compose down -v
sudo docker compose up -d
```
