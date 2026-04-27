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

def is_correct_logic(predict_text, label_letter, label_meaning):
    """
    针对长文本的判别逻辑：
    1. 寻找文本末尾出现的选项字母。
    2. 寻找带有“答案”关键词后的选项字母。
    3. 检查标签的语义内容是否被包含在预测文本中。
    """
    if not predict_text: return False
    predict_text = str(predict_text).strip().replace("\n", "")

    # 策略 A: 寻找结论性语句中的字母 (e.g., "答案是A", "选项是： A", "选择A")
    conclusion_patterns = [
        r'答案(?:是|为|：|码为)?\s*([A-E])',
        r'选(?:项)?(?:是|为|：)?\s*([A-E])',
        r'正确答案(?:是|为|：)?\s*([A-E])'
    ]
    for pattern in conclusion_patterns:
        match = re.search(pattern, predict_text, re.IGNORECASE)
        if match and match.group(1).upper() == label_letter:
            return True

    # 策略 B: 寻找文本最后出现的 [A-E] 字母（通常模型会在最后总结）
    last_letter_match = re.findall(r'([A-E])(?![A-Za-z0-9])', predict_text, re.IGNORECASE)
    if last_letter_match and last_letter_match[-1].upper() == label_letter:
        return True

    # 策略 C: 语义覆盖（如果预测文本中包含标签的含义文字，且该含义在标签中较长，则视为找回）
    if label_meaning and len(label_meaning) > 1:
        if label_meaning in predict_text:
            return True

    return False

def run_medqa_audit(file_path):
    if not os.path.exists(file_path):
        print(f"❌ 物理路径错误: {file_path}")
        return

    total = 0
    correct = 0
    semantic_recovered = 0  # 统计通过语义或末尾找回的“话痨”样本

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                predict = data.get('predict', '')
                label = data.get('label', '')

                l_letter, l_meaning = extract_label_info(label)
                
                if is_correct_logic(predict, l_letter, l_meaning):
                    correct += 1
                    # 如果不是简单的头匹配成功，则计为语义找回
                    if not predict.strip().startswith(l_letter if l_letter else "NONE"):
                        semantic_recovered += 1
                total += 1
            except:
                continue

    if total > 0:
        acc = (correct / total) * 100
        print("\n" + "="*60)
        print("📊 2052 实验室：Base 模型长文本逻辑审计报告")
        print("="*60)
        print(f"文件路径: {file_path}")
        print(f"总样本量: {total}")
        print(f"正确数量: {correct}")
        print(f"语义及末尾提取找回: {semantic_recovered} (占正确数的 {semantic_recovered/correct:.2%})")
        print("-" * 60)
        print(f"🎯 最终准确率 (Accuracy): {acc:.4f}%")
        print("="*60)
    else:
        print("❌ 未能提取到有效数据。")

if __name__ == "__main__":
    target = "/Users/chenziyu/Desktop/test4.27/record/微调/meqda测试/原模型预测结果.jsonl"
    run_medqa_audit(target)