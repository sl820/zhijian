# 古籍舆图与批校标注方案

> 为2026中国大学生计算机设计大赛 — 志鉴方志系统
>
> 版本：v1.0 | 日期：2026-04-03

---

## 一、数据概览

### 咸丰版固安县志（已扫描）

| 章节 | 图像数量 | 尺寸 | 主要内容 |
|------|---------|------|---------|
| 卷一·舆地志 | **64页** | 1240×1755 RGB | 地图 + 地理要素 |
| 卷七上·人物志 | **144页** | 1240×1755 RGB | 人物传记 + 批校痕迹 |

### 康熙版固安县志（待扫描）
- 3页已扫描（`data/raw/kangxi/`），其余需OCR

---

## 二、舆图提取 — U-Net 语义分割

### 2.1 标注类别

| 类别ID | 名称 | 颜色(可视化) | 说明 |
|-------|------|------------|------|
| 0 | 背景 | #000000 (黑) | 纸张、空白区域 |
| 1 | 河流 | #FFFF00 (黄) | 河道、湖泊、水系 |
| 2 | 山脉 | #8B5A2B (棕) | 山峰、山脉走向、丘陵 |
| 3 | 城市/聚落 | #FF0000 (红) | 城池、村庄、聚落标记 |
| 4 | 边界线/道路 | #00FF00 (绿) | 行政区划边界、道路 |
| 5 | 文字标注 | #FFFF00 (浅黄) | 地图上的文字标签 |

### 2.2 标注工具推荐

**首选：Label Studio（开源、浏览器端）**
```bash
pip install label-studio
label-studio
```
- 配置 Webhooks 直接输出 COCO 格式

**备选：CVAT（支持多用户协作）**
```bash
docker run -d -p 8080:8080 cvat/cvat
```

**备选：Labelme（本地单用户）**
```bash
pip install labelme
labelme
```

### 2.3 标注格式（COCO Stuff Segmentation）

```json
{
  "info": {
    "description": "古舆图语义分割数据集 v1.0",
    "version": "1.0",
    "year": 2026,
    "contributor": "志鉴团队"
  },
  "categories": [
    {"id": 0, "name": "背景", "supercategory": "map"},
    {"id": 1, "name": "河流", "supercategory": "map"},
    {"id": 2, "name": "山脉", "supercategory": "map"},
    {"id": 3, "name": "城市", "supercategory": "map"},
    {"id": 4, "name": "边界线", "supercategory": "map"},
    {"id": 5, "name": "文字标注", "supercategory": "map"}
  ],
  "images": [...],
  "annotations": [...]
}
```

### 2.4 标注规范细则

#### 河流（类别1）
- ✅ 标注蓝色/黑色的自然河道线条
- ✅ 湖泊、池塘等面状水体
- ❌ 不标注水井等小型水体
- 标注精度：线状河流用 polygonal chain，面状用封闭 polygon

#### 山脉（类别2）
- ✅ 标注山峰符号（三角形、锥形）
- ✅ 山脉走向线条（鳞片状纹理）
- ✅ 丘陵地形
- ❌ 不标注单个小石块
- 标注精度： polygonal 封闭区域

#### 城市/聚落（类别3）
- ✅ 城池轮廓（方框/圆形城墙）
- ✅ 村庄标记（小圆点、方框）
- ✅ 重要地标（庙宇、亭台）
- 标注精度：最小面积 ≥ 100 像素

#### 边界线/道路（类别4）
- ✅ 行政区划边界（虚线或实线）
- ✅ 道路（官道、大路、小路）
- ✅ 围墙、栅栏
- 标注精度：线状标注 polygonal chain

#### 文字标注（类别5）
- ✅ 所有地图上的地名标注
- ✅ 图例文字
- ✅ 方向标记（N/S箭头等）
- 标注精度：用tight bounding box包围文字区域

### 2.5 图像子集建议

从64页舆地志中，建议标注 **15-20页** 作为训练集：

```
舆地志_p0.png   → 封面/目录页（无地图，跳过）
舆地志_p1.png   → 地图页 ✓
舆地志_p2.png   → 地图页 ✓
舆地志_p3.png   → 地图页 ✓
舆地志_p4.png   → 文字页（跳过）
...
舆地志_p10.png  → 地图页 ✓
```

