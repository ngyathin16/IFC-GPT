# IFC-GPT Integration Plan: ThatOpen + Pascal Editor

> **For Windsurf:** This document is your complete implementation specification. Work through each phase sequentially. All file paths are relative to the IFC-GPT repo root (`ngyathin16/IFC-GPT`). Do not skip steps — each phase depends on the previous one. Where code is given verbatim, use it exactly. Where a description is given, implement it according to the pattern shown.

---

## Context & Goals

This plan integrates three repositories into a unified BIM-AI web application:

| Repo | Role |
|---|---|
| `ngyathin16/IFC-GPT` | Core AI generation engine (LangGraph + LLM + IFC output) — **this repo** |
| `ThatOpen/engine_components` | Browser-based IFC renderer with GUID-level element selection |
| `pascalorg/editor` | Visual 3D building editor (React Three Fiber) as design input layer |

**End state:** A single Next.js web app where an architect can (a) sketch walls visually or (b) type/speak a description → the AI generates a compliant IFC4 model → the IFC renders in a browser 3D viewer → the architect clicks any element to request targeted modifications.

**Model upgrade:** Replace `gpt-5.1-codex-max` with `gpt-5.4-pro` throughout.

---

## Phase 0 — Model Upgrade (Do This First)

### 0.1 Update `.env` / environment variables

Open `.env` (or create it from the pattern in `agent/llm.py`) and change:

```env
# OLD
AZURE_OPENAI_DEPLOYMENT=gpt-5.1-codex-max

# NEW
AZURE_OPENAI_DEPLOYMENT=gpt-5.4-pro
```

### 0.2 Update `agent/llm.py`

In `get_llm()`, change the fallback model string on the `ChatOpenAI` kwargs:

```python
# Line ~105 in agent/llm.py — change this:
kwargs: dict = {"temperature": temperature, "model": "gpt-5.1-codex-max"}

# To this:
kwargs: dict = {"temperature": temperature, "model": "gpt-5.4-pro"}
```

Also update the module docstring at the top of `agent/llm.py`:

```python
"""LLM client factory for the IFC generation agent.

Uses gpt-5.4-pro via the Azure OpenAI Responses API endpoint.
...
"""
```

### 0.3 Reset the LLM singleton cache

In `agent/llm.py`, the `_llm_instance` singleton caches the first model used. Add a `reset_llm()` helper so tests and hot-reloads can clear it:

```python
def reset_llm() -> None:
    """Clear the cached LLM singleton. Call this after changing env vars."""
    global _llm_instance
    _llm_instance = None
```

---

## Phase 1 — FastAPI HTTP Server Wrapper

The existing `main.py` only launches the MCP stdio server. We need to add a proper HTTP API that the web frontend can talk to. FastAPI is already in `pyproject.toml` as a dependency — no new installs needed.

### 1.1 Create `api/server.py`

Create a new file `api/server.py` at the project root:

