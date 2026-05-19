---
name: wolfram-alpha
description: Query Wolfram Alpha's computational engine via the local wolfram-alpha MCP server (wolfram_query). Use to compute or VERIFY self-contained math — integrals, derivatives, ODEs, series/limits, Laplace/Fourier/Z transforms, matrix ops (eigenvalues/det/inverse), equation solving, identity checks, distributions, number theory — and for unit/physical-constant conversion, plotting an expression, and scientific/numeric/geographic/financial reference data. Reach for it whenever a hand-computed math result should be double-checked, or an exact closed form / authoritative constant is needed.
---

# wolfram-alpha

The `wolfram-alpha` MCP server wraps the **Wolfram Alpha LLM API**. One
tool, returning LLM-shaped plaintext (no XML/pod parsing):

```
mcp__wolfram-alpha__wolfram_query(query: str, maxchars: int = 6800, units: str = "metric") -> {"result": str}
```

## 1. When to use it

Use it for **self-contained, atomic** computation or reference — one
question per call:

- closed-form integration / differentiation, ODEs
- solving equations / systems / inequalities
- series / Taylor / asymptotic expansion, limits
- Laplace / Fourier / Z transforms
- matrix ops: eigenvalues, determinant, inverse, rank, nullspace
- simplifying or **verifying a symbolic identity** (e.g.
  `simplify (sin x)^2 + (cos x)^2`, or
  `is d/dx[x^x] equal to x^x (ln(x)+1)`)
- statistical distributions, combinatorics, number theory
- unit / physical-constant conversion, dimensional checks
- plotting an expression (the result text carries `https://…png` URLs)
- scientific / numeric / geographic / financial reference data

**Strong default:** whenever you produce a non-trivial math result by
hand (an integral, an eigenvalue, a transform, an algebraic
simplification), spot-check it with one `wolfram_query` call before
presenting it as correct. Cheap insurance against a confidently wrong
answer.

## 2. When NOT to use it

It is weak at *contextual / multi-step* derivations where symbolic
intermediates must be carried across steps (RL Bellman / HJB,
multi-stage proofs). For those, keep symbolic objects in memory with
**SymPy in a code tool** and use `wolfram_query` only for atomic
spot-checks of individual steps. They complement, not substitute.

Also skip it for: pure arithmetic you can do trivially, non-math
questions, anything needing private/in-context data Wolfram can't see.

## 3. Writing good queries

- Plain natural language *or* Wolfram syntax both work:
  `"integrate x^2 sin(x) dx"`, `"solve x^2 + 3x - 4 = 0"`,
  `"eigenvalues {{1,2},{3,4}}"`, `"Laplace transform of t^2 e^(-3t)"`,
  `"speed of light in furlongs per fortnight"`.
- One atomic question per call. Don't chain ("solve this then plug
  in") — split into separate calls and combine yourself.
- Matrices: `{{a,b},{c,d}}`. Powers: `^`. Multiplication: explicit `*`
  or space.
- `units="imperial"` for imperial output; default `"metric"`.
- `maxchars` clamps to 200..25000. Raise it if a result looks
  truncated; lower it to save context. Default 6800 is usually fine.

## 4. Reading the result

The `result` string is prose-shaped and typically contains: the query
echo, **input interpretation** (check Wolfram understood you — a wrong
interpretation is the #1 failure mode, re-query more explicitly if so),
the primary result, alternate/closed forms, series, definite-integral
values, and plot image URLs. Use the input-interpretation line to
sanity-check before trusting the answer.

## 5. Errors

On failure the result is a single line starting with `Error:`:

- `Error: Wolfram Alpha did not understand the input (501). … Things to
  try instead: …` — rephrase using Wolfram's own suggestions and retry
  once.
- `Error: … rejected the AppID (403)` / `Error: WOLFRAM_ALPHA_APPID is
  not configured` — server-side config problem; tell the user, don't
  retry.
- `Error: … timed out` — heavy query; simplify it or retry once.

Report a genuine failure honestly; never fabricate a result the tool
didn't return.

## 6. The server is LOCAL — it must be running

The MCP server is a local Docker container (`mcp-wolfram`), bound to
`127.0.0.1:8019`, repo at `/home/alex/projects/mcp-worlfram-alpha`. It
has `restart: unless-stopped` but is not running if Docker/the host was
down.

If `wolfram_query` calls fail with a connection/transport error (not a
Wolfram `Error:` line), the container is likely down. Recover:

```bash
cd /home/alex/projects/mcp-worlfram-alpha
curl -s http://localhost:8019/health        # {"status":"healthy",...} == up
docker compose up -d                          # start if down
./compose.sh                                  # rebuild+restart after code changes
```

Then retry the query. Source/deploy details are in the repo README.
