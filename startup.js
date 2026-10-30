const fs = require('node:fs');
const path = require('node:path');
const {once} = require('node:events');

class ConfigurationError extends Error {}

class StartupError extends Error {
  constructor(stage, cause) {
    // Driver and Discord errors can contain connection strings or credentials.
    super(`${stage} failed. Check configuration and service availability.`, {cause});
  }
}

function loadToken({env = process.env, readAuth = () => JSON.parse(
  fs.readFileSync(path.join(__dirname, 'discordauth.json'), 'utf8')
)} = {}) {
  let token;
  if (Object.hasOwn(env, 'TOKEN')) {
    token = env.TOKEN;
  } else {
    try {
      token = readAuth().token;
    } catch {
      throw new ConfigurationError(
        'Set TOKEN to the raw Discord bot token, or create discordauth.json with a token property.'
      );
    }
  }
  if (typeof token !== 'string' || !token.trim() || /\s|^[{\[]/.test(token.trim())) {
    throw new ConfigurationError('TOKEN must contain the raw Discord bot token, not JSON.');
  }
  return token.trim();
}

function validateConfig(config) {
  if (!config || typeof config.dbUrl !== 'string'
    || !/^mongodb(?:\+srv)?:\/\//.test(config.dbUrl)) {
    throw new ConfigurationError('Set config.dbUrl to a MongoDB connection string in config.js.');
  }
  if (!Buffer.isBuffer(config.cryptoKey) || config.cryptoKey.length !== 32
    || !Buffer.isBuffer(config.cryptoVector) || config.cryptoVector.length !== 16) {
    throw new ConfigurationError(
      'Set config.cryptoKey (32-byte Buffer) and config.cryptoVector (16-byte Buffer) in config.js. '
      + 'Existing databases require their original encryption values.'
    );
  }
}

function loadSettings() {
  let config;
  try {
    ({config} = require('./settings'));
  } catch {
    throw new ConfigurationError(
      'Check config.js or the MongoDB and encryption environment variables. '
      + 'Use config.example.js as a configuration reference.'
    );
  }
  validateConfig(config);
  return {config, token: loadToken()};
}

function initializeGlobals(resetCache) {
  global.isMaintenanceModeBool = true;
  global.maintenanceStatusMessage = '\n**Bzzt. Hoi!** '
    + 'Encryption is go! `!skipstatus` to hide this message! See `!help troubleshoot` if you suspect a bug!';
  global.reminders = [];
  global.lastRemindersTime = '';
  global.filesFound = [];
  global.folderID = {UserData: null, reminders: null};
  global.config = {logspam: true};
  resetCache();
}

async function startBot({client, token, connectDatabase, initialize,
  afterLogin = () => {}, stopReminders = () => {}, closeDatabase}) {
  let stage = 'MongoDB connection';
  try {
    await connectDatabase();
    stage = 'Database initialization';
    await initialize();
    stage = 'Discord login';
    // Register before login: login can resolve before guild caches emit clientReady.
    const readyController = new AbortController();
    const ready = once(client, 'clientReady', {signal: readyController.signal});
    try {
      await Promise.all([Promise.resolve().then(() => client.login(token)), ready]);
    } finally {
      readyController.abort();
    }
    stage = 'Post-login initialization';
    await afterLogin();
    return client;
  } catch (cause) {
    // Try every cleanup action even if another cleanup fails.
    for (const cleanup of [stopReminders, () => client.destroy(), closeDatabase]) {
      try { await cleanup(); } catch { /* Preserve the original startup failure. */ }
    }
    throw new StartupError(stage, cause);
  }
}

function reportStartupFailure(error) {
  const message = error instanceof ConfigurationError || error instanceof StartupError
    ? error.message : 'Startup failed. Check configuration and service availability.';
  console.error(message);
  process.exitCode = 1;
}

module.exports = {
  ConfigurationError, StartupError, loadToken, validateConfig, loadSettings,
  initializeGlobals, startBot, reportStartupFailure
};
