/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            animation: {
                'grid-flow': 'grid-flow 20s linear infinite',
                'scanline': 'scanline 8s linear infinite',
                'typing': 'typing 0.5s steps(40, end)',
                'blink': 'blink 1s step-end infinite',
            },
            keyframes: {
                'grid-flow': {
                    '0%': { transform: 'translateY(0)' },
                    '100%': { transform: 'translateY(40px)' },
                },
                'scanline': {
                    '0%': { transform: 'translateY(-100%)' },
                    '100%': { transform: 'translateY(100%)' },
                },
                'typing': {
                    'from': { width: '0' },
                    'to': { width: '100%' },
                },
                'blink': {
                    '0%, 100%': { opacity: '1' },
                    '50%': { opacity: '0' },
                },
            },
        },
    },
    plugins: [],
}
