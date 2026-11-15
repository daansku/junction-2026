"""Run lm-eval with one extra model type, `bench-chat-completions`, then hand over to lm-eval's own CLI.

Why: in lm-eval 0.4.13 the `local-chat-completions` model sends each task's stop sequences (e.g. GSM8K's "Q:") to the
server. A thinking model writes those strings inside its <think> block, so generation stops mid-thought and the item
scores 0 (seen in a smoke run: 9 of 25 GSM8K items cut at "Q:"). lm-eval's in-process vLLM backend already
avoids this when `think_end_token` is set (it stops only at EOS and strips thinking first). This subclass does the
same for the API path: no task stop sequences on the request; the chat turn ends at the model's own end-of-turn,
and thinking is stripped by the parent's `think_end_token` handling.

    python -m bench.lmeval_shim --model bench-chat-completions --model_args ... (all other lm-eval flags as usual)
"""
from __future__ import annotations

import runpy

from lm_eval.api.registry import register_model
from lm_eval.models.openai_completions import LocalChatCompletion


@register_model("bench-chat-completions")
class BenchChatCompletion(LocalChatCompletion):
    def _create_payload(self, messages, generate=False, gen_kwargs=None, seed=1234, eos=None, **kwargs) -> dict:
        payload = super()._create_payload(messages, generate=generate, gen_kwargs=dict(gen_kwargs or {}),
                                          seed=seed, eos=eos, **kwargs)
        payload.pop("stop", None)
        return payload


if __name__ == "__main__":
    runpy.run_module("lm_eval", run_name="__main__", alter_sys=True)
