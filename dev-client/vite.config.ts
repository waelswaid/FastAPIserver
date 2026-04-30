import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      // Polling is required when the source is bind-mounted from a Windows host
      // into a Linux container — chokidar's inotify watcher does not see the
      // host's file events otherwise.
      usePolling: true,
      interval: 300,
    },
  },
})
