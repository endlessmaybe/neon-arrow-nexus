import assert from "node:assert/strict";
import {
  LEVEL_CONFIGS,
  countInitiallyBlocked,
  createLevel,
  isSolutionValid,
  traceArrow,
} from "../src/engine.js";

for (let index = 0; index < LEVEL_CONFIGS.length; index += 1) {
  const first = createLevel(index);
  const second = createLevel(index);
  assert.deepEqual(first, second, `Level ${index + 1} should be deterministic.`);
  assert.ok(first.arrows.length >= Math.floor(LEVEL_CONFIGS[index].target * 0.75));
  assert.equal(first.solutionOrder.length, first.arrows.length);
  assert.equal(isSolutionValid(first), true, `Level ${index + 1} must have a verified solution.`);
  assert.ok(countInitiallyBlocked(first) > 0, `Level ${index + 1} needs blocked arrows.`);

  const firstSolutionId = first.solutionOrder[0];
  const firstArrow = first.arrows.find((arrow) => arrow.id === firstSolutionId);
  assert.equal(traceArrow(firstArrow, first.arrows, first.config.gates).clear, true);
}

console.log(`engine.test: ${LEVEL_CONFIGS.length} deterministic, solvable levels verified.`);
