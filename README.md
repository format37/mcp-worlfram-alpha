# mcp-worlfram-alpha

Local MCP server giving Claude Code agents access to Wolfram Alpha.

Wraps the **Wolfram Alpha LLM API** (`/api/v1/llm-api`), not the classic
Full Results API — responses come back as LLM-shaped plaintext (input
interpretation, result, alternate forms, series, plot image URLs), so no
pod/subpod XML parsing.

## Tool

**`wolfram_query(query, maxchars=6800, units="metric")`** — one atomic
question per call: equations, integration/differentiation, ODEs,
series/limits, Laplace/Fourier/Z transforms, matrix ops, identity checks,
distributions, number theory, unit/constant conversion, plotting, and
scientific/numeric reference data. Failures return a single line starting
with `Error:` (including Wolfram's rephrasing suggestions on a 501).

Not for multi-step derivations that carry symbolic intermediates — use
SymPy in a code tool for those, this for atomic spot-checks.

## Setup

1. **AppID** — create one at <https://developer.wolframalpha.com> (free
   tier ~2000 calls/month).

2. **`.env`** in the project root (git-ignored):

   ```
   WOLFRAM_ALPHA_APPID=XXXXXX-XXXXXXXXXX
   ```

   Optional: `PORT` (default `8019`), `WOLFRAM_TIMEOUT` (seconds, default
   `30`), `MCP_TOKENS` (leave unset for local-only — auth is then
   disabled).

3. **Run** (binds `127.0.0.1:8019` only):

   ```bash
   ./compose.sh                          # build + start
   curl http://localhost:8019/health     # -> {"status":"healthy",...}
   ./logs.sh                             # follow logs
   ```

4. **Register with Claude Code**:

   ```bash
   claude mcp add --transport http --scope user \
       wolfram-alpha http://localhost:8019/wolfram/
   ```

   Verify with `claude mcp list` or `/mcp` in a session. The container has
   `restart: unless-stopped`, so it must be running for the MCP to connect.
