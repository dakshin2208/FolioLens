#!/bin/bash
# EC2 launch script for Amazon Linux 2023: Docker, Compose, Buildx, git, cron and 2 GB of swap.
set -euxo pipefail
dnf update -y
dnf install -y docker git cronie
systemctl enable --now docker crond
usermod -aG docker ec2-user

# Docker Compose and Buildx plugins
ARCH=$(uname -m); BX_ARCH=$([ "$ARCH" = aarch64 ] && echo arm64 || echo amd64)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$ARCH" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
BX_TAG=$(curl -fsSL https://api.github.com/repos/docker/buildx/releases/latest | grep -m1 tag_name | cut -d '"' -f4)
curl -fsSL "https://github.com/docker/buildx/releases/download/$BX_TAG/buildx-$BX_TAG.linux-$BX_ARCH" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-*

# 2 GB swap: building the images on a 2 GB server needs the headroom
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

mkdir -p /opt/foliolens && chown ec2-user:ec2-user /opt/foliolens
