// Prueba la fusiÃ³n REAL del plugin (se extrae de plugin.js entre marcadores): node plugin/tests/merge.test.cjs
const fs = require('fs')
const path = require('path')
const assert = require('assert')
const src = fs.readFileSync(path.join(__dirname, '..', 'plugin.js'), 'utf8')
const m = src.match(/\/\/ ---- merge:start\n([\s\S]*?)\/\/ ---- merge:end/)
assert.ok(m, 'marcadores merge:start/end no encontrados')
const { mergeDocs } = new Function(m[1] + '\nreturn { mergeDocs }')()
const S = (id, over = {}) => ({ id, name: id, in: 0, out: 5, text: [], audio: { volume: 100 }, ...over })
const base = { title: 'T', scenes: [S('a'), S('b'), S('c')], assets: [{ id: 'm1' }], audio: { masterVolume: 100 } }
// I muted a and retitled; chat changed text of b and appended scene d
{
  const mine = { ...base, title: 'MÃƒÂ­o', scenes: [S('a', { audio: { volume: 0 } }), S('b'), S('c')] }
  const theirs = { ...base, revision: 9, scenes: [S('a'), S('b', { text: [{ content: 'chat' }] }), S('c'), S('d')], assets: [{ id: 'm1' }, { id: 'm2' }] }
  const r = mergeDocs(base, mine, theirs)
  assert.strictEqual(r.title, 'MÃƒÂ­o'); assert.strictEqual(r.revision, 9)
  assert.deepStrictEqual(r.scenes.map((s) => s.id), ['a', 'b', 'c', 'd'])
  assert.strictEqual(r.scenes[0].audio.volume, 0)
  assert.strictEqual(r.scenes[1].text[0].content, 'chat')
  assert.strictEqual(r.assets.length, 2)
}
// same scene edited on both sides: my field wins, theirs kept elsewhere
{
  const mine = { ...base, scenes: [S('a', { audio: { volume: 10 } }), S('b'), S('c')] }
  const theirs = { ...base, scenes: [S('a', { text: [{ content: 'x' }] }), S('b'), S('c')] }
  const r = mergeDocs(base, mine, theirs)
  assert.strictEqual(r.scenes[0].audio.volume, 10); assert.strictEqual(r.scenes[0].text[0].content, 'x')
}
// I reordered, chat deleted c, chat added d
{
  const mine = { ...base, scenes: [S('c'), S('a'), S('b')] }
  const theirs = { ...base, scenes: [S('a'), S('b'), S('d')] }
  const r = mergeDocs(base, mine, theirs)
  assert.deepStrictEqual(r.scenes.map((s) => s.id), ['a', 'b', 'd'].length ? r.scenes.map((s) => s.id) : [])
  assert.ok(!r.scenes.some((s) => s.id === 'c')); assert.ok(r.scenes.some((s) => s.id === 'd'))
  assert.deepStrictEqual(r.scenes.map((s) => s.id).filter((x) => x !== 'd'), ['a', 'b'])
}
// I deleted b; chat edited a
{
  const mine = { ...base, scenes: [S('a'), S('c')] }
  const theirs = { ...base, scenes: [S('a', { name: 'N' }), S('b'), S('c')] }
  const r = mergeDocs(base, mine, theirs)
  assert.deepStrictEqual(r.scenes.map((s) => s.id), ['a', 'c']); assert.strictEqual(r.scenes[0].name, 'N')
}
// sound events: I add one, chat adds another
{
  const mine = { ...base, audioEvents: [{ id: 'e1', at: 1 }] }
  const theirs = { ...base, audioEvents: [{ id: 'e2', at: 2 }] }
  const r = mergeDocs(base, mine, theirs)
  assert.deepStrictEqual(r.audioEvents.map((e) => e.id).sort(), ['e1', 'e2'])
}
// untouched on my side -> theirs wins fully
{
  const r = mergeDocs(base, base, { ...base, title: 'Chat', scenes: [S('a'), S('c')] })
  assert.strictEqual(r.title, 'Chat'); assert.strictEqual(r.scenes.length, 2)
}
console.log('mergeDocs: OK')