```python
"""FastAPI HTTP server wrapping the IFC-GPT LangGraph pipeline.

Endpoints:
  POST /api/generate      — Full pipeline from natural language description
  POST /api/build-from-plan — Skip clarify/plan, execute a pre-built BuildingPlan JSON
  POST /api/modify        — Targeted single-element modification by IFC GUID
  POST /api/voice         — Accept audio, transcribe via Whisper, run pipeline
  GET  /api/status/{job_id} — Poll job progress (SSE stream)
  GET  /workspace/{filename} — Serve generated IFC files as static downloads
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)
app = FastAPI(title="IFC-GPT API", version="2.0.0")

# Allow the Next.js dev server (port 3000) and production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", os.getenv("FRONTEND_ORIGIN", "")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated IFC files directly
os.makedirs("workspace", exist_ok=True)
app.mount("/workspace", StaticFiles(directory="workspace"), name="workspace")

# In-memory job store (replace with Redis for production)
_jobs: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    message: str
    interactive: bool = False  # Always False for API — use defaults for missing fields


class BuildFromPlanRequest(BaseModel):
    """Skip the LLM clarify+plan phases; provide the BuildingPlan JSON directly.
    Use this when the frontend (Pascal editor) has already constructed the plan.
    """
    plan: Dict[str, Any]


class ModifyRequest(BaseModel):
    """Targeted modification of a single IFC element by GUID."""
    ifc_path: str          # path to the existing IFC file (relative to workspace/)
    guid: str              # IFC GlobalId of the element to modify
    instruction: str       # Natural language: "change wall thickness to 0.3m"


class JobResponse(BaseModel):
    job_id: str
    status: str
    ifc_url: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Background job runner
# ---------------------------------------------------------------------------

async def _run_pipeline_job(job_id: str, message: str) -> None:
    """Run run_pipeline() in a thread pool and update job state."""
    from agent.graph import run_pipeline
    from agent.graph import _load_mcp_tools_sync

    _jobs[job_id] = {"status": "running", "ifc_url": None, "error": None}
    try:
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(
            None,
            lambda: run_pipeline(message, mcp_client=None, interactive=False),
        )
        ifc_path = final_state.get("final_ifc_path", "")
        if ifc_path and Path(ifc_path).exists():
            filename = Path(ifc_path).name
            ifc_url = f"/workspace/{filename}"
        else:
            ifc_url = None
        _jobs[job_id] = {"status": "complete", "ifc_url": ifc_url, "error": None}
    except Exception as exc:
        logger.error(f"[job {job_id}] Pipeline failed: {exc}")
        _jobs[job_id] = {"status": "error", "ifc_url": None, "error": str(exc)}


async def _run_build_from_plan_job(job_id: str, plan: Dict[str, Any]) -> None:
    """Execute build/validate/export directly from a BuildingPlan dict (no LLM needed)."""
    import asyncio
    from agent.graph import (
        execute_build_steps,
        validate,
        present_and_export,
        should_repair,
        repair,
        _load_mcp_tools_sync,
    )
    from agent.schemas import BuildingPlan
    from langchain_core.messages import HumanMessage

    _jobs[job_id] = {"status": "running", "ifc_url": None, "error": None}
    try:
        # Validate the incoming plan against the Pydantic schema
        BuildingPlan.model_validate(plan)

        state: Dict[str, Any] = {
            "messages": [HumanMessage(content="Build from visual editor plan")],
            "building_plan": plan,
            "tool_calls_log": [],
            "validation_results": {},
            "repair_attempts": 0,
            "final_ifc_path": "",
            "ids_report_path": "ids/v0.ids",
            "scene_overview": "",
            "requirements": {},
            "clarification_done": True,
            "clarify_rounds": 0,
            "subagent_statuses": {},
            "mcp_client": None,  # will be loaded by execute_build_steps
        }

        loop = asyncio.get_event_loop()

        def _run_sync():
            try:
                mcp = _load_mcp_tools_sync()
                state["mcp_client"] = mcp
            except Exception:
                pass  # dry-run mode if Blender not available

            s = execute_build_steps(state)
            s = validate(s)
            route = should_repair(s)
            repair_attempts = 0
            while route == "repair" and repair_attempts < 3:
                s = repair(s)
                s = validate(s)
                route = should_repair(s)
                repair_attempts += 1
            s = present_and_export(s)
            return s

        final_state = await loop.run_in_executor(None, _run_sync)
        ifc_path = final_state.get("final_ifc_path", "")
        ifc_url = f"/workspace/{Path(ifc_path).name}" if ifc_path and Path(ifc_path).exists() else None
        _jobs[job_id] = {"status": "complete", "ifc_url": ifc_url, "error": None}
    except Exception as exc:
        logger.error(f"[job {job_id}] Build-from-plan failed: {exc}")
        _jobs[job_id] = {"status": "error", "ifc_url": None, "error": str(exc)}


async def _run_modify_job(job_id: str, req: ModifyRequest) -> None:
    """Run a targeted single-element modification by GUID."""
    _jobs[job_id] = {"status": "running", "ifc_url": None, "error": None}
    try:
        loop = asyncio.get_event_loop()

        def _run_sync():
            import ifcopenshell
            from agent.graph import _load_mcp_tools_sync

            ifc_path = Path("workspace") / req.ifc_path
            if not ifc_path.exists():
                raise FileNotFoundError(f"IFC file not found: {ifc_path}")

            # Load MCP tools and dispatch execute_ifc_code_tool with GUID context
            try:
                mcp_tools = _load_mcp_tools_sync()
            except Exception:
                mcp_tools = None

            if mcp_tools and "execute_ifc_code_tool" in mcp_tools:
                code = (
                    f"import ifcopenshell\n"
                    f"ifc = ifcopenshell.open(r'{ifc_path.resolve()}')\n"
                    f"element = ifc.by_guid('{req.guid}')\n"
                    f"# Instruction: {req.instruction}\n"
                    f"# Implement the modification above on `element`\n"
                    f"# Then: ifc.write(r'{ifc_path.resolve()}')\n"
                )
                result = mcp_tools["execute_ifc_code_tool"].invoke({"code": code, "instruction": req.instruction, "guid": req.guid})
                return str(ifc_path)
            else:
                # Fallback: use the LLM to generate and execute the modification code
                from agent.llm import get_llm
                from langchain_core.messages import HumanMessage, SystemMessage
                llm = get_llm(temperature=0.0)
                prompt = (
                    f"You are an IfcOpenShell expert. Given this IFC file path: {ifc_path.resolve()}\n"
                    f"Element GUID: {req.guid}\n"
                    f"Instruction: {req.instruction}\n\n"
                    f"Write Python code using ifcopenshell to apply this modification. "
                    f"Load the file, find the element by guid, apply the change, save back to the same path. "
                    f"Return ONLY the Python code, no markdown fences."
                )
                response = llm.invoke([SystemMessage(content="You are an IfcOpenShell expert."), HumanMessage(content=prompt)])
                exec(response.content)  # noqa: S102
                return str(ifc_path)

        await loop.run_in_executor(None, _run_sync)
        _jobs[job_id] = {
            "status": "complete",
            "ifc_url": f"/workspace/{req.ifc_path}",
            "error": None,
        }
    except Exception as exc:
        logger.error(f"[job {job_id}] Modify failed: {exc}")
        _jobs[job_id] = {"status": "error", "ifc_url": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/generate", response_model=JobResponse)
async def generate(req: GenerateRequest) -> JobResponse:
    """Accept a natural language building description and run the full pipeline."""
    job_id = str(uuid.uuid4())[:8]
    asyncio.create_task(_run_pipeline_job(job_id, req.message))
    return JobResponse(job_id=job_id, status="queued")


@app.post("/api/build-from-plan", response_model=JobResponse)
async def build_from_plan(req: BuildFromPlanRequest) -> JobResponse:
    """Accept a BuildingPlan JSON from the frontend editor and skip LLM planning."""
    job_id = str(uuid.uuid4())[:8]
    asyncio.create_task(_run_build_from_plan_job(job_id, req.plan))
    return JobResponse(job_id=job_id, status="queued")


@app.post("/api/modify", response_model=JobResponse)
async def modify_element(req: ModifyRequest) -> JobResponse:
    """Targeted modification of a single IFC element by GUID."""
    job_id = str(uuid.uuid4())[:8]
    asyncio.create_task(_run_modify_job(job_id, req))
    return JobResponse(job_id=job_id, status="queued")


@app.post("/api/voice", response_model=JobResponse)
async def voice_to_pipeline(audio: UploadFile = File(...)) -> JobResponse:
    """Accept an audio file, transcribe with Whisper, run the full pipeline."""
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    audio_bytes = await audio.read()

    # Write to a temp file — Whisper API requires a file-like object with a name
    tmp_path = Path(f"/tmp/voice_{uuid.uuid4()}.webm")
    tmp_path.write_bytes(audio_bytes)

    try:
        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
        message = transcript.text
    finally:
        tmp_path.unlink(missing_ok=True)

    job_id = str(uuid.uuid4())[:8]
    asyncio.create_task(_run_pipeline_job(job_id, message))
    return JobResponse(job_id=job_id, status="queued", )


@app.get("/api/status/{job_id}")
async def get_status(job_id: str) -> JobResponse:
    """Poll job status. Frontend should poll every 2 seconds."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(job_id=job_id, **job)


@app.get("/api/status/{job_id}/stream")
async def stream_status(job_id: str) -> StreamingResponse:
    """SSE stream for job status. Sends updates until job completes or errors."""
    async def event_generator():
        import json
        while True:
            job = _jobs.get(job_id, {"status": "not_found"})
            yield f"data: {json.dumps(job)}\n\n"
            if job.get("status") in ("complete", "error", "not_found"):
                break
            await asyncio.sleep(1.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 1.2 Update `main.py` to expose both MCP and HTTP servers

Replace the current `main.py` entirely:

```python
"""IFC-GPT entry point.

Usage:
    uv run main.py               # MCP stdio server (Windsurf/Claude Desktop)
    uv run main.py --http        # FastAPI HTTP server (web frontend)
    uv run main.py --http --port 8000
"""
import sys


