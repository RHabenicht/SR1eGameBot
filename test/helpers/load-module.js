const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createRequire} = require('node:module');

// Load the real CommonJS source with only network/configuration boundaries replaced.
function loadModule(filename, stubs = {}, globals = {}) {
  const fullPath = path.resolve(__dirname, '../..', filename);
  const realRequire = createRequire(fullPath);
  const module = {exports: {}};
  const requireStub = name => Object.hasOwn(stubs, name) ? stubs[name] : realRequire(name);
  const context = {
    module, exports: module.exports, require: requireStub,
    __dirname: path.dirname(fullPath), __filename: fullPath,
    Buffer, console, process, setTimeout, clearTimeout, AbortController, global: {}, ...globals
  };
  vm.runInNewContext(fs.readFileSync(fullPath, 'utf8'), context, {filename: fullPath, timeout: 5000});
  return {exports: module.exports, context};
}

module.exports = {loadModule};
