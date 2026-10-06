(function attachPathwayEngine(root) {
  function select(routes, filters = {}) {
    const { start, interest = "Not sure yet" } = filters;
    return routes.filter((route) =>
      (!start || route.start === start) &&
      (interest === "Not sure yet" || route.interest === interest)
    );
  }

  function through(routes, node) {
    return node ? routes.filter((route) => route.steps.includes(node)) : routes.slice();
  }

  function validate(routes, stages) {
    const issues = [];
    const ids = new Set();
    for (const route of routes) {
      if (!route.id || ids.has(route.id)) issues.push(`Missing or duplicate route id: ${route.id || "(empty)"}`);
      ids.add(route.id);
      if (!route.start || !route.interest) issues.push(`${route.id}: missing start or interest`);
      if (!Array.isArray(route.steps) || route.steps.length !== stages.length) {
        issues.push(`${route.id}: expected ${stages.length} stages`);
        continue;
      }
      if (route.steps.some((step) => typeof step !== "string" || !step.trim())) {
        issues.push(`${route.id}: contains an empty stage`);
      }
    }
    return { valid: issues.length === 0, routeCount: routes.length, stageCount: stages.length, issues };
  }

  root.NEXT_DREAMS_PATHWAY_ENGINE = Object.freeze({ select, through, validate });
})(typeof window === "undefined" ? globalThis : window);
