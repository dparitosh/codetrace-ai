import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const manifest = JSON.parse(readFileSync(new URL('./package.json', import.meta.url)))
const lock = JSON.parse(readFileSync(new URL('./package-lock.json', import.meta.url)))

test('npm root dependency specifications agree with the committed lockfile', () => {
  for (const section of ['dependencies', 'devDependencies']) {
    assert.deepEqual(lock.packages[''][section], manifest[section])
  }
  assert.deepEqual(lock.packages[''].engines, manifest.engines)
})
test('web frontend does not install unused native and 3D animation renderers', () => {
  for (const name of ['react-native', 'react-spring', '@react-spring/native', '@react-three/fiber']) {
    assert.ok(!lock.packages['node_modules/' + name], name)
  }
})

test('graph renderer installs D3 modules without Cytoscape', () => {
  assert.ok(!manifest.dependencies.cytoscape)
  assert.ok(!lock.packages['node_modules/cytoscape'])
  for (const name of ['d3-force', 'd3-selection', 'd3-drag', 'd3-zoom']) {
    assert.ok(manifest.dependencies[name], name)
    assert.ok(lock.packages['node_modules/' + name], name)
  }
})
