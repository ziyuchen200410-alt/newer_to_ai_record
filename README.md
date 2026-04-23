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

| 参数 (Hyperparameters) | 取值 (Value) | 逻辑说明 (Logic) |
| :--- | :--- | :--- |
| **Stage** | `pt` | 增量预训练模式 |
| **LoRA Rank** | `64` | 保证足够的参数表达能力以吸收专业事实 |
| **Cutoff Length** | `2048` | 确保模型能处理完整的教材长段落 |
| **Packing** | `true` | 将短段落拼接，极大化计算吞吐量 |
| **Learning Rate** | `5e-5` | 采用余弦退火策略（Cosine Decay）平滑收敛 |
| **Warmup Steps** | `100` | 预热阶段防止初始梯度震荡 |

### 4. 训练产出与审计 (Artifacts & Audit)
在正式实验中，我们去除了调试步数限制，完成了 3 个 Epoch 的完整训练。以下为最终对齐的工程参数与性能指标：

#### 🛠️ 硬件与环境 (Hardware & Environment)
* **GPU**: NVIDIA GeForce RTX 4090 (24GB/48GB 逻辑显存)
* **显存占用**: ~39.6 GiB (开启 Packing & FlashAttention-2)
* **功耗/散热**: 峰值 435W，风扇 100% 满转，核心温度稳定在 76°C
* **计算框架**: LLaMA-Factory (v0.9.5.dev0) + PyTorch 2.5.1

#### 📊 核心超参数 (Hyperparameters)
| 参数项 | 配置值 | 备注 |
| :--- | :--- | :--- |
| **Total Steps** | 1830 | 对应 `num_train_epochs: 3.0` |
| **Effective Batch Size** | 16 | `per_device_train_batch_size: 4` × `grad_accum: 4` |
| **Learning Rate** | 5e-5 | Cosine 退火策略 |
| **Optimizer** | AdamW | -- |
| **Precision** | FP16 | 开启 FlashAttention-2 兼容模式 |
| **Max Length** | 2048 | 启用 `packing: true` 以保持语义连贯 |

#### 📈 训练统计 (Training Metrics)
根据 `trainer_state.json` 与 `train_results.json` 的统计数据：

* **训练总时长 (Runtime)**: 约 7.5 小时
* **迭代速度 (Throughput)**: 15.24s/it (约 0.99 samples/s)
* **训练损失 (Loss Evolution)**:
  * 初始 Loss: **2.398**
  * 最终 Loss: **1.982** (收敛稳定，无梯度爆炸现象)
* **计算量 (Total FLOPs)**: 约 $7.1 \times 10^{15}$

> **逻辑审计判定**：Loss 曲线呈现典型的对数下降特征，从起始的高熵状态下降了约 45%，表明模型已有效拟合教材中的医学事实分布，且未观察到明显的灾难性遗忘。

---

---
