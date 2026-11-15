"""Post-training for Junction 2026.

Experiments (same base Qwen3.5-9B, same LoRA recipe, same token budget per run):
  sft-ctrl   general open reasoning SFT data only (no game data)        -> "does more fine-tuning help?"
  sft-games  game data v2 only (reasoning trajectories + aux tasks)      -> "do games help?"
  sft-mix    general + game data                                         -> the candidate
  grpo-*     RL with engine-verified rewards from the best SFT v2 checkpoint
Each checkpoint is merged, served with vLLM and scored by `bench/` (PROTOCOL.md fixes the comparison).
"""
