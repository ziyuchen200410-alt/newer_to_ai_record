# 医疗大模型第二轮 SFT 训练配置总结

该配置旨在对已具备一定医疗能力的模型（medical_qwen_v2_final）进行大规模（26万条数据）的精度微调。

## 1. 模型基础配置
* **基座路径 (`model_name_or_path`)**: `/data1/student/czy/LLaMA-Factory/models/medical_qwen_v2_final`
* **远程代码控制 (`trust_remote_code`)**: `true`。

## 2. LoRA 微调参数
* **策略**: 采用全量线性层注入 (`lora_target: all`)。
* **秩次与缩放**: 
    * `lora_rank`: `16`。相比首轮大幅收敛秩次，侧重于在现有权重上的微调而非结构性重塑。
    * `lora_alpha`: `32`。保持标准 2:1 比例。
* **正则化 (`lora_dropout`)**: `0.1`。相比首轮（0.05）提高了丢弃率，增强了在大规模数据集上的泛化能力，防止过拟合。

## 3. 数据处理规格
* **数据集 (`dataset`)**: `cmb_sft_26w` (26万条量级)。
* **样本控制**:
    * `max_samples`: `270000`。
    * `cutoff_len`: `1024`。缩短序列长度以换取更高的吞吐量和训练速度。
* **预处理**: 使用 16 线程 (`preprocessing_num_workers: 16`) 配合 `overwrite_cache`。

## 4. 优化器与训练超参
* **学习率 (`learning_rate`)**: `5.0e-6`。极低的学习率，符合第二轮精细化对齐（Refine）的逻辑。
* **调度器 (`lr_scheduler_type`)**: `cosine`。使用余弦退火策略，确保训练末期权重趋于平稳。
* **预热比例 (`warmup_ratio`)**: `0.05`。
* **训练轮数 (`num_train_epochs`)**: `1.0`。在大规模数据集上仅跑 1 个 Epoch 以控制计算资源成本。

## 5. 性能与并行加速
* **精度策略**: `bf16: true`。利用 BFloat16 提升数值稳定性，避免深度微调中的梯度消失或爆炸。
* **算子优化**: `flash_attn: fa2`。开启 Flash Attention 2，是支撑 26 万条数据在有限时间内跑完的关键。
* **批处理规模**:
    * `per_device_train_batch_size`: `4`。
    * `gradient_accumulation_steps`: `8`。
    * **等效 Global Batch Size**: `32 * GPU数量`。
* **超时设置 (`ddp_timeout`)**: `180000000`。设置为超长超时，防止大规模 DDP 通信在数据加载或保存时崩溃。

## 6. 保存与输出
* **输出目录**: `saves/qwen_v2_sft2_final`。
* **策略**: 每 2000 步保存一次 Checkpoint，每 10 步记录一次日志。