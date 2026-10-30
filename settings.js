const fs = require('node:fs');
const path = require('node:path');

// Keep existing local configuration authoritative; never fall back if it is invalid.
const filename = fs.existsSync(path.join(__dirname, 'config.js')) ? './config' : './config.example';
module.exports = require(filename);
