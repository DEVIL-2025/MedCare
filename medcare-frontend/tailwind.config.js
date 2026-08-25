/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 900: '#202522', 700: '#3A423E', 500: '#68716D', 300: '#A3ABA6', 100: '#E2E5E1' },
        cream: { DEFAULT: '#F7F7F4', 100: '#FFFFFF', 200: '#EFEFEA' },
        forest: { 900: '#063B2E', 800: '#0B4A3A', 700: '#0F5943', 600: '#177A5B', 500: '#1E9270', 100: '#DCEFE7' },
        gold: { 700: '#8A6A12', 600: '#D5A72C', 500: '#E0B94A', 100: '#FBF0D6' },
        brick: { 700: '#A83530', 600: '#D64545', 100: '#FBE2E1' },
        amber2: { 700: '#B4650E', 600: '#E58A24', 100: '#FCEBD7' },
        sage: { 700: '#1F6B4E', 600: '#2E8B68', 100: '#DCEFE7' },
        slate2: { 700: '#3A423E', 600: '#68716D', 100: '#E9EBE8' },
      },
      fontFamily: {
        heading: ['"Inter"', 'system-ui', 'sans-serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(32,37,34,0.04)',
      },
    },
  },
  plugins: [],
}