建议按以下策略选择：
1. 优先选择包含完整地图的页面（空白区域 < 50%）
2. 涵盖不同年代的地图风格
3. 覆盖所有要素类别（河流+山脉+城市+边界+文字）

### 2.6 数据集划分

```
data/
├── maps/
│   ├── images/          # 原始图像
│   │   ├── train/       # 12张
│   │   └── val/         # 5张
│   └── annotations/
│       ├── train.json   # COCO格式
│       └── val.json
└── checkpoints/
    └── unet_ancient_map_best.pth
```

---

## 三、批校痕迹 — Faster R-CNN 目标检测

### 3.1 标注类别

| 类别ID | 名称 | 颜色 | 说明 |
|-------|------|------|------|
| 0 | 朱批 | #FF0000 (红) | 红色毛笔批注 |
| 1 | 墨批 | #333333 (墨黑) | 墨色手写批注 |
| 2 | 圈点 | #FFA500 (橙) | 圈点标记（读后感） |
| 3 | 划线 | #0000FF (蓝) | 下划线/删除线 |

### 3.2 标注工具推荐

**首选：Label Studio + BBOX 模板**

Label Studio 配置模板（`.yaml`）：
```yaml
<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="annotation" toName="image">
    <Label value="朱批" background="#FF0000"/>
    <Label value="墨批" background="#333333"/>
    <Label value="圈点" background="#FFA500"/>
    <Label value="划线" background="#0000FF"/>
  </RectangleLabels>
</View>
```

**备选：CVAT（支持快捷键批量标注）**

### 3.3 标注格式（COCO Object Detection）

```json
{
  "categories": [
    {"id": 0, "name": "朱批", "supercategory": "annotation"},
    {"id": 1, "name": "墨批", "supercategory": "annotation"},
    {"id": 2, "name": "圈点", "supercategory": "annotation"},
    {"id": 3, "name": "划线", "supercategory": "annotation"}
  ],
  "images": [...],
  "annotations": [
    {
      "id": 1,
      "image_id": 1,
      "category_id": 0,
      "bbox": [x, y, width, height],
      "area": 1234,
      "iscrowd": 0
    }
  ]
}
```

### 3.4 标注规范细则

#### 朱批（类别0）
- ✅ 红色（HSV: H=0-20 or 340-360, S≥100, V≥50）的毛笔批字
- ✅ 朱砂批校、红墨圈点
- ✅ 批注文字框、批语区域
- 标注要求：用 **tight bounding box** 包含完整批注区域

#### 墨批（类别1）
- ✅ 黑色/深蓝色墨迹手写批注
- ✅ 毛笔字、钢笔字
- ✅ 墨色涂改痕迹
- 标注要求：墨批颜色较淡，需调高图像对比度后标注

#### 圈点（类别2）
- ✅ 红色/墨色圆圈（标记重要段落）
- ✅ 圆点（·、●）
- ✅ 波浪线等阅读标记
- 标注要求：小区域圈点允许最小 10×10 像素

#### 划线（类别3）
- ✅ 下划线（单线、双线）
- ✅ 删除线/划改痕迹
- ✅ 波浪线强调
- 标注要求：用水平 bounding box 包含划线区域

### 3.5 图像子集建议

从144页人物志中，建议标注 **20-30页**：

```
人物志_p0.png   → 可能有批校 ✓
人物志_p1.png   → 可能有批校 ✓
人物志_p2.png   → 可能有批校 ✓
...
人物志_p15.png  → 可能有批校 ✓
```

**选择策略：**
1. 优先选择OCR识别置信度较低的页面（可能有手写批校干扰）
2. 人物数量较多的页面（传主页面）
3. 善本/孤本页面（更有历史价值）

### 3.6 特殊情况处理

#### 批注重叠
- 若多个批注重叠，仅标注最上层的批注
- 在备注字段记录"有重叠批注"

#### 墨迹褪色
- 褪色批注用红色虚线框标注
- 在备注字段记录"批注褪色"

#### 污渍/水渍
- 污渍不标注
- 模糊区域在备注字段记录

---

## 四、标注工作流程

