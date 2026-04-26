import json
import re
import os

def parse_options(prompt_text):
    """提取选项字母与内容映射"""
    pattern = r"([A-G]):\s*(.*?)(?=\s*[A-G]:|$)"
    options = re.findall(pattern, prompt_text, re.DOTALL)
    return {letter.strip().upper(): content.strip() for letter, content in options}

def get_option_set(text):
    """提取唯一的、排序后的选项集合，如 'ABD' """
    if not text: return set()
    # 针对长文本，先尝试提取“正确答案是 X”之后的字母
    anchor_match = re.search(r"(?:正确答案是|答案是|选项为)\s*([A-G]+)", text)
    if anchor_match:
        text = anchor_match.group(1)
    return set(re.sub(r'[^A-G]', '', text.upper()))

def extract_single_letter(predict_str):
    """针对单选题的复杂文本提取逻辑"""
    predict_str = predict_str.strip()
    # 1. 寻找明确锚点
    anchor_match = re.search(r"(?:正确答案是|答案是|选项为)\s*([A-G])", predict_str)
    if anchor_match: return anchor_match.group(1).upper()
    # 2. 寻找开头字母
    prefix_match = re.search(r"^([A-G])(?=[:：\. \n\s])", predict_str)
    if prefix_match: return prefix_match.group(1).upper()
    # 3. 提取第一个出现的字母
    first_letter = re.search(r"([A-G])", predict_str)
    return first_letter.group(1).upper() if first_letter else None

def run_total_audit(file_path):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    # 初始化统计
    stats = {
        "single": {"total": 0, "correct": 0, "semantic": 0},
        "multi": {"total": 0, "correct": 0, "under": 0, "over": 0},
        "unknown": {"total": 0, "correct": 0}
    }
    
    grand_total = 0
    grand_correct = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            prompt = data.get("prompt", "")
            predict = data.get("predict", "")
            label = data.get("label", "").strip().upper()

            if not label: continue
            grand_total += 1

            # 1. 判定题型
            q_type = "single" if "单项选择题" in prompt else ("multi" if "多项选择题" in prompt else "unknown")
            stats[q_type]["total"] += 1
            
            # 2. 逻辑判定
            is_correct = False
            
            if q_type == "single":
                target = re.sub(r'[^A-G]', '', label)
                pred_letter = extract_single_letter(predict)
                if pred_letter == target:
                    is_correct = True
                else:
                    # 单选语义回溯
                    opts = parse_options(prompt)
                    correct_content = opts.get(target, "NON_EXISTENT")
                    if len(correct_content) > 2 and correct_content in predict:
                        is_correct = True
                        stats["single"]["semantic"] += 1
            
            elif q_type == "multi":
                target_set = get_option_set(label)
                pred_set = get_option_set(predict)
                if pred_set == target_set:
                    is_correct = True
                elif pred_set.issubset(target_set) and len(pred_set) > 0:
                    stats["multi"]["under"] += 1
                elif target_set.issubset(pred_set):
                    stats["multi"]["over"] += 1

            else: # Unknown
                if label in predict: is_correct = True

            if is_correct:
                stats[q_type]["correct"] += 1
                grand_correct += 1

    # 3. 输出审计报告
    print("="*55)
    print(f"📊 FINAL AUDIT REPORT: {os.path.basename(file_path)}")
    print("="*55)
    
    for qt in ["single", "multi", "unknown"]:
        d = stats[qt]
        if d["total"] == 0: continue
        acc = (d["correct"] / d["total"]) * 100
        print(f"[{qt.upper()}] Acc: {acc:.2f}% ({d['correct']}/{d['total']})")
        if qt == "single": print(f"  └─ Semantic Recovered: {d['semantic']}")
        if qt == "multi": print(f"  └─ Under-selected: {d['under']} | Over-selected: {d['over']}")
        print("-" * 55)

    # 4. 输出总计 (用户核心需求)
    total_acc = (grand_correct / grand_total) * 100 if grand_total > 0 else 0
    print(f"⭐ GRAND TOTAL ACCURACY: {total_acc:.4f}% ({grand_correct}/{grand_total})")
    print("="*55)

if __name__ == "__main__":
    run_total_audit("/Users/chenziyu/Desktop/test4.27/record/微调/sft3/generated_predictions.jsonl")