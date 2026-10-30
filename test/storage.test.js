const assert = require('node:assert/strict');
const {test} = require('node:test');
const {ObjectId} = require('mongodb');
const {loadModule} = require('./helpers/load-module');

// Keep real folder lookup, caching, encryption and macro handlers. Replace only
// MongoDB transport and Discord delivery, so a restart can reuse stored records.
function storageFixture() {
  const rootID = new ObjectId();
  const tables = {folders: [{_id: rootID, name: 'UserData', encrypted: false}], strings: []};
  const errors = [], replies = [], rolls = [];
  const matches = (doc, query) => Object.entries(query).every(([key, value]) => {
    if (key === '$and') return value.every(part => matches(doc, part));
    if (value instanceof ObjectId) return value.equals(doc[key]);
    return value == null ? doc[key] == null : doc[key] === value;
  });
  const database = {getTable: name => ({
    findOne: async query => tables[name].find(doc => matches(doc, query)) || null,
    insertOne: async doc => {
      const stored = {_id: new ObjectId(), ...doc};
      // BSON serializes an undefined field as null with the driver's defaults.
      for (const key of Object.keys(stored)) if (stored[key] === undefined) stored[key] = null;
      tables[name].push(stored);
      return {insertedId: stored._id};
    },
    updateOne: async (query, update, options) => {
      let doc = tables[name].find(record => matches(record, query));
      if (!doc && options.upsert) {
        doc = {_id: new ObjectId()};
        tables[name].push(doc);
      }
      Object.assign(doc, update.$set);
      return {acknowledged: true};
    }
  })};
  const log = {logWrite() {}, logSpam() {}, logError: error => errors.push(error)};
  const config = {cryptoKey: Buffer.alloc(32, 7), cryptoVector: Buffer.alloc(16, 8)};
  let api, macros;
  function restart() {
    const global = {folderID: {UserData: rootID.toString()}, isMaintenanceModeBool: false};
    api = loadModule('api.js', {
      './settings': {config}, './db': {Database: database}, './log': log
    }, {global}).exports;
    api.resetCache();
    macros = loadModule('ft_macro.js', {
      './api': api, './log': log,
      './ft_dicebot': {handleRollCommand: (_msg, cmd, args, _user, content) => {
        rolls.push({cmd, args: Array.from(args), content});
      }}
    }).exports;
  }
  function message(channelID = 'channel-a', userID = 'player-a') {
    return {channel: {id: channelID, guild: {id: 'server-a'}}, author: {id: userID},
      reply: async content => replies.push(content)};
  }
  restart();
  return {get api() { return api; }, get macros() { return macros; },
    tables, errors, replies, rolls, rootID, restart, message};
}

test('first saved roll creates valid encrypted folders without a false error reply', async () => {
  const f = storageFixture();
  await f.macros.handleSaveMacroCommand(f.message(), ['smoketest', '5!', 'tn4']);
  assert.deepEqual(f.replies, ['You now have 1 roll macros saved.']);
  assert.deepEqual(f.errors, []);
  const server = f.tables.folders.find(folder => folder.name === f.api.encrypt('server-a'));
  const channel = f.tables.folders.find(folder => folder.name === f.api.encrypt('channel-a'));
  assert.ok(channel, 'the channel must be stored by its real encrypted ID');
  assert.ok(channel.parent.equals(server._id));
  for (const folder of f.tables.folders.filter(folder => folder.encrypted)) {
    assert.equal(typeof folder.name, 'string');
  }
});

test('a saved roll decrypts and runs after a fresh process clears every cache', async () => {
  const f = storageFixture();
  await f.macros.handleSaveMacroCommand(f.message(), ['smoketest', '5!', 'tn4']);
  const record = f.tables.strings.find(file => file.name === 'savedRolls');
  assert.equal(record.encrypted, true);
  assert.notEqual(record.content, 'smoketest 5! tn4');
  assert.equal(f.api.decrypt(record.content), 'smoketest 5! tn4');
  f.replies.length = 0;
  f.errors.length = 0;
  f.restart();
  await f.macros.handleRollMacroCommand(f.message(), 'roll', ['smoketest'], f.message().author);
  assert.deepEqual(f.rolls, [{cmd: '!5!', args: ['tn4'], content: '!5! tn4'}]);
  assert.deepEqual(f.replies, [], 'a successful restored roll must not also report failure');
  assert.deepEqual(f.errors, []);
});

test('saved rolls stay separate between channels after a restart', async () => {
  const f = storageFixture();
  await f.macros.handleSaveMacroCommand(f.message('channel-a'), ['smoketest', '5!', 'tn4']);
  await f.macros.handleSaveMacroCommand(f.message('channel-b'), ['smoketest', '3']);
  f.restart();
  for (const channel of ['channel-a', 'channel-b']) {
    const msg = f.message(channel);
    await f.macros.handleRollMacroCommand(msg, 'roll', ['smoketest'], msg.author);
  }
  assert.deepEqual(f.rolls.map(roll => roll.content), ['!5! tn4', '!3 ']);
  assert.deepEqual(f.errors, []);
});

test('a new user in an existing channel gets their own folder and no false failure', async () => {
  const f = storageFixture();
  await f.macros.handleSaveMacroCommand(f.message(), ['first', '5']);
  f.restart();
  f.replies.length = 0;
  await f.macros.handleSaveMacroCommand(f.message('channel-a', 'player-b'), ['second', '3']);
  assert.deepEqual(f.replies, ['You now have 1 roll macros saved.']);
  assert.deepEqual(f.errors, []);
  assert.equal(f.tables.strings.filter(file => file.name === 'savedRolls').length, 2);
});

test('configured play channels preserve their own user folder and cache identity', async () => {
  const f = storageFixture();
  const msg = f.message('gm-screen');
  await f.api.ensureTriplet(msg);
  const screenID = await f.api.findUserFolderDBIDFromMsg(msg);
  await f.api.setStringByNameAndParent('gmPlayChannel', screenID, 'play-channel');
  f.restart();
  assert.equal(await f.api.getPlayChannel(msg), 'play-channel');
  await f.api.ensureTriplet(msg);
  const playID = await f.api.findUserFolderDBIDFromMsg(msg, true);
  assert.notEqual(playID, screenID);
  assert.equal(await f.api.findUserFolderDBIDFromMsg(msg), screenID);
  assert.equal(await f.api.getPlayChannel(msg), 'play-channel');
  assert.deepEqual(f.errors, []);
});

test('a missing user folder returns the normal error sentinel instead of throwing', async () => {
  const f = storageFixture();
  await f.api.ensureTriplet(f.message());
  f.replies.length = 0;
  const missing = await f.api.findUserFolderDBIDFromMsg(f.message('channel-a', 'new-player'));
  assert.equal(missing, -1);
  assert.equal(f.replies.length, 1);
  assert.match(f.replies[0], /Something went wrong/);
});
