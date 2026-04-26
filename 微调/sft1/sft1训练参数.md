# 医疗大模型 SFT 阶段训练配置总结

该配置文件定义了基于 **Qwen** 系列基座模型进行指令微调（SFT）的关键参数，采用了高秩次的 **LoRA** 适配方案。

## 1. 模型与路径配置
* **模型来源 (`model_name_or_path`)**: 使用已合并的本地模型路径 `./models/medical_qwen_v1_base`，表明这是在已有医疗能力基础上的增量微调。
* **远程代码加载 (`trust_remote_code`)**: `true`。允许加载模型目录下的自定义算子或配置。

## 2. 训练阶段与方法
* **训练阶段 (`stage`)**: `sft` (Supervised Fine-Tuning)。通过人工标注的对话数据进行监督学习。
* **微调方法 (`finetuning_type`)**: `lora`。使用低秩自适应（Low-Rank Adaptation）技术，降低显存占用。
* **LoRA 核心参数**:
    * **目标层 (`lora_target`)**: `all`。对模型所有线性层注入低秩矩阵，这种配置通常能获得更强的拟合能力。
    * **秩次 (`lora_rank`)**: `128`。相较于常规的 8 或 16，128 属于**高秩次**，旨在捕获更复杂的医疗领域指令特征。
    * **缩放系数 (`lora_alpha`)**: `256`。通常设为 `lora_rank` 的 2 倍，用于稳定训练过程中的权重缩放。
    * **丢弃率 (`lora_dropout`)**: `0.05`。防止过拟合。

## 3. 数据处理
* **数据集名称 (`dataset`)**: `medical_sft_train`。
* **提示词模板 (`template`)**: `qwen`。确保输入格式与 Qwen 模型的预训练阶段保持对齐。
* **截断长度 (`cutoff_len`)**: `2048`。限定单条样本的最大 Token 数。
* **并行加速 (`preprocessing_num_workers`)**: `16`。使用 16 线程进行数据预处理。

## 4. 优化策略与资源配置
* **学习率 (`learning_rate`)**: `1e-5`。较小的学习率有助于在微调阶段精细调整参数，避免破坏原有权重。
* **训练轮数 (`num_train_epochs`)**: `3.0`。
* **计算精度**:
    * **`fp16`**: `true`。开启半精度浮点数训练，平衡计算速度与精度。
    * **`flash_attn`**: `fa2` (Flash Attention 2)。利用硬件加速注意力机制计算，显著降低长序列的显存压力。

## 5. 输出与监控
* **输出路径 (`output_dir`)**: `saves/medical_sft1`。
* **可视化 (`plot_loss`)**: `true`。训练结束后将生成损失函数（Loss）变化图表。