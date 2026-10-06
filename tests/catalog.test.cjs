const test = require("node:test");
const assert = require("node:assert/strict");

global.window = {};
require("../data/catalog.js");
const catalog = global.window.NEXT_DREAMS_DATA;
require("../data/pathway-engine.js");
const pathwayEngine = global.window.NEXT_DREAMS_PATHWAY_ENGINE;

test("catalog provides a complete four-stage cybersecurity learning sequence", () => {
  assert.equal(catalog.roadmap.length, 4);
  assert.deepEqual(catalog.roadmap.map((stage) => stage.year), [
    "Year 1 · Foundations",
    "Year 2 · Core skills",
    "Year 3 · Specialization",
    "Year 4 · Practice",
  ]);
  assert.ok(catalog.roadmap.every((stage) => stage.items.length >= 4));
});

test("catalog exposes multiple alternatives after Class 10", () => {
  const names = catalog.streams.map((stream) => stream.name);
  for (const pathway of ["MPC", "BiPC", "CEC / MEC", "HEC / Arts", "Diploma / Polytechnic", "ITI / Vocational"]) {
    assert.ok(names.includes(pathway), `missing ${pathway}`);
  }
});

test("career catalog entries contain linked course, role and skill tags", () => {
  assert.ok(catalog.careers.length >= 50);
  for (const career of catalog.careers) {
    assert.ok(career.course);
    assert.ok(career.role);
    assert.ok(career.tags.length > 0);
    assert.ok(career.category);
    assert.ok(career.minimumEducation);
    assert.ok(career.eligibleStreams.length > 0);
  }
});

test("every pathway-tree career points to a catalog record", () => {
  const names = new Set(catalog.careers.map((career) => career.name));
  const missing = catalog.educationTree.flatMap((stage) =>
    stage.branches.flatMap((branch) => branch.children.flatMap((child) => child.careers.filter((name) => !names.has(name))))
  );
  assert.deepEqual([...new Set(missing)], []);
  const listed = new Set(catalog.educationTree.flatMap((stage) =>
    stage.branches.flatMap((branch) => branch.children.flatMap((child) => child.careers))
  ));
  assert.deepEqual(catalog.careers.filter((career) => !listed.has(career.name)).map((career) => career.name), []);
  assert.deepEqual(catalog.educationTree.map((stage) => stage.title), ["After Class 10", "After Class 12 / Intermediate", "After Graduation"]);
});

test("career records identify broad fields, streams, pathways and cautious sources", () => {
  assert.ok(new Set(catalog.careers.map((career) => career.category)).size >= 15);
  assert.deepEqual(new Set(catalog.careers.flatMap((career) => career.eligibleStreams)), new Set(["MPC", "BiPC", "MEC", "CEC", "Humanities", "Arts", "Vocational", "Any"]));
  assert.ok(catalog.sources.some((source) => source.name.startsWith("NCERT")));
  assert.ok(catalog.sources.some((source) => source.name.startsWith("National Career Service")));
});

test("pathway graph has complete, uniquely identified routes across the listed stages", () => {
  const report = pathwayEngine.validate(catalog.pathways, catalog.pathStages);
  assert.equal(report.valid, true, report.issues.join("; "));
  assert.ok(report.routeCount >= 10);
  assert.equal(report.stageCount, 8);
});

test("pathway simulation filters by both starting point and interest", () => {
  const routes = pathwayEngine.select(catalog.pathways, { start: "Graduation", interest: "Creative work" });
  assert.deepEqual(routes.map((route) => route.id), ["postgraduate-creative"]);
  assert.deepEqual(pathwayEngine.select(catalog.pathways, { start: "Class 10", interest: "Health and science" }).map((route) => route.id), ["healthcare", "life-sciences"]);
  for (const start of ["Class 10", "Intermediate", "Graduation"]) {
    assert.ok(pathwayEngine.select(catalog.pathways, { start }).length > 0, `no routes from ${start}`);
  }
});

test("selecting a graph node returns only routes containing that exact node", () => {
  assert.deepEqual(pathwayEngine.through(catalog.pathways, "B.Tech").map((route) => route.id), ["cybersecurity", "software", "electronics", "inter-cybersecurity"]);
  assert.equal(pathwayEngine.through(catalog.pathways, "not a route node").length, 0);
});
