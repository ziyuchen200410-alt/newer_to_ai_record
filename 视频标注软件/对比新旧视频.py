import cv2
import os
import json
from pathlib import Path
import numpy as np

def generate_masks_v2(json_path, data_root):
    json_path = Path(json_path).resolve()
    data_root = Path(data_root).resolve()
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 掩码输出目录：建议直接放在数据根目录下的 diff 文件夹
    diff_dir = data_root / "diff"
    diff_dir.mkdir(exist_ok=True)
    
    print(f"开始处理，根目录: {data_root}")
    success = 0

    for idx, item in enumerate(data):
        # 统一路径解析逻辑
        def to_abs(rel):
            if not rel: return None
            p = Path(str(rel).strip().strip('"'))
            return p if p.is_absolute() else (data_root / p).resolve()

        ref_path = to_abs(item.get('ref_video_path'))
        src_path = to_abs(item.get('src_video_path'))

        if not ref_path or not src_path or not ref_path.exists() or not src_path.exists():
            continue

        # --- 【核心修正 1：唯一性命名】 ---
        # 既然 1 个 Ref 对应 1 个 Mask，掩码必须以 Ref 的名字命名，防止被同 ID 的其他 Ref 覆盖
        mask_name = f"{ref_path.stem}.jpg" 
        save_path = diff_dir / mask_name

        cap_ref = cv2.VideoCapture(str(ref_path))
        cap_src = cv2.VideoCapture(str(src_path))
        
        # 读取第一帧进行差分（如有动态位移需在此处调帧）
        ret1, frame_ref = cap_ref.read()
        ret2, frame_src = cap_src.read()
        
        if ret1 and ret2:
            if frame_ref.shape != frame_src.shape:
                frame_ref = cv2.resize(frame_ref, (frame_src.shape[1], frame_src.shape[0]))
            
            # 计算差分
            diff = cv2.absdiff(frame_ref, frame_src)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            
            # --- 【核心修正 2：抗噪阈值】 ---
            # 针对“人影”干扰，提高阈值到 35，并使用形态学开运算去除细碎位移
            _, mask = cv2.threshold(gray, 35, 255, cv2.THRESH_BINARY_INV)
            
            # 形态学降噪
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            cv2.imwrite(str(save_path), mask)
            success += 1
            if success % 50 == 0:
                print(f"已生成 {success} 张唯一掩码...")
        
        cap_ref.release()
        cap_src.release()

    print(f"处理完成，共生成 {success} 张掩码。")

if __name__ == "__main__":
    # 替换为你实际的 JSON 路径和数据根目录
    JSON = r"/Users/chenziyu/Desktop/数据标注任务（4月22前）/打标/label_results/add_chunk_008_sample30k_part03_add_chunk_008_sample30k_part03/labeled_with_tag.json"
    ROOT = r"/Users/chenziyu/Desktop/数据标注任务（4月22前）/原数据/add_chunk_008_sample30k_part03"
    
    generate_masks_v2(JSON, ROOT)