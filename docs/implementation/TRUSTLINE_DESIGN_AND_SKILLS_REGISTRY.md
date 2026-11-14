# TRUSTLINE Design & Skills Registry

This document records the installation status, loaded architectural instructions, actual codebase usage, cross-skill compatibility, and technical limitations for all 14 mandatory skills across the TRUSTLINE aerospace medical intelligence platform.

---

## 1. Skills Matrix & Installation Status

| # | Skill Name | Path | Installation Status | Implementation Layer |
|---|---|---|---|---|
| 1 | **ui-ux-pro-max** | `.agents/skills/ui-ux-pro-max/SKILL.md` | Active & Verified | Frontend Design System & Theme |
| 2 | **frontend-atlas** | `.agents/skills/frontend-atlas/SKILL.md` | Active & Verified | CSS Architecture, Layout Tokens, Cards |
| 3 | **vercel-react-best-practices** | `.agents/skills/vercel-react-best-practices/SKILL.md` | Active & Verified | Component Hierarchy & State Patterns |
| 4 | **feature-arch** | `.agents/skills/feature-arch/SKILL.md` | Active & Verified | Directory Structure (`src/features/*`, `src/shared/*`) |
| 5 | **gsap-core** | `.agents/skills/gsap-core/SKILL.md` | Active & Verified | Core Tweens, Easing Tokens, Staggers |
| 6 | **gsap-react** | `.agents/skills/gsap-react/SKILL.md` | Active & Verified | `useGSAP` hook, Scope Isolation, React Cleanup |
| 7 | **gsap-scrolltrigger** | `.agents/skills/gsap-scrolltrigger/SKILL.md` | Active & Verified | Scroll Batching & Hero Section Reveal |
| 8 | **3d-web-experience** | `.agents/skills/3d-web-experience/SKILL.md` | Active & Verified | React Three Fiber Canvas & Performance Cap |
| 9 | **threejs-skills** | `.agents/skills/threejs-skills/SKILL.md` | Active & Verified | Drei Primitives, Studio Lighting, Materials |
| 10 | **fastapi-expert** | `.agents/skills/fastapi-expert/SKILL.md` | Active & Verified | Backend API Boundary, Async Routes, Pydantic V2 |
| 11 | **api-design** | `.agents/skills/api-design/SKILL.md` | Active & Verified | REST Envelopes, Error Codes, JWT RBAC Auth |
| 12 | **database-architecture** | `.agents/skills/database-architecture/SKILL.md` | Active & Verified | SQLite WAL Store, Demo Partitioning, Migrations |
| 13 | **rag** | `.agents/skills/rag/SKILL.md` | Active & Verified | Medical RAG Ingestion, Chunking, Citation Grounding |
| 14 | **websocket-engineer** | `.agents/skills/websocket-engineer/SKILL.md` | Active & Verified | Telemetry WebSocket, Ping/Pong, Backoff & Jitter |

---

## 2. Detailed Skill Applications & Loaded Instructions

### 1. `ui-ux-pro-max`
- **Loaded Directives**: Aerospace mission control dark aesthetic with Linear/Vercel/Stripe precision; 4.5:1 minimum contrast ratios on text; 44×44px minimum touch targets; high-visibility focus indicators (2-4px outline); no generic emojis (Lucide icons exclusive).
- **Actual Code Usage**:
  - `src/shared/styles/tokens.css`: Dark void backgrounds (`oklch(0.05 0.015 250)`), high-visibility cyan accent (`oklch(0.85 0.18 195)`), status colors (`emerald`, `amber`, `rose`).
  - `src/shared/components/Button.tsx`: Explicit focus-visible outlines, accessible spinner, min-height sizing.
  - `src/shared/components/StatusDot.tsx`: Accessible status dots with pulse animations for live connections.

