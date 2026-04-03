/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'chat-bg': '#343541',
        'sidebar-bg': '#202123',
        'input-bg': '#40414f',
        'hover-bg': '#2a2b32',
        'border-color': '#4e4e5f',
      },
    },
  },
  plugins: [],
}
