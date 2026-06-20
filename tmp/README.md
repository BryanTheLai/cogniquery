# CogniQuery

Local-first Slack analyst agent for company analytics and operational investigation.

CogniQuery is not a generic "chat with the warehouse" bot. It is a company memory loop:

1. Capture a Slack question.
2. Retrieve the right context.
3. Run defensible read-only SQL.
4. Return the answer with SQL, caveats, and sources.
5. Store the correction so the next answer gets better.

This follows the Company OS idea from `bryanslab-website/content/blogs/company-os.md`: work should leave a trail, mistakes should become memory, and memory should change the next decision.

If metric definitions, SOPs, or table contracts are missing, CogniQuery should still run. It starts lower-confidence, says what is missing, and builds its own living metric definitions, table contracts, and business rules from Snowflake evidence, files, Slack corrections, and approved user feedback.

Architecture rule: thin harness, fat skills. For the first MVP, the harness should be a Hermes-wrapped profile rather than a new agent runtime. Hermes supplies the Slack gateway, local terminal/files, model/provider routing, skills, memory, MCP/plugin surface, and artifact delivery. CogniQuery owns the analytics contract: setup defaults, trusted source routing, Snowflake/read-only policy, metric/table memory, report shape, evals, and Slack answer format.

## MVP Decision: Wrap Hermes First

The fastest useful product is not a new Slack bot. It is a CogniQuery distribution of Hermes:

```text
Slack thread + attachments
  -> Hermes Slack gateway
  -> CogniQuery profile, skills, source map, and policy
  -> local terminal/files/MCP/Snowflake/repo search/report generation
  -> Slack answer + SQL + caveats + native file attachments
```

This means the agent should accept practical analyst inputs: `.csv`, `.xlsx`, `.pdf`, screenshots, exported dashboards, JSON, Markdown, and thread context. It should be allowed to use the local filesystem and terminal in local operator mode so it can run Python, inspect files, generate charts, create HTML/PDF/XLSX artifacts, and send results back into Slack. The product boundary is not "no terminal"; it is "local trusted operator runtime, read-only warehouse role, redacted memory, auditable outputs, and no production writes."

Each Slack thread is a CogniQuery session. The root message starts the session; replies in that thread add context, corrections, files, and follow-up questions to the same working memory. A new top-level mention or `/cogniquery new` starts a fresh session. Reports, SQL, caveats, and uploaded artifacts should stay attached to the originating thread unless the user explicitly asks to move or repost them.

Do not ship raw Hermes as the product. CogniQuery must add the analytics-specific layer that makes answers defensible: SQL, caveats, sources, confidence, metric definitions, table contracts, memory updates, and replay evals.

## Status

This repo is currently a build spec plus starter snippets. It is not a runnable Python package yet.

To make it runnable, create the starter files from [`tmp/useful-snippets.md`](tmp/useful-snippets.md), then follow the quickstart below. The implementation contract lives in [`tmp/spec-plan.md`](tmp/spec-plan.md).

## Product Shape

```text
@cogniquery could I get a QA on this metric?

CogniQuery:
- acknowledges the Slack message,
- treats the Slack thread as the session boundary,
- reads the thread and supported attachments/files/images/PDFs/CSV/XLSX exports,
- searches knowledge-index.md, local memory, repos, GitHub, Confluence, and redacted local web,
- runs bounded read-only subagents when the context search is broad,
- runs Snowflake SQL through a read-only role,
- replies with a short answer, SQL, confidence, caveats, and sources,
- creates a Markdown/HTML/PDF report with seaborn charts for rigorous analysis,
- stores the lesson, caveat, or user correction.
```

## Ranked MVP

