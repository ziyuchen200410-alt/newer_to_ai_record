# train-test

这个仓库旨在用一个 Qwen2.5-VL-7B-Instruct 的基座模型进行训练，学习医学知识，训练推理能力。

第一批数据来自：
```bibtex
@article{jin2020disease,
  title={What Disease does this Patient Have? A Large-scale Open Domain Question Answering Dataset from Medical Exams},
  author={Jin, Di and Pan, Eileen and Oufattole, Nassim and Weng, Wei-Hung and Fang, Hanyi and Szolovits, Peter},
  journal={arXiv preprint arXiv:2009.13081},
  year={2020}
}
```

## 🏗️ 阶段一：中文医学知识增量预训练 (Continued Pre-training)

### 1. 预训练动机 (Motivation)
通用大模型在面对垂直领域（如医学）时，常因缺乏专业语料覆盖而产生“幻觉”或术语理解偏差。本阶段通过 **增量预训练 (PT)** 任务，在 **Qwen2.5-VL-7B-Instruct** 的基础上注入海量中文医学核心教材，旨在：
* **语义对齐**：调整模型对医学专有名词（如病理机制、药物代谢）的概率分布。
* **逻辑重构**：使模型掌握医学文本特有的论述逻辑与因果关系。

### 2. 语料库构建 (Corpus Construction)
数据源自 `data_clean/textbooks/zh_paragraph/` 路径下的结构化纯文本教材。我们对 15 门以上的核心学科进行了清洗，保留了高质量的学术描述段落。

**涵盖学科清单：**
* **基础医学**：病理学、病理生理学、人体寄生虫学、局部解剖学。
* **临床医学**：内科学、妇产科学、儿科学、神经病学、精神病学、传染病学。
* **专科医学**：耳鼻咽喉头颈外科学、临床药理学、法医学。

### 3. 训练配置 (Training Configuration)
本阶段采用 **LoRA (Low-Rank Adaptation)** 技术进行轻量化参数更新，确保在注入知识的同时不破坏基座模型的通用对话能力。

#### 3.1 pre_train(rank64)
这一部分参数放在文件夹pre_train下
实验综述：首轮增量预训练（CPT）旨在验证 Qwen2.5-VL 在医学垂直领域的“冷启动”能力。实验证明，在 2048 长度的段落流形下，模型能够稳健地吸收医学教材的统计分布特征。
| 维度 | 核心参数/指标 | 逻辑审计 (Logic Audit) |
| :--- | :--- | :--- |
| **基础配置** | LoRA Rank 64 / Alpha 128 | 采用中等秩设定，平衡了参数表达力与计算开销，适合初步特征对齐。 |
| **数据规模** | 1830 Steps (3.0 Epochs) | 物理更新步数充裕，确保模型在权重空间有足够的位移跨越通用语料势垒。 |
| **切分逻辑** | 段落模式 (Paragraph) / Packing | 保持了医学因果逻辑的连贯性；由于 2048 窗口无填充，梯度信息密度极高。 |
| **计算策略** | LR 5e-5 / BS 16 / Cosine | 能量释放符合预期，余弦退火保证了后期在局部极小值附近的精细搜索。 |
| **硬件表现** | RTX 4090 / 39.6 GiB / 76°C | 显存利用率达 82.5%，FlashAttention-2 有效压制了长序列的计算复杂度。 |
| **收敛表现** | **Initial: 2.398 → Final: 1.982** | Loss 曲线呈现典型的对数下降，最终下降约 17.3%，未观察到灾难性遗忘。 |
#### 3.2.1 pre_train1(rank128)
实验综述：本阶段完成了医学全量语料的初步增量预训练（CPT）。通过高秩（Rank 128）配置，模型在段落级长文本上展现了良好的拟合趋势，为后续的高能冲刺奠定了权重基础。
| 维度 | 核心参数/指标 | 逻辑审计 (Logic Audit) |
| :--- | :--- | :--- |
| **基础配置** | LoRA Rank 128 / Alpha 256 | 采用高秩设定以增强模型对医学专业流形的表达能力，参数更新空间更广阔。 |
| **数据规模** | 744 Steps (3.0 Epochs) | 对应约 4000 个段落样本，步数经过精简但信息密度极高。 |
| **切分逻辑** | 段落模式 (Paragraph) / Packing | 物理上保留了完整的医学因果逻辑，通过 Packing 彻底消除了填充 Token 带来的梯度稀释。 |
| **计算策略** | LR 2e-5 / BS 16 / Warmup 100 | 采用了相对稳健的学习率策略，确保模型在热启动阶段平稳吸收新分布。 |
| **收敛表现** | **Initial: 2.709 → Final: 2.308** | Loss 下降约 14.8%，曲线平滑且无梯度爆炸，证明医学知识注入逻辑正确。 |
| **评估状态** | Eval Loss: 2.368 / PPL: 10.65 | 验证集指标与训练集高度对齐，模型处于健康的欠拟合转拟合阶段，未见遗忘风险。 |
#### 3.2.2 pre_train2(rank128)
这一部分继承上一部分的参数进行多3.5个epoch的训练

---

---
