const assert = require('node:assert/strict');
const {test} = require('node:test');
const {loadModule} = require('./helpers/load-module');

function diceFixture(rolls) {
  const values = rolls.map(value => (value - 0.5) / 6);
  const math = Object.create(Math);
  math.random = () => {
    assert.ok(values.length, 'unexpected additional die roll');
    return values.shift();
  };
  const {exports: api} = loadModule('api.js', {
    './settings': {config: {}}, './db': {Database: {}},
    './log': {logWrite() {}, logSpam() {}, logError() {}}
  }, {Math: math});
  const {exports: dice} = loadModule('ft_dicebot.js', {
    './api': {...api, addMaintenanceStatusMessage: async (_msg, output) => output},
    './log': {logWrite() {}, logError() {}}
  });
  const messages = [], reactions = [], replies = [];
  const user = {toString: () => '<@player>'};
  const message = content => ({content, author: user,
    channel: {send: async value => messages.push(value)},
    react: async value => reactions.push(value), reply: async value => replies.push(value)});
  return {api, dice, messages, reactions, replies, user, message};
}

test('ordinary d6 success tests preserve target numbers and descending roll display', () => {
  const {api} = diceFixture([1, 4, 6]);
  const [successes, rolls] = api.rollDice(3, false, 4);
  assert.equal(successes, 2);
  assert.deepEqual(Array.from(rolls), [6, 4, 1]);
});

test('Rule of Six still explodes sixes for target numbers above six', () => {
  const {api} = diceFixture([6, 4, 2]);
  const [successes, rolls] = api.rollDice(2, true, 8);
  assert.equal(successes, 1);
  assert.deepEqual(Array.from(rolls), [10, 2]);
});

test('totalled and semicolon-separated roll commands retain output and reroll reaction', async () => {
  const fixture = diceFixture([2, 4, 1]);
  const msg = fixture.message('!2t +3; 1');
  await fixture.dice.handleRollCommand(msg, '2t', ['+3'], fixture.user);
  assert.equal(fixture.messages.length, 1);
  assert.match(fixture.messages[0], /\[Total: 9\]/);
  assert.match(fixture.messages[0], /Roll #2:.*\(1\)/);
  assert.deepEqual(fixture.reactions, ['🎲']);
});

test('opposed tests without an opponent target number return existing user guidance', async () => {
  const fixture = diceFixture([]);
  const msg = fixture.message('!2! tn4 vs2!');
  await fixture.dice.handleRollCommand(msg, '2!', ['tn4', 'vs2!'], fixture.user);
  assert.equal(fixture.messages.length, 0);
  assert.match(fixture.replies[0], /opponent TN/);
});