def main():
    if "--http" in sys.argv:
        import uvicorn
        port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000
        uvicorn.run("api.server:app", host="0.0.0.0", port=port, reload=True)
    else:
        from blender_mcp.server import main as server_main
        server_main()


if __name__ == "__main__":
    main()
```

### 1.3 Create `api/__init__.py`

```python
# api/__init__.py
```

### 1.4 Test Phase 1

Run: `uv run main.py --http`

Verify:
- `curl -X POST http://localhost:8000/api/generate -H "Content-Type: application/json" -d '{"message": "a 2-storey house 10x8m"}'` returns a `job_id`
- `curl http://localhost:8000/api/status/<job_id>` returns status updates
- After ~30–60s, status becomes `complete` and `ifc_url` is set

---

## Phase 2 — Next.js Web Frontend

Create a new Next.js app inside the IFC-GPT repo under `web/`. This will eventually embed both the Pascal editor viewer and the ThatOpen IFC viewer.

### 2.1 Scaffold the Next.js app

From the project root, run:

```bash
cd web
# Windsurf: run this shell command
npx create-next-app@latest . --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*"
```

### 2.2 Install ThatOpen dependencies

```bash
cd web
npm install @thatopen/components @thatopen/components-front three @types/three
```

### 2.3 Install Pascal Editor core + viewer packages

Pascal editor packages are not yet published to npm. Clone the repo and use local package linking, OR reference via GitHub directly. Use the GitHub approach:

```bash
cd web
npm install github:pascalorg/editor#main --workspace=packages/core
```

> **Note for Windsurf:** If npm workspace installation of the pascalorg packages fails (they may not export clean npm-compatible bundles yet), skip Pascal's `packages/viewer` and implement a simplified visual input panel in Phase 3 instead. ThatOpen integration (Phase 2) is the higher-priority item and is fully self-contained.

### 2.4 Create the ThatOpen IFC Viewer component

Create `web/components/IFCViewer.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";

interface IFCViewerProps {
  /** Full URL to the .ifc file, e.g. http://localhost:8000/workspace/abc123.ifc */
  ifcUrl: string | null;
  /** Called with array of selected IFC GUIDs when user clicks elements */
  onElementSelected?: (guids: string[]) => void;
}

export default function IFCViewer({ ifcUrl, onElementSelected }: IFCViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const componentsRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || !ifcUrl) return;

    let components: any;

    const init = async () => {
      // Dynamic import — ThatOpen uses browser APIs, must be client-side only
      const OBC = await import("@thatopen/components");
      const OBCF = await import("@thatopen/components-front");

      components = new OBC.Components();
      componentsRef.current = components;

      const worlds = components.get(OBC.Worlds);
      const world = worlds.create();

      world.scene = new OBC.SimpleScene(components);
      world.renderer = new OBC.SimpleRenderer(components, containerRef.current!);
      world.camera = new OBC.SimpleCamera(components);

      (world.scene as any).setup();
      components.init();

      // Load the IFC file
      const loader = components.get(OBC.IfcLoader);
      await loader.setup();

      const response = await fetch(ifcUrl);
      const buffer = await response.arrayBuffer();
      const model = await loader.load(new Uint8Array(buffer));

      // Fit camera to loaded model
      const bbox = components.get(OBC.BoundingBoxer);
      bbox.add(model);
      const sphere = bbox.getSphere();
      (world.camera as any).controls.fitToSphere(sphere, true);
      bbox.reset();

      // Set up element selection → GUID extraction
      if (onElementSelected) {
        const highlighter = components.get(OBCF.Highlighter);
        highlighter.setup({ world });

        highlighter.events.select.onHighlight.add((fragmentIdMap: any) => {
          // fragmentIdMap: { [fragmentId: string]: Set<number> }
          // We need to convert fragment local IDs → IFC GUIDs
          const frags = components.get(OBC.FragmentsManager);
          const guids: string[] = [];

          for (const [fragId, expressIds] of Object.entries(fragmentIdMap)) {
            const fragment = frags.list.get(fragId);
            if (!fragment) continue;
            for (const expressId of expressIds as Set<number>) {
              const attrs = fragment.mesh.geometry.attributes;
              // The GUID is stored in the fragment model's properties
              const guid = (fragment as any).getItemGuid?.(expressId);
              if (guid) guids.push(guid);
            }
          }

          if (guids.length > 0) onElementSelected(guids);
        });

        highlighter.events.select.onClear.add(() => {
          onElementSelected([]);
        });
      }
    };

    init().catch(console.error);

    return () => {
      // Cleanup Three.js resources
      if (componentsRef.current) {
        try { componentsRef.current.dispose(); } catch {}
      }
    };
  }, [ifcUrl]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", minHeight: "500px", background: "#1a1a2e" }}
    />
  );
}
```

