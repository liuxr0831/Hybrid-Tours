import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import svgr from "vite-plugin-svgr";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), svgr()],
  optimizeDeps: {
    exclude: ["three"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src_frontend"),
    },
  },
});
