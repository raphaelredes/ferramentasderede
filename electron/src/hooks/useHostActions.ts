import { useState } from 'react';
import { Host } from '../types';
import { API_BASE } from '../config/api';

export function useHostActions() {
    const [isAuthenticating, setIsAuthenticating] = useState(false);
    const [authError, setAuthError] = useState<string | null>(null);
    const [isAddingHost, setIsAddingHost] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    const executeAction = async (
        host: Host,
        actionType: string,
        username: string,
        password: string,
        tempAuth: boolean = false,
        message: string = "",
        delay: number = 30
    ) => {
        setIsAuthenticating(true);
        setAuthError(null);

        try {
            let endpoint = '';
            let body: Record<string, unknown> = {};

            if (actionType === 'wol') {
                endpoint = '/network/wol';
                body = { mac: host.mac, ip: host.address };
            } else {

                endpoint = '/system/power';
                body = {
                    target_ip: host.address,
                    username: username,
                    password: password,
                    action: actionType,
                    message: message || "Manutenção Programada",
                    timeout: delay,
                    force: true
                };
            }

            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (tempAuth) {
                headers['X-Temp-Auth'] = 'true';
            }

            const response = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                if (response.status === 403 && errorData.detail === "TRUSTED_HOSTS_REQUIRED") {
                    throw new Error("TRUSTED_HOSTS_REQUIRED");
                }
                throw new Error(errorData.detail || 'Falha na autenticação ou execução do comando');
            }

            // Read the response body to check for streaming errors
            const text = await response.text();
            const lines = text.split('\n');

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);
                    if (data.status === 'error') {
                        if (data.code === 'TRUSTED_HOSTS_REQUIRED') {
                            throw new Error("TRUSTED_HOSTS_REQUIRED");
                        }
                        throw new Error(data.message || 'Erro desconhecido durante a execução');
                    }
                } catch (e) {
                    // If it's the error we just threw, rethrow it
                    if (e instanceof Error && (e.message === "TRUSTED_HOSTS_REQUIRED" || e.message !== "Unexpected end of JSON input")) {
                        if (e instanceof Error && e.message.startsWith("Unexpected token")) continue; // Ignore parse errors for partial lines
                        throw e;
                    }
                }
            }

            return true;
        } catch (error: unknown) {
            console.error('Erro na ação:', error);
            const errorMessage = error instanceof Error ? error.message : 'Ocorreu um erro desconhecido';
            setAuthError(errorMessage);
            throw error;
        } finally {
            setIsAuthenticating(false);
        }
    };

    const addHost = async (name: string, address: string, mac: string, ports: number[], group: string) => {
        setIsAddingHost(true);
        try {
            const response = await fetch(`${API_BASE}/hosts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name || undefined,
                    address,
                    mac: mac || undefined,
                    ports,
                    group: group || undefined
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Falha ao adicionar host');
            }

            return true;
        } catch (error) {
            console.error('Erro ao adicionar host:', error);
            throw error;
        } finally {
            setIsAddingHost(false);
        }
    };

    const deleteHost = async (address: string) => {
        setIsDeleting(true);
        try {
            const response = await fetch(`${API_BASE}/hosts/${address}`, {
                method: 'DELETE'
            });
            return response.ok;
        } catch (error) {
            console.error('Erro ao remover host:', error);
            return false;
        } finally {
            setIsDeleting(false);
        }
    };

    const updateHost = async (address: string, updates: Partial<Host> & { reset_stats?: boolean }) => {
        try {
            const response = await fetch(`${API_BASE}/hosts/${address}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
            return response.ok;
        } catch (error) {
            console.error('Erro ao atualizar host:', error);
            return false;
        }
    };

    const fetchSystemInfo = async (host: Host, username: string, password: string) => {
        try {
            const response = await fetch(`${API_BASE}/system/info`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_ip: host.address,
                    username,
                    password
                })
            });

            if (!response.ok) return null;
            return await response.json();
        } catch (error) {
            console.error('Error fetching system info:', error);
            return null;
        }
    };

    return {
        isAuthenticating,
        authError,
        isAddingHost,
        isDeleting,
        executeAction,
        addHost,
        deleteHost,
        updateHost,
        fetchSystemInfo
    };
}
