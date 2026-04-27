import json
import re
import os

def extract_option_and_meaning(text):
    """
    严厉拆解选项与含义。
    支持格式：'E. 24小时内', 'E 24小时内', 'E', '24小时内'
    """
    if not text:
        return None, ""
    
    # 物理清理：去除换行符、首尾空格
    text = str(text).strip().replace("\n", "")
    
    # 正则审计：匹配开头为 A-E 的选项
    # Group 1: 字母, Group 2: 含义文本
    match = re.match(r'^([A-E])(?:[\.\s\：\、]+(.*))?$', text, re.IGNORECASE)
    
    if match:
        letter = match.group(1).upper()
        meaning = match.group(2).strip() if match.group(2) else ""
        return letter, meaning
    else:
        # 若无前导字母，则整体视为含义文本（用于找回“话痨”或纯含义输出）
        return None, text

def calculate_fuzzy_accuracy(file_path):
    if not os.path.exists(file_path):
        print(f"❌ 物理路径错误：找不到文件 {file_path}")
        return

    correct_count = 0
    total_count = 0
    semantic_recovered = 0 # 统计仅通过含义找回的样本数量

    print(f"🔍 正在审计文件: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                data = json.loads(line)
                predict_raw = data.get('predict', '')
                label_raw = data.get('label', '')
                
                # 提取预测项与标签项
                p_letter, p_meaning = extract_option_and_meaning(predict_raw)
                l_letter, l_meaning = extract_option_and_meaning(label_raw)
                
                is_correct = False
                
                # 判定逻辑：字母对 OR 意思对
                # 1. 优先判定字母对齐
                if p_letter and l_letter and p_letter == l_letter:
                    is_correct = True
                # 2. 其次判定语义对齐 (排除空值干扰)
                elif p_meaning and l_meaning and p_meaning == l_meaning:
                    is_correct = True
                    # 如果字母没对上（或者没给字母）但意思对了，记为语义找回
                    if not (p_letter and l_letter and p_letter == l_letter):
                        semantic_recovered += 1
                
                if is_correct:
                    correct_count += 1
                total_count += 1
                
            except Exception as e:
                print(f"⚠️ 解析异常 (跳过): {e}")

    # 逻辑审计结论
    if total_count > 0:
        # 使用 LaTeX 格式记录公式
        # $Accuracy = \frac{Correct}{Total} \times 100\%$
        accuracy = (correct_count / total_count) * 100
        print("\n" + "="*50)
        print("📊 2052 实验室：MEDQA 逻辑对齐审计报告")
        print("="*50)
        print(f"样本总量 (Total): {total_count}")
        print(f"正确总量 (Correct): {correct_count}")
        print(f"语义找回 (Semantic Recovered): {semantic_recovered}")
        print(f"最终准确率 (Accuracy): {accuracy:.2f}%")
        print("="*50)
    else:
        print("❌ 审计失败：样本量为零。")

if __name__ == "__main__":
    # 锁定物理路径
    target_path = "/Users/chenziyu/Desktop/test4.27/record/微调/meqda测试/sft1预测结果.jsonl"
    calculate_fuzzy_accuracy(target_path)