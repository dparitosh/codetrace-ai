import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const manifest = JSON.parse(readFileSync(new URL('./package.json', import.meta.url)))
const lock = JSON.parse(readFileSync(new URL('./package-lock.json', import.meta.url)))

test('npm root dependency specifications agree with the committed lockfile', () => {
  for (const section of ['dependencies', 'devDependencies']) {
    assert.deepEqual(lock.packages[''][section], manifest[section])
  }
})
test('web frontend does not install unused native and 3D animation renderers', () => {
  for (const name of ['react-native', 'react-spring', '@react-spring/native', '@react-three/fiber']) {
    assert.ok(!lock.packages['node_modules/' + name], name)
  }
})
