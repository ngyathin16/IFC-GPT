"use client";

/**
 * 2D wall-drawing canvas with snap-to-grid, undo, and proper coordinate mapping.
 *
 * Lightweight fallback for the Pascal editor. When pascalorg/editor is available
 * as an npm package, replace this component with their <Viewer> component.
 */

import { useRef, useEffect, useCallback, useState } from "react";
import { usePascalEditor } from "@/hooks/usePascalEditor";

interface VisualEditorProps {
  onExportPlan: (plan: any) => void;
}

const PX_PER_METER = 30;
const GRID_METERS = 1;
const SNAP = 0.5; // snap to half-meter

export default function VisualEditor({ onExportPlan }: VisualEditorProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { nodes, addNode, removeNode, clearScene, exportToBuildingPlan } = usePascalEditor();
  const [startPt, setStartPt] = useState<[number, number] | null>(null);
  const [mouseWorld, setMouseWorld] = useState<[number, number] | null>(null);
  const wallIdRef = useRef(0);

  /* ---- coordinate helpers ---- */
  const toCanvas = useCallback(
    (wx: number, wy: number, w: number, h: number): [number, number] => [
      w / 2 + wx * PX_PER_METER,
      h / 2 - wy * PX_PER_METER,
    ],
    [],
  );

  const toWorld = useCallback(
    (px: number, py: number, w: number, h: number): [number, number] => {
      const wx = (px - w / 2) / PX_PER_METER;
      const wy = -(py - h / 2) / PX_PER_METER;
      return [Math.round(wx / SNAP) * SNAP, Math.round(wy / SNAP) * SNAP];
    },
    [],
  );

  /* ---- resize canvas to fill container ---- */
  useEffect(() => {
    const resize = () => {
      const wrap = wrapRef.current;
      const cvs = canvasRef.current;
      if (!wrap || !cvs) return;
      const r = wrap.getBoundingClientRect();
      cvs.width = Math.floor(r.width);
      cvs.height = Math.floor(r.height);
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  /* ---- draw ---- */
  const draw = useCallback(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const ctx = cvs.getContext("2d")!;
    const W = cvs.width;
    const H = cvs.height;
    ctx.clearRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = "#27272a";
    ctx.lineWidth = 1;
    const step = GRID_METERS * PX_PER_METER;
    const ox = (W / 2) % step;
    const oy = (H / 2) % step;
    for (let x = ox; x < W; x += step) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = oy; y < H; y += step) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    // Origin crosshair
    const [cx, cy] = toCanvas(0, 0, W, H);
    ctx.strokeStyle = "#3f3f46";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cx - 8, cy); ctx.lineTo(cx + 8, cy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, cy - 8); ctx.lineTo(cx, cy + 8); ctx.stroke();

    // Walls
    const walls = Object.values(nodes).filter((n) => n.type === "wall");
    for (const w of walls) {
      const [sx, sy] = toCanvas(w.start[0], w.start[1], W, H);
      const [ex, ey] = toCanvas(w.end[0], w.end[1], W, H);
      // Wall body
      ctx.strokeStyle = "#8b5cf6";
      ctx.lineWidth = Math.max(3, (w.thickness ?? 0.2) * PX_PER_METER);
      ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey); ctx.stroke();
      // Endpoint dots
      ctx.fillStyle = "#a78bfa";
      for (const [px, py] of [[sx, sy], [ex, ey]]) {
        ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI * 2); ctx.fill();
      }
    }

    // In-progress wall preview
    if (startPt && mouseWorld) {
      const [sx, sy] = toCanvas(startPt[0], startPt[1], W, H);
      const [ex, ey] = toCanvas(mouseWorld[0], mouseWorld[1], W, H);
      ctx.strokeStyle = "#4ade80";
      ctx.lineWidth = 0.2 * PX_PER_METER;
      ctx.lineCap = "round";
      ctx.setLineDash([6, 4]);
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey); ctx.stroke();
      ctx.setLineDash([]);
      // Start dot
      ctx.fillStyle = "#4ade80";
      ctx.beginPath(); ctx.arc(sx, sy, 5, 0, Math.PI * 2); ctx.fill();
      // Length label
      const dx = mouseWorld[0] - startPt[0];
      const dy = mouseWorld[1] - startPt[1];
      const len = Math.sqrt(dx * dx + dy * dy);
      if (len > 0.1) {
        const mx = (sx + ex) / 2;
        const my = (sy + ey) / 2 - 12;
        ctx.fillStyle = "#a1a1aa";
        ctx.font = "11px var(--font-geist-mono, monospace)";
        ctx.textAlign = "center";
        ctx.fillText(`${len.toFixed(1)}m`, mx, my);
      }
    }

    // Snap cursor
    if (mouseWorld && !startPt) {
      const [mx, my] = toCanvas(mouseWorld[0], mouseWorld[1], W, H);
      ctx.strokeStyle = "#52525b";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(mx, my, 6, 0, Math.PI * 2); ctx.stroke();
    }
  }, [nodes, startPt, mouseWorld, toCanvas]);

  useEffect(() => { draw(); }, [draw]);

  /* ---- mouse handlers ---- */
  const getWorldFromEvent = (e: React.MouseEvent<HTMLCanvasElement>): [number, number] => {
    const cvs = canvasRef.current!;
    const rect = cvs.getBoundingClientRect();
    const sx = cvs.width / rect.width;
    const sy = cvs.height / rect.height;
    return toWorld(
      (e.clientX - rect.left) * sx,
      (e.clientY - rect.top) * sy,
      cvs.width,
      cvs.height,
    );
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const pt = getWorldFromEvent(e);
    if (!startPt) {
      setStartPt(pt);
    } else {
      const dx = pt[0] - startPt[0];
      const dy = pt[1] - startPt[1];
      if (Math.sqrt(dx * dx + dy * dy) < 0.3) {
        setStartPt(null); // cancel if too short
        return;
      }
      wallIdRef.current += 1;
      addNode({
        id: `W${wallIdRef.current}`,
        type: "wall",
        start: startPt,
        end: pt,
        parentId: "GF",
        isExterior: true,
        thickness: 0.2,
      });
      if (!Object.values(nodes).some((n) => n.type === "level")) {
        addNode({ id: "GF", type: "level", name: "Ground Floor", elevation: 0, height: 3.0 });
      }
      setStartPt(null);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setMouseWorld(getWorldFromEvent(e));
  };

  const handleRightClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setStartPt(null); // cancel in-progress wall
  };

  /* ---- undo last wall ---- */
  const handleUndo = () => {
    const wallIds = Object.keys(nodes).filter((id) => nodes[id].type === "wall").sort();
    if (wallIds.length) removeNode(wallIds[wallIds.length - 1]);
    setStartPt(null);
  };

  const handleClear = () => {
    clearScene();
    wallIdRef.current = 0;
    setStartPt(null);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "z") { e.preventDefault(); handleUndo(); }
      if (e.key === "Escape") setStartPt(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const wallCount = Object.values(nodes).filter((n) => n.type === "wall").length;

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2">
        <p className="flex-1 text-[11px] text-zinc-500">
          {startPt ? "Click to place endpoint" : "Click to start a wall"}
          {wallCount > 0 && <span className="text-zinc-400 ml-1">({wallCount})</span>}
        </p>
        <button
          onClick={handleUndo}
          disabled={wallCount === 0}
          className="px-2.5 py-1.5 text-[11px] rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 disabled:opacity-30 transition"
          title="Undo (Ctrl+Z)"
        >
          Undo
        </button>
        <button
          onClick={handleClear}
          disabled={wallCount === 0}
          className="px-2.5 py-1.5 text-[11px] rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 disabled:opacity-30 transition"
        >
          Clear
        </button>
      </div>

      {/* Canvas */}
      <div
        ref={wrapRef}
        className="relative w-full rounded-lg overflow-hidden border border-zinc-800 bg-zinc-950"
        style={{ height: "320px" }}
      >
        <canvas
          ref={canvasRef}
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onContextMenu={handleRightClick}
          className="absolute inset-0 w-full h-full cursor-crosshair"
        />
      </div>
      <p className="text-[10px] text-zinc-600 leading-relaxed">
        Right-click or Esc to cancel. Ctrl+Z to undo. Snaps to 0.5 m grid.
      </p>

      {/* Export button */}
      <button
        onClick={() => onExportPlan(exportToBuildingPlan())}
        disabled={wallCount === 0}
        className="w-full h-10 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold transition-colors"
      >
        Generate IFC from Drawing
      </button>
    </div>
  );
}
