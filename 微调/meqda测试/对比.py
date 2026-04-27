import json
import os
import re

def clean_text(text):
    """清理字符串：去除换行、首尾空格。"""
    if not text: return ""
    return str(text).strip().replace("\n", "")

def extract_parts(s):
    """
    提取选项字母和意思。
    支持格式: "E. 24小时内", "E 24小时内", "E", "24小时内"
    """
    s = clean_text(s)
    # 匹配开头是 A-E，后面跟着点、空格、冒号或直接结束的情况
    match = re.match(r'^([A-E])[\.\s\：]*(.*)$', s, re.IGNORECASE)
    if match:
        letter = match.group(1).upper()
        meaning = clean_text(match.group(2))
        return letter, meaning
    # 如果没匹配到字母开头，则视为纯意思
    return None, s

def is_logic_correct(predict, label):
    """
    核心审计逻辑：字母对 OR 意思对 = 正确
    """
    p_letter, p_meaning = extract_parts(predict)
    l_letter, l_meaning = extract_parts(label)

    # 1. 字母匹配逻辑 (A==A)
    if p_letter and l_letter and p_letter == l_letter:
        return True
    
    # 2. 意思匹配逻辑 (24小时内 == 24小时内)
    # 注意：如果 predict 只有字母，p_meaning 会是空，此时不走意思匹配
    if p_meaning and l_meaning and p_meaning == l_meaning:
        return True
        
    return False

def run_audit(file_a, file_b):
    def load_data(p):
        if not os.path.exists(p): return None
        with open(p, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f]

    data_a = load_data(file_a)
    data_b = load_data(file_b)

    if not data_a or not data_b:
        print("❌ 文件读取失败，请检查物理路径。")
        return

    min_len = min(len(data_a), len(data_b))
    stats = {"AA": 0, "BB": 0, "AB": 0, "BA": 0, "fail": 0}
    drifts = []

    for i in range(min_len):
        item_a, item_b = data_a[i], data_b[i]
        label = item_a.get('label', '')
        
        # 使用新规则判定正确性
        correct_a = is_logic_correct(item_a.get('predict', ''), label)
        correct_b = is_logic_correct(item_b.get('predict', ''), label)

        if correct_a and correct_b:
            stats["AA"] += 1 # 两次都对
        elif not correct_a and not correct_b:
            stats["fail"] += 1 # 两次都错
        elif not correct_a and correct_b:
            stats["AB"] += 1 # 运行B比运行A强 (修复)
            drifts.append({"idx": i, "type": "修复", "L": label, "A": item_a['predict'], "B": item_b['predict']})
        elif correct_a and not correct_b:
            stats["BA"] += 1 # 运行B比运行A弱 (退化)
            drifts.append({"idx": i, "type": "退化", "L": label, "A": item_a['predict'], "B": item_b['predict']})

    print("\n" + "="*70)
    print("📊 2052 实验室：SFT1 MedQA 逻辑模糊匹配审计报告")
    print("="*70)
    print(f"比对样本总数: {min_len}")
    print(f"● 绝对稳健 (两次均正确): {stats['AA']} ({stats['AA']/min_len:.2%})")
    print(f"● 逻辑增益 (运行B修正了A): {stats['AB']} 🟢")
    print(f"● 性能退化 (运行B弱于A): {stats['BA']} 🔴")
    print(f"● 顽固错误 (两次均错误): {stats['fail']}")
    print("-" * 70)
    
    # 打印前 5 个漂移样本
    for d in drifts[:5]:
        print(f"[{d['type']}] 索引 {d['idx']} | 答案: {d['L'].strip()} | A预测: {d['A']} | B预测: {d['B']}")
    print("="*70)

# 物理路径
path_a = "/Users/chenziyu/Desktop/test4.27/record/微调/medqa/sft1预测结果.jsonl"
path_b = "/Users/chenziyu/Desktop/meqda测试/generated_predictions.jsonl"

run_audit(path_a, path_b)