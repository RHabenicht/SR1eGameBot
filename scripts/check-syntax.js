const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
let count = 0;

function checkDirectory(directory) {
  for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
    if (entry.name === 'node_modules' || entry.name === '.git') continue;
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      checkDirectory(filename);
    } else if (entry.name.endsWith('.js') && entry.name !== 'config.js') {
      const result = spawnSync(process.execPath, ['--check', filename], {stdio: 'inherit'});
      if (result.status !== 0) process.exit(result.status || 1);
      count++;
    }
  }
}

checkDirectory(root);
console.log(`Syntax checked ${count} JavaScript files.`);
