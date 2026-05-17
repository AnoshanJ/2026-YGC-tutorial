import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The AM gateway doesn't send CORS headers, so a direct fetch from
// localhost:5173 -> gateway is blocked by the browser. We work around it by
// proxying chat calls through the Vite dev server: the browser hits
// /proxy/agent/* (same origin), and Vite forwards to the configured agent
// URL with all headers intact.
//
// The agent URL is read from public/config.js (the same file the React app
// reads at runtime), so there's a single source of truth. Restart the dev
// server after editing public/config.js so the new target is picked up.
function readAgentUrl(): string | null {
  const cfgPath = path.resolve(__dirname, "public/config.js");
  if (!fs.existsSync(cfgPath)) return null;
  const txt = fs.readFileSync(cfgPath, "utf8");
  const m = txt.match(/url:\s*["']([^"']+)["']/);
  return m ? m[1] : null;
}

function buildProxy() {
  const raw = readAgentUrl();
  if (!raw) {
    // No config yet — leave the proxy unset. The app will surface a friendly
    // "agent not reachable" banner on load.
    return undefined;
  }
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    console.warn(`[vite] could not parse agent URL "${raw}" from public/config.js`);
    return undefined;
  }
  const target = u.origin;
  const agentPath = u.pathname.replace(/\/+$/, "");
  console.log(`[vite] proxying /proxy/agent/* -> ${target}${agentPath}/*`);
  return {
    "/proxy/agent": {
      target,
      changeOrigin: true,
      secure: false,
      rewrite: (p: string) => p.replace(/^\/proxy\/agent/, agentPath),
    },
  };
}

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: buildProxy(),
  },
});
