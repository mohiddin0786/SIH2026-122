/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        cream: {
          50:  '#FFFDF7',
          100: '#FBF8EE',
          200: '#F5F1E7',
          300: '#EDE6D4',
          400: '#E0D5BC',
          500: '#CEBD9C',
        },
        teal: {
          50:  'rgba(22,121,110,0.05)',
          100: 'rgba(22,121,110,0.10)',
          200: 'rgba(22,121,110,0.18)',
          300: 'rgba(22,121,110,0.30)',
          400: '#16796E',
          500: '#0F5E54',
          600: '#0A4840',
        },
        gold: {
          50:  'rgba(184,137,50,0.05)',
          100: 'rgba(184,137,50,0.10)',
          200: 'rgba(184,137,50,0.18)',
          300: 'rgba(184,137,50,0.30)',
          400: '#B88932',
          500: '#9A7224',
        },
        charcoal: {
          50:  '#F5F3EF',
          100: '#E8E3DC',
          200: '#C8C0B4',
          300: '#8A8278',
          400: '#514B43',
          500: '#3A3630',
          600: '#1C1A18',
          700: '#0F0E0C',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        cream:       '0 6px 28px rgba(20,16,8,0.09), inset 0 1px 0 rgba(255,255,255,0.50)',
        'cream-sm':  '0 3px 14px rgba(20,16,8,0.07), inset 0 1px 0 rgba(255,255,255,0.42)',
        'cream-lg':  '0 12px 40px rgba(20,16,8,0.12), inset 0 1px 0 rgba(255,255,255,0.58)',
        'teal-ring': '0 0 0 3px rgba(22,121,110,0.10)',
        'gold-ring': '0 0 0 3px rgba(184,137,50,0.10)',
      },
    },
  },
  plugins: [],
};
