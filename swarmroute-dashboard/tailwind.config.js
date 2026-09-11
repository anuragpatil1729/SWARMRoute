/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0b0d12',
        panel: '#12151c',
        panel2: '#171b24',
        border: '#232834',
        accent: '#5eead4',
        accent2: '#818cf8',
        warn: '#fbbf24',
        danger: '#fb7185',
        muted: '#8b93a7',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
