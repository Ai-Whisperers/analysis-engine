#!/bin/bash
# Setup script for Oracle Cloud Free Tier deployment
# Run this once on fresh Oracle Cloud VM

set -e

echo "=== Dataset Analyzer - Oracle Cloud Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

echo "Step 1: System Update"
apt-get update
apt-get upgrade -y

echo ""
echo "Step 2: Install Docker"
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Add user to docker group
usermod -aG docker ubuntu

# Start Docker
systemctl enable docker
systemctl start docker

echo ""
echo "Step 3: Install Docker Compose"
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

echo ""
echo "Step 4: Install Nginx"
apt-get install -y nginx

echo ""
echo "Step 5: Install Certbot (Let's Encrypt)"
apt-get install -y certbot python3-certbot-nginx

echo ""
echo "Step 6: Create application directory"
mkdir -p /opt/dataset-analyzer
mkdir -p /data/uploads
mkdir -p /data/processed
mkdir -p /data/models

echo ""
echo "Step 7: Configure firewall"
# Allow HTTP, HTTPS, SSH
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo ""
echo "Step 8: Configure system limits"
# Increase file limits
cat >> /etc/security/limits.conf <<EOF
* soft nofile 65536
* hard nofile 65536
EOF

# Increase max map count (for performance)
echo "vm.max_map_count=262144" >> /etc/sysctl.conf
sysctl -p

echo ""
echo "Step 9: Setup swap (for 1GB RAM VMs)"
# Create 2GB swap file
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Optimize swap usage
echo "vm.swappiness=10" >> /etc/sysctl.conf
sysctl -p

echo ""
echo "Step 10: Clone repository"
cd /opt/dataset-analyzer
# User will need to clone their repo manually with credentials
echo "Please clone your repository to /opt/dataset-analyzer"
echo "Example: git clone https://github.com/your-username/dataset-analyzer.git ."

echo ""
echo "Step 11: Setup SSL certificate (Let's Encrypt)"
echo "Run after DNS is configured:"
echo "  certbot --nginx -d your-domain.com"

echo ""
echo "Step 12: Create environment file"
cat > /opt/dataset-analyzer/.env.prod <<EOF
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE_MB=100
RATE_LIMIT_REQUESTS_PER_MINUTE=100
GRAFANA_PASSWORD=changeme
EOF

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Next steps:"
echo "1. Configure DNS to point to this server"
echo "2. Clone your repository to /opt/dataset-analyzer"
echo "3. Run: certbot --nginx -d your-domain.com"
echo "4. Start services: cd /opt/dataset-analyzer && docker-compose -f deployment/docker-compose.prod.yml up -d"
echo "5. Check health: curl http://localhost:8000/health"
echo ""
echo "Monitoring URLs:"
echo "  - Grafana: http://your-domain.com:3000 (admin/changeme)"
echo "  - Prometheus: http://your-domain.com:9090"
echo "  - Jaeger: http://your-domain.com:16686"
echo ""
echo "Cost: $0/month (Oracle Cloud Always Free Tier)"
echo ""
