// Download this run's artifacts by exact name through the Actions artifact
// service, the same internal API actions/download-artifact uses without a
// token.
//
// Why not download-artifact: without a token it lists the run's artifacts
// before applying `pattern`, and that listing stops at 1000 (oldest first), so
// a full rebuild's newest waves were never downloaded (#970). With a token it
// lists over REST, but then starts every download at once over REST: run
// 44386298520 hit GitHub's secondary rate limit in publish and exhausted the
// installation's REST budget in every wave-1 build (#1204 follow-up). A lookup
// by exact name is filtered server side, so it has no 1000 cap, and it spends
// no REST budget.
//
// Runs inside actions/github-script, the only place a step sees
// ACTIONS_RUNTIME_TOKEN; it never leaves that step:
//
//   const {fetchArtifacts} = await import(`${process.env.GITHUB_WORKSPACE}/tools/fetch-artifacts/fetch.mjs`)
//   await fetchArtifacts({names, path, core})
//
// A name with no artifact is a build that did not upload one (it failed); it
// is returned in `missing`, and the caller decides. Any other error is retried
// and then thrown, so a short download can never pass for a complete one.

// Loaded only when no client is passed, so the unit tests need no
// node_modules (tests/test_fetch_artifacts.py).
async function defaultClient() {
  const {DefaultArtifactClient} = await import('@actions/artifact')
  return new DefaultArtifactClient()
}

// @actions/artifact's ArtifactNotFoundError, matched by name for the same reason.
const notFound = error => error?.name === 'ArtifactNotFoundError'

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

export async function withRetries(attempt, {tries = 4, delayMs = 2000, log = () => {}} = {}) {
  for (let n = 1; ; n++) {
    try {
      return await attempt()
    } catch (error) {
      if (notFound(error) || n >= tries) throw error
      log(`attempt ${n} failed (${error.message}); retrying in ${delayMs * n} ms`)
      await sleep(delayMs * n)
    }
  }
}

export async function fetchArtifacts({
  names,
  path,
  core,
  client,
  concurrency = 8,
  delayMs = 2000
}) {
  client = client ?? (await defaultClient())
  const queue = [...new Set(names)]
  const found = []
  const missing = []
  let bytes = 0
  const log = message => core.info(message)

  async function one(name) {
    let artifact
    try {
      ;({artifact} = await withRetries(() => client.getArtifact(name), {delayMs, log}))
    } catch (error) {
      if (notFound(error)) {
        missing.push(name)
        return
      }
      throw new Error(`looking up ${name}: ${error.message}`)
    }
    await withRetries(
      () => client.downloadArtifact(artifact.id, {path, expectedHash: artifact.digest}),
      {delayMs, log}
    ).catch(error => {
      throw new Error(`downloading ${name} (${artifact.id}): ${error.message}`)
    })
    found.push(name)
    bytes += artifact.size || 0
  }

  async function worker() {
    for (let name = queue.shift(); name !== undefined; name = queue.shift()) {
      await one(name)
    }
  }
  await Promise.all(Array.from({length: Math.max(1, concurrency)}, worker))

  found.sort()
  missing.sort()
  core.info(`downloaded ${found.length} artifact(s), ${bytes} bytes, into ${path}`)
  if (missing.length) {
    core.info(`no artifact (did not build): ${missing.join(', ')}`)
  }
  return {found, missing}
}
