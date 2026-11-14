# Fine-tune pipeline (A3-09 / A3-11)

1. **Data** (CPU, ~2 s/game):
   `python -m arena dataset --collection train-v1 --recover 2 --out ~/junction-data/sft/train-v1.jsonl`
   One example per harness turn, identical to what `agent_loop` h1 sends a text model (input mode `rle`).
   Optimal play plus recover-from-mistake trajectories (random detours are context only, never targets).
   Refuses any collection named `eval*`.
2. **Train** on one GPU (Verda instance or Modal): `train_sft.py --base <hf id> --data ... --out ...` (LoRA, loss on reply only).
3. **Merge + serve** with vLLM (OpenAI-compatible): see the docstring in `train_sft.py`.
4. **Register** in `arena/models.yaml`: `provider: verda` (or `modal`), `tier: finetuned`, `input_modes: [rle]`,
   `api_model: arena-ft`, `verified: true`; set `VERDA_BASE_URL` / `MODAL_BASE_URL` in `.env`.
5. **Eval** on `eval-v1` only, and run the **untuned base model** through the same harness as the comparison row.

The tiebreaker claim is "small model improves after training on experience from the environment", so the
base-vs-tuned pair on held-out eval games is the result that matters, not the absolute rank.
