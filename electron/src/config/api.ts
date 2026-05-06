// Centralized API endpoint config.
// Override at build time via VITE_API_HOST / VITE_API_PORT.
const HOST = (import.meta.env.VITE_API_HOST as string | undefined) ?? '127.0.0.1';
const PORT = (import.meta.env.VITE_API_PORT as string | undefined) ?? '8000';

export const API_BASE = `http://${HOST}:${PORT}`;
export const WS_BASE = `ws://${HOST}:${PORT}`;
