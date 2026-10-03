# Final Submission Checklist & Final-Day Protocol

**Step**: 30 — Submission check and final-day protocol  
**Date**: 2026-10-04  
**Auditor / Owner**: Assaduzzaman  
**Repository Branch**: `main`  
**Reference Guidelines**: AI Hackathon Rulebook Sections 5.3, 6.1, 6.2, 7 & Student Guideline Section 14  

---

## 1. Submission Gate Verification

| Check Item | Requirement / Rulebook Citation | Observed Status | Verified Evidence / Details |
| :--- | :--- | :---: | :--- |
| **1. Public Repository Isolation** | Rulebook 6.2 & Submission Plan: Clean clone without internal planning contamination | **PASS** | Automated audit of all 187 tracked files in `CampaignLift-Hackathon`: **0** denylisted paths (`planning/`, `decisions/`, `tasks/`, `agent-transcripts/`, `.env`, secrets). |
| **2. Incremental Git Commit History** | Rulebook 5.3: Continuous incremental commits required; single final upload strictly prohibited | **PASS** | Public repository contains **103 granular, chronological commits** spanning data schemas, ML training, backend routes, frontend views, and documentation. |
| **3. Project Report Draft** | Rulebook 6.2: Written project report following the official challenge outline | **READY** | Documented in [`docs/report_draft.md`](report_draft.md) with all 8 canonical sections and verified measured numbers from JSON artifacts. |
| **4. Demonstration Video Plan** | Rulebook 6.2: Product video walkthrough demonstrating working software | **READY** | Detailed 7-scene storyboard documented in [`docs/video_script.md`](video_script.md) using the observed demo path (highlighting customer `C00000170`). |
| **5. Working Prototype Stack** | Rulebook 6.2 & 7: Executable prototype with verified readiness | **READY** | Dual-container stack (`docker-compose.yml`) verified locally on port 80; passes automated liveness (`/health`) and readiness (`/ready`). |
| **6. Public GitHub Remote URL** | Rulebook 6.2: Accessible public GitHub repository link | **READY** | `https://github.com/mosabbir-maruf/CampaignLift-Hackathon.git` |
| **7. Official Submission Portal** | Rulebook 6.1: Submission to official hackathon portal | **UNVERIFIED** | Waiting for official organizer portal URL. No unauthorized external submission attempted. |

---

## 2. Public Repository Allowlist & Denylist Audit

Automated scan executed against `C:\Users\Assaduzzaman\Coding\CampaignLift-Hackathon`:

### Verified Allowlisted Components
- `backend/` (FastAPI services, routes, schemas, settings, tests, Dockerfile)
- `frontend/` (React 19 SPA, Tailwind CSS v4, Nginx config, Dockerfile, package.json)
- `ml/` (Uplift candidates, metrics, report evaluator, baseline models, Kaggle notebook)
- `data/` (`src/`, `config/`, `schemas/`, `fixtures/`, `manifests/`, `tests/`)
- `docs/` (`architecture.md`, `ml_methodology.md`, `api.md`, `deployment.md`, `reproducibility.md`, `responsible_ai.md`, `data_dictionary.md`, `security_checklist.md`, `test_evidence.md`, `demo_evidence.md`, `report_draft.md`, `video_script.md`, `submission_checklist.md`)
- Root: `README.md`, `docker-compose.yml`, `.env.example`, `pytest.ini`

### Confirmed Denylist Exclusions (Zero Violations)
- `planning/` -> **ABSENT**
- `decisions/` -> **ABSENT**
- `tasks/` -> **ABSENT**
- `agent-transcripts/` -> **ABSENT**
- `.env` / credentials / private keys -> **ABSENT**
- `data/generated/` / large raw dumps -> **ABSENT**
- `data/reports/` -> **ABSENT**

---

## 3. Final-Day Protocol & Governance Rules

When the hackathon moves into the final on-site phase:

### Rule 1: Handling On-Site Challenge Updates
1. Upon organizer announcement of the on-site problem update or modification:
   - Record the new requirement in `decisions/decision_log.md`.
   - Implement only the specific requested delta.
   - Run the automated test suites (`pytest`) to ensure zero regressions.
   - Commit to the internal branch and cleanly export the approved change to public `main`.
2. Do not widen scope or attempt unsolicited rewrites.

### Rule 2: The Final 90-Minute Freeze
- **Absolute Coding Freeze**: Stop coding immediately when the final 90 minutes of the hackathon begin.
- **Evaluation Purpose**: The final 90 minutes are reserved strictly for organizer judging, second-stage evaluation, presentation review, and live scoring. No new commits may be pushed during this window.

### Rule 3: Presentation & Explanation Integrity
- Every team member must be able to explain the uplift methodology and causal quadrants ($P(\text{treat})$ vs $P(\text{control})$).
- Reiterate that the platform is **human-in-the-loop decision support**: the system never dispatches live messages or executes financial transactions autonomously.
