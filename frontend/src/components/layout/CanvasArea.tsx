import { useCallback, useRef } from 'react';
import { ReactFlow, Background, Controls, ReactFlowProvider, useReactFlow } from 'reactflow';
import 'reactflow/dist/style.css';
import { useEditorStore } from '@/stores/useEditorStore';
import { nodeRegistry } from '@/features/nodes/registry';
import type { AssetRecord } from '@/features/assets/api';

function CanvasAreaInner() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, updateNodeData, addNode } = useEditorStore();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { project, getIntersectingNodes } = useReactFlow();

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect();
      const typeStr = event.dataTransfer.getData('application/json');

      if (!typeStr || !reactFlowBounds) return;

      try {
        const parsed = JSON.parse(typeStr);
        if (parsed.type === 'asset') {
          const asset = parsed.data as AssetRecord;
          
          // Calcular posición
          const position = project({
            x: event.clientX - reactFlowBounds.left,
            y: event.clientY - reactFlowBounds.top,
          });

          // Detectar si soltamos SOBRE un nodo existente
          const targetNode = getIntersectingNodes({
            x: event.clientX - reactFlowBounds.left,
            y: event.clientY - reactFlowBounds.top,
            width: 1,
            height: 1
          })[0];

          if (targetNode && targetNode.type === 'scene') {
            // Actualizar el background del nodo
            updateNodeData(targetNode.id, { 
              background: {
                asset: { asset_id: asset.asset_id, kind: asset.kind },
                trim_in_ms: 0,
                trim_out_ms: asset.duration_ms || 5000,
                loop_mode: 'cut',
                fit_mode: 'cover',
                blur_background: false
              } 
            });
          } else {
            // Crear nuevo nodo con este asset
            const newNodeId = `scene-${Date.now()}`;
            addNode({
              id: newNodeId,
              type: 'scene',
              position,
              data: {
                title: asset.absolute_path.split(/[/\\]/).pop() || 'Nueva Escena',
                enabled: true,
                duration_ms: asset.duration_ms || 5000,
                narrative: {
                  source_start_ms: null,
                  source_end_ms: null,
                  summary: 'Nueva Escena desde Asset',
                  transcript_excerpt: '',
                  entities: [],
                  narrative_role: 'context',
                  confidence: 1.0,
                },
                background: {
                  asset: { asset_id: asset.asset_id, kind: asset.kind },
                  trim_in_ms: 0,
                  trim_out_ms: asset.duration_ms || 5000,
                  loop_mode: 'cut',
                  fit_mode: 'cover',
                  blur_background: false
                },
                overlays: [],
                texts: [],
                zoom: { mode: 'none', start_ms: 0, end_ms: 0, start_scale: 1.0, end_scale: 1.0, anchor: 'center' },
                subtitles: { enabled: false, mode: 'segment', cues: [], style_preset: 'default_youtube' },
                tags: [],
                ui: { canvas_x: position.x, canvas_y: position.y, color_hint: null },
              },
            });
          }
        }
      } catch (e) {
        console.error('Error parsing dropped data', e);
      }
    },
    [project, getIntersectingNodes, updateNodeData, addNode]
  );

  return (
    <div className="flex-1 relative bg-slate-950" ref={reactFlowWrapper}>
      <ReactFlow 
        nodes={nodes} 
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeRegistry}
        onDrop={onDrop}
        onDragOver={onDragOver}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#334155" gap={16} />
        <Controls className="bg-slate-800 border-slate-700 fill-slate-300" />
      </ReactFlow>
      
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-slate-800/80 backdrop-blur text-slate-300 px-4 py-2 rounded-full text-sm font-medium border border-slate-700 pointer-events-none">
        Arrastra assets aquí o sobre un nodo
      </div>
    </div>
  );
}

export function CanvasArea() {
  return (
    <ReactFlowProvider>
      <CanvasAreaInner />
    </ReactFlowProvider>
  );
}
