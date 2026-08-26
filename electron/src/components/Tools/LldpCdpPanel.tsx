import { useState } from 'react';
import { Router, Play, RefreshCw, Radio, Server, Activity, Network } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface L2Data {
    protocol: string;
    switch_name?: string;
    switch_desc?: string;
    port_id?: string;
    port_desc?: string;
    vlan_id?: number;
    mgmt_ip?: string;
    model?: string;
    chassis_id?: string;
    adapter_name?: string;
    adapter_speed?: string;
    adapter_mac?: string;
    gateway_vendor?: string;
}

export function LldpCdpPanel({ defaultSourceIp }: { defaultSourceIp?: string }) {
    const { showToast } = useToast();
    const [listening, setListening] = useState(false);
    const [l2Result, setL2Result, clearL2Result] = usePersistedState<L2Data | null>('lldp_cdp_tool_result', null);
    const [rawMessage, setRawMessage] = usePersistedState<string | null>('lldp_cdp_tool_message', null);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('lldp_cdp_tool_last_run', null);

    const startListening = async () => {
        setListening(true);

        try {
            const res = await fetch(`${API_BASE}/l2/lldp-listen`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ interface_ip: defaultSourceIp || null, timeout_seconds: 3 })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (data.success && data.data) {
                setL2Result(data.data);
                setRawMessage(null);
                setLastRunAt(new Date().toISOString());
                showToast('Descoberta L2 e Switch concluída com sucesso!', 'success');
            } else {
                setRawMessage(data.message || 'Nenhum frame LLDP/CDP capturado.');
                setLastRunAt(new Date().toISOString());
                showToast('Nenhum anúncio detectado no tempo limite.', 'warning');
            }
        } catch (err: any) {
            showToast(`Erro na captura L2: ${err.message}`, 'error');
            setRawMessage(`Falha na captura: ${err.message}`);
        } finally {
            setListening(false);
        }
    };


    return (
        <div className="bg-zinc-900/60 rounded-xl p-5 border border-zinc-800 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                    <Router className="text-blue-400" size={20} />
                    <div>
                        <h3 className="text-base font-semibold text-zinc-100">Descoberta de Camada 2 & Switch (LLDP / CDP / L2)</h3>
                        <p className="text-xs text-zinc-400">Identifica o switch físico, modelo, porta, VLAN nativa e enlace da conexão</p>
                    </div>
                </div>
                <button
                    onClick={startListening}
                    disabled={listening}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg shadow transition-colors"
                >
                    {listening ? <RefreshCw size={15} className="animate-spin" /> : <Play size={15} />}
                    {listening ? 'Analisando Camada 2...' : 'Iniciar Descoberta L2'}
                </button>
            </div>

            {(l2Result || rawMessage) && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={l2Result?.switch_name || l2Result?.protocol || null}
                    onClear={() => { clearL2Result(); setRawMessage(null); setLastRunAt(null); }}
                />
            )}

            {listening && (

                <div className="flex items-center gap-3 p-4 bg-blue-950/40 border border-blue-800/60 rounded-xl text-blue-300 text-xs">
                    <Radio size={20} className="animate-pulse text-blue-400 shrink-0" />
                    <span>Escutando pacotes multicast LLDP/CDP e inspecionando enlace físico do switch/gateway...</span>
                </div>
            )}

            {l2Result && (
                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 space-y-4 animate-in fade-in duration-200">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/80 pb-3">
                        <div className="flex items-center gap-2">
                            <Server className="text-emerald-400" size={20} />
                            <span className="font-bold text-zinc-100 text-sm">{l2Result.switch_name || 'Switch Identificado'}</span>
                        </div>
                        <span className="px-2.5 py-1 rounded bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs font-mono font-medium">
                            {l2Result.protocol}
                        </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                        <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800">
                            <div className="text-zinc-500 flex items-center gap-1.5 mb-1">
                                <Network size={13} className="text-blue-400" />
                                Porta / Interface
                            </div>
                            <div className="text-sm font-bold text-blue-400 truncate">{l2Result.port_id || 'N/A'}</div>
                            {l2Result.adapter_speed && (
                                <div className="text-[11px] text-zinc-400 mt-0.5">{l2Result.adapter_speed}</div>
                            )}
                        </div>

                        <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800">
                            <div className="text-zinc-500 flex items-center gap-1.5 mb-1">
                                <Activity size={13} className="text-emerald-400" />
                                VLAN ID
                            </div>
                            <div className="text-base font-bold text-emerald-400">{l2Result.vlan_id ?? 1}</div>
                            <div className="text-[11px] text-zinc-500 mt-0.5">VLAN Nativa / PVID</div>
                        </div>

                        <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800">
                            <div className="text-zinc-500 mb-1">IP do Gateway / Switch</div>
                            <div className="text-sm font-bold text-zinc-200 font-mono">{l2Result.mgmt_ip || 'N/A'}</div>
                            <div className="text-[11px] text-zinc-500 mt-0.5">Próximo Salto L2</div>
                        </div>

                        <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800">
                            <div className="text-zinc-500 mb-1">Fabricante & Modelo</div>
                            <div className="text-sm font-bold text-zinc-100 truncate" title={l2Result.gateway_vendor || l2Result.model || 'N/A'}>
                                {l2Result.gateway_vendor || 'Equipamento L2'}
                            </div>
                            <div className="text-[11px] text-blue-400 font-semibold mt-0.5 truncate" title={l2Result.model || ''}>
                                {l2Result.model && l2Result.model !== l2Result.gateway_vendor ? l2Result.model : 'Equipamento de Rede L2'}
                            </div>
                            <div className="text-[10px] text-zinc-500 font-mono mt-0.5 truncate">{l2Result.chassis_id || 'N/A'}</div>
                        </div>
                    </div>

                    {l2Result.switch_desc && (
                        <div className="text-xs text-zinc-400 bg-zinc-900/40 p-3 rounded-lg border border-zinc-800 font-mono">
                            <strong>Detalhes do Enlace:</strong> {l2Result.switch_desc}
                        </div>
                    )}
                </div>
            )}

            {rawMessage && !l2Result && !listening && (
                <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-zinc-400">
                    {rawMessage}
                </div>
            )}
        </div>
    );
}
