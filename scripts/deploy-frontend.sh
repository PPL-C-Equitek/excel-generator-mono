#!/bin/bash
set -e

source "$(dirname "$0")/load-env.sh"
load_env_file "$HOME/apps/.env"

export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"

cd ~/apps/excel-generator-mono/frontend

npm ci
npm run build
pm2 restart nextjs || pm2 start npm --name "nextjs" -- start
