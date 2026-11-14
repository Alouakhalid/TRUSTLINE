# TRUSTLINE SKILLS REGISTRY

**Created:** November 14, 2026 (P06 kickoff)  
**Environment audited:** OpenCode agent harness (not Manus). Node v26.8.1, npm 11.19.0, Python 3.10.0rc2, macOS (Apple Silicon).

## 1. Skills Environment Discovery Findings

| Question | Finding |
|---|---|
| Does the host agent support Agent Skills? | **Yes** — OpenCode supports a `skill` tool with dynamically registered skills. Newly installed skills become invocable in-session and persist on disk across sessions. |
| Supported skill formats | SKILL.md directories (Claude/Vercel `skills` CLI format) with optional `references/` subdirectories. |
| GitHub skill repositories supported | **Yes** — the Vercel Skills CLI installs directly from `owner/repo`. |
| Is `npx skills` supported? | **Yes** — `npx -y skills` v1.8.1 (Vercel Skills CLI) verified working. |
| Where skills are installed | `<project>/.agents/skills/<skill-name>/` (project scope, persisted in the repository workspace). |
| Explicit invocation | **Yes** — skills can be invoked by ID via the agent's `skill` tool. |
| Instructions loaded during tasks | **Yes** — `skill` tool returns full SKILL.md + reference file list; references are read from disk as needed. |
| Persistence across sessions | **Yes** — files persist under `.agents/skills/`; the CLI also supports `experimental_install` from `skills-lock.json`. |

**Actual installation method used:** `npx -y skills add <owner>/<repo> --skill <skill-name> -y` executed in the repository root. All installations succeeded with the CLI reporting `✓ <skill> (copied) → ~/TRUSTLINE/.agents/skills/<skill-name>`.

**Verification of install claim:** every installed skill directory exists on disk under `.agents/skills/` (verified with `ls`), and each SKILL.md was returned by the loader during this session. No skill is claimed as "installed" without its files being present.

## 2. Installed Skills Inventory

| Skill | GitHub repo | Directory | Install method | Status | SKILL.md read | References loaded | Applied to |
|---|---|---|---|---|---|---|---|
| `ui-ux-pro-max` | nextlevelbuilder/ui-ux-pro-max-skill | `.agents/skills/ui-ux-pro-max` | `npx skills add` | INSTALLED | YES | design-system references as needed (P08) | Design system, tokens, dashboard design (P08) |
| `frontend-atlas` (GOATED UI) | flash-hero/GOATED-UI-SKILL | `.agents/skills/frontend-atlas` | `npx skills add` | INSTALLED | YES | motion-principles, interactions, component-recipes, webgl-shaders-3d, performance-a11y (P08) | Premium UI composition, motion strategy (P08) |
| `vercel-react-best-practices` | vercel-labs/agent-skills | `.agents/skills/vercel-react-best-practices` | `npx skills add` | INSTALLED | YES | rules selected per component work (P08) | React architecture/perf (P08) |
| `feature-arch` | PyModel/react-frontend-skills | `.agents/skills/feature-arch` | `npx skills add` | INSTALLED | YES | feature isolation + query rules (P08) | Frontend feature structure (P08) |
| `gsap-core` | greensock/gsap-skills | `.agents/skills/gsap-core` | `npx skills add` | INSTALLED | YES | on use | Timelines, `matchMedia`, reduced motion (P08) |
| `gsap-react` | greensock/gsap-skills | `.agents/skills/gsap-react` | `npx skills add` | INSTALLED | YES | on use | `useGSAP` hook + cleanup (P08) |
| `gsap-scrolltrigger` | greensock/gsap-skills | `.agents/skills/gsap-scrolltrigger` | `npx skills add` | INSTALLED | YES | on use | Scroll storytelling only (P08) |
| `3d-web-experience` | liuchiawei/agent-skills | `.agents/skills/3d-web-experience` | `npx skills add` | INSTALLED | YES | on use | Digital Twin scene architecture (P08) |
| `threejs-skills` | liuchiawei/agent-skills | `.agents/skills/threejs-skills` | `npx skills add` | INSTALLED | YES | on use | Three.js/R3F patterns (P08) |
| `fastapi-expert` | Emmraan/agent-skills | `.agents/skills/fastapi-expert` | `npx skills add` | INSTALLED | YES | pydantic-v2, endpoints-routing, testing-async | P06 backend (loaded during P06) |
| `api-design` | Emmraan/agent-skills | `.agents/skills/api-design` | `npx skills add` | INSTALLED | YES | on endpoint design | P06 API surface (loaded during P06) |
| `database-architecture` | Emmraan/agent-skills | `.agents/skills/database-architecture` | `npx skills add` | INSTALLED | YES | schema/indexing rules | P06 schema additions (loaded during P06) |
| `rag` | Emmraan/agent-skills | `.agents/skills/rag` | `npx skills add` | INSTALLED | YES | on RAG work only | Medical RAG context shaping (existing pipeline preserved) |
| `websocket-engineer` | Emmraan/agent-skills | `.agents/skills/websocket-engineer` | `npx skills add` | INSTALLED | YES | on telemetry work | Real-time telemetry + WS auth (P06/P07) |

