// node --test: tools/fetch-artifacts/fetch.mjs against a fake artifact client.
import test from 'node:test'
import assert from 'node:assert/strict'
import {fetchArtifacts} from '../../tools/fetch-artifacts/fetch.mjs'

const core = {info() {}}
class ArtifactNotFoundError extends Error {
  constructor() { super('Artifact not found'); this.name = 'ArtifactNotFoundError' }
}

function fakeClient({present, flaky = {}, broken = new Set()}) {
  const calls = {get: 0, download: [], inFlight: 0, peak: 0}
  return {
    calls,
    async getArtifact(name) {
      calls.get++
      if (broken.has(name)) throw new Error('secondary rate limit')
      if (flaky[name] > 0) { flaky[name]--; throw new Error('502') }
      if (!present.includes(name)) throw new ArtifactNotFoundError()
      return {artifact: {id: present.indexOf(name) + 1, name, size: 10, digest: `sha256:${name}`}}
    },
    async downloadArtifact(id, options) {
      calls.inFlight++
      calls.peak = Math.max(calls.peak, calls.inFlight)
      await new Promise(resolve => setTimeout(resolve, 2))
      calls.inFlight--
      calls.download.push([id, options.expectedHash, options.path])
      return {downloadPath: options.path}
    }
  }
}

test('downloads every present name and reports the missing ones', async () => {
  const client = fakeClient({present: ['rpm-s0-a', 'rpm-s1-b']})
  const result = await fetchArtifacts({
    names: ['rpm-s1-b', 'rpm-s0-a', 'rpm-s0-gone', 'rpm-s0-a'], path: '/x', core, client, delayMs: 0
  })
  assert.deepEqual(result, {found: ['rpm-s0-a', 'rpm-s1-b'], missing: ['rpm-s0-gone']})
  assert.deepEqual(client.calls.download.map(([, hash]) => hash).sort(),
                   ['sha256:rpm-s0-a', 'sha256:rpm-s1-b'])
})

test('a transient lookup error is retried', async () => {
  const client = fakeClient({present: ['a'], flaky: {a: 2}})
  const result = await fetchArtifacts({names: ['a'], path: '/x', core, client, delayMs: 0})
  assert.deepEqual(result.found, ['a'])
})

test('an error that persists fails the whole fetch instead of a short download', async () => {
  const client = fakeClient({present: ['a', 'b'], broken: new Set(['b'])})
  await assert.rejects(
    fetchArtifacts({names: ['a', 'b'], path: '/x', core, client, delayMs: 0}),
    /looking up b: secondary rate limit/
  )
})

test('no more than `concurrency` downloads run at once', async () => {
  const names = Array.from({length: 40}, (_, i) => `n${i}`)
  const client = fakeClient({present: names})
  await fetchArtifacts({names, path: '/x', core, client, concurrency: 3, delayMs: 0})
  assert.equal(client.calls.download.length, 40)
  assert.ok(client.calls.peak <= 3, `peak ${client.calls.peak}`)
})
