interface SparklineProps {
    history: (number | null)[];
    width?: number;
    height?: number;
    className?: string;
}

/**
 * Componente SVG leve para renderizar tendências de latência em linha (Sparkline).
 * Representa perdas de pacote como pontos vermelhos e colore a linha por nível de latência.
 */
export function Sparkline({ history, width = 110, height = 24, className }: SparklineProps) {
    if (!history || history.length === 0) {
        return <span className="text-zinc-600 text-[11px]">—</span>;
    }

    const validValues = history.filter((v): v is number => v !== null && typeof v === 'number');
    const minVal = validValues.length > 0 ? Math.min(...validValues) : 0;
    const maxVal = validValues.length > 0 ? Math.max(...validValues) : 100;
    const range = maxVal - minVal || 1;

    const padX = 4;
    const padY = 4;
    const usableW = width - padX * 2;
    const usableH = height - padY * 2;

    const step = history.length > 1 ? usableW / (history.length - 1) : usableW;

    // Constrói pontos da linha e lista de perdas (nulls)
    const points: string[] = [];
    const lossPoints: { x: number; y: number }[] = [];

    history.forEach((val, i) => {
        const x = padX + i * step;
        if (val === null) {
            lossPoints.push({ x, y: height - padY });
        } else {
            // y invertido no SVG: maior valor fica no topo (y menor)
            const normalized = (val - minVal) / range;
            const y = padY + (1 - normalized) * usableH;
            points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
        }
    });

    // Cor da linha baseada na média
    const avg = validValues.length > 0 ? validValues.reduce((a, b) => a + b, 0) / validValues.length : 0;
    const strokeColor = avg < 50 ? '#34d399' : avg < 150 ? '#fbbf24' : '#f87171'; // emerald, amber, rose

    const lastVal = validValues.length > 0 ? validValues[validValues.length - 1] : null;

    return (
        <div
            className={`inline-flex items-center gap-1.5 ${className || ''}`}
            title={`Tendência de RTT: Último ${lastVal !== null ? `${lastVal}ms` : 'Perda'} (Min: ${minVal}ms, Max: ${maxVal}ms)`}
        >
            <svg width={width} height={height} className="overflow-visible">
                {/* Linha guia de base */}
                <line
                    x1={padX}
                    y1={height - padY}
                    x2={width - padX}
                    y2={height - padY}
                    stroke="#27272a"
                    strokeWidth="1"
                    strokeDasharray="2,2"
                />

                {/* Linha de latência */}
                {points.length > 1 && (
                    <polyline
                        fill="none"
                        stroke={strokeColor}
                        strokeWidth="1.6"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        points={points.join(' ')}
                    />
                )}

                {/* Ponto único se só tiver 1 amostra válida */}
                {points.length === 1 && (
                    <circle
                        cx={points[0].split(',')[0]}
                        cy={points[0].split(',')[1]}
                        r="2.5"
                        fill={strokeColor}
                    />
                )}

                {/* Marcadores vermelhos para pacotes perdidos (timeout) */}
                {lossPoints.map((pt, idx) => (
                    <g key={idx}>
                        <circle cx={pt.x} cy={pt.y} r="2.2" fill="#ef4444" />
                        <line
                            x1={pt.x - 2}
                            y1={pt.y - 2}
                            x2={pt.x + 2}
                            y2={pt.y + 2}
                            stroke="#ffffff"
                            strokeWidth="0.8"
                        />
                    </g>
                ))}
            </svg>
        </div>
    );
}
