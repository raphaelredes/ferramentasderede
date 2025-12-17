import React, { useState } from 'react';
import { Printer, RotateCw, Trash2, AlertTriangle } from 'lucide-react';

interface PrintServiceTabProps {
    handleSpoolerAction: (action: string) => void;
    isLoading: boolean;
}

export const PrintServiceTab: React.FC<PrintServiceTabProps> = ({ handleSpoolerAction, isLoading }) => {
    const [showConfirmClear, setShowConfirmClear] = useState(false);

    return (
        <div className="space-y-6 p-4">
            <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 p-6">
                <div className="flex items-start gap-4">
                    <div className="p-3 bg-blue-500/10 rounded-lg text-blue-400">
                        <Printer size={24} />
                    </div>
                    <div className="flex-1">
                        <h3 className="text-lg font-medium text-white mb-1">Gerenciamento de Spooler de Impressão</h3>
                        <p className="text-zinc-400 text-sm mb-6">
                            Gerencie o serviço de spooler de impressão remoto. Você pode reiniciar o serviço ou limpar a fila de impressão e reiniciar.
                        </p>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-700/50">
                                <h4 className="text-white font-medium mb-2 flex items-center gap-2">
                                    <RotateCw size={16} className="text-blue-400" />
                                    Reiniciar Serviço
                                </h4>
                                <p className="text-zinc-500 text-xs mb-4">
                                    Reinicia o serviço de Spooler de Impressão. Útil para travamentos leves.
                                </p>
                                <button
                                    onClick={() => handleSpoolerAction('restart')}
                                    disabled={isLoading}
                                    className="w-full py-2 px-4 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white rounded-lg border border-zinc-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    {isLoading ? <RotateCw size={16} className="animate-spin" /> : <RotateCw size={16} />}
                                    Reiniciar Spooler
                                </button>
                            </div>

                            <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-700/50">
                                <h4 className="text-white font-medium mb-2 flex items-center gap-2">
                                    <Trash2 size={16} className="text-red-400" />
                                    Limpar Spool e Reiniciar
                                </h4>
                                <p className="text-zinc-500 text-xs mb-4">
                                    Para o serviço, apaga arquivos em C:\Windows\System32\spool\PRINTERS e inicia novamente.
                                </p>
                                {!showConfirmClear ? (
                                    <button
                                        onClick={() => setShowConfirmClear(true)}
                                        disabled={isLoading}
                                        className="w-full py-2 px-4 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded-lg border border-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                    >
                                        <Trash2 size={16} />
                                        Limpar e Reiniciar
                                    </button>
                                ) : (
                                    <div className="space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
                                        <div className="flex items-center gap-2 text-yellow-400 text-xs bg-yellow-500/10 p-2 rounded border border-yellow-500/20">
                                            <AlertTriangle size={12} />
                                            <span>Isso apagará todas as impressões pendentes!</span>
                                        </div>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setShowConfirmClear(false)}
                                                className="flex-1 py-1 px-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 rounded text-sm transition-colors"
                                            >
                                                Cancelar
                                            </button>
                                            <button
                                                onClick={() => {
                                                    handleSpoolerAction('clear_and_restart');
                                                    setShowConfirmClear(false);
                                                }}
                                                className="flex-1 py-1 px-2 bg-red-500 hover:bg-red-600 text-white rounded text-sm transition-colors flex items-center justify-center gap-1"
                                            >
                                                <Trash2 size={12} />
                                                Confirmar
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
