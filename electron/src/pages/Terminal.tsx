import { useEffect, useRef, useState } from 'react';
import { Terminal as XTerm } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { Terminal as TerminalIcon, Power, PowerOff } from 'lucide-react';
import { clsx } from 'clsx';

export function Terminal() {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<XTerm | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    const [connection, setConnection] = useState({
        ip: '',
        username: '',
        password: ''
    });
    const [isConnected, setIsConnected] = useState(false);
    const [status, setStatus] = useState('Desconectado');

    // Buffer de entrada local
    const inputBuffer = useRef('');

    const [settings, setSettings] = useState<any>(null);
    const [defaultCred, setDefaultCred] = useState<any>(null);

    useEffect(() => {
        // Fetch settings
        fetch('http://127.0.0.1:8000/settings')
            .then(res => res.json())
            .then(data => {
                setSettings(data);
                if (data.remote?.auto_login && data.remote?.default_credential_id) {
                    // Try to fetch credentials (requires vault unlocked)
                    fetch('http://127.0.0.1:8000/security/credentials')
                        .then(res => res.json())
                        .then(creds => {
                            const cred = creds.find((c: any) => c.id === data.remote.default_credential_id);
                            if (cred) {
                                setDefaultCred(cred);
                                setConnection(prev => ({ ...prev, username: cred.username, password: '' })); // Password empty, will use ID
                                xtermRef.current?.writeln(`\r\n[INFO] Credencial padrão '${cred.name}' carregada para login automático.`);
                            }
                        })
                        .catch(() => {
                            xtermRef.current?.writeln('\r\n[AVISO] Não foi possível carregar credencial padrão (Vault bloqueado?).');
                        });
                }
            })
            .catch(err => console.error("Failed to fetch settings", err));
    }, []);

    useEffect(() => {
        if (!terminalRef.current) return;

        const term = new XTerm({
            cursorBlink: true,
            theme: {
                background: '#09090b', // zinc-950
                foreground: '#f4f4f5', // zinc-100
            },
            fontFamily: 'Consolas, "Courier New", monospace',
            fontSize: 14,
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);

        term.open(terminalRef.current);
        fitAddon.fit();

        term.writeln('Bem-vindo ao Terminal Remoto (WinRM)');
        term.writeln('Configure a conexão acima para iniciar.\r\n');

        xtermRef.current = term;
        fitAddonRef.current = fitAddon;

        // Handle Input
        term.onData(data => {
            if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

            const code = data.charCodeAt(0);

            if (code === 13) { // Enter
                term.write('\r\n');
                const command = inputBuffer.current;
                inputBuffer.current = '';

                if (command.trim()) {
                    wsRef.current.send(JSON.stringify({ type: 'command', command }));
                } else {
                    term.write('PS > ');
                }
            } else if (code === 127) { // Backspace
                if (inputBuffer.current.length > 0) {
                    term.write('\b \b');
                    inputBuffer.current = inputBuffer.current.slice(0, -1);
                }
            } else if (code >= 32) { // Printable
                term.write(data);
                inputBuffer.current += data;
            }
        });

        const handleResize = () => fitAddon.fit();
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            term.dispose();
            wsRef.current?.close();
        };
    }, []);

    const connect = () => {
        // Allow connection if we have default cred (password empty is ok)
        if (!connection.ip || (!connection.username && !defaultCred) || (!connection.password && !defaultCred)) {
            // If we have default cred, username is filled. Password might be empty.
            // But if user manually cleared username, we shouldn't proceed.
            if (!defaultCred || !connection.username) {
                xtermRef.current?.writeln('\r\nErro: Preencha todos os campos de conexão.');
                return;
            }
        }

        setStatus('Conectando...');
        const ws = new WebSocket('ws://127.0.0.1:8000/ws/terminal');
        wsRef.current = ws;

        ws.onopen = () => {
            const payload: any = {
                type: 'connect',
                ip: connection.ip,
                username: connection.username,
                password: connection.password
            };

            // If using default cred and password field is empty (or match), send ID
            if (defaultCred && connection.username === defaultCred.username && !connection.password) {
                payload.credential_id = defaultCred.id;
                // Don't send empty password if sending ID, though backend handles it
            }

            ws.send(JSON.stringify(payload));
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            const term = xtermRef.current;
            if (!term) return;

            if (msg.type === 'status') {
                setStatus(msg.message);
                term.writeln(`\r\n[STATUS] ${msg.message}`);
            } else if (msg.type === 'ready') {
                setIsConnected(true);
                term.writeln('\r\nSessão WinRM estabelecida.');
                term.write('PS > ');
            } else if (msg.type === 'output') {
                // Converter newlines para CRLF para xterm
                const text = msg.data.replace(/\n/g, '\r\n');
                term.write(text);
            } else if (msg.type === 'error') {
                term.writeln(`\r\n[ERRO] ${msg.message}`);
                if (!isConnected) { // Se falhou na conexão
                    ws.close();
                } else {
                    term.write('PS > ');
                }
            } else if (msg.type === 'prompt') {
                term.write('PS > ');
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
            setStatus('Desconectado');
            xtermRef.current?.writeln('\r\n[STATUS] Conexão encerrada.');
        };

        ws.onerror = (err) => {
            console.error("WebSocket error", err);
            setStatus('Erro de Conexão');
            xtermRef.current?.writeln('\r\n[ERRO] Falha na conexão WebSocket.');
        }
    };

    const disconnect = () => {
        wsRef.current?.send(JSON.stringify({ type: 'disconnect' }));
        wsRef.current?.close();
    };

    return (
        <div className="h-full flex flex-col space-y-4 min-h-0 p-8">
            <header>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <TerminalIcon /> Terminal Remoto
                </h2>
                <p className="text-zinc-400">Acesso via WinRM/PowerShell.</p>
            </header>

            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 flex gap-4 items-end">
                <div className="flex-1 grid grid-cols-3 gap-4">
                    <div className="space-y-1">
                        <label className="text-xs text-white">IP / Hostname</label>
                        <input
                            type="text"
                            value={connection.ip}
                            onChange={e => setConnection(prev => ({ ...prev, ip: e.target.value }))}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-500 placeholder:text-zinc-500"
                            placeholder="192.168.1.10"
                            disabled={isConnected}
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs text-white">Usuário</label>
                        <input
                            type="text"
                            value={connection.username}
                            onChange={e => setConnection(prev => ({ ...prev, username: e.target.value }))}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-500 placeholder:text-zinc-500"
                            placeholder="Administrador"
                            disabled={isConnected}
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs text-white">Senha</label>
                        <input
                            type="password"
                            value={connection.password}
                            onChange={e => setConnection(prev => ({ ...prev, password: e.target.value }))}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-500 placeholder:text-zinc-500"
                            placeholder="••••••"
                            disabled={isConnected}
                        />
                    </div>
                </div>

                <button
                    onClick={isConnected ? disconnect : connect}
                    className={clsx(
                        "flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-colors h-[38px] border",
                        isConnected
                            ? "bg-zinc-800 hover:bg-zinc-700 text-red-400 border-red-900/30 hover:border-red-500/50"
                            : "bg-zinc-800 hover:bg-zinc-700 text-green-400 border-green-900/30 hover:border-green-500/50"
                    )}
                >
                    {isConnected ? <PowerOff size={18} /> : <Power size={18} />}
                    {isConnected ? 'Desconectar' : 'Conectar'}
                </button>
            </div>

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden p-2">
                <div ref={terminalRef} className="h-full w-full" />
            </div>

            <div className="text-xs text-zinc-600 flex justify-between px-2">
                <span>Status: {status}</span>
                <span>Protocolo: WinRM (HTTP/HTTPS Negotiate)</span>
            </div>
        </div>
    );
}
