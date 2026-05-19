import { create } from 'zustand';
import { addEdge, applyNodeChanges, applyEdgeChanges } from 'reactflow';
import type { Connection, Edge, EdgeChange, NodeChange } from 'reactflow';
import type { AppNode, SceneNodeData } from '@/features/nodes/types';

interface EditorState {
  nodes: AppNode[];
  edges: Edge[];
  selectedNodeId: string | null;

  // Acciones base de React Flow
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;

  // Acciones de la UI
  setSelectedNodeId: (id: string | null) => void;
  updateNodeData: (id: string, data: Partial<SceneNodeData>) => void;
  addNode: (node: AppNode) => void;
}

// Nodo de ejemplo inicial
const initialNodes: AppNode[] = [
  {
    id: 'scene-1',
    type: 'scene',
    position: { x: 100, y: 100 },
    data: {
      title: 'Hook Inicial',
      enabled: true,
      duration_ms: 3000,
      narrative: {
        source_start_ms: 0,
        source_end_ms: 3000,
        summary: 'Introducción atractiva',
        transcript_excerpt: '',
        entities: [],
        narrative_role: 'hook',
        confidence: 1.0,
      },
      overlays: [],
      texts: [],
      zoom: { mode: 'none', start_ms: 0, end_ms: 0, start_scale: 1.0, end_scale: 1.0, anchor: 'center' },
      subtitles: { enabled: false, mode: 'segment', cues: [], style_preset: 'default_youtube' },
      tags: ['intro'],
      ui: { canvas_x: 100, canvas_y: 100, color_hint: null },
    },
  },
  {
    id: 'scene-2',
    type: 'scene',
    position: { x: 450, y: 100 },
    data: {
      title: 'Contexto de la historia',
      enabled: true,
      duration_ms: 5500,
      narrative: {
        source_start_ms: 3000,
        source_end_ms: 8500,
        summary: 'Contexto principal',
        transcript_excerpt: '',
        entities: [],
        narrative_role: 'context',
        confidence: 1.0,
      },
      overlays: [],
      texts: [],
      zoom: { mode: 'none', start_ms: 0, end_ms: 0, start_scale: 1.0, end_scale: 1.0, anchor: 'center' },
      subtitles: { enabled: false, mode: 'segment', cues: [], style_preset: 'default_youtube' },
      tags: ['main'],
      ui: { canvas_x: 450, canvas_y: 100, color_hint: null },
    },
  },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: 'scene-1', target: 'scene-2' }
];

export const useEditorStore = create<EditorState>((set, get) => ({
  nodes: initialNodes,
  edges: initialEdges,
  selectedNodeId: null,

  onNodesChange: (changes: NodeChange[]) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes) as AppNode[],
    });
    
    // Si la selección cambia, actualizar selectedNodeId
    const selectionChange = changes.find((c) => c.type === 'select');
    if (selectionChange && selectionChange.type === 'select') {
      if (selectionChange.selected) {
        set({ selectedNodeId: selectionChange.id });
      } else if (get().selectedNodeId === selectionChange.id) {
        set({ selectedNodeId: null });
      }
    }
  },

  onEdgesChange: (changes: EdgeChange[]) => {
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
  },

  onConnect: (connection: Connection) => {
    set({
      edges: addEdge(connection, get().edges),
    });
  },

  setSelectedNodeId: (id: string | null) => {
    set({ selectedNodeId: id });
    // Sincronizar React Flow selection state
    set({
      nodes: get().nodes.map((node) => ({
        ...node,
        selected: node.id === id,
      })),
    });
  },

  updateNodeData: (id: string, data: Partial<SceneNodeData>) => {
    set({
      nodes: get().nodes.map((node) => {
        if (node.id === id) {
          // Importante crear un nuevo objeto data para inmutabilidad
          return { ...node, data: { ...node.data, ...data } };
        }
        return node;
      }),
    });
  },

  addNode: (node: AppNode) => {
    set({ nodes: [...get().nodes, node] });
  },
}));
