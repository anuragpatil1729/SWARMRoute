/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        paper: '#ffffff',
        panel: '#ffffff',
        panel2: '#f8fafc',
        rule: '#e2e8f0',
        ink: '#0f172a',
        muted: '#64748b',
        green: '#16a34a',
        greenLight: '#22c55e',
        red: '#dc2626',
        amber: '#d97706',
        navy: '#2563eb',
      },
      fontFamily: {
        serif: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', '"SF Mono"', '"Cascadia Code"', 'Menlo', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
