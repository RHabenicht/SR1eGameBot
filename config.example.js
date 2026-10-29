function readHexBuffer(name, byteLength) {
  const value = process.env[name];
  if (value === undefined) return undefined;
  if (!new RegExp(`^[0-9a-fA-F]{${byteLength * 2}}$`).test(value)) {
    throw new Error(`${name} must contain ${byteLength * 2} hexadecimal characters.`);
  }
  return Buffer.from(value, 'hex');
}
class DiceBotConfig {
  constructor() {
    this.logspam = true;
    this.dbUrl = process.env.MONGODB_URI || '';
    // For an existing database, preserve the original values in local config.js
    // or provide their exact hex equivalents through these environment variables.
    this.cryptoVector = readHexBuffer('CRYPTO_IV_HEX', 16);
    this.cryptoKey = readHexBuffer('CRYPTO_KEY_HEX', 32);
  }
}
const config = new DiceBotConfig();
module.exports = {config};
