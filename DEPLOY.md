# 志鉴系统部署手册

> 适用：Ubuntu 22.04+ / Debian 11+  服务器

## 一、环境清单

| 组件 | 最低 | 推荐 |
|------|------|------|
| CPU | 4 核 | 8 核 |
| 内存 | 16 GB | 32 GB |
| 磁盘 | 20 GB | 50 GB（含模型权重） |
| GPU | - | NVIDIA 8GB+（Qwen2.5-3B 推理 + BGE 嵌入） |
| Python | 3.10 | 3.10.5 |
| Node.js | 18 | 20 LTS |
| Nginx | 1.18+ | 1.24+ |

如使用 GPU 加速，需先装 NVIDIA Driver + CUDA 12.x（Ollama 自动检测）。

## 二、服务器前置准备

```bash
# 1. 创建部署目录
sudo mkdir -p /root/zhijian_deploy
sudo chown $USER:$USER /root/zhijian_deploy

# 2. 开放端口（防火墙）
sudo ufw allow 80/tcp     # Nginx HTTP
sudo ufw allow 11434/tcp  # Ollama（仅本机访问可不开放外网）

# 3. 上传部署包（在本机执行）
scp -r zhijian_deploy/zhijian_*.tar.gz user@SERVER_IP:/root/zhijian_deploy/
scp -r zhijian_deploy/zhijian.conf user@SERVER_IP:/root/zhijian_deploy/
scp -r zhijian_deploy/ollama.service user@SERVER_IP:/root/zhijian_deploy/
scp -r data/raw user@SERVER_IP:/root/zhijian_deploy/data_raw  # 方志原文

# 4. 上传后端代码（在服务器上 git clone 也可以）
scp -r backend_code/* user@SERVER_IP:/root/zhijian_deploy/
# 要求目录结构：
#   /root/zhijian_deploy/
#   ├── app/                 # 后端 Python 包
#   ├── requirements.txt
#   ├── data/                # 方志原文（与上面第 3 步合并）
#   ├── zhijian_backend.tar.gz  # （可选）打包好的后端
#   ├── zhijian_frontend.tar.gz # 前端 dist 打包
#   ├── zhijian.conf
#   └── ollama.service
```

## 三、快速部署

一行搞定（假设部署包已上传到 `/root/zhijian_deploy/`）：

```bash
cd /root/zhijian_deploy
SERVER_IP=8.218.131.76 sudo -E bash deploy.sh
```

deploy.sh 内部会按顺序执行：
1. 安装 Python 依赖 + RapidOCR
2. 安装 Ollama
3. 配置 systemd 服务
4. 拉取 Qwen2.5-3B 模型（约 2 GB，需 5-15 分钟）
5. 配置 Nginx + 解压前端
6. 解压后端代码
7. 创建 zhijian systemd 服务
8. 触发语料 ingest（重建 ChromaDB）

完成后日志会输出访问地址。

## 四、手动部署（分步）

deploy.sh 失败时可逐条执行排查：

### 4.1 Python 依赖
```bash
cd /root/zhijian_deploy
pip install -r requirements.txt
pip install rapidocr-onnxruntime
python -c "import rapidocr_onnxruntime; print('RapidOCR OK')"
python -c "import app.main; print('app importable')"
```

### 4.2 Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
systemctl enable --now ollama
systemctl status ollama
ollama pull qwen2.5:3b
ollama list
```

### 4.3 Nginx
```bash
sudo mkdir -p /var/www/zhijian
sudo tar -xzf zhijian_frontend.tar.gz -C /var/www/zhijian --strip-components=1
sudo cp zhijian.conf /etc/nginx/sites-available/zhijian.conf
sudo ln -sf /etc/nginx/sites-available/zhijian.conf /etc/nginx/sites-enabled/zhijian.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo nginx -s reload
```

### 4.4 后端 systemd 服务
```bash
sudo tee /etc/systemd/system/zhijian.service > /dev/null << 'EOF'
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

sudo systemctl daemon-reload
sudo systemctl enable zhijian
sudo systemctl restart zhijian
sudo systemctl status zhijian
```

### 4.5 语料 ingest
```bash
curl -fsS -X POST "http://127.0.0.1:8000/api/v1/rag/seed" \
    -d "data_dir=data/raw/1998&collection=gazetteer_chunks&rebuild=true" \
    --max-time 300
