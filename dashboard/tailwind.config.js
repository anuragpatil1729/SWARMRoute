/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        paper: '#f1f1ea',
        panel: '#fbfbf8',
        panel2: '#e9e9e0',
        rule: '#c9c9bc',
        ink: '#181a16',
        muted: '#61635a',
        green: '#2e6b34',
        greenLight: '#7a9c5e',
        red: '#a13a2e',
        amber: '#8a6d1f',
        navy: '#3d5566',
      },
      fontFamily: {
        serif: ['Georgia', 'Cambria', '"Times New Roman"', 'Times', 'serif'],
        sans: ['-apple-system', '"Segoe UI"', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', '"SF Mono"', '"Cascadia Code"', 'Menlo', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
