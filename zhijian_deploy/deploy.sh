#!/bin/bash
# 志鉴系统部署脚本 — Linux (Ubuntu/Debian)
# 部署栈：nginx + systemd + Ollama(Qwen2.5-3B)
#
# 用法：
#   SERVER_IP=8.218.131.76 bash deploy.sh
#   或带环境变量：ALIYUN_OCR_APP_CODE=xxx bash deploy.sh

set -euo pipefail

# ============== 参数 ==============
SERVER_IP="${SERVER_IP:-8.218.131.76}"
SERVER_PORT="${SERVER_PORT:-8000}"
DATA_DIR="${DATA_DIR:-data/raw/1998}"
LOG_FILE="${LOG_FILE:-/var/log/zhijian_deploy.log}"
DEPLOY_ROOT="${DEPLOY_ROOT:-/root/zhijian_deploy}"
WEB_ROOT="${WEB_ROOT:-/var/www/zhijian}"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG_FILE"; }

log "=== 志鉴系统部署开始 ==="
log "目标服务器 IP: $SERVER_IP"
log "部署目录: $DEPLOY_ROOT"

# ============== 0. 前置检查 ==============
log "[0/8] 前置检查..."
command -v python3 >/dev/null 2>&1 || { log "❌ 需 python3"; exit 1; }
command -v nginx >/dev/null 2>&1 || { log "❌ 需 nginx"; exit 1; }
command -v systemctl >/dev/null 2>&1 || { log "❌ 需 systemd"; exit 1; }

# ============== 1. Python 依赖 ==============
log "[1/8] 安装 Python 依赖..."
cd "$DEPLOY_ROOT"
pip install --upgrade pip 2>&1 | tail -2
pip install -r requirements.txt 2>&1 | tail -5
# RapidOCR 已含在 requirements；此处双保险
pip install rapidocr-onnxruntime 2>&1 | tail -3

# ============== 2. Ollama 安装 ==============
log "[2/8] 安装 Ollama..."
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh 2>&1 | tail -10
fi
ollama --version

# ============== 3. Ollama systemd 服务 ==============
log "[3/8] 配置 Ollama 服务..."
if [ ! -f /etc/systemd/system/ollama.service ]; then
    # 官方一键脚本已自动建 unit；若缺失则用本目录模板兜底
    cp ollama.service /etc/systemd/system/ollama.service
    systemctl daemon-reload
fi
systemctl enable --now ollama
sleep 3
systemctl status ollama --no-pager | head -5

# ============== 4. 拉模型 ==============
log "[4/8] 拉取 Qwen2.5-3B（约 2GB，可能需要 5-15 分钟）..."
timeout 1200 ollama pull qwen2.5:3b 2>&1 | tail -10
log "已安装模型："
ollama list | tee -a "$LOG_FILE"

# ============== 5. Nginx 配置 ==============
log "[5/8] 配置 Nginx..."
mkdir -p "$WEB_ROOT"
tar -xzf zhijian_frontend.tar.gz -C "$WEB_ROOT" --strip-components=1
cp zhijian.conf /etc/nginx/sites-available/zhijian.conf
ln -sf /etc/nginx/sites-available/zhijian.conf /etc/nginx/sites-enabled/zhijian.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
nginx -s reload
log "Nginx 加载配置 OK"

# ============== 6. 后端代码 ==============
log "[6/8] 部署后端代码..."
tar -xzf zhijian_backend.tar.gz -C "$DEPLOY_ROOT"

# ============== 7. zhijian systemd 服务 ==============
log "[7/8] 创建 zhijian 服务..."
cat > /etc/systemd/system/zhijian.service << 'EOF'
[Unit]
Description=Zhijian FastAPI Service
After=network.target ollama.service
Wants=ollama.service

[Service]
User=root
WorkingDirectory=/root/zhijian_deploy
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=3
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="OLLAMA_HOST=http://127.0.0.1:11434"

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable zhijian
systemctl restart zhijian
sleep 4

# ============== 8. 等待启动 + 语料 ingest ==============
log "[8/8] 等待后端就绪并触发语料 ingest..."
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS --max-time 5 "http://127.0.0.1:$SERVER_PORT/api/v1/health" >/dev/null 2>&1; then
        log "✅ 后端已就绪（耗时 ${i}×2s）"
        break
    fi
    sleep 2
done

# 触发 ingest（重建 gazetteer_chunks collection）
log "触发 RAG ingest（$DATA_DIR）..."
curl -fsS -X POST \
    "http://127.0.0.1:$SERVER_PORT/api/v1/rag/seed" \
    -d "data_dir=$DATA_DIR&collection=gazetteer_chunks&rebuild=true" \
    --max-time 300 || log "⚠️  ingest 调用失败（可手动重跑）"

log ""
log "=== 部署完成 ==="
log "访问地址: http://$SERVER_IP"
log "API 文档: http://$SERVER_IP/docs"
log "健康检查: http://$SERVER_IP/api/v1/health"
log ""
log "可选：启用阿里云高精度 OCR — 编辑 /etc/systemd/system/zhijian.service："
log "  Environment=\"ALIYUN_OCR_APP_CODE=your_code\""
log "然后 systemctl restart zhijian"