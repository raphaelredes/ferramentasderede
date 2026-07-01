import { useRef, useState, useCallback, useEffect } from 'react';
import { API_BASE } from '../../config/api';

/**
 * Small reusable hook for the self-contained streaming tool panels (TCP ping,
 * PMTU, PTR sweep). Handles: POST + ReadableStream reader, an output-line
 * buffer with a cap, an AbortController, a race-free re-entrancy guard, the
 * /tools/stop call, and cleanup on unmount.
 *
 * `onLine` (optional) lets a caller parse each decoded chunk (e.g. NDJSON);
 * when omitted, raw text chunks are appended to `output`.
 */
const OUTPUT_CAP = 2000;
const TRIM_MARKER = '[... linhas mais antigas removidas — buffer limitado a 2000 ...]';

export function useStreamingTool(endpoint: string, taskId: string) {
    const [output, setOutput] = useState<string[]>([]);
    const [isRunning, setIsRunning] = useState(false);
    const abortRef = useRef<AbortController | null>(null);
    const runningRef = useRef(false);

    const trim = (arr: string[]) =>
        arr.length > OUTPUT_CAP ? [TRIM_MARKER, ...arr.slice(-(OUTPUT_CAP - 1))] : arr;

    const clear = useCallback(() => {
        if (!runningRef.current) setOutput([]);
    }, []);

    const stop = useCallback(() => {
        if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
        runningRef.current = false;
        setIsRunning(false);
        fetch(`${API_BASE}/tools/stop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: taskId }),
        }).catch(() => { /* best effort */ });
    }, [taskId]);

    /**
     * Start a run. `body` is the JSON payload (task_id is merged in).
     * `onChunk` (optional) receives each decoded text chunk for custom parsing;
     * return false from it to suppress the default append.
     */
    const run = useCallback(async (
        body: Record<string, unknown>,
        onChunk?: (text: string) => void,
    ) => {
        // Race-free guard: a live run always holds a non-null controller.
        if (abortRef.current) return;
        abortRef.current = new AbortController();
        runningRef.current = true;
        setIsRunning(true);
        setOutput([]);

        try {
            const res = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...body, task_id: taskId }),
                signal: abortRef.current.signal,
            });
            if (!res.body) throw new Error('Sem corpo de resposta.');
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value, { stream: true });
                if (onChunk) {
                    onChunk(text);
                } else {
                    setOutput(prev => trim([...prev, text]));
                }
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                setOutput(prev => trim([...prev, `\nErro: ${e.message}`]));
            }
        } finally {
            runningRef.current = false;
            setIsRunning(false);
            abortRef.current = null;
        }
    }, [endpoint, taskId]);

    // Abort on unmount so a late .then can't setState on a dead component.
    useEffect(() => () => { if (abortRef.current) abortRef.current.abort(); }, []);

    return { output, setOutput, isRunning, run, stop, clear };
}
