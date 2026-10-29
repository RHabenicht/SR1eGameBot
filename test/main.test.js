const assert = require('node:assert/strict');
const {test} = require('node:test');
const {EventEmitter} = require('node:events');
const {setImmediate: nextTurn} = require('node:timers/promises');
const Discord = require('discord.js');
const startup = require('../startup');
const {loadModule} = require('./helpers/load-module');

function makeBot({login, roll = async () => {}, initialize = async () => {}} = {}) {
  const calls = [], errors = [], replies = [];
  let client;
  class FakeClient extends EventEmitter {
    constructor() {
      super();
      client = this;
      this.user = {tag: 'test-bot', setActivity() {}};
    }
    async login(token) {
      calls.push('login');
      if (login) await login(token);
      this.emit(Discord.Events.ClientReady);
      return token;
    }
    destroy() { calls.push('destroy'); }
  }
  const stubs = {
    './startup': {...startup, loadSettings: () => ({token: 'test-token'})},
    'discord.js': {...Discord, Client: FakeClient},
    './api': {resetCache() {}}, './admin': {},
    './log': {logWrite() {}, logSpam() {}, logError: error => errors.push(error)},
    './init': {
      initAll: async options => {
        assert.equal(options.scheduleReminders, false);
        calls.push('initialize');
        await initialize();
      },
      startReminders: () => calls.push('reminders'),
      stopReminders: () => calls.push('stop-reminders')
    },
    './db': {connectDatabase: async () => calls.push('connect'),
      closeDatabase: async () => calls.push('close')},
    './ft_dicebot': {handleRollCommand: roll}
  };
  for (const file of ['ft_ammo', 'ft_gmscreen', 'ft_help', 'ft_initiative',
    'ft_macro', 'ft_reminders', 'ft_scene', 'ft_misc']) stubs[`./${file}`] = {};
  const {exports} = loadModule('main.js', stubs);
  const message = {content: '!3', author: {id: 'player', bot: false},
    reply: async value => replies.push(value)};
  return {start: exports.start, get client() { return client; }, calls, errors, replies, message};
}

test('does not connect merely by importing the main module', () => {
  const bot = makeBot();
  assert.equal(bot.client, undefined);
  assert.deepEqual(bot.calls, []);
});

test('ignores commands until login succeeds, then enables commands and saved reminders', async () => {
  let releaseLogin;
  let rolls = 0;
  const bot = makeBot({login: () => new Promise(resolve => { releaseLogin = resolve; }),
    roll: async () => { rolls++; }});
  const starting = bot.start();
  await nextTurn();
  bot.client.emit(Discord.Events.MessageCreate, bot.message);
  assert.equal(rolls, 0);
  assert.deepEqual(bot.calls, ['connect', 'initialize', 'login']);
  releaseLogin();
  await starting;
  bot.client.emit(Discord.Events.MessageCreate, bot.message);
  await nextTurn();
  assert.equal(rolls, 1);
  assert.deepEqual(bot.calls, ['connect', 'initialize', 'login', 'reminders']);
});

test('awaits asynchronous command status before sending the failure response', async () => {
  const bot = makeBot({roll: async () => { await nextTurn(); return -1; }});
  await bot.start();
  bot.client.emit(Discord.Events.MessageCreate, bot.message);
  await nextTurn();
  await nextTurn();
  assert.equal(bot.replies.length, 1);
  assert.match(bot.replies[0], /Something went wrong/);
});

test('handles rejected asynchronous commands without an unhandled rejection', async () => {
  const failure = new Error('command failed');
  const bot = makeBot({roll: async () => { throw failure; }});
  await bot.start();
  bot.client.emit(Discord.Events.MessageCreate, bot.message);
  await nextTurn();
  assert.deepEqual(bot.errors, [failure]);
});

test('human rerolls retain the reacting user and bot messages/reactions are ignored', async () => {
  const users = [];
  const bot = makeBot({roll: async (_msg, _cmd, _args, user) => users.push(user.id)});
  await bot.start();
  bot.client.emit(Discord.Events.MessageCreate, {...bot.message, author: {id: 'bot', bot: true}});
  const reaction = {emoji: {name: '🎲'}, message: bot.message};
  bot.client.emit(Discord.Events.MessageReactionAdd, reaction, {id: 'bot', bot: true});
  bot.client.emit(Discord.Events.MessageReactionAdd, reaction, {id: 'reroller', bot: false});
  await nextTurn();
  assert.deepEqual(users, ['reroller']);
});

test('failed login closes resources and leaves command handlers inactive', async () => {
  let rolls = 0;
  const bot = makeBot({login: async () => { throw new Error('invalid token'); },
    roll: async () => { rolls++; }});
  await assert.rejects(bot.start(), /Discord login failed/);
  bot.client.emit(Discord.Events.MessageCreate, bot.message);
  assert.equal(rolls, 0);
  assert.deepEqual(bot.calls.slice(-3), ['stop-reminders', 'destroy', 'close']);
});
