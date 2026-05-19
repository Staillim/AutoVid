import { useEditorStore } from '@/stores/useEditorStore';
import { useRenderNode } from '@/features/jobs/api';
import { useAssets } from '@/features/assets/api';
import { Loader2 } from 'lucide-react';
import { useState } from 'react';

export function PropertiesPanel() {
  const selectedNodeId = useEditorStore((s) => s.selectedNodeId);
  const selectedNode = useEditorStore((s) => 
    s.nodes.find((n) => n.id === selectedNodeId)
  );
  const updateNodeData = useEditorStore((s) => s.updateNodeData);

  if (!selectedNode || selectedNode.type !== 'scene') {
    return (
      <aside className="w-80 border-l border-slate-800 bg-slate-900 p-4 flex flex-col items-center justify-center text-slate-500 text-sm italic text-center h-full">
        Selecciona un nodo o asset para ver sus propiedades.
      </aside>
    );
  }

  const { data } = selectedNode;

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'link';
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const typeStr = e.dataTransfer.getData('application/json');
    if (!typeStr) return;
    try {
      const parsed = JSON.parse(typeStr);
      if (parsed.type === 'asset') {
        const asset = parsed.data;
        updateNodeData(selectedNode.id, { 
          background: {
            asset: { asset_id: asset.asset_id, kind: asset.kind },
            trim_in_ms: 0,
            trim_out_ms: asset.duration_ms || 5000,
            loop_mode: 'cut',
            fit_mode: 'cover',
            blur_background: false
          }
        });
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <aside 
      className="w-80 border-l border-slate-800 bg-slate-900 p-4 overflow-y-auto"
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-6">
        Propiedades: Escena
      </h3>
      
      <div className="space-y-4">
        {/* Título */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">
            Título
          </label>
          <input
            type="text"
            className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            value={data.title}
            onChange={(e) => updateNodeData(selectedNode.id, { title: e.target.value })}
          />
        </div>

        {/* Duración */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">
            Duración (ms)
          </label>
          <input
            type="number"
            min="0"
            step="100"
            className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            value={data.duration_ms}
            onChange={(e) => updateNodeData(selectedNode.id, { duration_ms: Number(e.target.value) })}
          />
          <p className="text-[10px] text-slate-500 mt-1">
            Equivale a {(data.duration_ms / 1000).toFixed(1)} segundos
          </p>
        </div>

        {/* Rol Narrativo */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">
            Rol Narrativo
          </label>
          <select
            className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            value={data.narrative?.narrative_role || ''}
            onChange={(e) => updateNodeData(selectedNode.id, { 
              narrative: { ...data.narrative, narrative_role: e.target.value as any } 
            })}
          >
            <option value="hook">Hook</option>
            <option value="setup">Setup</option>
            <option value="context">Context</option>
            <option value="argument">Argument</option>
            <option value="evidence">Evidence</option>
            <option value="transition">Transition</option>
            <option value="payoff">Payoff</option>
            <option value="cta">CTA</option>
          </select>
        </div>

        {/* Fondo Visual (Asset) */}
        <div className="pt-4 border-t border-slate-800">
          <label className="block text-xs font-medium text-slate-400 mb-2">
            Fondo (Background)
          </label>
          {data.background?.asset ? (
            <div className="bg-slate-950 border border-indigo-500/50 rounded p-2 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <div className="text-xs text-slate-300 truncate font-mono" title={data.background.asset.asset_id}>
                  {data.background.asset.asset_id.split('-')[0]}...
                </div>
                <button 
                  onClick={() => updateNodeData(selectedNode.id, { background: undefined })}
                  className="text-slate-500 hover:text-red-400 transition-colors"
                  title="Quitar fondo"
                >
                  ×
                </button>
              </div>
            </div>
          ) : (
            <div className="border border-dashed border-slate-700 rounded p-3 text-center text-[10px] text-slate-500">
              Arrastra un Asset aquí o sobre el nodo en el canvas
            </div>
          )}
        </div>

        {/* Textos y Overlays */}
        <div className="pt-4 border-t border-slate-800 space-y-4">
          <label className="block text-xs font-medium text-slate-400">
            Composición (Textos)
          </label>
          
          <button
            onClick={() => {
              const newText = {
                id: `txt-${Date.now()}`,
                content: 'Nuevo Texto',
                start_ms: 0,
                end_ms: data.duration_ms,
                anchor: 'center' as const,
                x_offset_px: 0,
                y_offset_px: 0,
                font_family: 'Arial',
                font_size_px: 72,
                font_weight: 700 as const,
                color_rgba: 'rgba(255,255,255,1)',
                stroke_rgba: 'rgba(0,0,0,1)',
                stroke_width_px: 4,
                bg_rgba: null,
                padding_px: 0,
                anim: 'pop' as const,
                z_index: 10
              };
              updateNodeData(selectedNode.id, { texts: [...(data.texts || []), newText] });
            }}
            className="w-full bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 py-1.5 rounded transition-colors"
          >
            + Añadir Texto
          </button>

          {data.texts?.map((txt) => (
            <div key={txt.id} className="bg-slate-950 border border-slate-700 rounded p-2 text-xs flex items-center justify-between">
              <input
                className="bg-transparent text-slate-200 w-full focus:outline-none"
                value={txt.content}
                onChange={(e) => {
                  const updated = data.texts.map(t => t.id === txt.id ? { ...t, content: e.target.value } : t);
                  updateNodeData(selectedNode.id, { texts: updated });
                }}
              />
              <button 
                onClick={() => {
                  const updated = data.texts.filter(t => t.id !== txt.id);
                  updateNodeData(selectedNode.id, { texts: updated });
                }}
                className="text-slate-500 hover:text-red-400 ml-2"
              >
                ×
              </button>
            </div>
          ))}
        </div>

        {/* Sección de Renderizado de Prueba */}
        <RenderNodeSection selectedNode={selectedNode} />
      </div>
    </aside>
  );
}

function RenderNodeSection({ selectedNode }: { selectedNode: any }) {
  const { data: assets } = useAssets();
  const renderMutation = useRenderNode();
  const [jobId, setJobId] = useState<string | null>(null);

  const handleRender = () => {
    const { data } = selectedNode;
    
    // Solo enviar assets usados en este nodo
    const activeAssets = (assets || []).filter(a => {
      const isBg = data.background?.asset?.asset_id === a.asset_id;
      const isOverlay = data.overlays?.some((ov: any) => ov.asset.asset_id === a.asset_id);
      return isBg || isOverlay;
    });

    const payload = {
      settings: {
        width: 1920,
        height: 1080,
        fps: 30,
        video_codec: 'h264' as const,
        audio_codec: 'aac' as const,
        subtitle_language: 'es',
        export_preset: 'youtube_1080p' as const,
      },
      node: {
        id: selectedNode.id,
        order: 0,
        title: data.title,
        enabled: data.enabled ?? true,
        duration_ms: data.duration_ms,
        narrative: data.narrative || {
          source_start_ms: null,
          source_end_ms: null,
          summary: 'Composición',
          transcript_excerpt: '',
          entities: [],
          narrative_role: 'context',
          confidence: 1.0,
        },
        background: data.background,
        overlays: data.overlays || [],
        texts: data.texts || [],
        zoom: data.zoom || { mode: 'none', start_ms: 0, end_ms: 0, start_scale: 1.0, end_scale: 1.0, anchor: 'center' },
        subtitles: data.subtitles || { enabled: false, mode: 'segment', cues: [], style_preset: 'default_youtube' },
        tags: data.tags || [],
        ui: data.ui || { canvas_x: selectedNode.position.x, canvas_y: selectedNode.position.y, color_hint: null },
      },
      assets: activeAssets,
    };

    renderMutation.mutate(payload, {
      onSuccess: (res) => {
        setJobId(res.job_id);
      }
    });
  };

  return (
    <div className="pt-4 border-t border-slate-800 space-y-2">
      <button
        onClick={handleRender}
        disabled={renderMutation.isPending}
        className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 text-white font-medium py-2 rounded text-xs transition-colors flex items-center justify-center gap-2"
      >
        {renderMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
        Generar MP4 (Test)
      </button>

      {renderMutation.isSuccess && jobId && (
        <div className="text-[10px] bg-slate-950 border border-emerald-500/20 text-emerald-400 p-2 rounded">
          Trabajo iniciado exitosamente. ID: {jobId.slice(0, 8)}...
        </div>
      )}

      {renderMutation.isError && (
        <div className="text-[10px] bg-red-950/30 border border-red-900 text-red-400 p-2 rounded">
          Error: {renderMutation.error.message}
        </div>
      )}
    </div>
  );
}