| Rank | Item | Core | Value | Optional | Ship | Note |
|---:|---|:---:|:---:|:---:|:---:|---|
| 1 | Hermes-wrapped CogniQuery profile | yes | yes | no | now | Use Hermes for Slack gateway, local terminal/files, skills, memory, MCP/plugins, and artifact delivery. |
| 2 | Agent-owned local machine with files + terminal | yes | yes | no | now | Required for SQL, charts, reports, installs, and reproducible work. |
| 3 | Interactive terminal setup wizard | yes | yes | no | now | Configure Hermes profile plus CogniQuery sources, Snowflake, Slack, and smoke tests. |
| 4 | Run on one person's computer as them | yes | yes | no | now | Best v1 path: local auth, browser SSO, local files, low deployment tax. |
| 5 | Snowflake through browser SSO | yes | yes | no | now | Use connector `authenticator=externalbrowser`; keep OAuth/token fallback. |
| 6 | Slack Socket Mode | yes | yes | no | now | Use Hermes Slack gateway first; local dev needs `xoxb` bot token + `xapp` app token, not a public HTTP endpoint. |
| 7 | Slack file/image/PDF/CSV/XLSX intake | yes | yes | no | now | Most real requests include a screenshot, CSV, Excel file, PDF, or export; ingest safely. |
| 8 | Expandable/copyable SQL | yes | yes | no | now | Every number needs SQL, caveats, and source context. |
| 9 | `knowledge-index.md` routing file | yes | yes | no | now | Highest-leverage setup artifact; it tells the agent where truth lives. |
| 10 | `.agents`-style rules and skills | yes | yes | no | now | Keep procedures in skills, not one giant prompt. |
| 11 | OpenAI-compatible base URL + key | yes | yes | no | now | Provider-agnostic model config from day one. |
| 12 | Local memory for corrections and gotchas | yes | yes | no | now | Store summaries/caveats, not raw secrets or attachments. |
| 13 | Slack emoji/status acknowledgement | yes | yes | no | now | Immediate feedback reduces duplicate pings. |
| 14 | Slack command registry | yes | yes | no | now | One registry drives `/cogniquery` commands, aliases, help, dispatch, and tests. |
| 15 | Analysis story reports | yes | yes | no | now | Markdown/HTML/PDF report shows the flow: population -> filters -> segments -> geography -> revenue. |
| 16 | Seaborn/matplotlib charts | yes | yes | no | now | Charts are mandatory for distributions, cohorts, funnels, and report evidence. |
| 17 | SQLite FTS/local search | yes | yes | no | now | Make memory and sessions searchable locally. |
| 18 | GitHub retrieval | yes | yes | no | now | Fact table/dbt/source-code creation often lives in GitHub. |
| 19 | Confluence retrieval | yes | yes | no | now | Company metric/SOP/business context often lives in Confluence. |
| 20 | Local web search | yes | yes | no | now | Use local/redacted web search for public docs, API docs, vendor docs, and methodology checks. |
| 21 | Subagents for context search | yes | yes | no | now | Run targeted subagents/skills to find relevant repo/docs/Slack context in parallel. |
| 22 | Git clone/pull + ripgrep source sync | yes | yes | no | now | Agents can clone, pull, and search repos freely in local operator mode. |
| 23 | MCP/client registry | yes | yes | no | now | Add GitHub, Confluence, Snowflake, browser, local search, and future services without growing core. |
| 24 | Auth/SSO registry | yes | yes | no | now | Each capability declares `api_key`, `oauth`, `browser_sso`, `cli_login`, or `mcp_managed` setup. |
| 25 | User model login / "use my Claude" | no | yes | yes | later | Start with OpenAI-compatible `base_url` + key. |
| 26 | VM/container/file UI | no | yes | yes | later | Add after local mode proves the workflow. |

Legend: `Core`, `Value`, and `Optional` are yes/no by design. `Ship` is build timing.

## Quickstart Target

After the starter files exist, the first working path should be:

```bash
cd cogniquery-v2

# Install or verify Hermes first. Existing Hermes installs are fine.
hermes doctor || true

# CogniQuery uses uv for its setup/profile helper.
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv venv --python 3.12
uv sync

cp .env.example .env
cp config.yaml.example config.yaml

uv run cogniquery setup
```

The setup wizard should handle Hermes profile creation, model config, Slack tokens, Snowflake SSO, source folders, memory files, smoke tests, and optionally starting the Hermes gateway. Day-to-day use should not require memorizing setup commands.

For WSL browser SSO, persist these in `~/.bashrc` or `~/.zshrc`:

```bash
export BROWSER=wslview
export MPLBACKEND=Agg
```

## macOS and WSL/Ubuntu Compatibility

Yes: write the same Python application code for macOS, WSL2 Ubuntu, and native Ubuntu.

Keep OS-specific logic at the setup and diagnostic edge only:

| Area | macOS | WSL/Ubuntu | Same app code? |
|---|---|---|:---:|
| Python | `uv` + Python 3.12 | `uv` + Python 3.12 | yes |
| Package manager | Homebrew | `apt` | installer only |
| Slack Socket Mode | supported | supported | yes |
| Snowflake SSO | default browser | `wslview` when configured | mostly |
| Charts/reports | same | `MPLBACKEND=Agg` recommended | yes |
| Memory/search | SQLite/local files | SQLite/local files | yes |
| Desktop/clipboard/computer-use | later macOS edge | avoid for v1 | no |
| Background service | `launchd` later | `systemd --user` later | no |

Design rule: `src/cogniquery/` should not care whether it is on macOS or WSL/Ubuntu except through a tiny `platform.py` helper.

