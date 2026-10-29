const assert = require('node:assert/strict');
const {test} = require('node:test');
const {setImmediate: nextTurn} = require('node:timers/promises');
const {loadModule} = require('./helpers/load-module');

function reminderFixture({deliver = async () => {}} = {}) {
  const timers = [], cleared = [], errors = [];
  const reminders = [
    {shortID: 'overdue', dateTime: new Date(Date.now() - 5000).toISOString(), playersString: 'player'},
    {shortID: 'future', dateTime: new Date(Date.now() + 60000).toISOString(), playersString: 'player'}
  ];
  const global = {folderID: {}};
  const api = {
    doNothing() {}, createFolder: async () => {}, ensureFolderByName: async () => {},
    findFolderByName: async name => ({name, _id: {toString: () => name + '-id'}}),
    getActiveReminders: async () => reminders,
    _addRemindersSetTimeoutPayload: deliver
  };
  const loaded = loadModule('init.js', {
    './api': api,
    './log': {logWrite() {}, logSpam() {}, logError: error => errors.push(error)}
  }, {global, setTimeout: (callback, delay) => {
    const timer = {callback, delay}; timers.push(timer); return timer;
  }, clearTimeout: timer => cleared.push(timer)});
  return {init: loaded.exports, global, timers, cleared, errors, reminders};
}

test('restores reminder state without scheduling delivery during database initialization', async () => {
  const fixture = reminderFixture();
  await fixture.init.initAll({scheduleReminders: false});
  assert.equal(fixture.global.folderID.UserData, 'UserData-id');
  assert.equal(fixture.global.folderID.reminders, 'reminders-id');
  assert.equal(fixture.global.reminders.length, 2);
  assert.equal(fixture.timers.length, 0);
  fixture.init.startReminders();
  assert.equal(fixture.timers.length, 2);
  assert.equal(fixture.timers[0].delay, 0);
  assert.ok(fixture.timers[1].delay > 0);
  fixture.init.stopReminders();
  assert.deepEqual(fixture.cleared, fixture.timers);
});

test('scheduled reminders deliver their saved payload and catch rejected deliveries', async () => {
  const delivered = [];
  const failure = new Error('delivery unavailable');
  const fixture = reminderFixture({deliver: async reminder => {
    delivered.push(reminder.shortID);
    throw failure;
  }});
  await fixture.init.initAll({scheduleReminders: false});
  fixture.init.startReminders();
  fixture.timers[0].callback();
  await nextTurn();
  assert.deepEqual(delivered, ['overdue']);
  assert.deepEqual(fixture.errors, [failure]);
});