```
Step 1: 工具安装
  ↓
Step 2: 数据筛选（确定标注子集）
  ↓
Step 3: 预标注（使用规则+EasyOCR辅助）
  ↓
Step 4: 人工校正
  ↓
Step 5: 质量检查（QA）
  ↓
Step 6: 格式转换（COCO/YOLO）
  ↓
Step 7: 数据集划分（train/val/test）
  ↓
Step 8: 模型训练
```

### 4.1 预标注策略

古籍批校图像可使用规则进行**半自动化预标注**：

```python
# 基于颜色的快速预检测
import cv2
import numpy as np

def detect_red_annotations(image):
    """检测红色批注候选区域"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # 红色范围
    mask1 = cv2.inRange(hsv, (0, 100, 50), (20, 255, 255))
    mask2 = cv2.inRange(hsv, (340, 100, 50), (360, 255, 255))
    return mask1 + mask2

def detect_ink_annotations(image):
    """检测墨色批注候选区域"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 低亮度区域
    _, mask = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    return mask
```

---

## 五、Label Studio 项目配置

### 5.1 舆图分割项目

```bash
# 启动 Label Studio
label-studio start --init NEW_PROJECT

# 或导入已有项目
label-studio import PROJECT_NAME.tar.gz
```

**Import config:**
```xml
<View>
  <Image name="image" value="$image"/>
  <PolygonLabels name="map_labels" toName="image" showInline="true">
    <Label value="河流" stroke="#FFFF00" fill="#FFFF00" fillOpacity="0.3"/>
    <Label value="山脉" stroke="#8B5A2B" fill="#8B5A2B" fillOpacity="0.3"/>
    <Label value="城市" stroke="#FF0000" fill="#FF0000" fillOpacity="0.3"/>
    <Label value="边界线" stroke="#00FF00" fill="#00FF00" fillOpacity="0.3"/>
    <Label value="文字标注" stroke="#FFFF00" fill="#FFFF00" fillOpacity="0.3"/>
  </PolygonLabels>
</View>
```

### 5.2 批校检测项目

```xml
<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="annotation_labels" toName="image">
    <Label value="朱批" background="#FF0000"/>
    <Label value="墨批" background="#333333"/>
    <Label value="圈点" background="#FFA500"/>
    <Label value="划线" background="#0000FF"/>
  </RectangleLabels>
</View>
```

---

## 六、数据集统计目标

### 舆图（U-Net）
| 指标 | 目标 |
|-----|------|
| 标注图像数 | 15-20张 |
| 图像分辨率 | 1240×1755 → 512×512 (训练时resize) |
| 平均每图河流数 | 3-8个 |
| 平均每图山脉数 | 2-5个 |
| 平均每图城市标记 | 5-15个 |
| 训练/验证划分 | 80% / 20% |

### 批校（Faster R-CNN）
| 指标 | 目标 |
|-----|------|
| 标注图像数 | 20-30张 |
| 平均每图朱批数 | 0-10个 |
| 平均每图墨批数 | 0-5个 |
| 平均每图圈点数 | 0-20个 |
| 平均每图划线数 | 0-15个 |
| 训练/验证划分 | 80% / 20% |

---

## 七、训练脚本

### 7.1 U-Net 舆图分割训练

```bash
# 训练舆图分割模型（50 epochs, batch_size=8）
python scripts/train_unet_maps.py \
    --data data/maps/dataset \
    --output checkpoints/unet_maps \
    --epochs 50 \
    --batch-size 8 \
    --lr 1e-4 \
    --num-workers 4

# 如需恢复训练
python scripts/train_unet_maps.py \
    --data data/maps/dataset \
    --output checkpoints/unet_maps \
    --resume checkpoints/unet_maps/unet_ancient_map_best.pth
```

**输出**:
- `checkpoints/unet_maps/unet_ancient_map_best.pth` — 最佳模型
- `checkpoints/unet_maps/unet_epoch_*.pth` — 定期checkpoint

**硬件要求**:
- GPU显存 ≥ 4GB（batch_size=8, 512×512）
- CPU训练约慢5-10倍

### 7.2 Faster R-CNN 批校检测训练

