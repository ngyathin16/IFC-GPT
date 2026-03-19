"use client";

import { useState, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";

const IFCViewer = dynamic(() => import("@/components/IFCViewer"), { ssr: false });
const VisualEditor = dynamic(() => import("@/components/VisualEditor"), { ssr: false });

interface Job {
  job_id: string;
  status: "queued" | "running" | "complete" | "error";
  ifc_url: string | null;
  error: string | null;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [message, setMessage] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [selectedGuids, setSelectedGuids] = useState<string[]>([]);
  const [modifyInstruction, setModifyInstruction] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const pollStatus = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/status/${jobId}`);
        const data: Job = await res.json();
        setJob(data);
        if (data.status === "complete" || data.status === "error") {
          clearInterval(pollRef.current!);
          setIsLoading(false);
        }
      } catch {}
    }, 2000);
  }, []);

  const handleGenerate = async () => {
    if (!message.trim()) return;
    setIsLoading(true);
    setJob(null);
    setSelectedGuids([]);
    try {
      const res = await fetch(`${API}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      setJob({ ...data, ifc_url: null });
      pollStatus(data.job_id);
    } catch (e: any) {
      setJob({ job_id: "--", status: "error", ifc_url: null, error: e.message });
      setIsLoading(false);
    }
  };

  const handleModify = async () => {
    if (!selectedGuids.length || !modifyInstruction || !job?.ifc_url) return;
    setIsLoading(true);
    const filename = job.ifc_url.replace("/workspace/", "");
    const res = await fetch(`${API}/api/modify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ifc_path: filename, guid: selectedGuids[0], instruction: modifyInstruction }),
    });
    const data = await res.json();
    setJob((prev) => ({ ...prev!, ...data }));
    pollStatus(data.job_id);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => chunksRef.current.push(e.data);
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const fd = new FormData();
        fd.append("audio", blob, "voice.webm");
        setIsLoading(true);
        const res = await fetch(`${API}/api/voice`, { method: "POST", body: fd });
        const data = await res.json();
        setJob({ ...data, ifc_url: null });
        pollStatus(data.job_id);
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setIsRecording(true);
    } catch {}
  };
  const stopRecording = () => { mediaRecorderRef.current?.stop(); setIsRecording(false); };

  const handleBuildFromPlan = async (plan: any) => {
    setIsLoading(true);
    setJob(null);
    const res = await fetch(`${API}/api/build-from-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan }),
    });
    const data = await res.json();
    setJob({ ...data, ifc_url: null });
    pollStatus(data.job_id);
  };

  const downloadIfc = async () => {
    if (!job?.ifc_url) return;
    try {
      const res = await fetch(`${API}${job.ifc_url}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = job.ifc_url.split("/").pop() || "model.ifc";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch { window.open(`${API}${job.ifc_url}`, "_blank"); }
  };

  const ifcFullUrl = job?.ifc_url ? `${API}${job.ifc_url}` : null;

  return (
    <div className="flex h-full bg-background">
      {/* ---- SIDEBAR ---- */}
      <aside className="w-[420px] shrink-0 flex flex-col border-r border-border bg-card">
        {/* Brand */}
        <div className="flex items-center gap-3 px-5 h-14 border-b border-border">
          <div className="size-7 rounded-md bg-primary flex items-center justify-center text-primary-foreground">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /></svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold leading-tight">IFC-GPT</p>
            <p className="text-[10px] text-muted-foreground font-mono">gpt-5.4-pro</p>
          </div>
          <Badge variant="outline" className="text-[10px] h-5">v2.0</Badge>
        </div>

        {/* Content */}
        <ScrollArea className="flex-1">
          <div className="p-5 space-y-5">
            <Tabs defaultValue="text" className="w-full">
              <TabsList className="w-full">
                <TabsTrigger value="text" className="flex-1 text-xs">Describe</TabsTrigger>
                <TabsTrigger value="draw" className="flex-1 text-xs">Draw</TabsTrigger>
              </TabsList>

              <TabsContent value="text" className="mt-4 space-y-3">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">
                    Building description
                  </label>
                  <Textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleGenerate(); }}
                    rows={5}
                    placeholder="A 3-storey office building, 20x15m footprint, concrete frame with central corridor..."
                    className="resize-none text-sm"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={handleGenerate}
                    disabled={isLoading || !message.trim()}
                    className="flex-1"
                    size="lg"
                  >
                    {isLoading ? (
                      <span className="flex items-center gap-2">
                        <span className="size-3.5 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                        Working...
                      </span>
                    ) : (
                      "Generate"
                    )}
                  </Button>
                  <Button
                    variant={isRecording ? "destructive" : "outline"}
                    size="icon-lg"
                    onClick={isRecording ? stopRecording : startRecording}
                    title={isRecording ? "Stop" : "Voice input"}
                  >
                    {isRecording ? (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" x2="12" y1="19" y2="22" /></svg>
                    )}
                  </Button>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  Ctrl+Enter to submit &middot; Blender must be running for IFC output
                </p>
              </TabsContent>

              <TabsContent value="draw" className="mt-4">
                <VisualEditor onExportPlan={handleBuildFromPlan} />
              </TabsContent>
            </Tabs>

            {/* Job status */}
            {job && (
              <>
                <Separator />
                <Card className={
                  job.status === "complete" ? "border-emerald-800/50 bg-emerald-950/20" :
                  job.status === "error" ? "border-destructive/30 bg-destructive/5" : ""
                }>
                  <CardContent className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground font-mono">
                        {job.job_id}
                      </span>
                      <Badge
                        variant={job.status === "complete" ? "default" : job.status === "error" ? "destructive" : "secondary"}
                        className="text-[10px] uppercase"
                      >
                        {(job.status === "running" || job.status === "queued") && (
                          <span className="size-1.5 rounded-full bg-current mr-1 animate-pulse" />
                        )}
                        {job.status}
                      </Badge>
                    </div>
                    {job.error && (
                      <p className="text-xs text-destructive leading-relaxed">{job.error}</p>
                    )}
                    {job.status === "complete" && !job.ifc_url && (
                      <p className="text-xs text-muted-foreground">
                        Pipeline finished but no IFC file was produced. Is Blender + Bonsai running?
                      </p>
                    )}
                    {job.ifc_url && (
                      <Button variant="outline" size="sm" onClick={downloadIfc} className="w-full">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" /></svg>
                        Download .ifc
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </>
            )}

            {/* Element modification */}
            {selectedGuids.length > 0 && (
              <>
                <Separator />
                <Card>
                  <CardContent className="p-4 space-y-3">
                    <div>
                      <p className="text-xs font-medium mb-1">Selected element</p>
                      <code className="text-[10px] text-muted-foreground break-all block leading-relaxed">
                        {selectedGuids[0]}
                      </code>
                    </div>
                    <input
                      value={modifyInstruction}
                      onChange={(e) => setModifyInstruction(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleModify(); }}
                      placeholder="e.g. change thickness to 0.3m"
                      className="w-full h-8 rounded-md border border-input bg-transparent px-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    />
                    <Button onClick={handleModify} disabled={isLoading || !modifyInstruction.trim()} size="sm" className="w-full">
                      Apply modification
                    </Button>
                  </CardContent>
                </Card>
              </>
            )}
          </div>
        </ScrollArea>
      </aside>

      {/* ---- VIEWER ---- */}
      <main className="flex-1 relative bg-muted/30">
        {!ifcFullUrl && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center space-y-3 max-w-xs">
              <div className="mx-auto size-12 rounded-lg border border-border bg-card flex items-center justify-center text-muted-foreground">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" x2="12" y1="22.08" y2="12" /></svg>
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">No model loaded</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Describe a building or draw walls to generate an IFC model.
                </p>
              </div>
            </div>
          </div>
        )}
        {!ifcFullUrl && isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center space-y-3">
              <div className="mx-auto size-8 border-2 border-muted-foreground/20 border-t-foreground rounded-full animate-spin" />
              <p className="text-xs text-muted-foreground">Generating model...</p>
            </div>
          </div>
        )}
        {ifcFullUrl && (
          <IFCViewer ifcUrl={ifcFullUrl} onElementSelected={setSelectedGuids} />
        )}
      </main>
    </div>
  );
}
