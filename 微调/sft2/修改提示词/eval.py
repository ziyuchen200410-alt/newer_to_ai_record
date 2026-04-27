import json
import re
import os

def parse_options(prompt_text):
    """提取选项字母与内容的映射，用于语义回溯"""
    pattern = r"([A-G]):\s*(.*?)(?=\s*[A-G]:|$)"
    options = re.findall(pattern, prompt_text, re.DOTALL)
    return {letter.strip().upper(): content.strip() for letter, content in options}

def extract_logic_prediction(predict_str, is_multi=False):
    """
    严厉的提取逻辑：
    1. 寻找明确锚点 (正确答案是 X / 答案选 AB)
    2. 如果是多选，提取所有 A-G 字母
    3. 如果是单选，优先提取锚点或开头字母
    """
    predict_str = predict_str.strip()
    
    # 模式 1: 寻找明确的答案声明锚点
    anchor_match = re.search(r"(?:正确答案是|答案是|应选择|选项为|答案选)\s*([A-G]+)", predict_str, re.I)
    if anchor_match:
        found = anchor_match.group(1).upper()
        return "".join(sorted(set(re.sub(r'[^A-G]', '', found)))) if is_multi else found[0]

    # 模式 2: 如果是单选，尝试匹配开头字母 (如 "A: 内容" 或 "A. 内容")
    if not is_multi:
        prefix_match = re.search(r"^([A-G])(?=[:：\. \n\s])", predict_str)
        if prefix_match:
            return prefix_match.group(1).upper()

    # 模式 3: 提取所有 A-G 字母并去重排序 (针对多选或无锚点情况)
    letters = "".join(sorted(set(re.findall(r'[A-G]', predict_str.upper()))))
    if is_multi:
        return letters
    return letters[0] if letters else ""

def calculate_comprehensive_accuracy(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    # 初始化分类统计
    stats = {
        "single": {"total": 0, "correct": 0, "semantic": 0},
        "multi": {"total": 0, "correct": 0, "under": 0, "over": 0},
        "unknown": {"total": 0, "correct": 0}
    }
    
    grand_total = 0
    grand_correct = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            prompt = data.get("prompt", "")
            predict_raw = data.get("predict", "").strip()
            label_raw = data.get("label", "").strip().upper()

            if not label_raw:
                continue

            grand_total += 1

            # 1. 题型判定 (合并 C 型选择题到单选)
            if "单项选择题" in prompt or "C型选择题" in prompt:
                q_type = "single"
                is_multi = False
            elif "多项选择题" in prompt:
                q_type = "multi"
                is_multi = True
            else:
                q_type = "unknown"
                is_multi = False

            stats[q_type]["total"] += 1
            
            # 2. 清理标签
            target = "".join(sorted(re.sub(r'[^A-G]', '', label_raw)))
            
            # 3. 提取预测
            prediction = extract_logic_prediction(predict_raw, is_multi)

            # 4. 核心判定逻辑
            is_match = (prediction == target)
            
            # 5. 语义回溯 (仅针对单选题失败时)
            if not is_match and q_type == "single" and len(predict_raw) > 1:
                options_dict = parse_options(prompt)
                correct_content = options_dict.get(target, "NON_EXISTENT")
                # 如果预测文本里包含了正确选项的完整内容，则判定为对
                if len(correct_content) > 2 and correct_content in predict_raw:
                    is_match = True
                    stats["single"]["semantic"] += 1

            # 6. 多选题子集分析 (选少了/选多了)
            if not is_match and q_type == "multi" and prediction:
                pred_set = set(prediction)
                target_set = set(target)
                if pred_set.issubset(target_set):
                    stats["multi"]["under"] += 1
                elif target_set.issubset(pred_set):
                    stats["multi"]["over"] += 1

            # 7. 累计得分
            if is_match:
                stats[q_type]["correct"] += 1
                grand_correct += 1

    # 8. 输出专业审计报告
    print("\n" + "="*60)
    print(f"📊 MEDICAL LLM FINAL AUDIT REPORT")
    print(f"Source: {os.path.basename(file_path)}")
    print("="*60)
    
    for qt in ["single", "multi", "unknown"]:
        d = stats[qt]
        if d["total"] == 0: continue
        acc = (d["correct"] / d["total"]) * 100
        print(f"[{qt.upper()} QUESTIONS]")
        print(f"  Accuracy: {acc:.2f}% ({d['correct']}/{d['total']})")
        if qt == "single":
            print(f"  └─ Semantic Recovered: {d['semantic']} (通过内容对齐找回)")
        if qt == "multi":
            print(f"  └─ Under-selected: {d['under']} | Over-selected: {d['over']}")
        print("-" * 30)

    # 全局总指标
    final_acc = (grand_correct / grand_total) * 100 if grand_total > 0 else 0
    print(f"⭐ GRAND TOTAL ACCURACY: {final_acc:.4f}% ({grand_correct}/{grand_total})")
    print("="*60 + "\n")

if __name__ == "__main__":
    # 执行审计
    calculate_comprehensive_accuracy("generated_predictions.jsonl")