### 2.5 Create the main page

Create `web/app/page.tsx`:

```tsx
"use client";

import { useState, useRef } from "react";
import dynamic from "next/dynamic";

// Dynamic import — IFCViewer uses browser-only APIs
const IFCViewer = dynamic(() => import("@/components/IFCViewer"), { ssr: false });

interface Job {
  job_id: string;
  status: "queued" | "running" | "complete" | "error";
  ifc_url: string | null;
  error: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [message, setMessage] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [selectedGuids, setSelectedGuids] = useState<string[]>([]);
  const [modifyInstruction, setModifyInstruction] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const pollStatus = (jobId: string) => {
    pollRef.current = setInterval(async () => {
      const res = await fetch(`${API_BASE}/api/status/${jobId}`);
      const data: Job = await res.json();
      setJob(data);
      if (data.status === "complete" || data.status === "error") {
        clearInterval(pollRef.current!);
        setIsLoading(false);
      }
    }, 2000);
  };

  const handleGenerate = async () => {
    if (!message.trim()) return;
    setIsLoading(true);
    setJob(null);
    setSelectedGuids([]);

    const res = await fetch(`${API_BASE}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    setJob({ ...data, ifc_url: null });
    pollStatus(data.job_id);
  };

  const handleModify = async () => {
    if (!selectedGuids.length || !modifyInstruction || !job?.ifc_url) return;
    setIsLoading(true);

    const filename = job.ifc_url.replace("/workspace/", "");
    const res = await fetch(`${API_BASE}/api/modify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ifc_path: filename,
        guid: selectedGuids[0],
        instruction: modifyInstruction,
      }),
    });
    const data = await res.json();
    setJob((prev) => ({ ...prev!, ...data }));
    pollStatus(data.job_id);
  };

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream);
    chunksRef.current = [];
    mr.ondataavailable = (e) => chunksRef.current.push(e.data);
    mr.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const formData = new FormData();
      formData.append("audio", blob, "voice.webm");
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/api/voice`, { method: "POST", body: formData });
      const data = await res.json();
      setJob({ ...data, ifc_url: null });
      pollStatus(data.job_id);
    };
    mr.start();
    mediaRecorderRef.current = mr;
    setIsRecording(true);
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  };

  const ifcFullUrl = job?.ifc_url ? `${API_BASE}${job.ifc_url}` : null;

  return (
    <main style={{ display: "flex", height: "100vh", fontFamily: "sans-serif", background: "#0f0f1a", color: "#e0e0e0" }}>
      {/* Left panel — controls */}
      <aside style={{ width: "380px", padding: "24px", borderRight: "1px solid #2a2a3a", display: "flex", flexDirection: "column", gap: "16px", overflowY: "auto" }}>
        <h1 style={{ margin: 0, fontSize: "20px", fontWeight: 700, color: "#a78bfa" }}>IFC-GPT</h1>
        <p style={{ margin: 0, fontSize: "12px", color: "#888" }}>Powered by gpt-5.4-pro</p>

        {/* Text input */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <label style={{ fontSize: "13px", fontWeight: 600, color: "#ccc" }}>Describe your building</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            placeholder="e.g. A 3-storey office building, 20x15m footprint, concrete frame, flat roof..."
            style={{ background: "#1e1e2e", border: "1px solid #3a3a5a", borderRadius: "6px", color: "#e0e0e0", padding: "10px", resize: "vertical", fontSize: "13px" }}
          />
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={handleGenerate}
              disabled={isLoading || !message.trim()}
              style={{ flex: 1, padding: "10px", background: "#7c3aed", border: "none", borderRadius: "6px", color: "#fff", fontWeight: 600, cursor: "pointer", opacity: isLoading ? 0.5 : 1 }}
            >
              {isLoading ? "Generating…" : "Generate IFC"}
            </button>
            <button
              onClick={isRecording ? stopRecording : startRecording}
              style={{ padding: "10px 14px", background: isRecording ? "#dc2626" : "#1e1e2e", border: "1px solid #3a3a5a", borderRadius: "6px", color: "#fff", cursor: "pointer", fontSize: "18px" }}
              title={isRecording ? "Stop recording" : "Start voice input"}
            >
              {isRecording ? "⏹" : "🎤"}
            </button>
          </div>
        </div>

        {/* Job status */}
        {job && (
          <div style={{ padding: "12px", background: "#1e1e2e", borderRadius: "6px", border: "1px solid #3a3a5a" }}>
            <p style={{ margin: 0, fontSize: "12px", color: "#888" }}>Job: {job.job_id}</p>
            <p style={{ margin: "4px 0 0", fontSize: "14px", fontWeight: 600, color: job.status === "complete" ? "#4ade80" : job.status === "error" ? "#f87171" : "#facc15" }}>
              {job.status.toUpperCase()}
            </p>
            {job.error && <p style={{ margin: "4px 0 0", fontSize: "12px", color: "#f87171" }}>{job.error}</p>}
            {job.ifc_url && (
              <a href={`${API_BASE}${job.ifc_url}`} download style={{ display: "block", marginTop: "8px", fontSize: "12px", color: "#a78bfa" }}>
                ⬇ Download IFC
              </a>
            )}
          </div>
        )}

        {/* Element modification panel */}
        {selectedGuids.length > 0 && (
          <div style={{ padding: "12px", background: "#1e1e2e", borderRadius: "6px", border: "1px solid #4c1d95" }}>
            <p style={{ margin: 0, fontSize: "12px", fontWeight: 600, color: "#a78bfa" }}>Selected element</p>
            <p style={{ margin: "4px 0 8px", fontSize: "11px", color: "#888", fontFamily: "monospace", wordBreak: "break-all" }}>{selectedGuids[0]}</p>
            <input
              value={modifyInstruction}
              onChange={(e) => setModifyInstruction(e.target.value)}
              placeholder="e.g. change thickness to 0.3m"
              style={{ width: "100%", boxSizing: "border-box", padding: "8px", background: "#0f0f1a", border: "1px solid #3a3a5a", borderRadius: "4px", color: "#e0e0e0", fontSize: "13px" }}
            />
            <button
              onClick={handleModify}
              disabled={isLoading || !modifyInstruction.trim()}
              style={{ marginTop: "8px", width: "100%", padding: "8px", background: "#4c1d95", border: "none", borderRadius: "4px", color: "#fff", fontWeight: 600, cursor: "pointer", opacity: isLoading ? 0.5 : 1 }}
            >
              Modify Element
            </button>
          </div>
        )}
      </aside>

      {/* Right panel — 3D viewer */}
      <div style={{ flex: 1, position: "relative" }}>
        {!ifcFullUrl && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#444", fontSize: "16px" }}>
            Generate a building to see the 3D IFC model here
          </div>
        )}
        {ifcFullUrl && (
          <IFCViewer ifcUrl={ifcFullUrl} onElementSelected={setSelectedGuids} />
        )}
      </div>
    </main>
  );
}
```

### 2.6 Add environment config for the web app

Create `web/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2.7 Update `web/next.config.ts`

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  webpack: (config) => {
    // ThatOpen uses WASM — allow loading .wasm files
    config.experiments = { ...config.experiments, asyncWebAssembly: true };
    return config;
  },
};

