const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {EventEmitter} = require('node:events');
const {setImmediate: nextTurn} = require('node:timers/promises');
const {loadToken, validateConfig, startBot, StartupError} = require('../startup');

function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return {promise, resolve, reject};
}

test('environment token takes precedence and is trimmed without reading a file', () => {
  assert.equal(loadToken({env: {TOKEN: ' token-value '}, readAuth: () => {
    throw new Error('Must not read local credentials');
  }}), 'token-value');
});

test('local token file remains supported when TOKEN is absent', () => {
  assert.equal(loadToken({env: {}, readAuth: () => ({token: 'local-token'})}), 'local-token');
});

for (const token of ['', '   ', '{"token":"secret"}', 'token with spaces']) {
  test(`rejects invalid environment token (${JSON.stringify(token).replace('secret', 'redacted')})`, () => {
    assert.throws(() => loadToken({env: {TOKEN: token}, readAuth: () => ({token: 'fallback'})}),
      /raw Discord bot token/);
  });
}

test('credential-file failures do not disclose file contents', () => {
  assert.throws(() => loadToken({env: {}, readAuth: () => {
    throw new Error('sensitive-token');
  }}), error => !error.message.includes('sensitive-token') && error.message.includes('TOKEN'));
});

test('validates MongoDB URL and existing encryption material before startup', () => {
  const config = {dbUrl: 'mongodb://localhost/sr1egamebot',
    cryptoKey: Buffer.alloc(32), cryptoVector: Buffer.alloc(16)};
  assert.doesNotThrow(() => validateConfig(config));
  assert.throws(() => validateConfig({...config, dbUrl: ''}), /config.dbUrl/);
  assert.throws(() => validateConfig({...config, cryptoKey: undefined}), /original encryption values/);
  assert.throws(() => validateConfig({...config, cryptoVector: Buffer.alloc(15)}), /16-byte Buffer/);
});

test('awaits database readiness and Discord login before activating reminders', async () => {
  const connection = deferred();
  const login = deferred();
  const calls = [];
  const client = Object.assign(new EventEmitter(), {login: async token => {
    calls.push(`login:${token}`);
    await login.promise;
    client.emit('clientReady');
  }, destroy() { calls.push('destroy'); }});
  const started = startBot({client, token: 'test-token',
    connectDatabase: async () => { calls.push('connect'); await connection.promise; },
    initialize: async () => { calls.push('initialize'); },
    afterLogin: () => { calls.push('reminders'); },
    closeDatabase: async () => { calls.push('close'); }});
  await nextTurn();
  assert.deepEqual(calls, ['connect']);
  connection.resolve();
  await nextTurn();
  assert.deepEqual(calls, ['connect', 'initialize', 'login:test-token']);
  login.resolve();
  assert.equal(await started, client);
  assert.deepEqual(calls, ['connect', 'initialize', 'login:test-token', 'reminders']);
});

for (const failedStage of ['connectDatabase', 'initialize', 'login', 'afterLogin']) {
  test(`cleans up and propagates asynchronous ${failedStage} failure safely`, async () => {
    const calls = [];
    const secretError = new Error('mongodb://user:password@private-host/');
    const step = name => async () => {
      calls.push(name);
      if (name === failedStage) throw secretError;
    };
    const client = Object.assign(new EventEmitter(), {
      login: async () => { await step('login')(); client.emit('clientReady'); },
      destroy: step('destroy')
    });
    await assert.rejects(startBot({
      client, token: 'test-token',
      connectDatabase: step('connectDatabase'), initialize: step('initialize'),
      afterLogin: step('afterLogin'), stopReminders: step('stopReminders'),
      closeDatabase: step('closeDatabase')
    }), error => error instanceof StartupError && error.cause === secretError
      && !error.message.includes('password') && !error.message.includes('private-host'));
    assert.deepEqual(calls.slice(-3), ['stopReminders', 'destroy', 'closeDatabase']);
    const order = ['connectDatabase', 'initialize', 'login', 'afterLogin'];
    assert.deepEqual(calls.slice(0, -3), order.slice(0, order.indexOf(failedStage) + 1));
    assert.equal(client.listenerCount('clientReady'), 0);
  });
}

test('login resolution alone does not activate reminders before clientReady', async () => {
  const client = new EventEmitter();
  client.login = async () => 'test-token';
  client.destroy = () => {};
  let activated = false;
  const started = startBot({client, token: 'test-token',
    connectDatabase: async () => {}, initialize: async () => {},
    afterLogin: () => { activated = true; }, closeDatabase: async () => {}});
  await nextTurn();
  assert.equal(activated, false);
  client.emit('clientReady');
  await started;
  assert.equal(activated, true);
});

test('one failing cleanup does not prevent the other cleanup actions', async () => {
  let closed = false;
  await assert.rejects(startBot({
    client: {login() {}, destroy() { throw new Error('cleanup'); }}, token: 'test-token',
    connectDatabase: async () => { throw new Error('unavailable'); }, initialize() {},
    stopReminders() { throw new Error('timer cleanup'); },
    closeDatabase: async () => { closed = true; }
  }), /MongoDB connection failed/);
  assert.equal(closed, true);
});

test('CLI exits nonzero with useful configuration guidance before loading the bot', t => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'sr1e-startup-'));
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  for (const filename of ['main.js', 'startup.js', 'settings.js', 'config.example.js']) {
    fs.copyFileSync(path.join(__dirname, '..', filename), path.join(directory, filename));
  }
  const env = {...process.env};
  for (const key of ['TOKEN', 'MONGODB_URI', 'CRYPTO_KEY_HEX', 'CRYPTO_IV_HEX']) delete env[key];
  const result = spawnSync(process.execPath, [path.join(directory, 'main.js')],
    {encoding: 'utf8', timeout: 5000, env});
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Set config.dbUrl/);
  assert.doesNotMatch(result.stderr, /at .*startup.js/);
});
