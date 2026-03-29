# Plane Platform Maturity — From Thin to Production-Grade

**Date:** 2026-03-29
**Status:** Requirements captured — investigation and execution needed
**Scope:** Everything required to make Plane a real, usable, professional platform

---

## User Requirements (Verbatim — Complete)

> "Yes there is stuff and I see them, like I see Project Manager assigned but
> if I click to see / change there is only me / You and even if I search there
> is nothing...."

> "Then there is all the lack of configuration and metadata setting....
> Everything is so thin.... no relations...."

> "You can do a better usage of the TextEditor whatever it might be...."

> "Its as if there is no team configured and no workspace and personalisations
> like picture, colors and more...."

> "Then there is also the Pages and like I said a lot more of information about
> the idea and the projects and the ideas and what they represent and the clear
> requirements, create our own custom field requirements if needed and make sure
> that we allow cowork and synergy like on the ocmc."

> "There is also no quick links on the home."

> "I know I said a lot but its all very serious... we have to insert there
> milestone and continue. Do not minimize what I said or corrupt it. Quote me
> and work from it and make sure you cover everything. Using proper styles and
> structure and then making skills of them so that when there is the use of it
> or use via event or chain that its a proper render."

> "We will also need to make it so that we can keep the IaC definition in sync
> as the plane evolve as the agent works, so that if we restart it will pick up
> where we left approximately or even perfectly."

> "Do not minimize anything and plan everything and consider all milestones and
> everything I said and all the quoting needed. We take our time to do this right."

---

## Problems Identified

### 1. Team Not Visible / Not Searchable

Agent bot accounts exist in the database (12 users) but they are NOT showing
up when assigning issues. The Plane UI member picker likely only shows users
who have logged in at least once, or users created through the proper workspace
invite flow — not raw ORM inserts.

**Root cause:** Bot users created via `User.objects.get_or_create` bypass
Plane's user activation flow. The workspace member picker may require:
- `is_email_verified = True`
- Profile completion
- Session/login at minimum once
- Or creation via the workspace invite API

**Investigation needed:**
- How does Plane's member picker query users?
- What flags must be set for a user to appear in search?
- Can we use the invite API instead of raw ORM?
- Does Plane have a service account / bot framework?

### 2. Everything is Thin — No Relations

Modules have descriptions but no rich content. Issues have HTML but it's
basic `<p>` and `<ul>` tags. No cross-references between items, no links
between epics and their related docs, no dependency visualization.

**What's missing:**
- Issue-to-issue relations (blocks/blocked_by, relates_to, duplicate)
- Module-to-module relations (dependencies between epics)
- Rich descriptions using Plane's editor capabilities
- Cross-project references
- Inline links to GitHub commits, PRs, files

### 3. No TextEditor Usage

Plane has a rich text editor (likely TipTap/ProseMirror based). We're
writing plain `<p>` and `<pre>` tags. The editor supports:
- Headings, bold, italic, code blocks
- Tables
- Checklists
- Embeds (images, links)
- Mentions (@user)
- Code syntax highlighting
- Callouts/admonitions

**Investigation needed:**
- What editor does Plane use?
- What HTML/JSON format does it accept?
- Can we generate rich editor content in our IaC?
- Does `description_html` accept full TipTap JSON or just HTML?

### 4. No Workspace Personalization

No workspace avatar, no project avatars (only emojis), no color themes,
no workspace description visible in the UI.

**Investigation needed:**
- Workspace `logo` field — does it accept URL or upload?
- User avatars for agents — can we set default avatars?
- Theme customization — `WorkspaceTheme` model exists
- Home page customization — `WorkspaceHomePreference` exists

### 5. Pages Are Shallow

Pages exist but contain minimal content in `<pre>` blocks. They need:
- Full architecture diagrams (rendered properly, not preformatted)
- Requirements documents with checklists
- Strategic vision with proper formatting
- Living specs that agents update as they work
- Project overviews with status, links, context

**Investigation needed:**
- Page `description_binary` field — is this the TipTap JSON format?
- Can we write rich page content via ORM/API?
- Are pages versioned? (PageVersion model exists)

### 6. No Custom Fields

