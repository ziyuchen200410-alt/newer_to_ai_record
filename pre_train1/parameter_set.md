1. 训练配置 (Training Configuration)
本阶段为针对医学全量语料的增量预训练 (CPT)，重点在于通过高秩 LoRA 矩阵捕获医学领域的深层语义特征。
| 参数 (Hyperparameters) | 取值 (Value) | 逻辑说明 (Logic) |
| :--- | :--- | :--- |
| **Stage** | `pt` | 增量预训练模式，专注于知识注入 |
| **LoRA Rank** | `128` | 提升参数秩以增强对复杂医学逻辑的建模能力 |
| **Cutoff Length** | `2048` | 匹配教材长段落，确保上下文逻辑完整 |
| **Packing** | `true` | 开启数据打包，消除填充 Token 带来的计算浪费 |
| **Learning Rate** | `2e-5` | 采用较为稳健的初始学习率，防止在 Instruct 基座上产生梯度震荡 |
| **Warmup Steps** | `100` | 初始 100 步线性预热，平滑进入高能优化区间 |
2. 训练产出与审计 (Artifacts & Audit)
由于开启了 packing 且数据按段落进行了逻辑整合，总训练步数相比初版大幅压缩至 744 步。

🛠️ 硬件与环境 (Hardware & Environment)
GPU: NVIDIA GeForce RTX 4090 (24GB/48GB 逻辑显存)

计算框架: LLaMA-Factory (v0.9.5.dev0) + PyTorch 2.5.1

加速技术: 开启 FlashAttention-2 与 FP16 混合精度训练
| 参数项 | 配置值 | 备注 |
| :--- | :--- | :--- |
| **Total Steps** | 744 | 对应 `num_train_epochs: 3.0` |
| **Effective Batch Size** | 16 | `per_device_train_batch_size: 4` × `grad_accum: 4` |
| **Learning Rate** | 2e-5 | Cosine 退火策略 |
| **Optimizer** | AdamW | -- |
| **Precision** | FP16 | 开启 FlashAttention-2 兼容模式 |
| **Max Length** | 2048 | 启用 `packing: true` 以保持语义连贯 |