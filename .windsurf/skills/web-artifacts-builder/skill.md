---
description: Suite of tools for creating elaborate, multi-component HTML web apps using modern frontend technologies (React, Tailwind CSS, shadcn/ui). Use for complex web previews requiring state management, routing, or shadcn/ui components - not for simple single-file HTML/JSX.
---

# Web Artifacts Builder (Windsurf)

To build powerful frontend web apps and preview them in Windsurf, follow these steps:
1. Initialize the frontend repo using `scripts/init-artifact.sh`
2. Develop your app by editing the generated code
3. Bundle all code into a single HTML file using `scripts/bundle-artifact.sh`
4. Preview the result using Windsurf's Browser Preview or open `bundle.html` locally
5. (Optional) Test via Browser Preview for live interaction

**Stack**: React 18 + TypeScript + Vite + Parcel (bundling) + Tailwind CSS + shadcn/ui

## Design & Style Guidelines

VERY IMPORTANT: To avoid what is often referred to as "AI slop", avoid using excessive centered layouts, purple gradients, uniform rounded corners, and Inter font.

## Windows Note

These scripts are bash-based. On Windows, run them via **Git Bash** (included with Git for Windows) or **WSL**. Example:
```bash
# From Git Bash or WSL terminal
bash .windsurf/skills/web-artifacts-builder/scripts/init-artifact.sh <project-name>
```

## Quick Start

### Step 1: Initialize Project

Run the initialization script to create a new React project:
```bash
bash scripts/init-artifact.sh <project-name>
cd <project-name>
```

This creates a fully configured project with:
- React + TypeScript (via Vite)
- Tailwind CSS 3.4.1 with shadcn/ui theming system
- Path aliases (`@/`) configured
- 40+ shadcn/ui components pre-installed
- All Radix UI dependencies included
- Parcel configured for bundling (via .parcelrc)
- Node 18+ compatibility (auto-detects and pins Vite version)

### Step 2: Develop Your App

Edit the generated files in the project directory. See **Common Development Tasks** below for guidance.

### Step 3: Bundle to Single HTML File

To bundle the React app into a single self-contained HTML file:
```bash
bash scripts/bundle-artifact.sh
```

This creates `bundle.html` — a self-contained file with all JavaScript, CSS, and dependencies inlined.

**Requirements**: Your project must have an `index.html` in the root directory.

**What the script does**:
- Installs bundling dependencies (parcel, @parcel/config-default, parcel-resolver-tspaths, html-inline)
- Creates `.parcelrc` config with path alias support
- Builds with Parcel (no source maps)
- Inlines all assets into single HTML using html-inline

### Step 4: Preview the Result

Use one of these approaches to view the built app:

**Option A — Windsurf Browser Preview** (preferred):
Start a local dev server (`pnpm dev`) and use Cascade's `browser_preview` tool to open it in-IDE.

**Option B — Open bundle.html**:
Open `bundle.html` directly in your browser to verify the bundled output.

### Step 5: Testing (Optional)

Only perform if necessary or requested. Use Windsurf's Browser Preview to interact with the running app and verify behavior. Avoid upfront testing as it adds latency — test after presenting the result if issues arise.

## Reference

- **shadcn/ui components**: https://ui.shadcn.com/docs/components
