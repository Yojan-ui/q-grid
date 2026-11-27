import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'
import { themeStyle } from './src/lib/tokens.ts'

// Sets <html data-theme> before first paint (no flash): saved choice (localStorage, guarded), a ?theme= override
// for screenshots, else the OS preference. The CSS variables for both themes are generated from src/lib/theme.ts.
const NO_FLASH = `(function(){var m='system';try{m=localStorage.getItem('qgrid-theme')||'system'}catch(e){}
var q=new URLSearchParams(location.search).get('theme');if(q==='light'||q==='dark'||q==='system')m=q;
var d=m==='dark'||(m==='system'&&window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches);
var h=document.documentElement;h.setAttribute('data-theme',d?'dark':'light');h.setAttribute('data-mode',m);
if(new URLSearchParams(location.search).has('present'))h.setAttribute('data-present','')})()`

function themeTokens(): Plugin {
  return {
    name: 'qgrid-theme-tokens',
    transformIndexHtml: () => [
      { tag: 'style', attrs: { id: 'theme-tokens' }, children: themeStyle(), injectTo: 'head-prepend' },
      { tag: 'script', children: NO_FLASH, injectTo: 'head-prepend' },
    ],
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), themeTokens()],
  build: {
    rolldownOptions: {
      output: {
        // the 3D stack is the heavy part: its own chunk, loaded after the panel is on screen
        advancedChunks: { groups: [
          { name: 'three', test: /node_modules[\\/](three|@react-three|three-stdlib|troika|camera-controls|maath|meshline|stats-gl|its-fine|zustand|suspend-react)/ },
          { name: 'charts', test: /node_modules[\\/](recharts|d3-|victory-vendor|decimal\.js|es-toolkit|immer|reselect|redux|@reduxjs)/ },
        ] },
      },
    },
  },
})
