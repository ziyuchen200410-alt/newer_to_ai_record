(base) chenziyu@ChendeMacBook-Air sft2 % /Users/chenziyu/.pyenv/versions/3.11.9/bin/python /Users/chenziyu/Desktop/test4.27/sft2/unknown.py
✅ 已提取 11 个 Unknown 问题到 unknown_audit.txt
(base) chenziyu@ChendeMacBook-Air sft2 % /Users/chenziyu/.pyenv/versions/3.11.9/bin/python /Users/chenziyu/Desktop/test4.27/sft2/eval.py

============================================================
📊 MEDICAL LLM FINAL AUDIT REPORT
Source: generated_predictions.jsonl
============================================================
[SINGLE QUESTIONS]
  Accuracy: 73.99% (7406/10010)
  └─ Semantic Recovered: 0 (通过内容对齐找回)
------------------------------
[MULTI QUESTIONS]
  Accuracy: 51.76% (616/1190)
  └─ Under-selected: 138 | Over-selected: 295
------------------------------
⭐ GRAND TOTAL ACCURACY: 71.6250% (8022/11200)
============================================================