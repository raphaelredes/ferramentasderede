import React from 'react';
import { User, LogOut, Monitor, ShieldAlert } from 'lucide-react';
import { Session } from '../../types';

interface SessionsTabProps {
    sessions: Session[];
    handleDisconnect: (sessionId: string) => void;
    formatDate: (dateStr: string) => string;
}

export const SessionsTab: React.FC<SessionsTabProps> = ({ sessions, handleDisconnect, formatDate }) => {
    return (
        <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 overflow-hidden flex flex-col h-full shadow-lg">
            <div className="p-4 bg-zinc-900/60 border-b border-zinc-700/50 flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        <User size={16} className="text-blue-400" />
                        Sessões de Usuários Conectados
                    </h3>
                    <p className="text-xs text-zinc-400 mt-0.5">
                        Lista os usuários atualmente logados via Console físico ou Terminal Services (RDP).
                    </p>
                </div>
                <span className="text-xs px-2.5 py-1 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700 font-medium">
                    {sessions.length} {sessions.length === 1 ? 'sessão ativa' : 'sessões ativas'}
                </span>
            </div>

            <div className="overflow-auto flex-1 custom-scrollbar">
                <table className="w-full text-left table-fixed">
                    <thead className="bg-zinc-900/80 text-zinc-400 text-xs uppercase tracking-wider sticky top-0 backdrop-blur-sm z-10 border-b border-zinc-700/40">
                        <tr>
                            <th className="p-3.5 font-semibold w-1/4">Usuário</th>
                            <th className="p-3.5 font-semibold w-24 text-center">ID Sessão</th>
                            <th className="p-3.5 font-semibold w-28 text-center">Estado</th>
                            <th className="p-3.5 font-semibold w-1/4">Tipo / Nome de Sessão</th>
                            <th className="p-3.5 font-semibold w-40">Horário de Logon</th>
                            <th className="p-3.5 font-semibold w-28">Duração</th>
                            <th className="p-3.5 font-semibold text-right w-24">Ações</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-700/40 text-sm">
                        {sessions.length === 0 ? (
                            <tr>
                                <td colSpan={7} className="p-8 text-center text-zinc-500">
                                    Nenhuma sessão de usuário ativa encontrada no momento.
                                </td>
                            </tr>
                        ) : (
                            sessions.map((session) => {
                                const isConsole = session.SessionName === 'Console';
                                const isActive = session.State === 'Active';

                                return (
                                    <tr key={session.ID} className="hover:bg-zinc-700/20 transition-colors group">
                                        <td className="p-3.5 text-white font-medium flex items-center gap-2.5 truncate" title={session.UserName}>
                                            <div className="p-1.5 rounded-lg bg-zinc-800 text-zinc-300 border border-zinc-700/60 shrink-0">
                                                <User size={15} />
                                            </div>
                                            <span className="truncate font-semibold text-zinc-100">{session.UserName}</span>
                                        </td>
                                        <td className="p-3.5 text-zinc-400 font-mono text-xs text-center">{session.ID}</td>
                                        <td className="p-3.5 text-center">
                                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold inline-block ${
                                                isActive
                                                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                                    : 'bg-zinc-700/40 text-zinc-400 border border-zinc-700/50'
                                            }`}>
                                                {isActive ? 'Ativo' : session.State}
                                            </span>
                                        </td>
                                        <td className="p-3.5 text-zinc-300 truncate text-xs" title={session.SessionName}>
                                            {isConsole ? (
                                                <span className="flex items-center gap-1.5 text-blue-300 font-medium">
                                                    <Monitor size={13} className="text-blue-400" />
                                                    Console (Terminal Físico)
                                                </span>
                                            ) : (
                                                <span className="text-zinc-300 font-mono">
                                                    {session.SessionName || 'RDP / Remoto'}
                                                </span>
                                            )}
                                        </td>
                                        <td className="p-3.5 text-zinc-400 text-xs font-mono truncate" title={session.LogonTime}>
                                            {formatDate(session.LogonTime || '')}
                                        </td>
                                        <td className="p-3.5 text-zinc-400 text-xs truncate" title={session.Duration}>
                                            {session.Duration || '-'}
                                        </td>
                                        <td className="p-3.5 text-right">
                                            <button
                                                onClick={() => handleDisconnect(session.ID)}
                                                className="p-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded-lg border border-red-500/20 transition-all opacity-85 group-hover:opacity-100"
                                                title={`Desconectar ${session.UserName}`}
                                            >
                                                <LogOut size={15} />
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>
            
            {sessions.length > 0 && (
                <div className="p-3 bg-zinc-900/60 border-t border-zinc-700/40 text-xs text-zinc-400 flex items-center gap-2">
                    <ShieldAlert size={14} className="text-amber-400 shrink-0" />
                    <span>Desconectar uma sessão encerra os programas do usuário e fecha sua área de trabalho.</span>
                </div>
            )}
        </div>
    );
};