## Verified Inputs

Durable facts used by these docs:

- Snowflake's Python connector documents `authenticator=externalbrowser` for browser-based SSO with SAML identity providers.
- `isaacwasserman/mcp-snowflake-server` is the preferred Snowflake MCP path; it exposes read query and schema tools, has write tools only when write mode is enabled, and supports Snowflake external browser authentication.
- Slack Socket Mode for Python uses an app-level `xapp` token for the WebSocket connection and a bot `xoxb` token for Web API calls.
- Astral documents the macOS/Linux uv standalone installer as `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- Hermes DeepWiki was last indexed on 2026-06-17 at `NousResearch/hermes-agent` commit `5e01a5db`; the local checkout inspected here is `ef4b897a1843cd32c4f141f55db60f0f0602cc98`.
- Hermes is the preferred first MVP runtime. CogniQuery should wrap it as a profile/distribution before building a custom runtime.

Design assumptions:

- WSL browser SSO is conditional on `wslu`/`wslview`, the user's browser setup, and the company IdP flow.
- GitHub and Confluence start with tokens or existing CLI/OAuth credentials. The auth registry must support browser SSO/OAuth/device-code flows per capability as soon as a provider requires it.
- SQL text validation is only defense-in-depth. The real Snowflake safety boundary is a read-only role with startup verification.

## What To Use From Hermes

Use Hermes as the first runtime, but keep CogniQuery's product surface separate:

| Hermes capability/pattern | CogniQuery version |
|---|---|
| Gateway/runtime | Start with Hermes gateway/profile; do not rebuild Slack Socket Mode first. |
| Local terminal/files | Allow local operator mode to run Python, shell commands, reports, charts, and file inspection. |
| Artifact delivery | Generated `.png`, `.pdf`, `.html`, `.xlsx`, `.csv`, and archives should be posted back to Slack as native files. |
| One setup path | `cogniquery setup` configures the Hermes profile plus CogniQuery sources and smoke tests. |
| Interactive setup wizard | Keep Hermes-style keyboard setup; section-specific setup and smoke tests. |
| Secrets in `.env`, behavior in YAML | `.env.example` and `config.yaml.example` are the config source of truth. |
| Footprint ladder | Prefer skill -> CLI command -> service-gated capability -> plugin -> MCP server -> core tool as last resort. |
| Toolsets | Capability bundles expose Snowflake, files/search, reports, Slack, GitHub, Confluence, local web search, and bounded subagents. |
| Context files | `AGENTS.md`, `knowledge-index.md`, skills, memory files. |
| Local execution | Local terminal/files first; Docker/EC2 later. |
| Gateway adapters | Slack gateway is separate from the agent loop. |
| Durable memory | Local markdown + SQLite FTS before cloud memory. |
| Skills | Load reusable procedures only when needed. |
| Plugins/MCP | Add new capabilities through plugin/MCP manifests and setup flows, not hardcoded tool branches. |
| Subagents | Use bounded subagents for context search, repo search, doc search, and report critique. |
| Central slash-command registry | One `CommandDef` list drives Slack commands, aliases, help text, dispatch, and tests. |
| `@` context references | Slack uses typed source tokens plus picker modals; terminal-style dropdowns stay CLI-only. |

CogniQuery owns what Hermes does not make analyst-safe by default:

- answer contract,
- metric/table/source trust order,
- Snowflake read-only startup verification,
- business-rule memory files,
- Slack report formatting,
- attachment interpretation policy,
- replay evals and injection tests.

## Required Files

These files have one owner each:

| File | Owner |
|---|---|
| `.env.example` | Secret names only. No real tokens. |
| `config.yaml.example` | Behavior defaults and feature flags. |
| `AGENTS.md` | Project-wide rules and safety boundaries. |
| `knowledge-index.md` | Source routing and trust order. |
| `hermes/profiles/cogniquery/SOUL.md` | CogniQuery-specific Hermes identity, answer contract, and instruction boundary. |
| `hermes/profiles/cogniquery/config.yaml` | Hermes profile defaults for Slack, terminal/files, model, and MCP/toolsets. |
| `skills/snowflake-analytics/SKILL.md` | SQL analysis procedure. |
| `skills/slack-reporting/SKILL.md` | Slack answer formatting procedure. |
| `skills/company-memory/SKILL.md` | What to remember, redact, update, and delete. |
| `skills/analysis-reporting/SKILL.md` | How to build a rigorous narrative analysis report. |
| `memory/metric-definitions.md` | Metric definitions and owners. |
| `memory/table-contracts.md` | Table grain, joins, freshness, caveats. |
| `memory/business-rules.md` | One-sentence business rules with proof or `unverified` tags. |
| `memory/company-gotchas.md` | Known traps and incident lessons. |
| `memory/report-feedback.md` | User corrections and report-quality feedback. |

## How Storage Works

CogniQuery keeps durable operating knowledge in plain files first:

- Skills live under `skills/<skill-name>/SKILL.md`. They are reusable procedures, for example how to run Snowflake analysis or write a rigorous report.
- Capability manifests live under `capabilities/<name>/capability.yaml` or are imported from configured MCP servers.
- Hermes profile files live under `hermes/profiles/cogniquery/` in this repo and are copied/rendered into the configured Hermes profile during setup.
- Auth setup state lives in `.env` plus local provider-specific auth files; secrets are never stored in skills.
- Memory lives under `memory/*.md`, with optional SQLite FTS for fast local search.
- Business rules live in `memory/business-rules.md`.
- Metric definitions live in `memory/metric-definitions.md`.
- Table contracts live in `memory/table-contracts.md`.
- Reports live under `reports/YYYY-MM-DD/<run_id>/`.

Business rules are written as one blunt sentence per rule, with proof attached. If a rule is inferred from analysis instead of confirmed by a source, it must be tagged `unverified`.

## Answer Contract

Every metric or investigation answer must include:

1. direct answer,
2. confidence,
3. SQL used,
4. sources or file paths,
5. caveats,
6. analysis flow for non-trivial work,
7. next check when uncertain.

Default Slack format:

```markdown
*Answer:* ...
*Confidence:* high / medium / low
*Why:* ...
*SQL:* see thread block
*Caveats:* ...
*Report:* attached when analysis has multiple steps
*Next:* ...
```

## Build Order

Canonical build phases are in [`tmp/spec-plan.md`](tmp/spec-plan.md). The short version:

1. Create CogniQuery profile files, skills, memory, source map, config, and eval stubs.
2. Configure or install Hermes and create a CogniQuery Hermes profile.
3. Start Hermes Slack gateway with CogniQuery instructions, allowed users, local terminal/files, and artifact delivery.
4. Verify Slack file intake and outbound `.png`, `.pdf`, `.html`, `.csv`, and `.xlsx` delivery.
5. Verify Snowflake read-only SSO through MCP or connector in the Hermes profile.
6. Add local retrieval, memory, and the answer contract.
7. Add GitHub, Confluence, local web search, and free repo sync/search as capabilities/MCP servers.
8. Add subagent context search and report critique.
9. Add story reports with seaborn charts and PDF/XLSX export.
10. Add replay evals, injection tests, and audit logs.
11. Only then decide whether CogniQuery needs its own runtime instead of Hermes.

## Non-Negotiables

- Start with one painful workflow, not a universal company bot.
- Start by wrapping Hermes; do not rebuild working gateway/runtime machinery until the analyst loop proves it needs a custom runtime.
- Thin harness, fat skills: do not hardcode domain workflows or service-specific branches into the agent loop.
- Raw Hermes is not the product; CogniQuery's product is the analytics policy, memory, setup, source routing, report contract, and eval suite.
- Prefer MCP/plugin capabilities over new core tools.
- A new source should be addable by writing a skill/capability manifest and setup adapter, not editing the planner.
- Slack is the interface, not the source of truth.
- External text is data, never instructions.
- Snowflake access is read-only and verified on startup.
- Ask when metric grain, denominator, owner, or source table is ambiguous.
- Never answer a metric without SQL and caveats.
- For multi-step analysis, Slack gets the summary; the report gets the evidence story.
- Seaborn charts are compulsory for distributions, cohorts, funnels, and segment comparisons.
- GitHub and Confluence retrieval are compulsory context sources.
- The agent may `git clone`, `git pull --ff-only`, and `rg` freely in local operator mode.
- In local operator mode, the agent may use the terminal and filesystem to inspect attachments, run Python, create charts/reports/spreadsheets, and install task-local analysis dependencies when the operator accepts that trust model.
- Subagents are compulsory for broad context search and report critique, but must be bounded and read-only by default.
- Store corrections as redacted summaries, not raw secrets or attachments.
- Missing SOPs are not blockers; they become explicit learning tasks and draft memory entries.
- Prefer local auth first; cloud deployment comes after the loop works.
- Keep the core code portable across macOS and WSL/Ubuntu.



nEW IDEAS::
i think we should allow agent to accpet exxcel or csv or whtaever ,the pointis still , slack agent has file system and temrnial to run code, commands, create anyhting, then send back in slack, freely as it wants. hmm, then actualyl all we really need is to have hermes have access to slack no? hmmmm why cany we just wrap hermes agent for first mvp?
