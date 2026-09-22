import React, { useState } from 'react';
import { Printer, RotateCw, Trash2, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';

interface PrintServiceTabProps {
    handleSpoolerAction: (action: string) => void;
    isLoading: boolean;
    spoolerService?: any;
}

export const PrintServiceTab: React.FC<PrintServiceTabProps> = ({ handleSpoolerAction, isLoading, spoolerService }) => {
    const [showConfirmClear, setShowConfirmClear] = useState(false);

    const isRunning = spoolerService
        ? (spoolerService.Status === 'Running' || spoolerService.Status === 4 || spoolerService.Status === '4')
        : null;

    return (
        <div className="space-y-6">
            <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 p-6 shadow-lg">
                <div className="flex items-start gap-4">
                    <div className="p-3.5 bg-blue-500/10 rounded-xl text-blue-400 border border-blue-500/20">
                        <Printer size={26} />
                    </div>
                    <div className="flex-1">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                            <h3 className="text-lg font-bold text-white">Gerenciamento do Spooler de Impressão Remoto</h3>
                            {spoolerService && (
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-zinc-400">Status do Spooler:</span>
                                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold flex items-center gap-1.5 ${
                                        isRunning
                                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                            : 'bg-red-500/20 text-red-400 border border-red-500/30'
                                    }`}>
                                        {isRunning ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                                        {isRunning ? 'Em Execução' : 'Parado / Travado'}
                                    </span>
                                </div>
                            )}
                        </div>
                        <p className="text-zinc-400 text-sm mb-6 leading-relaxed">
                            Controle o serviço <code className="text-blue-300 font-mono bg-zinc-900 px-1.5 py-0.5 rounded">Spooler</code> nesta máquina remota. 
                            Ideal para destravar filas de documentos retidos ou documentos corrompidos que impedem novas impressões.
                        </p>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            {/* Card 1: Reiniciar Spooler */}
                            <div className="bg-zinc-900/60 rounded-xl p-5 border border-zinc-700/60 flex flex-col justify-between space-y-4">
                                <div>
                                    <h4 className="text-white font-semibold mb-1.5 flex items-center gap-2">
                                        <RotateCw size={17} className="text-blue-400" />
                                        Reiniciar Serviço (Suave)
                                    </h4>
                                    <p className="text-zinc-400 text-xs leading-relaxed">
                                        Reinicia o processo do Spooler sem apagar a fila de documentos. Indicado quando a impressora está apenas demorando a responder ou em pausa temporária.
                                    </p>
                                </div>
                                <button
                                    onClick={() => handleSpoolerAction('restart')}
                                    disabled={isLoading}
                                    className="w-full py-2.5 px-4 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white rounded-lg border border-zinc-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-medium text-sm"
                                >
                                    {isLoading ? <RotateCw size={16} className="animate-spin text-blue-400" /> : <RotateCw size={16} className="text-blue-400" />}
                                    Reiniciar Spooler
                                </button>
                            </div>

                            {/* Card 2: Limpar e Reiniciar */}
                            <div className="bg-zinc-900/60 rounded-xl p-5 border border-zinc-700/60 flex flex-col justify-between space-y-4">
                                <div>
                                    <h4 className="text-white font-semibold mb-1.5 flex items-center gap-2">
                                        <Trash2 size={17} className="text-red-400" />
                                        Limpar Fila & Reiniciar (Completo)
                                    </h4>
                                    <p className="text-zinc-400 text-xs leading-relaxed">
                                        Para o serviço, deleta todos os arquivos temporários (<code className="text-zinc-300 font-mono">*.spl</code>, <code className="text-zinc-300 font-mono">*.shd</code>) presos na pasta <span className="font-mono text-zinc-300">C:\Windows\System32\spool\PRINTERS</span> e inicia o serviço novamente.
                                    </p>
                                </div>
                                {!showConfirmClear ? (
                                    <button
                                        onClick={() => setShowConfirmClear(true)}
                                        disabled={isLoading}
                                        className="w-full py-2.5 px-4 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded-lg border border-red-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-medium text-sm"
                                    >
                                        <Trash2 size={16} />
                                        Limpar e Reiniciar
                                    </button>
                                ) : (
                                    <div className="space-y-3 bg-red-950/30 border border-red-900/50 p-3.5 rounded-lg animate-in fade-in zoom-in-95 duration-150">
                                        <div className="flex items-center gap-2 text-red-300 text-xs font-semibold">
                                            <AlertTriangle size={14} className="text-red-400 shrink-0" />
                                            <span>Atenção: todas as impressões pendentes na fila serão canceladas!</span>
                                        </div>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setShowConfirmClear(false)}
                                                className="flex-1 py-1.5 px-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-medium transition-colors"
                                            >
                                                Cancelar
                                            </button>
                                            <button
                                                onClick={() => {
                                                    handleSpoolerAction('clear_and_restart');
                                                    setShowConfirmClear(false);
                                                }}
                                                className="flex-1 py-1.5 px-3 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-md shadow-red-900/30"
                                            >
                                                <Trash2 size={13} />
                                                Confirmar Limpeza
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
