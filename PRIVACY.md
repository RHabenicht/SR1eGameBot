# Privacy Policy

Last updated: October 29, 2026

This policy covers the hosted SR1e-3e GameBot maintained by NightLife (`.nightlife` on Discord). It describes the bot's handling of data. Discord and other services have their own privacy policies.

## Data the bot receives

Discord supplies messages and related account, server, and channel information where the bot has access. The bot checks message text for commands and uses Discord identifiers to associate game settings with the correct people and channels. It also receives reaction events used to reroll dice.

The bot processes command text and dice results. Its saved records can include:

- Discord user, server, and channel IDs, including player and GM associations.
- Saved dice macros, initiative formulas, NPC labels, and player lists.
- Fictional weapons, ammunition inventories, and ammunition counts.
- Prepared scene text, music links, and private-GM-channel settings.
- Session dates, reminder schedules, and the Discord IDs of reminder recipients.
- User preferences and optional account-linking codes submitted through bot commands.

Runtime logs can contain Discord IDs, timestamps, error information, and game or command data. Debug logging can include saved content. Keep real credentials and sensitive personal information out of commands and scene text.

## How the data is used

Data is used to run the requested game features, restore saved settings after restarts, send scheduled reminders, investigate faults, and handle support or deletion requests. I do not sell bot data or use it for advertising.

## Where data goes and who can see it

Saved records are held in the bot's MongoDB database. Hosting and database service providers process data as needed to operate that infrastructure. The maintainer can access stored data and logs for operation, support, security work, and deletion requests.

Command results appear in the Discord channel used by the feature or its configured play channel. Reminders are sent by direct message to their saved recipients. Server permissions determine who can read a channel, including a private GM channel.

Application encryption does not prevent the maintainer from accessing stored data. Some information can also appear in plaintext logs or Discord messages.

Discord processes messages and account information under its [Privacy Policy](https://discord.com/privacy). If you follow an external music or other link, that service's policies apply to your visit.

## Retention and deletion

Saved records currently have no automatic expiry. Use the relevant commands to remove individual macros, scenes, ammunition entries, or reminders. Those commands do not necessarily remove every related account or channel record.

Deleting a Discord message or removing the bot from a server does not automatically erase the bot's saved database records.

For access to your stored data or a deletion request, contact NightLife (`.nightlife`) on Discord. Provide your Discord user ID and the server or channel IDs needed to identify the records. I may ask you to verify control of the account or server before releasing or removing data. Do not send passwords or bot tokens.

After verifying a valid request, I will remove the relevant records from active bot storage, subject to any retention required by law. Hosting logs and any backup copies follow their configured retention settings; I will explain any limits that apply to your request. Deleting bot records does not delete messages or copies held independently by Discord or other users.

## Changes and questions

Changes to this policy will be posted here with an updated date. Contact NightLife (`.nightlife`) on Discord with questions about the bot's handling of your data.