**Playwright:** used as a testing tool (per the master prompt), not installed as a skill — it will be added as a devDependency of the frontend with real browser tests in P09. The upstream repository (microsoft/playwright) is documentation-only for us; license Apache-2.0.

## 3. Task → Skill Mapping

| Project task | Required skill | Notes |
|---|---|---|
| Design system | `ui-ux-pro-max` | Tokens, typography, color, accessibility |
| Frontend architecture | `vercel-react-best-practices` + `feature-arch` | Version-checked against actual package.json before applying |
| Premium interface | `frontend-atlas` | Motion + composition cookbook |
| Complex animations | `gsap-core` / `gsap-react` / `gsap-scrolltrigger` | Only where GSAP adds real value; reduced-motion respected |
| Smooth scrolling | `frontend-atlas` (scroll recipes) | Lenis only on presentation-like sections, never operational dashboards |
| 3D human model | `3d-web-experience` + `threejs-skills` | R3F + Drei; licensed GLB required |
| Animated components | `frontend-atlas` component-recipes | React Bits / 21st.dev references |
| Backend APIs | `fastapi-expert` + `api-design` | Applied to P06 endpoints |
| Database architecture | `database-architecture` | Schema/index/retention design |
| Real-time telemetry | `websocket-engineer` | WS subscriptions, backpressure, auth |
| Browser testing | Playwright (tool, not skill) | P09 end-to-end |

## 4. Compatibility Decisions and Rejections

| Decision | Rationale |
|---|---|
| **Keep synchronous SQLite store** (deviation from `fastapi-expert` MUST-DO "async DB") | The existing `backend/database/store.py` is a deliberate, dependency-light edge store ("works at spacecraft edge and in local tests") with WAL, RLock, and demo isolation. Replacing it with async SQLAlchemy would be an architecture rewrite without demonstrated necessity, violating the approved project decisions. The skill's Pydantic V2, Annotated-DI, status-code, and testing guidance IS applied. |
| **No CrewAI / no new orchestrator** | LangGraph Supervisor must remain the sole orchestrator (project decision). The `rag` skill is used for retrieval context shaping only. |
| **Do not blindly upgrade React/Next/TS/Tailwind** | Actual versions will be read from the frontend package manifest before applying `vercel-react-best-practices` version-specific rules. |
| **21st.dev / React Bits / Lenis** | Component sources, not Agent Skills — used selectively at P08; no auto-install of component collections. |
| **No duplicate/conflicting skills installed** | Only one skill per concern (e.g., `gsap-*` family from the official greensock repo, not third-party GSAP clones). |

## 5. Licenses

| Skill / source | License (as stated by repository) |
|---|---|
| nextlevelbuilder/ui-ux-pro-max-skill | Repository license at install time (MIT per repo notice) |
| flash-hero/GOATED-UI-SKILL | MIT (per repository) |
| vercel-labs/agent-skills | Per-package notices (skills for internal engineering use) |
| PyModel/react-frontend-skills | MIT (per repository) |
| greensock/gsap-skills | Skill docs; GSAP library itself is used under its standard (no-charge) license |
| liuchiawei/agent-skills | MIT (per repository) |
| Emmraan/agent-skills | MIT (per repository) |
| microsoft/playwright | Apache-2.0 |

Any 3D anatomical GLB model introduced in P08 **must** ship with a documented source + license (e.g., CC0/CC-BY asset). No invented asset URLs.
