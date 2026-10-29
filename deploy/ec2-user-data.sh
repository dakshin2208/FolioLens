#!/bin/bash
# EC2 launch script for Amazon Linux 2023: installs Docker, Compose and git.
set -euxo pipefail
dnf update -y
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
curl -fsSL "https://github.com/docker/buildx/releases/latest/download/buildx-$(curl -s https://api.github.com/repos/docker/buildx/releases/latest | grep tag_name | cut -d '"' -f4).linux-$( [ "$(uname -m)" = aarch64 ] && echo arm64 || echo amd64)" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx || true
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx || true
mkdir -p /opt/foliolens && chown ec2-user /opt/foliolens
