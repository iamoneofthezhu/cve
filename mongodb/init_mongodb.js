const fs = require('fs');

//read a secret file and remove extra whitespace/newlines
function getSecret(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8').trim();
  } catch (err) {
    print(`Error reading secret at ${filePath}: ${err}`);
    return null;
  }
}

//Read secrets from files instead of using environment variables (Tried using environment variables but variables not set by the time this script runs)
//No need to create root user in admin database here because it is already created by docker as defined in docker-compose.yml
var appUser = getSecret('/etc/mongo/db_user_username.txt');
var appPwd = getSecret('/etc/mongo/db_user_password.txt');
var dbName = 'web_scraper_db';

const adminDb = db.getSiblingDB('admin');

//create user in admin database
function createUsersInAdminDatabase(username, password) {
  adminDb.createUser({
    user: username,
    pwd: password,
    roles: [{ role: "readWrite", db: dbName }]
  });
  print(`User ${username} created successfully.`);
}

const userInfo = adminDb.runCommand({ usersInfo: { user: appUser, db: "admin" } });

  
// usersInfo returns an array in the 'users' field. If empty, the user doesn't exist.
if (userInfo.users && userInfo.users.length > 0) {
  print(`User ${appUser} already exists. Skipping.`);
} else {
  print(`Creating user ${appUser} for database ${dbName}...`);
  createUsersInAdminDatabase(appUser, appPwd);
}

//need to create a collection in the database so the database shows up in the mongo shell
//add validation to the collection to ensure the data is in the correct format
const targetDb = db.getSiblingDB(dbName);
if (!targetDb.getCollectionNames().includes("cve_collection")) {
  print(`Creating initial collection in ${dbName}...`);
  targetDb.createCollection("cve_collection", {
    validator: {
      $jsonSchema: {
        bsonType: "object",
        required: ["cve_id", "published", "status", "description"],
        properties: {
          cve_id: { bsonType: "string" },
          published: { bsonType: "string" },
          status: { bsonType: "string" },
          description: { bsonType: "string" },
          cvss: {
            bsonType: "object",
            properties: {
              "v31": {
                bsonType: "object",
                properties: {
                  "base_score": { bsonType: "number" },
                  "severity": { bsonType: "string" },
                  "vector": { bsonType: "string" },
                  "exploitability": { bsonType: "number" },
                  "impact": { bsonType: "number" }
                }
              },
              "v40": {
                bsonType: "object",
                properties: {
                  "base_score": { bsonType: "number" },
                  "severity": { bsonType: "string" },
                  "vector": { bsonType: "string" },
                  "exploitability": { bsonType: "number" }
                }
              }
            }
          },
          "weaknesses": { 
            bsonType: "array",
            items: {
              bsonType: "string"
            }
          },
          "affected": {
            bsonType: "array",
            items: {
              bsonType: "object",
              properties: {
                "vendor": { bsonType: "string" },
                "product": { bsonType: "string" },
                "version": { bsonType: "string" }
              }
            }
          },
          "references": {
            bsonType: "array",
            items: {
              bsonType: "object",
              properties: {
                url: { bsonType: "string" }
              }
            }
          }
        }
      }
    }
  });
  
  print("Database '" + dbName + "' created.");
}

  
