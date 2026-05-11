"""
图像增强模块 - 解决古籍OCR小样本问题
通过对现有图像进行各种变换生成更多训练样本
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from pathlib import Path
from typing import List, Tuple, Optional
import random
import math


class AncientTextAugmentor:
    """古籍图像数据增强器"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def add_gaussian_noise(self, image: np.ndarray, mean: float = 0, sigma: float = 15) -> np.ndarray:
        """添加高斯噪声（模拟老化效果）"""
        noise = np.random.normal(mean, sigma, image.shape).astype(np.uint8)
        noisy = cv2.add(image, noise)
        return noisy

    def add_ink_bleed(self, image: np.ndarray, intensity: float = 0.3) -> np.ndarray:
        """添加墨迹渗透效果"""
        h, w = image.shape[:2]
        kernel_size = random.randint(3, 7)
        kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size ** 2)

        blurred = cv2.filter2D(image.astype(np.float32), -1, kernel)
        bleed = cv2.addWeighted(image.astype(np.float32), 1 - intensity, blurred, intensity, 0)
        return np.clip(bleed, 0, 255).astype(np.uint8)

    def add_paper_texture(self, image: np.ndarray, intensity: float = 0.2) -> np.ndarray:
        """添加纸张纹理"""
        h, w = image.shape[:2]
        texture = np.random.normal(128, 20, (h, w)).astype(np.float32)

        if len(image.shape) == 3:
            texture = np.stack([texture] * 3, axis=-1)

        textured = cv2.addWeighted(image.astype(np.float32), 1 - intensity, texture, intensity, 0)
        return np.clip(textured, 0, 255).astype(np.uint8)

    def add_brightness_variation(self, image: np.ndarray, factor: float = None) -> np.ndarray:
        """添加亮度变化"""
        if factor is None:
            factor = random.uniform(0.6, 1.4)

        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else image)
        enhancer = ImageEnhance.Brightness(pil_img)
        enhanced = enhancer.enhance(factor)

        return cv2.cvtColor(np.array(enhanced), cv2.COLOR_RGB2BGR) if len(image.shape) == 3 else np.array(enhanced)

    def add_contrast_variation(self, image: np.ndarray, factor: float = None) -> np.ndarray:
        """添加对比度变化"""
        if factor is None:
            factor = random.uniform(0.6, 1.4)

        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else image)
        enhancer = ImageEnhance.Contrast(pil_img)
        enhanced = enhancer.enhance(factor)

        return cv2.cvtColor(np.array(enhanced), cv2.COLOR_RGB2BGR) if len(image.shape) == 3 else np.array(enhanced)

    def add_blur(self, image: np.ndarray, blur_type: str = "gaussian") -> np.ndarray:
        """添加模糊（模拟聚焦不准/老旧照片）"""
        if blur_type == "gaussian":
            ksize = random.choice([3, 5, 7, 9])
            return cv2.GaussianBlur(image, (ksize, ksize), 0)
        elif blur_type == "motion":
            kernel_size = random.randint(5, 15)
            kernel = np.zeros((kernel_size, kernel_size))
            kernel[int((kernel_size - 1) / 2), :] = np.ones(kernel_size)
            kernel = kernel / kernel_size
            return cv2.filter2D(image, -1, kernel)
        else:
            return image

    def rotate_image(self, image: np.ndarray, angle: float = None) -> Tuple[np.ndarray, float]:
        """旋转图像（古籍可能有倾斜）"""
        if angle is None:
            angle = random.uniform(-15, 15)

        h, w = image.shape[:2]
        center = (w / 2, h / 2)

        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, rotation_matrix, (w, h),
                                  borderMode=cv2.BORDER_REFLECT)

        return rotated, angle

    def add_occlusion(self, image: np.ndarray, num_rectangles: int = None) -> np.ndarray:
        """添加遮挡（模拟破损/污渍）"""
        if num_rectangles is None:
            num_rectangles = random.randint(1, 3)

        h, w = image.shape[:2]
        result = image.copy()

        for _ in range(num_rectangles):
            rect_w = random.randint(int(w * 0.05), int(w * 0.2))
            rect_h = random.randint(int(h * 0.05), int(h * 0.2))
            x = random.randint(0, w - rect_w)
            y = random.randint(0, h - rect_h)

            color = random.randint(200, 255) if len(image.shape) == 2 or image.shape[2] == 1 else (
                random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))

            if len(image.shape) == 2:
                cv2.rectangle(result, (x, y), (x + rect_w, y + rect_h), color, -1)
            else:
                cv2.rectangle(result, (x, y), (x + rect_w, y + rect_h), color, -1)

        return result

    def perspective_transform(self, image: np.ndarray) -> np.ndarray:
        """透视变换（模拟拍摄角度）"""
        h, w = image.shape[:2]

        # 随机生成四个角的偏移量
        margin = 0.1
        src_points = np.float32([
            [0, 0],
            [w, 0],
            [w, h],
            [0, h]
        ])

        dst_points = np.float32([
            [random.uniform(-w * margin, w * margin), random.uniform(-h * margin, h * margin)],
            [w + random.uniform(-w * margin, w * margin), random.uniform(-h * margin, h * margin)],
            [w + random.uniform(-w * margin, w * margin), h + random.uniform(-h * margin, h * margin)],
            [random.uniform(-w * margin, w * margin), h + random.uniform(-h * margin, h * margin)]
        ])

        matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        transformed = cv2.warpPerspective(image, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)

        return transformed

    def random_augment(self, image: np.ndarray, num_augmentations: int = None) -> List[np.ndarray]:
        """随机组合多种增强"""
        if num_augmentations is None:
            num_augmentations = random.randint(2, 5)

        augmentations = [
            lambda img: self.add_gaussian_noise(img, sigma=random.uniform(5, 25)),
            lambda img: self.add_ink_bleed(img, intensity=random.uniform(0.1, 0.4)),
            lambda img: self.add_paper_texture(img, intensity=random.uniform(0.1, 0.3)),
            lambda img: self.add_brightness_variation(img),
            lambda img: self.add_contrast_variation(img),
            lambda img: self.add_blur(img, random.choice(["gaussian", "motion"])),
            lambda img: self.rotate_image(img)[0],
            lambda img: self.add_occlusion(img),
            lambda img: self.perspective_transform(img)
        ]

        selected = random.sample(augmentations, min(num_augmentations, len(augmentations)))
        result = image.copy()

        for aug in selected:
            result = aug(result)

        return result

    def augment_dataset(self, input_images: List[Path], num_variants_per_image: int = 5) -> List[Path]:
        """批量增强数据集"""
        output_paths = []

        for idx, img_path in enumerate(input_images):
            print(f"Processing {idx + 1}/{len(input_images)}: {img_path.name}")

            image = cv2.imread(str(img_path))
            if image is None:
                print(f"  Failed to read {img_path}")
                continue

            for aug_idx in range(num_variants_per_image):
                augmented = self.random_augment(image)

                output_name = f"{img_path.stem}_aug{aug_idx:02d}{img_path.suffix}"
                output_path = self.output_dir / output_name
                cv2.imwrite(str(output_path), augmented)
                output_paths.append(output_path)

        print(f"\nGenerated {len(output_paths)} augmented images")
        return output_paths


if __name__ == "__main__":
    # 测试增强器
    augmentor = AncientTextAugmentor(
        output_dir="C:/Users/hbusl/qi_wu_bo_yan/dataset/ocr_training/augmented"
    )

    # 示例：增强单张图像
    test_image = Path("C:/Users/hbusl/qi_wu_bo_yan/dataset/ocr_raw")
    if test_image.exists():
        images = list(test_image.glob("*.jpg"))[:1]
        if images:
            result = augmentor.random_augment(cv2.imread(str(images[0])))
            cv2.imwrite(str(augmentor.output_dir / "test_augmented.jpg"), result)
            print("Test augmentation completed")