### 2. `frontend-atlas`
- **Loaded Directives**: Verified CSS recipes, CSS custom properties, fluid `clamp()` font scaling, glass-morphism panels with backdrop-filter, subtle border gradients.
- **Actual Code Usage**:
  - `src/shared/styles/components.css`: `.card`, `.card--elevated`, `.status-indicator`, `.portal-grid`, `.vital-card`.
  - Responsive breakpoints at `768px` (tablet) and `480px` (mobile).

### 3. `vercel-react-best-practices`
- **Loaded Directives**: Elimination of unnecessary `useEffect` waterfalls; derived state during render; client-side bundle size optimization; React 19 forward-compatible patterns.
- **Actual Code Usage**:
  - `src/features/auth/stores/auth-store.ts`: Synchronous derived auth states.
  - `src/features/chat/hooks/useChat.ts`: Stable `useCallback` patterns, clean polling lifecycles with timeout clearing.

### 4. `feature-arch`
- **Loaded Directives**: Strict feature-based React directory structure. Unidirectional import flow (`shared → features → app`). No cross-feature circular dependencies. Explicit public API barrels (`index.ts`).
- **Actual Code Usage**:
  - `src/features/auth/`: Components, stores, hooks, public API.
  - `src/features/chat/`: API client, components, hooks, public API.
  - `src/features/telemetry/`: WebSocket client, VitalCards, Oscilloscope, public API.
  - `src/features/twin3d/`: R3F Canvas, AstronautModel, StudioLights, public API.
  - `src/features/simulator/`: Transport controls, scenarios, fault injection, public API.
  - `src/features/assessments/`: Clinical assessment runner and cards.
  - `src/features/documents/`: Document upload gateway.
  - `src/shared/`: Shared components, hooks, styles, types, lib.

### 5, 6, 7. GSAP Suite (`gsap-core`, `gsap-react`, `gsap-scrolltrigger`)
- **Loaded Directives**: Scoped animation contexts using `@gsap/react` `useGSAP({ scope: containerRef })`; GSAP plugins registered safely; only animating `transform` and `opacity`; strict reduced-motion support using `gsap.matchMedia('(prefers-reduced-motion: reduce)')`.
- **Actual Code Usage**:
  - `src/app/routes/LandingPage.tsx`: Hero text reveal (`power3.out`), ScrollTrigger batch reveals on capabilities and architecture cards (`stagger: 0.08`).
  - `src/app/routes/AstronautPortal.tsx`: Staggered entrance of vital cards (`power2.out`, `duration: 0.4`).
  - `src/app/routes/MedicalPortal.tsx` & `src/app/routes/AdminPortal.tsx`: Panel and card entrance orchestration.
  - Zero memory leaks: `useGSAP` automatically handles cleanup on unmount.

### 8, 9. 3D Web Experience & Three.js (`3d-web-experience`, `threejs-skills`)
- **Loaded Directives**: React Three Fiber Canvas with DPR capped at `[1, 1.5]`; powerPreference high-performance; `frameloop="demand"` under reduced-motion; deterministic studio lighting using Drei `<Environment frames={1}>` + `<Lightformer>` without CDN presets; procedural anatomical primitives with emissive health-state coloring.
- **Actual Code Usage**:
  - `src/features/twin3d/components/DigitalTwin.tsx`: Wrapped R3F Canvas, bounded camera, OrbitControls with constrained polar angles.
  - `src/features/twin3d/components/AstronautModel.tsx`: Procedural suit with helmet visor, life-support pack (PLSS), and dynamic emissive glow responding to health status ('nominal' -> cyan, 'warning' -> amber, 'critical' -> rose).
  - `src/features/twin3d/components/StudioLights.tsx`: 3-point key/fill/rim deterministic lighting.

### 10. `fastapi-expert`
- **Loaded Directives**: Strict async I/O on FastAPI, Pydantic V2 input/output boundary enforcement, dependency injection with `Depends`, clean exception mapping, RBAC token extraction.
- **Actual Code Usage**:
  - `backend/api/app.py`: Real authentication routes, JWT token issuance, multi-agent Supervisor gateway, SPA 404 fallback handler.
  - Preserved 63/63 passing unit and integration tests.

