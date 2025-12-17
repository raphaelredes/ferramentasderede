import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
        errorInfo: null
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error, errorInfo: null };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
        this.setState({ errorInfo });
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
                    <div className="bg-zinc-900 border border-red-500/20 rounded-xl p-8 max-w-lg w-full shadow-2xl">
                        <div className="flex items-center gap-3 text-red-500 mb-4">
                            <AlertTriangle size={32} />
                            <h1 className="text-2xl font-bold">Algo deu errado</h1>
                        </div>

                        <p className="text-zinc-400 mb-6">
                            Ocorreu um erro inesperado na aplicação. Tente recarregar a página.
                        </p>

                        {this.state.error && (
                            <div className="bg-black/50 rounded-lg p-4 mb-6 overflow-auto max-h-48 border border-zinc-800">
                                <p className="text-red-400 font-mono text-sm break-words">
                                    {this.state.error.toString()}
                                </p>
                                {this.state.errorInfo && (
                                    <pre className="text-zinc-500 text-xs mt-2 whitespace-pre-wrap">
                                        {this.state.errorInfo.componentStack}
                                    </pre>
                                )}
                            </div>
                        )}

                        <button
                            onClick={() => window.location.reload()}
                            className="w-full bg-red-600 hover:bg-red-500 text-white py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
                        >
                            <RefreshCw size={20} />
                            Recarregar Aplicação
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
