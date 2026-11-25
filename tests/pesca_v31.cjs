const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const questions = JSON.parse(fs.readFileSync(path.join(root, 'questions.json'), 'utf8'));
const state = {questions, selected: new Set()};
const categories = [...new Set(questions.map(q => q.category_id))];
const byId = new Map(questions.map(q => [q.id, q.category_id]));
const field = {reportValidity: () => true, focus() {}};
const ctx = vm.createContext({state, $: () => field, notice() {}});
vm.runInContext(fs.readFileSync(path.join(root, 'static/studio.js'), 'utf8'), ctx);
ctx.refreshStudio = () => {};

function draw(count, allowed) {
  state.drawCategories = new Set(allowed);
  field.valueAsNumber = count;
  ctx.balancedDraw();
  const totals = {};
  for (const id of state.selected) {
    assert.ok(byId.has(id), 'La selezione deve contenere ID validi per la lobby');
    const category = byId.get(id);
    totals[category] = (totals[category] || 0) + 1;
  }
  return totals;
}

assert.equal(categories.length, 10);
for (let run = 0; run < 20; run++) {
  for (const count of [1, 3, 9, 10, 18, questions.length]) {
    const totals = Object.values(draw(count, categories));
    assert.equal(state.selected.size, count);
    assert.equal(totals.length, Math.min(count, categories.length));
    if (count <= 18) assert.ok(Math.max(...totals) - Math.min(...totals) <= 1);
  }
  assert.deepEqual(draw(48, ['PRI', 'SSL']), {PRI: 20, SSL: 28});
  const before = [...state.selected];
  draw(71, ['PRI', 'SSL']);
  assert.deepEqual([...state.selected], before);
  draw(10, []);
  assert.deepEqual([...state.selected], before);
}
console.log('OK: pesca bilanciata, categorie escluse, esaurimento, ID e conservazione del mazzo');
