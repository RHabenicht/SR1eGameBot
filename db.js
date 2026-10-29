const {config} = require('./settings');
const {logWrite} = require('./log');
const {MongoClient} = require('mongodb');
const mdb = new MongoClient( config.dbUrl );
async function connectDatabase() {
  await mdb.connect();
  logWrite('Connected to MongoDB');
}
async function closeDatabase() {
  await mdb.close();
}
class Database {
  constructor() {
    this.mdb = mdb;
  }
  static getTable(tableName) {
    return mdb.db("sr1egamebot").collection(tableName);
  }
}
module.exports = {db: new Database(), Database, connectDatabase, closeDatabase};