export default nextConfig;
```

### 2.8 Test Phase 2

1. In terminal 1: `uv run main.py --http` (from project root)
2. In terminal 2: `cd web && npm run dev`
3. Open `http://localhost:3000`
4. Type a building description, click Generate IFC
5. After job completes, the IFC should render in the 3D panel
6. Clicking a wall should display its GUID in the left panel

---

## Phase 3 — Pascal Editor Visual Design Canvas

This phase embeds the Pascal editor's drawing tools so users can sketch a building and export it directly to IFC-GPT's build pipeline, bypassing the LLM clarification + planning phases.

### 3.1 Create the BuildingPlan serializer

Create `web/lib/toPlanJSON.ts`:

```typescript
/**
 * Converts a Pascal editor scene (Zustand store snapshot) into an
 * IFC-GPT BuildingPlan JSON object compatible with /api/build-from-plan.
 *
 * Pascal node types used:
 *   - level  → StoreyDefinition
 *   - wall   → WallPlacement
 *   - slab   → SlabPlacement
 *   - item (door/window) → OpeningPlacement
 *   - roof   → RoofPlacement
 */

export interface StoreyDefinition {
  storey_ref: string;
  name: string;
  elevation: number;
  floor_to_floor_height: number;
}

export interface WallPlacement {
  element_type: "wall";
  wall_ref: string;
  component_id: "exterior_wall" | "interior_wall";
  storey_ref: string;
  start_point: [number, number];
  end_point: [number, number];
  height?: number;
  thickness?: number;
}

export interface OpeningPlacement {
  element_type: "door" | "window";
  component_id: "standard_door" | "standard_window";
  storey_ref: string;
  host_wall_ref: string;
  distance_along_wall: number;
  sill_height: number;
  width?: number;
  height?: number;
}

export interface SlabPlacement {
  element_type: "slab";
  component_id: "ground_slab";
  storey_ref: string;
  boundary_points: [number, number][];
  depth?: number;
}

export interface RoofPlacement {
  element_type: "roof";
  component_id: "flat_roof";
  storey_ref: string;
  boundary_points: [number, number, number][];
  roof_type: string;
  angle: number;
}

export type ElementPlacement = WallPlacement | OpeningPlacement | SlabPlacement | RoofPlacement;

export interface BuildingPlan {
  description: string;
  site: { name: string };
  building: { name: string; building_type: string };
  storeys: StoreyDefinition[];
  elements: ElementPlacement[];
  wall_junctions: any[];
  rooms: any[];
}

/**
 * Compute distance from a 2D point to the start of a wall segment.
 * Used to convert absolute door/window positions to parametric wall-distance.
 */
function distanceAlongWall(
  wallStart: [number, number],
  wallEnd: [number, number],
  point: [number, number]
): number {
  const dx = wallEnd[0] - wallStart[0];
  const dy = wallEnd[1] - wallStart[1];
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len === 0) return 0;
  // Project point onto wall axis
  const t = ((point[0] - wallStart[0]) * dx + (point[1] - wallStart[1]) * dy) / (len * len);
  return Math.max(0, Math.min(len, t * len));
}

export function sceneToBuildingPlan(nodes: Record<string, any>): BuildingPlan {
  const allNodes = Object.values(nodes);

  const levels = allNodes.filter((n) => n.type === "level").sort((a, b) => a.elevation - b.elevation);
  const walls = allNodes.filter((n) => n.type === "wall");
  const slabs = allNodes.filter((n) => n.type === "slab");
  const roofs = allNodes.filter((n) => n.type === "roof");
  // Pascal stores doors/windows as Item nodes with an itemType field
  const doors = allNodes.filter((n) => n.type === "item" && n.itemType === "door");
  const windows = allNodes.filter((n) => n.type === "item" && n.itemType === "window");

  const storeys: StoreyDefinition[] = levels.map((l) => ({
    storey_ref: l.id,
    name: l.name || `Level ${l.elevation}m`,
    elevation: l.elevation ?? 0,
    floor_to_floor_height: l.height ?? 3.0,
  }));

  const wallElements: WallPlacement[] = walls.map((w) => ({
    element_type: "wall",
    wall_ref: w.id,
    component_id: w.isExterior ? "exterior_wall" : "interior_wall",
    storey_ref: w.parentId ?? (levels[0]?.id || "GF"),
    start_point: [w.start?.[0] ?? 0, w.start?.[1] ?? 0],
    end_point: [w.end?.[0] ?? 1, w.end?.[1] ?? 0],
    height: w.height ?? undefined,
    thickness: w.thickness ?? undefined,
  }));

  // Build a wall lookup for door/window placement
  const wallById: Record<string, WallPlacement> = {};
  wallElements.forEach((w) => { wallById[w.wall_ref] = w; });

  const doorElements: OpeningPlacement[] = doors.map((d) => {
    const hostWall = wallById[d.hostWallId] ?? wallElements[0];
    const dist = hostWall
      ? distanceAlongWall(hostWall.start_point, hostWall.end_point, [d.position?.[0] ?? 0, d.position?.[1] ?? 0])
      : 0;
    return {
      element_type: "door",
      component_id: "standard_door",
      storey_ref: d.parentId ?? (levels[0]?.id || "GF"),
      host_wall_ref: d.hostWallId ?? (wallElements[0]?.wall_ref || "W1"),
      distance_along_wall: dist,
      sill_height: 0,
      width: d.width ?? undefined,
      height: d.height ?? undefined,
    };
  });

  const windowElements: OpeningPlacement[] = windows.map((w) => {
    const hostWall = wallById[w.hostWallId] ?? wallElements[0];
    const dist = hostWall
      ? distanceAlongWall(hostWall.start_point, hostWall.end_point, [w.position?.[0] ?? 0, w.position?.[1] ?? 0])
      : 1;
    return {
      element_type: "window",
      component_id: "standard_window",
      storey_ref: w.parentId ?? (levels[0]?.id || "GF"),
      host_wall_ref: w.hostWallId ?? (wallElements[0]?.wall_ref || "W1"),
      distance_along_wall: dist,
      sill_height: w.sillHeight ?? 0.9,
      width: w.width ?? undefined,
      height: w.height ?? undefined,
    };
  });

  const slabElements: SlabPlacement[] = slabs.map((s) => ({
    element_type: "slab",
    component_id: "ground_slab",
    storey_ref: s.parentId ?? (levels[0]?.id || "GF"),
    boundary_points: (s.boundary ?? []).map((p: number[]) => [p[0], p[1]] as [number, number]),
    depth: s.depth ?? undefined,
  }));

  const roofElements: RoofPlacement[] = roofs.map((r) => ({
    element_type: "roof",
    component_id: "flat_roof",
    storey_ref: r.parentId ?? (levels[levels.length - 1]?.id || "RF"),
    boundary_points: (r.boundary ?? []).map((p: number[]) => [p[0], p[1], p[2] ?? 0] as [number, number, number]),
    roof_type: r.roofType ?? "FLAT",
    angle: r.angle ?? 5.0,
  }));

  return {
    description: "Building plan from visual editor",
    site: { name: "Default Site" },
    building: { name: "Building A", building_type: "Mixed-use" },
    storeys,
    elements: [...wallElements, ...slabElements, ...doorElements, ...windowElements, ...roofElements],
    wall_junctions: [],
    rooms: [],
  };
}
```

