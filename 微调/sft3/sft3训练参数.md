# 医疗大模型 SFT 阶段 3：知识召回（40GB 显存优化版）

本阶段核心目标是在显存受限（40GB）的前提下，通过高秩 LoRA 方案实现对 2.5 万条核心医疗知识的深度拟合与召回。

## 1. 模型与阶段定义
* **模型路径 (`model_name_or_path`)**: 使用第二阶段合并后的模型 `medical_qwen_sft2_merged`，进行增量微调。
* **训练阶段**: `sft` + `lora`。

## 2. LoRA 架构（模拟全参数量级）
* **秩次设置**:
    * `lora_rank`: `128`。采用高秩设计，赋予 LoRA 适配器足够的参数空间来捕捉复杂的知识映射。
    * `lora_alpha`: `256`。严格遵循 $2 \times r$ 的经验缩放，强化更新权重的影响力。
* **覆盖范围 (`lora_target`)**: `all`。全线性层注入，确保知识渗透到注意力机制与前馈网络的所有维度。
* **正则化**: `lora_dropout: 0.05`。保持较低的丢弃率，优先保证拟合强度。

## 3. 显存策略与极致压缩
* **序列长度 (`cutoff_len`)**: `512`。通过极度压缩序列长度，释放显存冗余，是适配 40GB 卡的关键。
* **优化器控制**: `paged_adamw_8bit`。利用分页技术（Paged）防止 OOM，并结合 8-bit 量化降低优化器状态的显存占用。
* **计算技巧**:
    * `gradient_checkpointing`: `true`。以时间换空间，减少激活值的存储。
    * `flash_attn: fa2`。加速计算并降低注意力矩阵的显存峰值。

## 4. 训练超参数
* **数据规模**: `cmb_pure_recall_25k`。
* **有效 Batch Size**: `32`。
    * `per_device_train_batch_size: 2`
    * `gradient_accumulation_steps: 8`
    * (注：若单卡运行，实际 Global Batch Size 为 16；若多卡则翻倍)。
* **学习率策略**: `1.0e-4`。采用 LoRA 典型的高学习率，配合 `cosine` 调度器及 10% 的 `warmup_ratio` 进行快速知识摄取。
* **计算精度**: `bf16: true`。

## 5. 输出管理
* **保存策略**: `save_strategy: "no"`。由于是增量微调且数据量较小，选择不保存中间 Checkpoint 以节省磁盘 IO 和空间，仅输出最终产物。