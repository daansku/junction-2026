# API keys: which variable is which

Keys live only in `.env` in the repo root. Git ignores `.env`, so never `git add -f` it.
Share key values only over a private channel, never in git, chat logs or issues.
Sweeps that count run from A3's machine, so that `.env` needs every key. Other machines only need the keys they test with.

## Setup

```bash
cp .env.example .env      # once per clone; then paste values after the `=`
chmod 600 .env
```

The arena loads `.env` automatically (`python -m arena …`).

## Variables

| Variable | Provider / endpoint | Used by (`arena/models.yaml` ids) |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` |
| `GEMINI_API_KEY` | Google Gemini, OpenAI-compatible layer | `gemini-flash`, `gemini-pro` |
| `FEATHERLESS_API_KEY` | featherless.ai, `https://api.featherless.ai/v1` | `featherless-open` (DeepSeek V3.2), `featherless-kimi-k2-6`, `featherless-glm-5-3`, `featherless-qwen3-5-397b`, `featherless-gpt-oss-120b`, `featherless-qwen3-5-9b`, `featherless-qwen3-vl-30b` |
| `NVIDIA_VERDA_INFERENCE_KEY` | Verda (DataCrunch) deployment of NVIDIA Nemotron, `https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1` | `nemotron-3-5-super-vl` |
| `VERDA_INFERENCE_KEY` | Verda managed inference API, `https://inference.verda.com/v1` (URL fixed in `arena/models.yaml`) | `verda-kimi-k3-1-pro` (Kimi K3.1 Pro) |
| `VERDA_BASE_URL` | our own Verda deployment, if we make one (URL must end in `/v1`); uses `VERDA_INFERENCE_KEY` | `verda-small` (not set up) |
| `NVIDIA_API_KEY` | build.nvidia.com API | none at the moment |
| `MODAL_BASE_URL` | Modal endpoint serving a model, **with `/v1`**, e.g. `https://gnudgnaoh-work--ep-junction26-server.eu-west.modal.direct/v1` | `provider: modal` models (fine-tune) |
| `MODAL_API_KEY` | Modal **proxy auth token**, written as `wk-<id>.ws-<secret>` (both parts joined by a dot). Create it in the Modal dashboard → Settings → Proxy Auth Tokens. The endpoint answers `401 proxy auth required` without it. | `provider: modal` models |
| `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | Modal **CLI/API** token, used to deploy and fine-tune (`modal deploy`, `modal run`). Not the endpoint key. | fine-tune scripts |
| `OPENAI_BASE_URL`, `OPENAI_API_KEY` | any OpenAI-compatible endpoint (optional) | none at the moment |
| `ADMIN_TOKEN` | our server's `/api/admin/*` | server only |

## Common mistakes

- **The Nemotron key is not `NVIDIA_API_KEY`.** Nemotron runs on Verda: its key goes in `NVIDIA_VERDA_INFERENCE_KEY`.
- **A Verda key works only for its own deployment.** The Nemotron endpoint serves only `nemotron-3.5-super-vl`, and other model names return 404. With `VERDA_INFERENCE_KEY`, `https://inference.verda.com/v1/models` lists only `kimi-k3-1-pro`.
- **Verda URLs need `/v1`.** `https://inference.verda.com/chat/completions` returns 404; `https://inference.verda.com/v1/chat/completions` works. Kimi's URL is fixed in the registry, so `VERDA_BASE_URL` is not needed for it.
- **The Nemotron endpoint returns 404 without a valid key, on every path including `/v1/models`.** A 404 there usually means a missing or wrong key, not a wrong URL.
- **Modal has two kinds of token.** The CLI token (`MODAL_TOKEN_ID/SECRET`) deploys apps. The proxy auth token (`MODAL_API_KEY` = `wk-….ws-…`) calls an endpoint. The arena sends it as `Authorization: Bearer wk-….ws-…`, which the Modal proxy accepts.
- **Before 2026-11-14 ~03:30 the Nemotron key was read from `VERDA_INFERENCE_KEY`.** If you put it there, rename it to `NVIDIA_VERDA_INFERENCE_KEY`.

## Check a key works

```bash
.venv/bin/python -m arena models --check     # lists live models per provider (not Nemotron: its /models needs the key)
.venv/bin/python -m arena play --model nemotron-3-5-super-vl --game <game_id> --api http://localhost:8000
```

Use a local server (`--api http://localhost:8000`) for key tests, so test runs stay out of the shared results.

## Adding a deployment with its own key

In `arena/models.yaml`, a model entry can override the provider defaults:

```yaml
  provider: verda
  base_url: https://<deployment>/v1
  api_key_env: SOME_NEW_KEY_NAME
```

Then add `SOME_NEW_KEY_NAME=` to `.env.example` and a row to this table.
