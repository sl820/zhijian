# OCR Provider 配置指南

## 概述

志鉴系统支持多 OCR Provider，可以通过 `provider` 参数切换：
- `easyocr` - EasyOCR (本地 GPU 加速，默认)
- `aliyun` - 阿里云 OCR (云端 API)

## 阿里云 OCR 配置

### 1. 获取阿里云 OCR 凭证

登录阿里云控制台，开通文字识别服务：
- https://ocr.console.aliyun.com/

获取以下凭证之一：

**方式一：AppCode (推荐，简单)**
1. 开通 API 网关服务
2. 创建应用，获取 AppCode

**方式二：AccessKey (更安全)**
1. 创建 RAM 用户
2. 授予 OCR 服务权限
3. 获取 AccessKey ID 和 AccessKey Secret

### 2. 配置环境变量

```bash
# 方式一：AppCode
export ALIYUN_OCR_APP_CODE="your_app_code_here"

# 方式二：AccessKey
export ALIYUN_ACCESS_KEY_ID="your_aki_here"
export ALIYUN_ACCESS_KEY_SECRET="your_aks_here"
```

或在 Python 代码中直接传入：
```python
from app.ocr.providers import AliyunOCRProvider

provider = AliyunOCRProvider(config={
    "app_code": "your_app_code",
    # 或
    "access_key_id": "your_aki",
    "access_key_secret": "your_aks",
})
```

### 3. 使用 API

**cURL 示例：**
```bash
curl -X POST "http://localhost:8000/api/v1/ocr/recognize?provider=aliyun" \
  -F "file=@your_image.png"
```

**Python 示例：**
```python
import requests

url = "http://localhost:8000/api/v1/ocr/recognize?provider=aliyun"
with open("image.png", "rb") as f:
    files = {"file": f}
    response = requests.post(url, files=files)
print(response.json())
```

## Provider 对比

| Feature | EasyOCR | Aliyun OCR |
|---------|---------|------------|
| 部署方式 | 本地 | 云端 |
| GPU 要求 | 需要 | 不需要 |
| 费用 | 免费 | 按量计费 |
| 古籍支持 | 一般 | 较好 |
| 竖排文字 | 支持 | 支持 |
| 速度 | 快(GPU) | 取决于网络 |

## 阿里云 OCR 计费

- 通用文字识别：50元/千次起
- 具体价格以阿里云官网为准
- 每月有免费额度

官网：https://help.aliyun.com/document_detail/300069.html
