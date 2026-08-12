# 新服务器上的 Pi0.5 Sanity Training

- 结果：通过
- GPU：NVIDIA RTX 6000D
- 总显存：83.05 GiB
- Steps：20 / 20
- Batch size：1
- 精度：bfloat16（Accelerate bf16）
- 仅训练 expert：是
- Gradient checkpointing：开启
- 冻结 vision encoder：是
- 峰值 allocated VRAM：12.85 GiB
- 峰值 reserved VRAM：13.00 GiB
- 平均 step 时间：0.4727584111038595 秒
- 总运行时间：131.95 秒
- 初始 loss：1.4703712463378906
- 最终 loss：1.9117406606674194
- 所有 loss 均为有限值：是
- OOM：否
- 最终 checkpoint：通过（`/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_sanity_new_server/run/checkpoints/000020`）