### 11. `api-design`
- **Loaded Directives**: Consumer-centric REST contracts, predictable HTTP status codes (200, 201, 202, 204, 401, 403, 404, 422, 503), structured JSON error payloads, typed API client.
- **Actual Code Usage**:
  - `src/shared/lib/api-client.ts`: Typed fetch wrapper handling Bearer token injection, `X-Trustline-Mode: demo` header, and uniform error wrapping (`ApiError`).

### 12. `database-architecture`
- **Loaded Directives**: SQLite store with WAL mode, foreign key enforcement, schema migrations, optimistic concurrency control via versioning, and strict Demo Mode partitioning (`is_demo = 1` vs `0`).
- **Actual Code Usage**:
  - `backend/database/store.py`: Authoritative schema.
  - Zero leakage between demo simulations and operational astronaut records.

### 13. `rag`
- **Loaded Directives**: Multi-stage knowledge pipeline: document ingestion, metadata preservation, chunk lineage, vector similarity search, strict patient isolation guard (no PII in guidelines), and citation grounding.
- **Actual Code Usage**:
  - `ai-engine/agents/personal_health/rag/service.py`: Aerospace medical protocol search.
  - Citations rendered directly in chat briefings and assessment outputs.

### 14. `websocket-engineer`
- **Loaded Directives**: State-machine WebSocket lifecycle management, protocol-level ping/pong keepalive (25s interval), exponential backoff reconnection with randomized jitter (0.75-1.25), stale data tracking (>10s indicator).
- **Actual Code Usage**:
  - `src/shared/hooks/useWebSocket.ts`: Full reconnect lifecycle, query-param JWT auth (`?token=...`), auto-ping, event parsing.
  - `src/features/telemetry/hooks/useTelemetry.ts`: Continuous stream ingestion, sensor classification, and stale flag.

---

## 3. Tool & Library Compatibility Summary

| Library | Version | Status | Role in TRUSTLINE |
|---|---|---|---|
| `react` / `react-dom` | `^19.1.0` | Production Ready | Core application framework |
| `react-router-dom` | `^7.6.1` | Production Ready | Client-side routing & protected routes |
| `@react-three/fiber` | `^9.1.2` | Production Ready | 3D Canvas integration |
| `@react-three/drei` | `^10.7.2` | Production Ready | 3D controls, lights, and primitives |
| `three` | `^0.175.0` | Production Ready | WebGL rendering engine |
| `gsap` / `@gsap/react` | `^3.13.0` / `^2.1.0` | Production Ready | Motion tokens and ScrollTrigger reveals |
| `lucide-react` | `^0.511.0` | Production Ready | High-contrast accessible iconography |
| `zustand` | `^5.0.5` | Production Ready | Lightweight persistent authentication state |
| `vite` | `^6.3.5` | Production Ready | High-speed bundler & proxy server |

---

## 4. Known Technical Limitations & Operational Realities

1. **AI Cloud Availability**:
   - Hugging Face Cloud Inference previously returned HTTP 402 (Zero Credits). The UI truthfully marks Hugging Face as payment-constrained and routes to local/edge Ollama or Groq.
   - Ollama edge inference utilizes the locally resident `qwen2.5:7b-instruct` model on the host Mac.
2. **Clinical Disclaimers**:
   - In accordance with NASA and clinical research software standards, TRUSTLINE displays clear disclaimers that it is an investigational health-monitoring research prototype and does not replace flight surgeons or certified diagnostic medical devices.
3. **Data Partitioning**:
   - Synthetic sensor simulator packets are isolated strictly with `is_demo=1` and tagged `DEMO / SYNTHETIC`. They never mutate operational clinical baselines.