```bash
# 训练批校检测模型（30 epochs, batch_size=4）
python scripts/train_faster_rcnn_annotations.py \
    --data data/annotations/dataset \
    --output checkpoints/faster_rcnn_annotations \
    --epochs 30 \
    --batch-size 4 \
    --lr 1e-4 \
    --num-workers 4

# 如需恢复训练
python scripts/train_faster_rcnn_annotations.py \
    --data data/annotations/dataset \
    --output checkpoints/faster_rcnn_annotations \
    --resume checkpoints/faster_rcnn_annotations/faster_rcnn_best.pth
```

**输出**:
- `checkpoints/faster_rcnn_annotations/faster_rcnn_best.pth` — 最佳模型

**硬件要求**:
- GPU显存 ≥ 6GB（batch_size=4）
- Faster R-CNN 对显存需求较高

### 7.3 模型推理示例

```python
# U-Net舆图分割推理
from app.map_extraction.unet_model import AncientMapUNet
import torch

model = AncientMapUNet(pretrained_encoder=False)
ckpt = torch.load("checkpoints/unet_maps/unet_ancient_map_best.pth")
model.load_state_dict(ckpt["model_state_dict"])
model.eval()

# 推理
from PIL import Image
import torchvision.transforms as T

img = Image.open("test_map.png").convert("RGB")
tensor = T.Compose([
    T.Resize((512, 512)),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])(img).unsqueeze(0)

with torch.no_grad():
    output = model(tensor)
    mask = output.argmax(dim=1).squeeze(0).numpy()

# mask: 0=背景, 1=河流, 2=山脉, 3=城市, 4=边界线, 5=文字标注
```

```python
# Faster R-CNN 批校检测推理
from app.annotation_extract.faster_rcnn_model import AnnotationDetector
import torch

detector = AnnotationDetector(model_path="checkpoints/faster_rcnn_annotations/faster_rcnn_best.pth")
results = detector.detect("test_annotation.png")
# results: [{bbox, label, label_name, confidence}, ...]
```

---

## 八、质量控制（QA）

### 标注一致性检查
- [ ] 同一标注员对同一图像的两次标注 IoU ≥ 0.85
- [ ] 两名标注员对同一图像的标注 IoU ≥ 0.75
- [ ] 类别分布符合预期（无空类别）

### 格式验证
- [ ] COCO JSON 可用 `pycococreator` 验证
- [ ] 图像与标注数量匹配
- [ ] bbox 坐标在图像范围内

---

## 九、已生成的数据集结构

### 舆图（U-Net）
```
data/maps/
├── label_studio/
│   ├── label_studio_config.xml    # Label Studio导入配置（PolygonLabels）
│   ├── import_images.json        # 64张舆地志图像列表
│   └── README.md
├── dataset/
│   ├── images/train/            # 待标注
│   ├── images/val/             # 待标注
│   └── annotations/
│       ├── train.json           # COCO格式（待填充）
│       └── val.json
└── preannotations/              # 运行 analyze_annotation_candidates.py 后生成
```

### 批校（Faster R-CNN）
```
data/annotations/
├── label_studio/
│   ├── label_studio_bbox_config.xml  # Label Studio导入配置（RectangleLabels）
│   ├── import_images.json           # 144张人物志图像列表
│   └── README.md
├── dataset/
│   ├── images/train/
│   ├── images/val/
│   └── annotations/
│       ├── train.json
│       └── val.json
└── preannotations/              # 运行 analyze_annotation_candidates.py 后生成
```

### 快速开始

```bash
# 1. 启动Label Studio
label-studio start

# 2. 创建新项目，导入对应配置XML

# 3. 生成预标注候选（使用PIL解决中文路径）
python scripts/analyze_annotation_candidates.py --mode map --output data/maps/preannotations
python scripts/analyze_annotation_candidates.py --mode annotation --output data/annotations/preannotations

# 4. 标注完成后导出COCO格式
# Settings → Export → COCO Detection → Download

# 5. 格式转换（如需YOLO）
python scripts/prepare_annotation_detection_dataset.py \\
    --source data/ocr_training/images --output data/annotations
```

## 十、参考资料

- [Label Studio 官方文档](https://labelstud.io/)
- [COCO Dataset Format](https://cocodataset.org/#format-data)
- [CVAT 文档](https://cvat.org/documentation/)
- [Supervise.ly](https://supervise.ly/)（付费，推荐）
