# SR1eGameBot

## What It Is

A Discord dicebot for Shadowrun 1e/2e/3e, which does d6 rolls with modifiers, as well as Success Tests and Opposed Success Tests. It can also store **dice macros,** and even generates **initiative** for Shadowrun 1st-3rd Editions -- both forwards and backwards. **New in 2022**
it also does **reminders**, **ammo tracking**, **scene text and music**, and has a
**virtual GM screen** for hiding your prep from your players. And, hey, why not: it also
does **initiative for Cyberpunk 2020 and Cyberpunk RED**.

Instructions on using the bot are below, after the self-hosting instructions.

* <a href="#how-to-install">How to Install</a>
* <a href="#shadowrun-dicebot-features">Shadowrun Dicebot Features</a>
* <a href="#boom-initiative-system-boom">Initiative System</a>
* <a href="#blue_book-prepared-scenes-with-or-without-music-blue_book">Prepared Scenes</a>
* <a href="#ninja-virtual-gm-screen-ninja">Virtual GM Screen</a>
* <a href="#alarm_clock-reminders-alarm_clock">Reminders</a>
* <a href="#gun-ammo-tracking-gun">Ammo Tracking</a>

## How to Install

[Click here to deploy the bot on your server](https://discordapp.com/oauth2/authorize?client_id=609274260007026689&scope=bot&permissions=3136).

### Runtime and installation

Use **Node.js 24 LTS (24.17.0 or newer within 24.x)** and **npm 11**. The
`.nvmrc` selects Node 24.22.1; `packageManager` records npm 11.9.0. Install those
versions before running the following commands from the repository directory:

```sh
npm ci --ignore-scripts
npm run check
npm test
npm audit --omit=dev
```

Keep `package-lock.json` in version control. `node_modules` is generated locally
and must not be committed or copied from an older checkout. Use `npm ci` on
subsequent deployments so the installed dependency tree matches the lockfile.
The installation does not require dependency lifecycle scripts.

### Database and encryption configuration

Install MongoDB and create the `sr1egamebot` database. The application uses
MongoDB driver 4.x in this maintenance update. Configure database authentication
and restrict database access to the bot host or another trusted private network.

Choose one configuration method:

* **Existing local configuration:** keep your ignored `config.js`. It takes
  precedence over the environment-backed example. The file must export
  `{config}` with `dbUrl`, a 32-byte `Buffer` named `cryptoKey`, and a 16-byte
  `Buffer` named `cryptoVector`.
* **New local configuration:** copy `config.example.js` to `config.js` and fill
  in those values, either directly or through its environment variables.
* **Environment-only deployment:** leave `config.js` absent and set
  `MONGODB_URI`, `CRYPTO_KEY_HEX` (64 hexadecimal characters), and
  `CRYPTO_IV_HEX` (32 hexadecimal characters). The application then loads
  `config.example.js` as its environment-backed configuration.

A connection string has the form
`mongodb://USERNAME:PASSWORD@HOST:PORT/sr1egamebot`. URI-encode special characters
in the username and password.

**For an existing database, reuse its exact encryption key and vector.** This
update does not migrate stored ciphertext or generate replacement keys. Keep a
backup of the database and its original encryption material together with your
recovery procedures.

For a **new database only**, `node make-crypto-vars.js` generates the two Buffer
assignments in the ignored `crypto-vars.txt` file. Copy those assignments into
`config.js`, or convert those same byte values to hex for environment-only
configuration. Keep the generated material private and backed up.

If upgrading from the old Google Drive storage, see **Data Migration** below.

### Discord configuration and startup

Create a bot application in the [Discord Developer Portal](https://discord.com/developers/applications)
and enable **Message Content Intent** for its existing prefix commands.
Provide its token in either of these ways:

* Set the `TOKEN` environment variable to the **raw bot token**, without a
  `Bot ` prefix or a JSON object.
* Create the ignored `discordauth.json` file next to `main.js`:

```json
{"token": "your-bot-token"}
```

`TOKEN` takes precedence over the local token file. An empty or malformed
explicit `TOKEN` is an error; it does not silently fall back to local credentials.

Start the bot with `npm start` or `node main.js`. Startup validates configuration,
connects to MongoDB, initializes stored state, logs in to Discord, and then
activates saved reminders and accepts commands. A startup failure closes opened
resources and exits with a nonzero status so your process supervisor can handle
restarts. It does not retry invalid credentials in a loop.

The `Procfile` continues to run `worker: node main.js`. On a platform that uses
Procfiles, select the **worker** process and supply the configuration above.
Invite your own bot application to your Discord server using its application ID
and the permissions required for messages and reactions.

### Development checks

CI uses the same Node/npm versions, a clean installation, syntax checks, offline
regression tests, and an npm audit that fails for high or critical advisories.
The tests replace Discord and MongoDB network boundaries; they do not establish
that a live deployment can authenticate or that a real database migration works.
Before deploying, use a separate test bot and database to check persisted macros,
initiative, ammo, scenes, reactions, and reminders across a restart.

### Data Migration

To migrate the data, first make sure MongoDB is installed and running. Make sure `config.js` is set up with the proper `this.dbUrl` value including MongoDB user credentials if you've turned on MongoDB's password authentication. Then go to Google Drive and right-click your `UserData` folder, and choose Download. Then rename the downloaded file to simply `UserData.zip` and place it in the same folder with the bot's code files. Then run `node ./migrate.js` from the bot's folder.

After migrating, you will have more entries in the `folders` collection than were reported in the `migrate.js` output. This is normal; it happens because `node-stream-zip` only reports folder endpoints: `UserData/serverID/channelID/userID` gets reported as one folder, when actually it's four folders nested in each other.

### Hosting the Bot Elsewhere

Unfortunately, this is beyond the scope of these instructions.

### Administrative commands

The legacy `!open`, `!showcache`, and `!clearcache` commands are disabled in the
maintained branch. They inspect or change shared process state, and their output
can contain data from other servers. No Discord account has an exception.

Manage the bot through your hosting account and database tools. Normal game
commands remain available.

## Shadowrun Dicebot Features

### :game_die: Plain Old d6\'s :game_die:

* !***X***<br/>Roll ***X***d6 *without* Rule of 6<br/>***example:*** `!5` <br/> rolls 5d6 *without* Rule of 6
* !X***t***<br/>Roll Xd6 *and total them*.<br/>***example:*** `!6t` <br/> rolls 6d6 and *adds them up*.
* !Xt ***+Z***<br/>Roll Xd6, total them, and *add or subtract a modifier*.<br/>***example:*** `!6t -5` <br/> rolls 6d6, totals them, and *subtracts 5 from the total*.

### :six: Rule of 6 & Target Numbers :dart:

* ***!X!***<br/>Roll ***X***d6 ***with*** Rule of 6<br/>***example:*** `!5!` <br/> rolls 5d6 *with Rule of 6*
* !X ***tnY***<br/>Roll *without* Rule of 6 against Target Number ***Y***<br/>***example:*** `!5 tn4` <br/> rolls 5d6 w/o Rule of 6 vs TN4
* ***!X! tnY***<br/>Roll ***with*** Rule of 6 against Target Number ***Y***<br/>***example:*** `!5! tn4` <br/> rolls 5d6 w/ Rule of 6 vs TN4

### :boxing_glove: Opposed Rolls :boxing_glove:

* !A! tnB ***vsX!*** ***otnY***<br/>Roll *A*d6 (with Rule of 6) with tn *B*, opposed by *X*d6 (with Rule of 6) with opponent\'s TN *Y*<br/>:arrow_right: ***vsX*** = the number of dice the opponent throws (***vsX! for Rule of 6***)<br/>:arrow_right: ***otnY*** = the opponent\'s target number<br/>***example:*** `!5! tn3 vs6! otn4`<br/>Roll 5d6 (Rule of 6) with TN 3, against 6d6 (Rule of 6) with TN 4

### :1234: Multiple Rolls per Message :1234:

You can order GameBot to do multiple rolls with one message. Just separate the dice commands with semicolons.

***example:*** `!1 ; 2t ; 3!; 4t +5 and a note for good measure`

Be careful not to use semicolons for any other reason.

### :label: Notes :label:

Notes are OK, and your options can be in the middle of the note.

examples:

*  `!3! TN4 resist wagemage sorcery` :arrow_left: works
*  `!3! resist wagemage sorcery TN4` :arrow_left: works
*  `!3! resist TN4 wagemage sorcery` :arrow_left: works
*  `resist wagemage sorcery !3! TN4` :arrow_left: won't work

### :fast_forward: Macros (Saved Rolls) :fast_forward:

* !***save*** *name* *dice_command_without_preceding_bang*<br/>Creates or updates a named "dice command". *(See all the sections above for valid "dice commands".)*
* !***roll*** *name*<br/>Rolls the saved "dice command" with the given name.
* !***lm***<br/>Lists your saved dice command macros for that channel.
* !***removemacro*** *name* or !***rmm*** *name*<br/>Removes one of your saved macros in that channel.

### :recycle: Reroll :recycle:

* Anyone can click the :game_die: reaction to reroll any *recent* roll.
* Remove and re-add your reaction to keep re-rolling that roll.

## :boom: Initiative System :boom:

### Player setup:

  :one: `!setgm @someone`<br/>  :two: `!setinit X Y`

### GM setup:

  :one: `!setgm`<br/>  :two: `!setplayers @player1 @player2 (etc)`<br/>  :three: `!setnpcinits` (see below)

  **!setinit** syntax is `!setinit X Y` where X is the number of dice and Y is the modifier. For example, `!setinit 1 4` sets your initiative formula to 1d6+4. *(Or, for Cyberpunk, 1d10+4. It'll say 1d6+4, but it'll roll 1d10+4 if you roll Cyberpunk initiative.)*

  IMPORTANT: Commands won't work unless you @people correctly. Use the menu that pops-up while you type, or tab-completion.  **If it's highlighted blue, you did it right.**

### :game_die: **Rolling Initiative** :game_die:

  :arrow_right: **!init** - Shadowrun 1e initiative<br/>  :arrow_right: **!initflip** - Shadowrun 1e initiative, reversed<br/>  :arrow_right: **!init2** - Shadowrun 2e initiative<br/>  :arrow_right: **!init2flip** - Shadowrun 2e initiative, reversed<br/>  :arrow_right: **!init3** - Shadowrun 3e initiative<br/>  :arrow_right: **!init3flip** - Shadowrun 3e initiative, reversed<br/>  :arrow_right: **!initcp** - Cyberpunk 2020 initiative<br/>
  :arrow_right: **!initcpr** - Cyberpunk RED initiative

  The bot remembers stuff; you won't need to redo setup, just update whatever changes. ***However:***

* Everything is linked to GM **and chat channel.**
* If you move to a different channel, you must re-enter everything.
* Multiple GM's can share a channel, but anyone playing in both groups must repeat their set-up steps (starting with !setgm).
* To play in two games at the same time, you'll need two channels.

### :game_die: **Other initiative commands** :game_die:

  ```
  Shortcut  Full command    [Required] options
  --------------------------------------------
            !setgm          @someone
  !si       !setinit        [X Y]
  !setp     !setplayers     [@player1 @player2 etc]
  !addp     !addplayers     [@player1 @player2 etc]
  !lp       !listplayers
  !rmp      !removeplayers  [@player1 @player2 etc]
  !clrp     !clearplayers
  !setn     !setnpcinits    [X1 Y1 label1 X2 Y2 label2 etc]
  !addn     !addnpcinits    [X1 Y1 label1 X2 Y2 label2 etc]
  !ln       !listnpcinits
  !rmn      !removenpcinits [label1 label2 etc]
  !clrn     !clearnpcinits
  ```

### :dragon_face: **Adding NPC's** :dragon_face:

  **!setnpcinits** and **!addnpcinits** syntax:<br/>`!(command) X Y label`<br/>Labels cannot have spaces or commas. Add as many NPCs as you want, separated by spaces.

  e.g. `!addnpcinits 1 5 thugs` (means the thugs have 1d6+5 initiative).

  If you have multiple NPC's with the same label, **!removeNPCInits** also accepts the format `!removenpcinits X Y label` which requires a full match. But, having multiple NPC's with the same label is confusing anyway, so maybe just don't do that.

## :blue_book: Prepared Scenes with (or without) Music :blue_book: ##

**It is strongly recommended** that you also read `!help gmscreen` so you can do your prep in secret!

Every adventure has passages of text that must be given to the players at each new scene.
You no longer need to type these out in real time! Now you can prepare the texts in advance via the bot, and deploy them easily later.

!**setscene** name musicLink sceneText<br/>
Creates or updates a named scene. The music link is optional. Scene text can have line breaks and formatting, and is only limited by Discord message length limits.<br/>
**Example 1:** `!setscene example1 https://www.youtube.com/watch?v=zsq-tAz54Pg The orks burst through the door carrying uzis and a grudge.`<br/>
**Example 2:** `!setscene example2 Suddenly the band stops playing as everyone stares at you in horror.`

!**getscene** name<br/>
Deploys the named scene. The name of the scene is **not** displayed in the output. Music (if any) is shown as a link, with Discord's embedded player below that.

!**listscenes**<br/>
Shows a list of scene names that you've saved to the current channel (or play channel, if you're using the virtual GM Screen feature).

!**delscene** name<br/>
Deletes one or more scenes identified by name(s). To delete multiple scenes, simply put spaces between the names. **Deleted scenes cannot be recovered!**

## :ninja: Virtual GM Screen :ninja: ##

Using this feature, **ammo tracking**, **reminders**, **initiative** and **scene** commands can be done in a hidden channel.

Players still need to **!setgm** and **!setinit** in the play channel.

**It's simple!**

Step :one:: Go to your hidden channel<br/>
This will be the channel where you do all your prep from now on.

Step :two:: **!setchannel** linkToPlayChannel<br/>
Your "play channel" is the channel players have access to; your main channel for the game.<br/>
You make a channel link by typing the # sign and typing the channel name or choosing it from the pop-up menu.<br/>
**If the channel name is highlighted blue, you did it right.**

Step :three:: Do your prep!

**Notes about running various commands behind the GM screen:**<br/>
:arrow_forward: !getscene will output to the play channel so you don't need to reveal your scene titles.<br/>
:arrow_forward: You can now run !init in secret, or you can prep your NPC's in the secret channel and then do the !init command in the play channel.

## :alarm_clock: Reminders :alarm_clock: ##

The bot can DM reminders of your upcoming game sessions to your players.

**!addreminder** sessionDate&Time timer1 timer2 etc<br/>
* *sessionDate&Time* needs the format **YYYY-MM-DD*T*HH:MM** *(note the "T" separating date from time)*
* ***sessionDate&Time*** **is now based on the GMT+0 time zone**
* Note the hour of the session must be in 24-hour format; e.g. for 6pm, you enter 18:00
* Each *timer* needs a format of minutes, hours, or days, such as **10m**, **3h**, **7d** etc
* **Example:** `!addreminder 2022-05-04T18:00 30m 6h 1d 3d 7d`
Sets a game session at 6pm on May 4, and five reminders (30 minutes before the session, etc)
* The reminders will go to everyone you've got in your players list at the time when you added the reminder.
* To manage your players list, see the `!setplayers`, `!addplayers`, etc commands under `!help init`

**!listreminders**<br/>
* Shows a list of your upcoming reminders, and the ID's you'd use to cancel them if necessary, plus who they're going to.
* Due to Discord message size-limits this command can be slow if you have more than a few reminders.

**!cancelreminder** id#1 id#2 etc<br/>
Cancels one or more reminders. See `!listreminders` to get the ID's.

## :gun: **Ammo Tracking** :gun: ##

GameBot can track ammo during combat, enforcing max ROF and weapon capacity.

**!ammo addgun** name maxROF ammoContainerType ammoCapacity ammoTypes<br/>
Adds a weapon for ammo tracking purposes. The name must not have any spaces or commas.<br/>
If the gun is compatible with multiple types of round, separate them with spaces.<br/>
You should keep the name short, since you'll be typing it for the `!ammo fire` and `!ammo reload` commands.<br/>
If the rules don't specify maxROF any other way, don't forget autofire is Skill Rating +1.<br/>
**Example:** `!ammo addgun uzi3 7 clip 16 slug`

**!ammo delgun** name<br/>
**Example:** `!ammo delgun uzi3`<br/>
Removes the uzi3 from your inventory.

**!ammo addammo** qtyContainers containerType qtyRounds roundType maxRounds<br/>
The maxRounds should match the ammoCapacity of the gun you want to use this ammo for.<br/>
The roundType should match one of the ammoTypes for the matching weapon.<br/>
**Example:** `!ammo addammo 10 clip 16 slug 16`<br/>
Adds 10 clips that are fully loaded with 16 slugs each. This matches the uzi3.

**!ammo delammo** qtyContainers containerType qtyRounds roundType maxRounds<br/>
**Example:** `!ammo delammo 4 clip 16 slug 16`<br/>
Removes 4 of those clips for your uzi3 from your inventory.

**!ammo list**<br/>
Shows a list of guns, and what they're loaded with, plus a list of your ammo.<br/>
Empty clips are not shown, so track those yourself.

**!ammo fire** weaponName nbrShots<br/>
Depletes a number of rounds (nbrShots) from the gun identified by weaponName, assuming nbrShots doesn't exceed the gun's maxROF.<br/>
If you try to shoot more rounds than are currently loaded, the weapon will be depleted of all ammo and you will be told how many rounds were shot before the weapon clicked empty.

**!ammo reload** weaponName<br/>or<br/>**!ammo reload** weaponName shotType<br/>
The first form assumes you only have one compatible ammo type for that weapon.<br/>
**Example:** `!ammo reload uzi3`<br/>
The second form allows you to specify which type of round you want to load, for cases where your weapon has multiple compatible ammoTypes *and* you have compatible ammo entries for 2 or more of those ammoTypes.<br/>
**Example:** `!ammo reload enfield shot`

## Misc ##

  Commands are not case-sensitive. Go WiLd WitH tHaT.

  You can find my Patreon at https://patreon.com/nathanhawks if this bot helps you game.

## Legal

This software is released as-is under the terms of the UnLicense; it is available to the public domain.