```

## 五、环境变量

| 变量 | 必填 | 用途 |
|------|------|------|
| `OLLAMA_HOST` | 否 | Ollama 服务地址，默认 `http://127.0.0.1:11434` |
| `ALIYUN_OCR_APP_CODE` | 否 | 启用阿里云 OCR（高精度） |
| `ALIYUN_ACCESS_KEY_ID` | 否 | 同上，AK/SK 模式二选一 |
| `ALIYUN_ACCESS_KEY_SECRET` | 否 | 同上 |

修改方式：编辑 `/etc/systemd/system/zhijian.service`，加 `Environment="ALIYUN_OCR_APP_CODE=xxx"`，然后 `sudo systemctl daemon-reload && sudo systemctl restart zhijian`。

## 六、验证清单

部署完成后依次确认：

```bash
# 1. 后端存活
curl http://$SERVER_IP/api/v1/health
# 期望：{"status":"healthy","service":"zhijian-api"}

# 2. RAG 模块：embedder + LLM 加载
curl http://$SERVER_IP/api/v1/rag/status | python -m json.tool
# 期望：embedder.status=loaded, llm_provider=ollama:ready
#       collections 至少含 gazetteer_chunks 且 count > 0

# 3. OCR 模块：RapidOCR 默认引擎可用
curl http://$SERVER_IP/api/v1/ocr/status | python -m json.tool
# 期望：providers.rapidocr=true, default_provider=rapidocr

# 4. OCR 样本图列表
curl http://$SERVER_IP/api/v1/ocr/samples | python -m json.tool
# 期望：samples 数组非空，首项 name 以 kangxi 开头

# 5. 端到端 RAG 问答
curl -X POST http://$SERVER_IP/api/v1/rag/ask \
    -H "Content-Type: application/json" \
    -d '{"question":"固安县位于哪里？","top_k":3}'
# 期望：answer 含具体地理位置描述，sources 含 1-3 条引用
```

## 七、故障排查

### 413 Request Entity Too Large（OCR 上传失败）
- 检查 nginx 配置：`grep client_max_body_size /etc/nginx/sites-enabled/zhijian.conf`
- 应为 `client_max_body_size 25M;`
- `sudo nginx -t && sudo nginx -s reload`

### RAG/ask 502 / 超时
```bash
# 检查 Ollama
systemctl status ollama
journalctl -u ollama -n 50 --no-pager
curl http://127.0.0.1:11434/api/tags

# 检查模型是否在跑
ollama ps
```

### 首次 /ocr/recognize 超慢（几十秒）
- RapidOCR 首次会下载 ~50MB ONNX 模型到 `~/.rapidocr/`
- 检查网络：`curl -I https://huggingface.co`
- 预热可手动跑一次：`python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"`

### ChromaDB ingest 失败
- 检查 `data/raw/` 是否在 `/root/zhijian_deploy/data/raw/`
- `ls -la /root/zhijian_deploy/data/raw/1998/`
- 手动重跑 ingest：`curl -X POST http://127.0.0.1:8000/api/v1/rag/seed?data_dir=data/raw/1998&rebuild=true`

### 前端白屏
- 检查 dist 部署：`ls /var/www/zhijian/`
- 检查 nginx 错误：`sudo tail -f /var/log/nginx/error.log`

## 八、回滚

```bash
# 停止服务
sudo systemctl stop zhijian ollama

# 禁用自启
sudo systemctl disable zhijian ollama

# 删除服务文件
sudo rm /etc/systemd/system/zhijian.service
sudo rm /etc/systemd/system/ollama.service
sudo systemctl daemon-reload

# 删除部署文件（如需要）
sudo rm -rf /root/zhijian_deploy /var/www/zhijian
```

## 九、Docker 部署（备选）

> 主部署走 `deploy.sh`（更轻量、更易排错）。Docker 路径仅供参考。

```bash
cd /root/zhijian_deploy
docker-compose up -d ollama      # 先起 Ollama
docker-compose --profile init up model-init  # 拉模型
docker-compose up -d app         # 再起后端
```

## 十、升级

```bash
# 1. 备份数据
sudo systemctl stop zhijian
cp -r /root/zhijian_deploy/chroma_zhijian /tmp/chroma_backup

# 2. 更新代码
cd /root/zhijian_deploy
git pull  # 或重新 scp 上传

# 3. 更新依赖（如 requirements.txt 变化）
pip install -r requirements.txt

# 4. 重启
sudo systemctl restart zhijian
```