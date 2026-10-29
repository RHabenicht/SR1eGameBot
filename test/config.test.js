const assert = require('node:assert/strict');
const {test} = require('node:test');
const {loadModule} = require('./helpers/load-module');
const {validateConfig} = require('../startup');

test('environment-only configuration supports a clean deployment without config.js', () => {
  const env = {MONGODB_URI: 'mongodb://localhost/sr1egamebot',
    CRYPTO_KEY_HEX: 'ab'.repeat(32), CRYPTO_IV_HEX: 'cd'.repeat(16)};
  const {exports: example} = loadModule('config.example.js', {}, {process: {env}});
  const {exports: settings} = loadModule('settings.js', {
    'node:fs': {existsSync: () => false}, './config.example': example
  });
  validateConfig(settings.config);
  assert.equal(settings.config.cryptoKey.toString('hex'), env.CRYPTO_KEY_HEX);
  assert.equal(settings.config.cryptoVector.toString('hex'), env.CRYPTO_IV_HEX);
});

test('existing config.js takes precedence without changing its encryption material', () => {
  const local = {config: {cryptoKey: Buffer.alloc(32, 7), cryptoVector: Buffer.alloc(16, 8)}};
  const {exports} = loadModule('settings.js', {
    'node:fs': {existsSync: () => true}, './config': local
  });
  assert.equal(exports, local);
  assert.equal(exports.config.cryptoKey, local.config.cryptoKey);
});

test('malformed hex configuration is rejected instead of silently truncated', () => {
  assert.throws(() => loadModule('config.example.js', {}, {process: {env: {
    CRYPTO_KEY_HEX: 'ab'.repeat(32) + 'zz'
  }}}), /64 hexadecimal characters/);
});
