import React, { useState, useEffect } from 'react';
import { X, Terminal, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { API_BASE } from '../../config/api';

interface TestConnectionModalProps {
    isOpen: boolean;
    onClose: () => void;
    ip: string;
    credentials: { username: string; password: string } | null;
}

export const TestConnectionModal: React.FC<TestConnectionModalProps> = ({ isOpen, onClose, ip, credentials }) => {
    const [logs, setLogs] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<{ success: boolean; error?: string } | null>(null);

    useEffect(() => {
        if (isOpen) {
            setLogs('');
            setResult(null);
            runTest();
        }
    }, [isOpen]);

    const runTest = async () => {
        if (!credentials) {
            setLogs('Erro: Credenciais não fornecidas.');
            return;
        }

        setLoading(true);
        setLogs('Iniciando teste de conexão...\n');

        try {
            const res = await fetch(`${API_BASE}/system/test-connection`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    target_ip: ip,
                    username: credentials.username,
                    password: credentials.password
                })
            });

            const data = await res.json();
            setResult(data.result);
            setLogs(prev => prev + (data.logs || 'Nenhum log retornado.'));

        } catch (error) {
            setResult({ success: false, error: String(error) });
            setLogs(prev => prev + `\nErro ao conectar ao servidor: ${error}`);
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-3xl flex flex-col max-h-[80vh] shadow-2xl">
                <div className="flex items-center justify-between p-4 border-b border-zinc-800">
                    <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                        <Terminal size={20} className="text-blue-400" />
                        Teste de Conexão WinRM
                    </h2>
                    <button onClick={onClose} className="text-zinc-400 hover:text-white transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="p-4 flex-1 overflow-hidden flex flex-col gap-4">
                    <div className="flex items-center gap-4">
                        <div className="flex-1 bg-zinc-950 rounded-lg p-3 border border-zinc-800 flex items-center gap-3">
                            <div className={`p-2 rounded-full ${loading ? 'bg-blue-500/10 text-blue-400' :
                                    result?.success ? 'bg-green-500/10 text-green-400' :
                                        'bg-red-500/10 text-red-400'
                                }`}>
                                {loading ? <Loader2 size={20} className="animate-spin" /> :
                                    result?.success ? <CheckCircle size={20} /> :
                                        <AlertCircle size={20} />}
                            </div>
                            <div>
                                <div className="text-sm font-medium text-white">
                                    {loading ? 'Testando conexão...' :
                                        result?.success ? 'Conexão Estabelecida' :
                                            'Falha na Conexão'}
                                </div>
                                <div className="text-xs text-zinc-500">
                                    {loading ? 'Aguarde enquanto verificamos o acesso WinRM' :
                                        result?.success ? 'O host está acessível e configurado corretamente.' :
                                            result?.error || 'Erro desconhecido'}
                                </div>
                            </div>
                        </div>
                        <button
                            onClick={runTest}
                            disabled={loading}
                            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors disabled:opacity-50 text-sm font-medium"
                        >
                            Retestar
                        </button>
                    </div>

                    <div className="flex-1 bg-black rounded-lg border border-zinc-800 p-4 overflow-auto font-mono text-xs">
                        <pre className="text-zinc-300 whitespace-pre-wrap">{logs}</pre>
                    </div>
                </div>
            </div>
        </div>
    );
};