OCMC has custom fields (14 defined: project, branch, pr_url, worktree,
agent_name, story_points, sprint, complexity, model, parent_task, task_type,
plan_id, review_gates, security_hold).

Plane CE may not support custom fields natively. Need to investigate:
- Does Plane have a custom field system?
- If not, can we use labels + conventions as a workaround?
- Or use the `external_source` / `external_id` fields for OCMC linking?

### 7. No Quick Links on Home

The workspace home page has no shortcuts to important resources:
- GitHub repos
- OCMC dashboard
- IRC/Lounge
- Milestone docs
- Strategic vision

**Investigation needed:**
- `WorkspaceUserLink` model — can we create home page links?
- `UserFavorite` model — can we set default favorites?
- `WorkspaceHomePreference` — what customization is possible?

### 8. IaC Sync — Keep Config in Sync as Plane Evolves

The biggest architectural challenge. Currently:
- IaC seeds Plane from YAML configs on install
- Agents and humans modify Plane during operation
- If Plane is restarted/rebuilt, we lose all runtime changes
- The IaC doesn't know what agents created

**Required:**
- Export script: dump current Plane state → update YAML configs
- Or: bidirectional sync between YAML configs and Plane state
- Or: treat YAML as base config, Plane runtime as additive
- The restart should pick up where we left off

**This requires a Plane state export/import capability.**

### 9. Skills for Plane Rendering

When agents create content in Plane (via MCP tools or chains), the content
must be properly formatted:
- Rich HTML/editor format, not plain text
- Proper headings, lists, code blocks, tables
- Cross-references as links, not plain text
- Templates for common content types (sprint report, task description, etc.)

**Required:**
- A Plane rendering skill that agents use to format content
- Templates for: issue descriptions, comments, page content, sprint reports
- The skill should produce editor-compatible output

---

## Milestones

### M-PM01: Fix Agent User Visibility

Investigate WHY bot users don't appear in the member picker.
Fix the user creation to use the proper activation flow.
All 10 agents must be searchable and assignable in the UI.

**Investigation tasks:**
- Check what `is_email_verified`, `is_active`, profile flags do
- Try creating users via workspace invite API instead of ORM
- Check if there's a user activation endpoint
- Test: create one user properly, verify it shows in picker

### M-PM02: Workspace Personalization

Configure the workspace to look professional:
- Workspace logo/avatar
- Agent user avatars (generated or default per role)
- Workspace theme/colors
- Workspace description
- Home page preferences

**Config:** Add `workspace.logo`, `workspace.theme` to mission.yaml
**Script:** Update seed script

### M-PM03: Home Page Quick Links

Add useful links to the workspace home:
- GitHub organizations/repos
- OCMC dashboard (localhost:3000)
- IRC/Lounge (localhost:9000)
- Fleet documentation
- Strategic vision

**Model:** `WorkspaceUserLink` — title + URL per workspace
**Config:** Add `workspace.links` to mission.yaml

### M-PM04: Rich Text Content — Investigation

Research Plane's editor format:
- What does `description_html` accept?
- What is `description_binary`? (TipTap JSON? Yjs binary?)
- How to generate rich content that renders properly in the editor
- Test: create an issue with tables, code blocks, checklists via API

**Output:** Document the editor format and create a content generation utility

### M-PM05: Rich Pages — Rewrite All Pages

Rewrite all 8 pages using proper rich text:
- Architecture diagrams with proper formatting (not `<pre>`)
- Requirements as checklists
- Strategic vision with headings, quotes, emphasis
- Status tables
- Cross-reference links

**Depends:** M-PM04 (must know the editor format first)

### M-PM06: Issue Relations and Cross-References

Create relations between items:
- Welcome issues linked cross-project
- Module dependencies documented as issue relations
- AICP stages have sequential dependency chain
- Links to GitHub repos, docs, related items on every issue

**Model:** `IssueRelation` (relation_type), `IssueLink` (title + URL)

### M-PM07: Custom Fields or Conventions

Investigate Plane CE custom field support.
If not available, define conventions:
- Labels for metadata (`complexity:high`, `effort:5`, `sprint:s1`)
- `external_id` for OCMC task linking
- Issue description templates with structured sections

