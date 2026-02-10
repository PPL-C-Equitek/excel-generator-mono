#!/bin/bash
set -e

set -a
source ~/apps/.env
set +a

export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"

cd ~/apps/excel-generator-mono/frontend

npm ci
npm run build
pm2 restart nextjs || pm2 start npm --name "nextjs" -- start