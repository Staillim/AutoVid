import { useState } from 'react';
import { useAssets, useImportAsset } from '../api';
import type { AssetRecord } from '../api';
import { Film, Image as ImageIcon, Music, Plus, Loader2, FileWarning } from 'lucide-react';

function AssetIcon({ kind }: { kind: string }) {
  if (kind === 'video') return <Film className="w-4 h-4 text-indigo-400" />;
  if (kind === 'image') return <ImageIcon className="w-4 h-4 text-emerald-400" />;
  if (kind === 'audio') return <Music className="w-4 h-4 text-amber-400" />;
  return <FileWarning className="w-4 h-4 text-slate-400" />;
}

export function AssetSidebar() {
  const { data: assets, isLoading } = useAssets();
  const importMutation = useImportAsset();
  const [importPath, setImportPath] = useState('');

  const handleImport = (e: React.FormEvent) => {
    e.preventDefault();
    if (!importPath.trim()) return;
    importMutation.mutate(importPath.trim(), {
      onSuccess: () => setImportPath('')
    });
  };

  return (
    <div className="flex flex-col gap-3 h-full">
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Assets Locales
      </h3>

      {/* Formulario de Importación */}
      <form onSubmit={handleImport} className="flex gap-2">
        <input
          type="text"
          placeholder="C:\ruta\al\archivo.mp4"
          className="flex-1 min-w-0 bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 placeholder-slate-600"
          value={importPath}
          onChange={(e) => setImportPath(e.target.value)}
          disabled={importMutation.isPending}
        />
        <button
          type="submit"
          disabled={importMutation.isPending || !importPath.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white p-1.5 rounded transition-colors"
          title="Importar Asset"
        >
          {importMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
        </button>
      </form>
      
      {importMutation.isError && (
        <div className="text-[10px] text-red-400 bg-red-950/50 p-2 rounded border border-red-900">
          Error: {importMutation.error.message}
        </div>
      )}

      {/* Lista de Assets */}
      <div className="flex-1 overflow-y-auto pr-1 -mr-1 space-y-2">
        {isLoading && (
          <div className="text-sm text-slate-500 italic flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Cargando assets...
          </div>
        )}

        {!isLoading && assets?.length === 0 && (
          <div className="text-sm text-slate-500 italic mt-2">
            No hay assets en la biblioteca. Pega una ruta para importar.
          </div>
        )}

        {!isLoading && assets?.map((asset: AssetRecord) => {
          // Extraer el nombre de archivo de la ruta absoluta
          const filename = asset.absolute_path.split(/[/\\]/).pop() || 'Desconocido';
          
          return (
            <div 
              key={asset.asset_id}
              className="bg-slate-950 border border-slate-800 rounded p-2 flex flex-col gap-1 cursor-grab hover:border-slate-600 transition-colors group"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/json', JSON.stringify({ type: 'asset', data: asset }));
              }}
            >
              <div className="flex items-center gap-2">
                <AssetIcon kind={asset.kind} />
                <span className="text-xs font-medium text-slate-200 truncate flex-1" title={asset.absolute_path}>
                  {filename}
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-[10px] text-slate-500 mt-1">
                <span className="uppercase">{asset.kind}</span>
                <span>•</span>
                <span>{(asset.size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                {asset.duration_ms ? (
                  <>
                    <span>•</span>
                    <span>{(asset.duration_ms / 1000).toFixed(1)}s</span>
                  </>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