If custom fields exist, define and configure:
- Complexity (trivial/simple/moderate/complex/very-complex)
- OCMC Task ID (link to MC task)
- GitHub PR URL
- Story Points (if not using estimate system)

### M-PM08: Plane Content Rendering Skill

Create a Claude Code skill and/or Python utility for generating
properly formatted Plane content:

- Issue description templates (feature, bug, spike, chore)
- Sprint report template (velocity, burn-down, highlights)
- Page templates (architecture, requirements, status)
- Comment templates (progress update, review feedback, decision record)

Used by: MCP tools, chain events, PM agent heartbeat

### M-PM09: IaC State Sync — Export/Import

Build the capability to keep IaC configs in sync with live Plane:

**Export:** `scripts/plane-export-state.sh`
- Reads current Plane state via API
- Updates config YAML files with current data
- Preserves base config, adds runtime additions
- Git-friendly output (deterministic ordering)

**Import:** The existing seed scripts (idempotent)

**Workflow:**
1. Before rebuild: `./setup.sh export` → configs updated
2. Rebuild: `./setup.sh install` → seeds from updated configs
3. Result: Plane picks up where it left off

### M-PM10: Module Descriptions as Editor Content

Update all 22 module descriptions to use rich editor format
instead of plain text. Each module should have:
- Proper headings and structure
- User vision quotes (blockquote format)
- Links to related GitHub code
- Acceptance criteria as checklists
- Status indicators

**Depends:** M-PM04 (editor format), M-PM05 (page rewrite learnings)

---

## Dependencies

```
M-PM01 (Agent visibility) → no deps, CRITICAL, do first
M-PM02 (Workspace personalization) → no deps
M-PM03 (Home quick links) → no deps
M-PM04 (Rich text investigation) → no deps, CRITICAL for content quality
M-PM05 (Rich pages) → M-PM04
M-PM06 (Issue relations) → M-PM01 (agents must be assignable)
M-PM07 (Custom fields) → M-PM04 (investigation)
M-PM08 (Rendering skill) → M-PM04 + M-PM05
M-PM09 (State sync) → M-PM04 (need to serialize editor content)
M-PM10 (Rich module descriptions) → M-PM04 + M-PM08
```

## Priority Order

1. **M-PM01** — Agent visibility. Blocks all agent interaction with Plane.
2. **M-PM04** — Rich text investigation. Blocks all content quality improvements.
3. **M-PM02** — Workspace personalization. Quick win, makes it look professional.
4. **M-PM03** — Home quick links. Quick win, improves navigation.
5. **M-PM05** — Rich pages. Content quality.
6. **M-PM06** — Issue relations. Cross-referencing.
7. **M-PM07** — Custom fields. Metadata richness.
8. **M-PM08** — Rendering skill. Agent content quality.
9. **M-PM10** — Rich module descriptions. Content quality.
10. **M-PM09** — State sync. Operational resilience.

---

## Relationship to Other Milestones

This document extends:
- `plane-full-configuration.md` (M-PF01-09) — basic setup
- `plane-skills-and-chains.md` (M-SC01-08) — chain integration
- `plane-fleet-integration-architecture.md` — architectural principles
- `plane-iac-evolution.md` (M-P01-10) — infrastructure evolution

Total Plane milestones across all documents:
- M-PF: 9 (basic setup — mostly done)
- M-SC: 8 (skills and chains)
- M-P: 10 (IaC evolution)
- M-PM: 10 (platform maturity — this document)
- **Total: 37 milestones** for complete Plane integration

---

## Non-Negotiable Standards

> "Do not minimize anything and plan everything and consider all milestones
> and everything I said and all the quoting needed. We take our time to do
> this right."

Every piece of content in Plane must be:
- Properly formatted using the platform's rich editor capabilities
- Cross-referenced to related resources (GitHub, docs, other items)
- Assigned to the right agent with proper role context
- Styled with icons, colors, and visual hierarchy
- Actionable — the PM can read it and know what to do next

The IaC must be:
- Config-driven (YAML files define the desired state)
- Idempotent (safe to re-run)
- Exportable (runtime state → config files)
- Complete (restart recovers full state)