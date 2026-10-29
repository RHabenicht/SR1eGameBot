/*
 * Shadowrun 1e GameBot by Discord user AstroMacGuffin#1486 (Nathan Hawks)
 * https://github.com/NathanHawks/SR1eGameBot
 * Yes I do regret baking 1e into the name
 * version 0.3, yeah that sounds good
 * Released under the terms of the UnLicense. This work is in the public domain.
 * Released as-is with no warranty or claim of usability for any purpose.
 */
const {loadSettings, initializeGlobals, startBot, reportStartupFailure} = require('./startup');

async function start() {
  const {token} = loadSettings();
  const {resetCache, fetchAndStoreAllLabels} = require('./api');
  const {logWrite, logError} = require('./log');
  const {initAll, stopReminders} = require('./init');
  const {connectDatabase, closeDatabase} = require('./db');
  const Discord = require('discord.js');
  initializeGlobals(resetCache);
  global.bot = new Discord.Client({
    intents: [
      Discord.GatewayIntentBits.Guilds,
      Discord.GatewayIntentBits.GuildMessages,
      Discord.GatewayIntentBits.GuildMessageReactions,
      Discord.GatewayIntentBits.DirectMessages,
      Discord.GatewayIntentBits.MessageContent
    ],
    partials: [Discord.Partials.Channel]
  });
  global.bot.once(Discord.Events.ClientReady, () => {
    logWrite('Connected to Discord as [' + global.bot.user.tag + ']');
    global.bot.user.setActivity('!help', {type: 2});
  });
  global.bot.on(Discord.Events.Error, logError);
  global.bot.on(Discord.Events.ShardError, logError);
  return startBot({
    client: global.bot,
    token,
    connectDatabase,
    initialize: () => initAll({scheduleReminders: false}),
    afterLogin: fetchAndStoreAllLabels,
    stopReminders,
    closeDatabase
  });
}

if (require.main === module) start().catch(reportStartupFailure);
module.exports = {start};
