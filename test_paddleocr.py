"""
使用 PaddleOCR 进行文字定位
PaddleOCR 已安装，可以直接返回文字的像素坐标
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("PaddleOCR Text Detection Test")
print("=" * 60)

from paddleocr import PaddleOCR
import cv2

# 初始化 PaddleOCR（中文+英文）
print("\n1. Initializing PaddleOCR...")
import os
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
ocr = PaddleOCR(lang='ch')
print("   PaddleOCR initialized!")

# 用最新的截图测试
img_path = Path(__file__).parent / ".screenshots" / "exec_4_20260415_161419_252489.png"
print(f"\n2. Processing: {img_path}")

# 执行 OCR
result = ocr.ocr(str(img_path))

# 解析结果
if result and result[0]:
    print(f"\n3. Found {len(result[0])} text elements:")
    for line in result[0]:
        bbox = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        text = line[1][0]  # 识别的文字
        confidence = line[1][1]
        # 计算中心点
        x_coords = [p[0] for p in bbox]
        y_coords = [p[1] for p in bbox]
        cx = int(sum(x_coords) / 4)
        cy = int(sum(y_coords) / 4)
        print(f"   [{text[:20]}] center=({cx}, {cy}) conf={confidence:.2f}")
else:
    print("   No text found!")

# 专门找 "测试" 或 "Agent" 或 "发送"
print("\n4. Searching for target text...")
targets = ["测试", "Agent", "发送", "Hands", "你好", "输入"]
found = []
if result and result[0]:
    for line in result[0]:
        text = line[1][0].strip()
        bbox = line[0]
        cx = int(sum(p[0] for p in bbox) / 4)
        cy = int(sum(p[1] for p in bbox) / 4)
        for t in targets:
            if t in text:
                found.append((text, cx, cy))
                print(f"   [FOUND] '{text}' at ({cx}, {cy})")

if not found:
    print("   Target text not found, showing all detected text:")
    if result and result[0]:
        for line in result[0][:10]:
            text = line[1][0].strip()
            bbox = line[0]
            cx = int(sum(p[0] for p in bbox) / 4)
            cy = int(sum(p[1] for p in bbox) / 4)
            print(f"   '{text[:30]}' at ({cx}, {cy})")

print("\n" + "=" * 60)
