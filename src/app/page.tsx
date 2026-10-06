"use client";

import { useEffect } from "react";

export default function HomePage() {
  useEffect(() => {
    let active = true;
    const scripts: HTMLScriptElement[] = [];
    const sources = ["/demo/data/catalog.js", "/demo/data/pathway-engine.js", "/demo/app.js"];
    const loadScript = (index: number) => {
      if (!active || index >= sources.length) return;
      const script = document.createElement("script");
      script.src = sources[index];
      script.onload = () => loadScript(index + 1);
      script.onerror = () => {
        const app = document.querySelector<HTMLDivElement>("#app");
        if (app) app.textContent = `Unable to load ${sources[index]}. Refresh to retry.`;
      };
      scripts.push(script);
      document.body.append(script);
    };
    loadScript(0);
    return () => {
      active = false;
      scripts.forEach((script) => script.remove());
      document.querySelector("#app")?.replaceChildren();
    };
  }, []);

  return <div id="app" data-api-base={process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001"} />;
}