### 3.2 Create Pascal Editor integration hook

Create `web/hooks/usePascalEditor.ts`:

```typescript
/**
 * Hook to manage the Pascal editor scene state and export to BuildingPlan.
 *
 * If pascalorg/editor packages are not available via npm, this hook
 * falls back to a minimal local Zustand store with the same interface.
 */
"use client";

import { create } from "zustand";
import { sceneToBuildingPlan, type BuildingPlan } from "@/lib/toPlanJSON";

interface Node {
  id: string;
  type: string;
  [key: string]: any;
}

interface PascalEditorStore {
  nodes: Record<string, Node>;
  addNode: (node: Node) => void;
  removeNode: (id: string) => void;
  updateNode: (id: string, patch: Partial<Node>) => void;
  clearScene: () => void;
  exportToBuildingPlan: () => BuildingPlan;
}

export const usePascalEditor = create<PascalEditorStore>((set, get) => ({
  nodes: {},
  addNode: (node) => set((s) => ({ nodes: { ...s.nodes, [node.id]: node } })),
  removeNode: (id) =>
    set((s) => {
      const { [id]: _, ...rest } = s.nodes;
      return { nodes: rest };
    }),
  updateNode: (id, patch) =>
    set((s) => ({ nodes: { ...s.nodes, [id]: { ...s.nodes[id], ...patch } } })),
  clearScene: () => set({ nodes: {} }),
  exportToBuildingPlan: () => sceneToBuildingPlan(get().nodes),
}));
```

### 3.3 Create a minimal visual wall-drawing panel

Create `web/components/VisualEditor.tsx`:

