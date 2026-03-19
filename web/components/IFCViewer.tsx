"use client";

import { useEffect, useRef, useState } from "react";

interface IFCViewerProps {
  ifcUrl: string | null;
  onElementSelected?: (guids: string[]) => void;
}

export default function IFCViewer({ ifcUrl, onElementSelected }: IFCViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const componentsRef = useRef<any>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!containerRef.current || !ifcUrl) return;
    let disposed = false;

    const init = async () => {
      setStatus("loading");
      setErrorMsg("");

      try {
        const OBC = await import("@thatopen/components");

        // Dispose previous instance
        if (componentsRef.current) {
          try { componentsRef.current.dispose(); } catch {}
        }

        const components = new OBC.Components();
        if (disposed) return;
        componentsRef.current = components;

        const worlds = components.get(OBC.Worlds);
        const world = worlds.create();

        world.scene = new OBC.SimpleScene(components);
        world.renderer = new OBC.SimpleRenderer(components, containerRef.current!);
        world.camera = new OBC.SimpleCamera(components);

        (world.scene as any).setup();
        components.init();

        // FragmentsManager MUST be initialized before IfcLoader
        components.get(OBC.FragmentsManager);

        const loader = components.get(OBC.IfcLoader);
        await loader.setup({ autoSetWasm: true });

        const response = await fetch(ifcUrl);
        if (!response.ok) throw new Error(`Failed to fetch IFC: ${response.status}`);
        const buffer = await response.arrayBuffer();
        if (disposed) return;

        const model = await loader.load(new Uint8Array(buffer), true, "model");

        // Fit camera to loaded model
        const bbox = components.get(OBC.BoundingBoxer);
        bbox.addFromModels();
        const box = bbox.get();
        const center = box.getCenter(new (await import("three")).Vector3());
        const size = box.getSize(new (await import("three")).Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        (world.camera as any).controls.setLookAt(
          center.x + maxDim, center.y + maxDim, center.z + maxDim,
          center.x, center.y, center.z,
          true,
        );

        if (!disposed) setStatus("ready");

        // Element selection
        if (onElementSelected) {
          try {
            const OBCF = await import("@thatopen/components-front");
            const highlighter = components.get(OBCF.Highlighter);
            highlighter.setup({ world });
            highlighter.events.select.onHighlight.add((fragmentIdMap: any) => {
              const frags = components.get(OBC.FragmentsManager);
              const guids: string[] = [];
              for (const [fragId, expressIds] of Object.entries(fragmentIdMap)) {
                const fragment = frags.list.get(fragId);
                if (!fragment) continue;
                for (const expressId of expressIds as Set<number>) {
                  const guid = (fragment as any).getItemGuid?.(expressId);
                  if (guid) guids.push(guid);
                }
              }
              if (guids.length > 0) onElementSelected(guids);
            });
            highlighter.events.select.onClear.add(() => onElementSelected([]));
          } catch {
            // Highlighter is optional — viewer still works without click selection
          }
        }
      } catch (err: any) {
        console.error("[IFCViewer]", err);
        if (!disposed) {
          setStatus("error");
          setErrorMsg(err?.message || "Unknown error loading IFC viewer");
        }
      }
    };

    init();

    return () => {
      disposed = true;
      if (componentsRef.current) {
        try { componentsRef.current.dispose(); } catch {}
        componentsRef.current = null;
      }
    };
  }, [ifcUrl]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="absolute inset-0" />

      {/* Loading overlay */}
      {status === "loading" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900/80 backdrop-blur-sm z-10">
          <div className="w-10 h-10 border-3 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mb-3" />
          <p className="text-sm text-zinc-400">Loading 3D model...</p>
        </div>
      )}

      {/* Error overlay */}
      {status === "error" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900/90 z-10 px-8">
          <div className="w-12 h-12 rounded-xl bg-red-950/50 border border-red-800/30 flex items-center justify-center mb-3">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><line x1="15" x2="9" y1="9" y2="15" /><line x1="9" x2="15" y1="9" y2="15" />
            </svg>
          </div>
          <p className="text-sm font-medium text-red-400 mb-1">Failed to load 3D viewer</p>
          <p className="text-xs text-zinc-500 text-center max-w-sm leading-relaxed">{errorMsg}</p>
          <p className="text-xs text-zinc-600 mt-3">The IFC file was generated successfully — use the download link to view it in an external IFC viewer.</p>
        </div>
      )}
    </div>
  );
}
