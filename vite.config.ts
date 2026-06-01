import {defineConfig} from 'vite';
import vue from '@vitejs/plugin-vue';

// base: './' keeps asset paths relative so the built dist/ works when served
// from a local file path or any sub-path on the Pi's kiosk Chromium.
export default defineConfig({
  plugins: [vue()],
  base: './',
  server: {host: true, port: 5174},
});
