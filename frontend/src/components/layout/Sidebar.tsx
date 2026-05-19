import { AssetSidebar } from '@/features/assets/components/AssetSidebar';

export function Sidebar() {
  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900 p-4 flex flex-col gap-4 overflow-y-auto shrink-0">
      <div className="text-slate-100 font-bold text-lg mb-2">NodeAV</div>
      
      <div className="flex-1 flex flex-col min-h-0">
        <AssetSidebar />
      </div>
      
      <div className="flex-1">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Nodos
        </h3>
        <div className="text-sm text-slate-500 italic">
          Selecciona nodos para arrastrar.
        </div>
      </div>
    </aside>
  );
}
