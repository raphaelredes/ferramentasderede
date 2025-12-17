export function HostListSkeleton() {
    // Generate an array of 12 items to simulate a grid
    const skeletons = Array.from({ length: 12 });

    return (
        <div className="flex flex-wrap gap-4">
            {skeletons.map((_, i) => (
                <div
                    key={i}
                    className="w-full md:w-[calc(50%-0.5rem)] lg:w-[calc(33.333%-0.667rem)] xl:w-[calc(25%-0.75rem)] h-[180px] bg-zinc-900/50 border border-zinc-800/50 rounded-xl relative overflow-hidden"
                >
                    {/* Shimmer Effect */}
                    <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent" />

                    <div className="p-4 space-y-4">
                        {/* Header: Status + Name */}
                        <div className="flex items-start justify-between">
                            <div className="flex items-center gap-3">
                                {/* Status Dot */}
                                <div className="w-3 h-3 rounded-full bg-zinc-800 animate-pulse" />
                                <div className="space-y-2">
                                    {/* Name */}
                                    <div className="h-4 w-32 bg-zinc-800 rounded animate-pulse" />
                                    {/* IP */}
                                    <div className="h-3 w-24 bg-zinc-800/60 rounded animate-pulse" />
                                </div>
                            </div>
                            {/* Menu Button */}
                            <div className="w-8 h-8 rounded bg-zinc-800/40 animate-pulse" />
                        </div>

                        {/* Stats Grid */}
                        <div className="grid grid-cols-2 gap-2 mt-4">
                            <div className="h-16 rounded bg-zinc-800/20 animate-pulse" />
                            <div className="h-16 rounded bg-zinc-800/20 animate-pulse" />
                        </div>

                        {/* Footer Actions */}
                        <div className="flex justify-between items-center pt-2 border-t border-zinc-800/50">
                            <div className="h-3 w-16 bg-zinc-800/40 rounded animate-pulse" />
                            <div className="flex gap-2">
                                <div className="w-6 h-6 rounded bg-zinc-800/40 animate-pulse" />
                                <div className="w-6 h-6 rounded bg-zinc-800/40 animate-pulse" />
                            </div>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}
