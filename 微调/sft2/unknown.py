import json

file_path = "generated_predictions.jsonl"
output_path = "unknown_audit.txt"

unknown_samples = []

with open(file_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        prompt = data.get("prompt", "")
        # 逻辑：既没有“单项选择题”也没有“多项选择题”
        if "单项选择题" not in prompt and "多项选择题" not in prompt:
            unknown_samples.append({
                "prompt": prompt[-200:], # 只取结尾部分看题干
                "predict": data.get("predict"),
                "label": data.get("label")
            })

with open(output_path, 'w', encoding='utf-8') as f:
    for idx, sample in enumerate(unknown_samples, 1):
        f.write(f"--- [Unknown Case {idx}] ---\n")
        f.write(f"PROMPT_TAIL: {sample['prompt']}\n")
        f.write(f"PREDICT: {sample['predict']}\n")
        f.write(f"LABEL: {sample['label']}\n\n")

print(f"✅ 已提取 {len(unknown_samples)} 个 Unknown 问题到 {output_path}")