```tsx
"use client";

/**
 * Minimal 2D wall-drawing canvas.
 *
 * This is a lightweight fallback for environments where the full Pascal editor
 * package cannot be installed. It provides basic click-to-draw wall functionality
 * using an HTML Canvas element.
 *
 * When pascalorg/editor is available as an npm package, replace this component
 * with the Pascal <Viewer> component and bind its onExport callback.
 */

import { useRef, useEffect, useCallback } from "react";
import { usePascalEditor } from "@/hooks/usePascalEditor";

interface VisualEditorProps {
  onExportPlan: (plan: any) => void;
}

export default function VisualEditor({ onExportPlan }: VisualEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { nodes, addNode, clearScene, exportToBuildingPlan } = usePascalEditor();
  const drawingRef = useRef<{ x: number; y: number } | null>(null);
  const wallCountRef = useRef(0);

  const SCALE = 40; // pixels per meter

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw grid
    ctx.strokeStyle = "#2a2a3a";
    ctx.lineWidth = 0.5;
    for (let x = 0; x < canvas.width; x += SCALE) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += SCALE) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
    }

    // Draw walls
    Object.values(nodes)
      .filter((n) => n.type === "wall")
      .forEach((w) => {
        const sx = w.start[0] * SCALE + canvas.width / 2;
        const sy = -w.start[1] * SCALE + canvas.height / 2;
        const ex = w.end[0] * SCALE + canvas.width / 2;
        const ey = -w.end[1] * SCALE + canvas.height / 2;
        ctx.strokeStyle = "#a78bfa";
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(ex, ey);
        ctx.stroke();
      });

    // Draw current in-progress wall
    if (drawingRef.current) {
      const { x, y } = drawingRef.current;
      const sx = x * SCALE + canvas.width / 2;
      const sy = -y * SCALE + canvas.height / 2;
      ctx.fillStyle = "#4ade80";
      ctx.beginPath();
      ctx.arc(sx, sy, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [nodes]);

  useEffect(() => { redraw(); }, [redraw]);

  const toWorldCoords = (e: React.MouseEvent<HTMLCanvasElement>): [number, number] => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const wx = (px - canvasRef.current!.width / 2) / SCALE;
    const wy = -(py - canvasRef.current!.height / 2) / SCALE;
    // Snap to 0.5m grid
    return [Math.round(wx * 2) / 2, Math.round(wy * 2) / 2];
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const [wx, wy] = toWorldCoords(e);
    if (!drawingRef.current) {
      drawingRef.current = { x: wx, y: wy };
      redraw();
    } else {
      const start: [number, number] = [drawingRef.current.x, drawingRef.current.y];
      const end: [number, number] = [wx, wy];
      wallCountRef.current += 1;
      addNode({
        id: `W${wallCountRef.current}`,
        type: "wall",
        start,
        end,
        parentId: "GF",
        isExterior: true,
        thickness: 0.2,
      });
      // Make sure we have at least one level
      if (!Object.values(nodes).some((n) => n.type === "level")) {
        addNode({ id: "GF", type: "level", name: "Ground Floor", elevation: 0, height: 3.0 });
      }
      drawingRef.current = null;
      redraw();
    }
  };

  const handleExport = () => {
    const plan = exportToBuildingPlan();
    onExportPlan(plan);
  };

  const wallCount = Object.values(nodes).filter((n) => n.type === "wall").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: "8px" }}>
      <div style={{ display: "flex", gap: "8px", padding: "8px", alignItems: "center" }}>
        <span style={{ fontSize: "12px", color: "#888" }}>
          {drawingRef.current ? "Click to place wall end point" : "Click to start a wall"}
          {wallCount > 0 && ` · ${wallCount} wall${wallCount !== 1 ? "s" : ""}`}
        </span>
        <button
          onClick={() => { clearScene(); wallCountRef.current = 0; drawingRef.current = null; redraw(); }}
          style={{ marginLeft: "auto", padding: "6px 12px", background: "#1e1e2e", border: "1px solid #3a3a5a", borderRadius: "4px", color: "#e0e0e0", cursor: "pointer", fontSize: "12px" }}
        >
          Clear
        </button>
        <button
          onClick={handleExport}
          disabled={wallCount === 0}
          style={{ padding: "6px 12px", background: "#7c3aed", border: "none", borderRadius: "4px", color: "#fff", cursor: "pointer", fontSize: "12px", opacity: wallCount === 0 ? 0.5 : 1 }}
        >
          Generate IFC from Drawing
        </button>
      </div>
      <canvas
        ref={canvasRef}
        width={800}
        height={500}
        onClick={handleClick}
        style={{ flex: 1, cursor: "crosshair", background: "#0f0f1a", display: "block" }}
      />
    </div>
  );
}
```

### 3.4 Add tabbed view to `web/app/page.tsx`

Update `web/app/page.tsx` to include a tab switcher between "Text/Voice Input" and "Visual Drawing" modes. Add this import and state at the top of the component:

```tsx
import dynamic from "next/dynamic";
const VisualEditor = dynamic(() => import("@/components/VisualEditor"), { ssr: false });

// Inside the component, add:
const [inputMode, setInputMode] = useState<"text" | "draw">("text");
```

Replace the text input section in the left panel with:

```tsx
{/* Mode switcher */}
<div style={{ display: "flex", gap: "4px", background: "#1e1e2e", padding: "4px", borderRadius: "6px" }}>
  {(["text", "draw"] as const).map((mode) => (
    <button
      key={mode}
      onClick={() => setInputMode(mode)}
      style={{
        flex: 1, padding: "6px", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "12px", fontWeight: 600,
        background: inputMode === mode ? "#7c3aed" : "transparent",
        color: inputMode === mode ? "#fff" : "#888",
      }}
    >
      {mode === "text" ? "💬 Text / Voice" : "✏️ Draw"}
    </button>
  ))}
</div>

{inputMode === "text" && (
  // ... existing text input + voice button JSX
)}

{inputMode === "draw" && (
  <div style={{ flex: 1, minHeight: "300px", border: "1px solid #3a3a5a", borderRadius: "6px", overflow: "hidden" }}>
    <VisualEditor
      onExportPlan={async (plan) => {
        setIsLoading(true);
        setJob(null);
        const res = await fetch(`${API_BASE}/api/build-from-plan`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan }),
        });
        const data = await res.json();
        setJob({ ...data, ifc_url: null });
        pollStatus(data.job_id);
      }}
    />
  </div>
)}
```

---

## Phase 4 — Voice Input Enhancements

The basic voice capture (Web MediaRecorder → Whisper) is already wired in `page.tsx` from Phase 2. This phase adds refinements.

### 4.1 Add visual recording indicator

In `web/app/page.tsx`, add a pulsing indicator when recording is active. Add this CSS-in-JS style block at the top of the file:

