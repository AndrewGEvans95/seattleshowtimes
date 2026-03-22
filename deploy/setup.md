# DigitalOcean Deployment

## 1. Create Droplet
- Ubuntu 24.04 LTS, $6/mo Basic (1 vCPU, 1GB RAM) is sufficient
- Enable SSH key auth

## 2. Server Setup
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx
```

## 3. Deploy App
```bash
sudo mkdir -p /var/www/seattleshowtimes
sudo chown $USER:$USER /var/www/seattleshowtimes
cd /var/www/seattleshowtimes

git clone https://github.com/AndrewGEvans95/seattleshowtimes.git .

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

mkdir -p data
```

## 4. Configure Nginx
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/seattleshowtimes
sudo ln -s /etc/nginx/sites-available/seattleshowtimes /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 5. SSL via Let's Encrypt
```bash
# Point your domain DNS A record to the droplet IP first, then:
sudo certbot --nginx -d seattleshowtimes.com -d www.seattleshowtimes.com
```

## 6. Systemd Service
```bash
sudo cp deploy/seattleshowtimes.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable seattleshowtimes
sudo systemctl start seattleshowtimes
sudo systemctl status seattleshowtimes
```

## 7. Logs
```bash
# App logs
sudo journalctl -u seattleshowtimes -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 8. Updating
```bash
cd /var/www/seattleshowtimes
git pull
sudo systemctl restart seattleshowtimes
```
