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
