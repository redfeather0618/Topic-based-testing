import assert from 'node:assert/strict';
import test from 'node:test';
import { createAnnotationsClient } from '../api/annotations-client.mjs';

test('dashboard pins one dataset version and forwards bearer token', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  const version = 'a'.repeat(64);
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    const path = new URL(url).pathname;
    const data = path.endsWith('/datasets/current')
      ? { dataset_version: version }
      : { dataset_version: new URL(url).searchParams.get('dataset_version') };
    return new Response(JSON.stringify(data), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    });
  };
  try {
    const api = createAnnotationsClient('http://127.0.0.1:8000/', 'test-token');
    const result = await api.dashboard({ cohort: 'reviewed' });
    assert.equal(calls.length, 4);
    assert.equal(result.filters.dataset_version, version);
    assert.ok(new URL(calls[0].url).pathname.endsWith("/datasets/current"));
    for (const call of calls.slice(1)) {
      const url = new URL(call.url);
      assert.equal(url.searchParams.get('dataset_version'), version);
      assert.equal(url.searchParams.get('cohort'), 'reviewed');
      assert.equal(call.options.headers.Authorization, 'Bearer test-token');
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('client returns structured HTTP errors', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    error: { code: 'unauthorized', message: '權杖無效', details: {} },
  }), { status: 401, headers: { 'Content-Type': 'application/json' } });
  try {
    const api = createAnnotationsClient('http://127.0.0.1:8000', 'bad-token');
    await assert.rejects(api.overview({ cohort: 'annotated' }), error =>
      error.status === 401 && error.code === 'unauthorized' && error.message === '權杖無效'
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
