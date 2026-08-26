import { useState } from 'react';
import { X, FileText, Download, Printer, Server, BarChart2 } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

interface ReportGeneratorModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function ReportGeneratorModal({ isOpen, onClose }: ReportGeneratorModalProps) {
    const { showToast } = useToast();
    const [reportType, setReportType] = useState<'inventory' | 'sla'>('inventory');
    const [timeRange, setTimeRange] = useState<'24h' | '7d' | '30d'>('24h');
    const [generating, setGenerating] = useState(false);

    if (!isOpen) return null;

    const handleGenerate = async () => {
        setGenerating(true);
        try {
            const res = await fetch(`${API_BASE}/reports/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    report_type: reportType,
                    time_range: timeRange
                })
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const html = await res.text();
            
            const blob = new Blob([html], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank');
            showToast('Relatório gerado com sucesso!', 'success');
            onClose();
        } catch (err: any) {
            showToast(`Erro ao gerar relatório: ${err.message}`, 'error');
        } finally {
            setGenerating(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-950/50">
                    <div className="flex items-center gap-2.5">
                        <FileText className="text-blue-400" size={20} />
                        <h2 className="text-base font-semibold text-zinc-100">Gerador de Relatórios Técnicos</h2>
                    </div>
                    <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800">
                        <X size={18} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 space-y-5 text-xs">
                    <div className="space-y-2">
                        <label className="font-semibold text-zinc-300">Tipo de Relatório</label>
                        <div className="grid grid-cols-2 gap-3">
                            <button
                                type="button"
                                onClick={() => setReportType('inventory')}
                                className={`p-3 rounded-xl border text-left flex flex-col gap-1 transition-colors ${reportType === 'inventory' ? 'bg-blue-950/60 border-blue-600 text-blue-300' : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'}`}
                            >
                                <Server size={18} className={reportType === 'inventory' ? 'text-blue-400' : 'text-zinc-500'} />
                                <span className="font-semibold text-zinc-200">Inventário de Rede</span>
                                <span className="text-[11px] text-zinc-500">Hosts, grupos, fabricantes e status</span>
                            </button>

                            <button
                                type="button"
                                onClick={() => setReportType('sla')}
                                className={`p-3 rounded-xl border text-left flex flex-col gap-1 transition-colors ${reportType === 'sla' ? 'bg-blue-950/60 border-blue-600 text-blue-300' : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'}`}
                            >
                                <BarChart2 size={18} className={reportType === 'sla' ? 'text-blue-400' : 'text-zinc-500'} />
                                <span className="font-semibold text-zinc-200">SLA & Disponibilidade</span>
                                <span className="text-[11px] text-zinc-500">Métricas de latência, uptime e perda</span>
                            </button>
                        </div>
                    </div>

                    {reportType === 'sla' && (
                        <div className="space-y-2">
                            <label className="font-semibold text-zinc-300">Janela Temporal</label>
                            <div className="flex gap-2">
                                {(['24h', '7d', '30d'] as const).map(r => (
                                    <button
                                        key={r}
                                        onClick={() => setTimeRange(r)}
                                        className={`flex-1 py-1.5 rounded-lg border font-medium transition-colors ${timeRange === r ? 'bg-blue-600 text-white border-blue-600' : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200'}`}
                                    >
                                        {r}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-400 text-[11px] space-y-1">
                        <div className="flex items-center gap-1.5 text-zinc-300 font-medium">
                            <Printer size={14} className="text-blue-400" />
                            <span>Exportação e Impressão</span>
                        </div>
                        <p>O documento gerado é compatível com impressão direta em PDF de alta resolução pelo navegador.</p>
                    </div>

                    <button
                        onClick={handleGenerate}
                        disabled={generating}
                        className="w-full flex items-center justify-center gap-2 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow transition-colors"
                    >
                        <Download size={14} />
                        {generating ? 'Compilando Relatório...' : 'Gerar Relatório HTML / PDF'}
                    </button>
                </div>
            </div>
        </div>
    );
}
