# π0.5 Smoke Test

状态：已验证 Hugging Face gated tokenizer 访问权限；当时正在预下载固定版本的公开模型和数据集，尚未开始正式训练、Rollout 或 Evaluation。

目标实验：

- GPU：NVIDIA GeForce RTX 4090 24 GB
- Policy：`pi05`
- Dataset：`lerobot/libero`
- Batch size：1
- Steps：50
- 精度：bfloat16
- Gradient checkpointing：开启
- Expert-only training：开启
- 对 LeRobot 上游源码的修改：无

Smoke test 完成后，远程 GPU 服务器的运行产物将复制到本目录。
