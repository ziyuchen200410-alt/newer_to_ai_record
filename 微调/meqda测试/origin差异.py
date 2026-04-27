import json
import re
import os

def extract_label_info(label_text):
    """提取标签中的字母和含义 (e.g., 'E. 24小时内' -> 'E', '24小时内')"""
    label_text = str(label_text).strip().replace("\n", "")
    match = re.match(r'^([A-E])[\.\s\：\、\-\)]*(.*)$', label_text, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2).strip()
    return None, label_text

def is_correct_fuzzy(predict_text, label_letter, label_meaning):
    """
    针对原模型长文本的判别逻辑：
    1. 寻找带有“答案是/选”等关键词后的选项字母。
    2. 寻找文本中最后出现的独立 A-E 字母。
    3. 检查标签的语义内容是否被包含在预测文本中。
    """
    if not predict_text: return False
    predict_text = str(predict_text).strip().replace("\n", "")

    # 策略 1: 结论性关键词提取
    conclusion_patterns = [
        r'答案(?:是|为|：|码为)?\s*([A-E])',
        r'选(?:项)?(?:是|为|：)?\s*([A-E])',
        r'正确答案(?:是|为|：)?\s*([A-E])',
        r'因此(?:.*?)(?:选|答案是)\s*([A-E])'
    ]
    for pattern in conclusion_patterns:
        match = re.search(pattern, predict_text, re.IGNORECASE)
        if match and match.group(1).upper() == label_letter:
            return True

    # 策略 2: 提取文本末尾最后一个出现的独立字母（原模型常在末尾总结）
    last_letter_match = re.findall(r'(?<![A-Za-z])([A-E])(?![A-Za-z0-9])', predict_text, re.IGNORECASE)
    if last_letter_match and last_letter_match[-1].upper() == label_letter:
        return True

    # 策略 3: 语义覆盖 (仅当含义文本长度大于1时有效)
    if label_meaning and len(label_meaning) > 1:
        if label_meaning in predict_text:
            return True

    return False

def compare_base_runs(path_a, path_b):
    def load_jsonl(p):
        if not os.path.exists(p): return None
        with open(p, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f]

    data_a = load_jsonl(path_a)
    data_b = load_jsonl(path_b)

    if not data_a or not data_b:
        print("❌ 路径错误，请检查文件是否存在。")
        return

    min_len = min(len(data_a), len(data_b))
    stats = {"AA": 0, "BB": 0, "AB": 0, "BA": 0, "fail": 0}
    
    for i in range(min_len):
        l_letter, l_meaning = extract_label_info(data_a[i].get('label', ''))
        
        # 应用模糊判定方法
        is_a_correct = is_correct_fuzzy(data_a[i].get('predict', ''), l_letter, l_meaning)
        is_b_correct = is_correct_fuzzy(data_b[i].get('predict', ''), l_letter, l_meaning)

        if is_a_correct and is_b_correct: stats["AA"] += 1
        elif not is_a_correct and not is_b_correct: stats["fail"] += 1
        elif not is_a_correct and is_b_correct: stats["AB"] += 1 # B修正了A
        elif is_a_correct and not is_b_correct: stats["BA"] += 1 # B导致退化

    # 结果审计报告
    acc_a = (stats["AA"] + stats["BA"]) / min_len * 100
    acc_b = (stats["AA"] + stats["AB"]) / min_len * 100

    print("\n" + "="*65)
    print("📊 2052 实验室：原模型 MedQA 两次运行逻辑对比报告")
    print("="*65)
    print(f"对比样本量: {min_len}")
    print(f"1. 运行 A 准确率 (旧路径): {acc_a:.2f}%")
    print(f"2. 运行 B 准确率 (新测试): {acc_b:.2f}%")
    print(f"3. 准确率净增益: {acc_b - acc_a:+.2f}%")
    print("-" * 65)
    print(f"● 共同正确 (稳健点): {stats['AA']}")
    print(f"● 逻辑漂移 [正向] (A错B对): {stats['AB']} 🟢")
    print(f"● 逻辑漂移 [负向] (A对B错): {stats['BA']} 🔴")
    print(f"● 顽固错误 (两次均错): {stats['fail']}")
    print("="*65)
    
    if abs(acc_a - acc_b) > 2:
        print("⚠️ 警告：原模型表现波动剧烈，请严厉核实两次测试的 Temperature 参数是否一致。")

# 设置物理路径
file_a = "/Users/chenziyu/Desktop/test4.27/record/微调/medqa/原模型.jsonl"
file_b = "/Users/chenziyu/Desktop/meqda测试/原模型预测结果.jsonl"

compare_base_runs(file_a, file_b)