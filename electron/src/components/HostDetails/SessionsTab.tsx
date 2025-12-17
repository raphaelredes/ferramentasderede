import React from 'react';
import { User, LogOut } from 'lucide-react';
import { Session } from '../../types';

interface SessionsTabProps {
    sessions: Session[];
    handleDisconnect: (sessionId: string) => void;
}

export const SessionsTab: React.FC<SessionsTabProps> = ({ sessions, handleDisconnect }) => {
    return (
        <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 overflow-hidden flex flex-col h-full">
            <div className="overflow-auto flex-1 custom-scrollbar">
                <table className="w-full text-left table-fixed">
                    <thead className="bg-zinc-900/50 text-zinc-400 text-sm sticky top-0 backdrop-blur-sm z-10">
                        <tr>
                            <th className="p-4 font-medium w-1/4">Usuário</th>
                            <th className="p-4 font-medium w-24">ID da Sessão</th>
                            <th className="p-4 font-medium w-32">Estado</th>
                            <th className="p-4 font-medium w-1/4">Nome da Sessão</th>
                            <th className="p-4 font-medium w-1/6">Logon Time</th>
                            <th className="p-4 font-medium w-1/6">Duração</th>
                            <th className="p-4 font-medium text-right w-24">Ações</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-700/50">
                        {sessions.length === 0 ? (
                            <tr>
                                <td colSpan={7} className="p-8 text-center text-zinc-500">
                                    Nenhuma sessão ativa encontrada
                                </td>
                            </tr>
                        ) : (
                            sessions.map((session) => (
                                <tr key={session.ID} className="hover:bg-zinc-700/20 transition-colors group">
                                    <td className="p-4 text-white font-medium flex items-center gap-2 truncate" title={session.UserName}>
                                        <User size={16} className="text-zinc-400 shrink-0" />
                                        <span className="truncate">{session.UserName}</span>
                                    </td>
                                    <td className="p-4 text-zinc-400">{session.ID}</td>
                                    <td className="p-4">
                                        <span className={`px-2 py-1 rounded text-xs font-medium ${session.State === 'Active'
                                            ? 'bg-green-500/20 text-green-400'
                                            : 'bg-zinc-700/50 text-zinc-400'
                                            }`}>
                                            {session.State}
                                        </span>
                                    </td>
                                    <td className="p-4 text-zinc-400 truncate" title={session.SessionName}>
                                        {session.SessionName === 'Console' ? 'Console (Usuário no local)' : session.SessionName}
                                    </td>
                                    <td className="p-4 text-zinc-400 text-sm truncate" title={session.LogonTime}>
                                        {session.LogonTime || '-'}
                                    </td>
                                    <td className="p-4 text-zinc-400 text-sm truncate" title={session.Duration}>
                                        {session.Duration || '-'}
                                    </td>
                                    <td className="p-4 text-right">
                                        <button
                                            onClick={() => handleDisconnect(session.ID)}
                                            className="p-1.5 hover:bg-red-500/20 text-red-400 rounded transition-colors opacity-0 group-hover:opacity-100"
                                            title="Desconectar Usuário"
                                        >
                                            <LogOut size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