```tsx
// Add to the top of the file
const pulseStyle = `
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  .recording-dot { animation: pulse 1s ease-in-out infinite; }
`;
```

Inject it in the component: `<style>{pulseStyle}</style>` as the first child of `<main>`.

Update the voice button to show a recording dot:

```tsx
<button onClick={isRecording ? stopRecording : startRecording} ...>
  {isRecording ? (
    <span>
      <span className="recording-dot" style={{ display: "inline-block", width: "8px", height: "8px", background: "#dc2626", borderRadius: "50%", marginRight: "6px" }} />
      Stop
    </span>
  ) : "🎤"}
</button>
```

### 4.2 Display transcript before generation

In `page.tsx`, add a `transcript` state. After the Whisper call succeeds in `startRecording`, set the transcript and pre-fill the text input:

```tsx
const [transcript, setTranscript] = useState("");

// Inside mr.onstop handler, before the fetch call:
setTranscript(transcript.text);
setMessage(transcript.text);
```

This gives the user a chance to review/edit the transcription before it's sent to the LLM.

---

## Phase 5 — Cleanup & Production Hardening

### 5.1 Add `Procfile` for concurrent startup

Create `Procfile` at the project root:

```
api: uv run main.py --http --port 8000
web: cd web && npm run start
```

For development, install `concurrently`:

```bash
npm install -g concurrently
```

Add to `package.json` at project root (create if missing):

```json
{
  "scripts": {
    "dev": "concurrently \"uv run main.py --http\" \"cd web && npm run dev\"",
    "build": "cd web && npm run build",
    "start": "concurrently \"uv run main.py --http --port 8000\" \"cd web && npm run start\""
  }
}
```

### 5.2 Add `api/__init__.py` guard for missing Blender

In `api/server.py`, ensure `_run_modify_job` gracefully handles environments without Blender/Bonsai:

The existing implementation already handles this with the `try/except` around `_load_mcp_tools_sync()` — confirm this is present.

### 5.3 Update `.gitignore`

Append to `.gitignore`:

```gitignore
# Web frontend
web/node_modules/
web/.next/
web/.env.local

# API temp files
/tmp/voice_*.webm
```

### 5.4 Validate the full end-to-end flow

Run through this checklist:

- [ ] `uv run main.py --http` starts without errors
- [ ] `cd web && npm run dev` starts without errors
- [ ] Text generation: type description → job queued → IFC renders in viewer
- [ ] Voice generation: click mic → speak → stop → transcript appears → IFC generates
- [ ] Visual drawing: draw walls → "Generate IFC from Drawing" → IFC renders
- [ ] Element selection: click wall in IFC viewer → GUID appears in left panel
- [ ] Element modification: enter instruction → "Modify Element" → updated IFC reloads
- [ ] `agent/llm.py` log shows `model=gpt-5.4-pro` on first LLM call

---

## File Creation Summary

Windsurf should create or modify these files in order:

| # | Action | File |
|---|---|---|
| 1 | MODIFY | `agent/llm.py` — change model to `gpt-5.4-pro` |
| 2 | MODIFY | `.env` — set `AZURE_OPENAI_DEPLOYMENT=gpt-5.4-pro` |
| 3 | MODIFY | `main.py` — add `--http` flag |
| 4 | CREATE | `api/__init__.py` |
| 5 | CREATE | `api/server.py` |
| 6 | RUN | `npx create-next-app@latest web/ --typescript --tailwind --eslint --app --no-src-dir` |
| 7 | RUN | `cd web && npm install @thatopen/components @thatopen/components-front three @types/three` |
| 8 | RUN | `cd web && npm install zustand` |
| 9 | CREATE | `web/components/IFCViewer.tsx` |
| 10 | CREATE | `web/lib/toPlanJSON.ts` |
| 11 | CREATE | `web/hooks/usePascalEditor.ts` |
| 12 | CREATE | `web/components/VisualEditor.tsx` |
| 13 | CREATE | `web/app/page.tsx` |
| 14 | MODIFY | `web/next.config.ts` — add WASM experiment |
| 15 | CREATE | `web/.env.local` |
| 16 | CREATE | `Procfile` |
| 17 | MODIFY | `.gitignore` — add web/ entries |

---

## Known Constraints & Decisions

### ThatOpen AGPL License
`@thatopen/components` is licensed under AGPL-3.0. For open-source or internal deployments this is fine. For a commercial product, obtain a commercial license from That Open Company before shipping to customers.

### Pascal Editor npm packages
The `pascalorg/editor` packages are not yet published to npm as standalone packages. The `VisualEditor.tsx` component in Phase 3 provides a functional lightweight fallback. When Pascal publishes their packages, replace `VisualEditor.tsx` with their `<Viewer>` component and bind its `onExport` prop.

### Blender + Bonsai still required for full IFC generation
The `/api/build-from-plan` and `/api/generate` endpoints call `_load_mcp_tools_sync()` which requires a running Blender 4.4 + Bonsai instance. Without it, the pipeline runs in dry-run mode (tool calls logged but not executed). The IFC output will be empty. **Blender + Bonsai must still be running locally for actual IFC generation.** The web UI is the frontend layer; Blender remains the IFC geometry backend.

### gpt-5.4-pro endpoint compatibility
The current `AzureResponsesChatModel` in `agent/llm.py` uses the Azure Responses API (`POST /openai/responses`). Confirm that `gpt-5.4-pro` is deployed in your Azure resource and uses the same Responses API endpoint format. If `gpt-5.4-pro` uses Chat Completions instead, switch to `AzureChatOpenAI` from `langchain_openai` — remove the custom `AzureResponsesChatModel` class and replace the return value in `get_llm()` with:

```python
from langchain_openai import AzureChatOpenAI
_llm_instance = AzureChatOpenAI(
    azure_deployment="gpt-5.4-pro",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
    temperature=temperature,
)
```
