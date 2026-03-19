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
    from agent.graph import (
        _load_mcp_tools_sync,
        execute_build_steps,
        present_and_export,
        repair,
        should_repair,
        validate,
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

        def _run_sync() -> Dict[str, Any]:
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

        def _run_sync() -> str:
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
                mcp_tools["execute_ifc_code_tool"].invoke(
                    {"code": code, "instruction": req.instruction, "guid": req.guid}
                )
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
                response = llm.invoke(
                    [SystemMessage(content="You are an IfcOpenShell expert."), HumanMessage(content=prompt)]
                )
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
    import tempfile

    import openai

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    audio_bytes = await audio.read()

    # Write to a temp file — Whisper API requires a file-like object with a name
    tmp_path = Path(tempfile.gettempdir()) / f"voice_{uuid.uuid4()}.webm"
    tmp_path.write_bytes(audio_bytes)

    try:
        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
        message = transcript.text
    finally:
        tmp_path.unlink(missing_ok=True)

    job_id = str(uuid.uuid4())[:8]
    asyncio.create_task(_run_pipeline_job(job_id, message))
    return JobResponse(job_id=job_id, status="queued")


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
    import json as json_mod

    async def event_generator():
        while True:
            job = _jobs.get(job_id, {"status": "not_found"})
            yield f"data: {json_mod.dumps(job)}\n\n"
            if job.get("status") in ("complete", "error", "not_found"):
                break
            await asyncio.sleep(1.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
