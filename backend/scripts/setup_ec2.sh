#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Clearbook EC2 setup script — Amazon Linux 2023, t3.micro (AWS free tier)
#
# Usage:
#   chmod +x setup_ec2.sh
#   ./setup_ec2.sh <duckdns-subdomain> <duckdns-token>
#
# Example:
#   ./setup_ec2.sh clearbook-demo abc12345-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# ─────────────────────────────────────────────────────────────────────────────
set -e

SUBDOMAIN=$1
DUCKDNS_TOKEN=$2

if [ -z "$SUBDOMAIN" ] || [ -z "$DUCKDNS_TOKEN" ]; then
  echo "Usage: ./setup_ec2.sh <duckdns-subdomain> <duckdns-token>"
  exit 1
fi

DOMAIN="${SUBDOMAIN}.duckdns.org"
echo "Setting up Clearbook backend for: $DOMAIN"

# ── Step 1: System packages ───────────────────────────────────────────────────
echo "[1/7] Installing system packages..."
sudo dnf update -y
sudo dnf install -y docker nginx certbot python3-certbot-nginx git curl

# ── Step 2: Docker ────────────────────────────────────────────────────────────
echo "[2/7] Configuring Docker..."
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user

# Docker Compose v2
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# ── Step 3: DuckDNS ───────────────────────────────────────────────────────────
echo "[3/7] Setting up DuckDNS dynamic DNS..."
mkdir -p ~/duckdns
cat > ~/duckdns/duck.sh << EOF
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=" | curl -k -o ~/duckdns/duck.log -K -
EOF
chmod +x ~/duckdns/duck.sh
~/duckdns/duck.sh   # run once immediately to register IP

# Cron every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
echo "DuckDNS configured. IP registered for $DOMAIN"

# ── Step 4: Nginx HTTP (needed for Certbot challenge) ─────────────────────────
echo "[4/7] Configuring Nginx for Certbot challenge..."
sudo tee /etc/nginx/conf.d/clearbook.conf > /dev/null << EOF
server {
    listen 80;
    server_name ${DOMAIN};
    location / { return 200 'ok'; }
}
EOF
sudo systemctl enable nginx
sudo systemctl restart nginx

# ── Step 5: Let's Encrypt SSL ─────────────────────────────────────────────────
echo "[5/7] Obtaining Let's Encrypt SSL certificate..."
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
  -m "admin@${SUBDOMAIN}.duckdns.org" --redirect

# ── Step 6: Full Nginx config with WebSocket support ─────────────────────────
echo "[6/7] Writing production Nginx config..."
sudo tee /etc/nginx/conf.d/clearbook.conf > /dev/null << EOF
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # WebSocket tunnel — extended timeouts critical
    location /api/v1/tally/ws/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_read_timeout  3600s;
        proxy_send_timeout  3600s;
    }

    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
    }
}
EOF
sudo nginx -t && sudo systemctl reload nginx

# ── Step 7: App directory and .env template ───────────────────────────────────
echo "[7/7] Creating app directory and .env template..."
sudo mkdir -p /app/clearbook
sudo chown ec2-user:ec2-user /app/clearbook

cat > /app/clearbook/.env << EOF
# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://clearbook:CHANGE_ME@YOUR_RDS_ENDPOINT:5432/clearbook

# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY=CHANGE_ME_TO_A_LONG_RANDOM_STRING
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ── Environment ───────────────────────────────────────────────────────────────
ENV=production
CORS_ORIGINS=["https://YOUR_VERCEL_APP.vercel.app"]

# ── AWS ───────────────────────────────────────────────────────────────────────
AWS_REGION=ap-south-1
S3_BUCKET=clearbook-documents

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
EOF

echo ""
echo "════════════════════════════════════════════════════════════"
echo " Clearbook EC2 setup complete!"
echo "════════════════════════════════════════════════════════════"
echo " Backend URL : https://${DOMAIN}"
echo ""
echo " Next steps:"
echo "   1. Edit /app/clearbook/.env — fill in DATABASE_URL, SECRET_KEY, etc."
echo "   2. Add these GitHub Secrets to your repo:"
echo "      EC2_HOST        = ${DOMAIN}"
echo "      EC2_USER        = ec2-user"
echo "      EC2_SSH_KEY     = (contents of your .pem file)"
echo "      AWS_ACCOUNT_ID  = (your AWS account ID)"
echo "      AWS_REGION      = ap-south-1"
echo "   3. Set Vercel env var:"
echo "      NEXT_PUBLIC_API_URL = https://${DOMAIN}"
echo "   4. Push to main to trigger first deploy."
echo "════════════════════════════════════════════════════════════"