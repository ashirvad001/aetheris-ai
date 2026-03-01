import { useState, useEffect } from 'react'
import { Wifi, WifiOff } from 'lucide-react'

const BASE_URL = import.meta.env.VITE_API_URL || 'https://aetheris-backend.onrender.com'
const POLL_INTERVAL_MS = 30_000

/**
 * BackendStatus
 * A small badge that polls GET /health every 30 s and displays API status.
 * Shows tooltip on hover with the backend URL.
 */
export default function BackendStatus() {
    const [online, setOnline] = useState(null)   // null = checking
    const [tooltip, setTooltip] = useState(false)
    const [checking, setChecking] = useState(false)

    useEffect(() => {
        async function check() {
            setChecking(true)
            try {
                const res = await fetch(`${BASE_URL}/health`, { signal: AbortSignal.timeout(5000) })
                setOnline(res.ok)
            } catch {
                setOnline(false)
            } finally {
                setChecking(false)
            }
        }

        check()
        const id = setInterval(check, POLL_INTERVAL_MS)
        return () => clearInterval(id)
    }, [])

    return (
        <div
            className="relative hidden sm:block"
            onMouseEnter={() => setTooltip(true)}
            onMouseLeave={() => setTooltip(false)}
        >
            <div
                className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-full border transition-all
          ${online === null
                        ? 'bg-gray-800 border-gray-700 text-gray-500'           // checking
                        : online
                            ? 'bg-green-900/30 border-green-800/40 text-green-400'  // online
                            : 'bg-red-900/30 border-red-800/40 text-red-400'        // offline
                    }`}
            >
                {/* Dot */}
                {online === null ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-pulse" />
                ) : online ? (
                    <>
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-60" />
                            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-green-500" />
                        </span>
                    </>
                ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                )}

                {/* Label */}
                {checking && online === null
                    ? 'Checking…'
                    : online
                        ? 'API Online'
                        : 'API Offline'}
            </div>

            {/* Tooltip */}
            {tooltip && (
                <div className="absolute top-full mt-2 right-0 z-50 whitespace-nowrap
          bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 shadow-xl">
                    <p className="text-[10px] text-gray-400 font-mono">{BASE_URL}</p>
                    <p className="text-[10px] text-gray-500 mt-0.5">
                        {online ? 'FastAPI backend responding' : 'No response — start uvicorn'}
                    </p>
                    {/* Arrow */}
                    <div className="absolute -top-1.5 right-4 w-3 h-3 bg-gray-800 border-l border-t border-gray-700 rotate-45" />
                </div>
            )}
        </div>
    )
}
