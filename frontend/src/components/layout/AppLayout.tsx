import { Sidebar } from './Sidebar';
import { PropertiesPanel } from './PropertiesPanel';
import { CanvasArea } from './CanvasArea';
import { useHealthCheck } from '@/features/projects/api';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';

export function AppLayout() {
  const { data: health, isLoading, isError } = useHealthCheck();

  return (
    <div className="flex flex-col h-screen w-full bg-slate-950 text-slate-200 overflow-hidden font-sans">
      
      {/* Top Header */}
      <header className="h-14 border-b border-slate-800 bg-slate-900 flex items-center px-4 justify-between shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 bg-indigo-600 rounded flex items-center justify-center font-bold text-white">
            N
          </div>
          <h1 className="font-semibold text-slate-100">Proyecto sin título</h1>
        </div>
        
        <div className="flex items-center gap-3 text-sm">
          {isLoading && (
            <span className="flex items-center gap-2 text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin" /> Conectando...
            </span>
          )}
          {isError && (
            <span className="flex items-center gap-2 text-red-400">
              <XCircle className="w-4 h-4" /> Backend Offline
            </span>
          )}
          {health && (
            <span className="flex items-center gap-2 text-emerald-400" title="Render Ready">
              <CheckCircle2 className="w-4 h-4" /> Backend Online
            </span>
          )}
          <button className="ml-4 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-medium transition-colors">
            Exportar
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <CanvasArea />
        <PropertiesPanel />
      </div>

    </div>
  );
}
