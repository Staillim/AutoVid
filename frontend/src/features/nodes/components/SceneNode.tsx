import { memo } from 'react';
import { Handle, Position } from 'reactflow';
import type { NodeProps } from 'reactflow';
import type { SceneNodeData } from '../types';
import { Film, MoreHorizontal, Image as ImageIcon } from 'lucide-react';
import { clsx } from 'clsx';

function SceneNodeComponent({ data, selected }: NodeProps<SceneNodeData>) {
  // Formatear la duración para mostrar '0.0s'
  const durationSecs = (data.duration_ms / 1000).toFixed(1);

  return (
    <div
      className={clsx(
        "relative min-w-[240px] rounded-xl border bg-slate-900 shadow-xl transition-all",
        selected 
          ? "border-indigo-500 shadow-indigo-500/20 ring-1 ring-indigo-500" 
          : "border-slate-700 hover:border-slate-600"
      )}
    >
      {/* Handle de entrada (Izquierda) */}
      <Handle
        type="target"
        position={Position.Left}
        className={clsx(
          "w-3 h-3 border-2 border-slate-900 bg-slate-400 transition-colors",
          selected && "bg-indigo-400"
        )}
      />

      {/* Header del Nodo */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800 bg-slate-800/50 rounded-t-xl">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded bg-indigo-500/20 text-indigo-400">
            <Film className="w-4 h-4" />
          </div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Escena
          </span>
        </div>
        
        {/* Badge del rol narrativo (opcional) */}
        {data.narrative?.narrative_role && (
          <span className="absolute -top-2.5 right-2 bg-indigo-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider shadow-sm">
            {data.narrative.narrative_role}
          </span>
        )}
      </div>

      {/* Cuerpo del Nodo */}
      <div className="p-3">
        <div className="font-medium text-slate-200 truncate pr-6 mb-1">
          {data.title || 'Escena sin título'}
        </div>
        
        <div className="flex items-center justify-between mt-3 text-xs">
          <span className="text-slate-500 font-mono bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
            {durationSecs}s
          </span>
          
          <div className="flex items-center gap-1">
            {data.background && (
              <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded flex items-center gap-1" title="Background Asset Assigned">
                <ImageIcon className="w-3 h-3" />
                Asset
              </span>
            )}
            {(data.overlays.length > 0 || data.texts.length > 0) && (
              <span className="text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-1.5 py-0.5 rounded flex items-center gap-1" title="Overlays activos">
                <div className="w-1 h-1 bg-indigo-400 rounded-full" />
                {data.overlays.length + data.texts.length}
              </span>
            )}
            <button className="text-slate-500 hover:text-slate-300 p-1 rounded hover:bg-slate-800 transition-colors">
              <MoreHorizontal className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Handle de salida (Derecha) */}
      <Handle
        type="source"
        position={Position.Right}
        className={clsx(
          "w-3 h-3 border-2 border-slate-900 bg-slate-400 transition-colors",
          selected && "bg-indigo-400"
        )}
      />
    </div>
  );
}

// Envolvemos en React.memo para performance de re-renders
export const SceneNode = memo(SceneNodeComponent);
