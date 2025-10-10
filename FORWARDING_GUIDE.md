# Message Forwarding Guide

This guide explains how to set up message forwarding to Telegram channels and Discord webhooks.

## Telegram Channel Forwarding

### Setup Steps:

1. **Create a Telegram Channel**
   - Open Telegram and create a new channel
   - Make it private or public based on your needs

2. **Add Your Bot to the Channel**
   - Go to channel settings → Administrators
   - Click "Add Administrator"
   - Search for your bot and add it
   - Give it permission to post messages

3. **Get the Channel ID**
   - Forward a message from your channel to @userinfobot
   - It will reply with the channel ID (e.g., `-1001234567890`)
   - Or use @getidsbot for the same purpose

4. **Use the Channel ID**
   - When running the bot dumper, enter the channel ID when prompted
   - You can use the full ID with `-100` prefix or just the numeric part

### Example:
```
Telegram channel ID to forward to: -1001234567890
```

## Discord Webhook Forwarding

### Setup Steps:

1. **Create a Discord Webhook**
   - Go to your Discord server
   - Right-click on the channel where you want messages
   - Select "Edit Channel" → "Integrations" → "Webhooks"
   - Click "New Webhook"
   - Give it a name and copy the webhook URL

2. **Use the Webhook URL**
   - When running the bot dumper, paste the webhook URL when prompted

### Example:
```
Discord webhook URL: https://discord.com/api/webhooks/1234567890/abcdefghijklmnopqrstuvwxyz
```

## Important Notes

### For Group Messages:
- **Privacy Mode must be disabled** for the bot to receive all group messages
- By default, bots only receive:
  - Direct messages
  - Messages that mention the bot (@botname)
  - Commands (starting with /)

### To Disable Privacy Mode:
1. Open @BotFather in Telegram
2. Send `/setprivacy`
3. Select your bot
4. Choose "Disable"
5. Now your bot will receive ALL messages in groups where it's a member

### Message Format:

**Telegram Channel:**
- Messages are formatted with markdown
- Includes chat type, sender ID, timestamp
- Media is forwarded with captions

**Discord Webhook:**
- Messages are sent as embeds
- Color-coded by chat type (Blue=Private, Green=Group, Purple=Channel)
- Includes all metadata in embed fields

## Troubleshooting

### Bot Not Receiving Group Messages:
1. Check if Privacy Mode is disabled in @BotFather
2. Ensure the bot is a member of the group
3. Check if the group has restricted bot access

### Telegram Forwarding Not Working:
1. Verify the bot is an administrator in the target channel
2. Check that the channel ID is correct (with -100 prefix)
3. Ensure the bot has permission to post messages

### Discord Forwarding Not Working:
1. Verify the webhook URL is correct and active
2. Check that the webhook hasn't been deleted
3. Ensure the channel still exists

## Privacy Considerations

- All forwarded messages include sender IDs and chat IDs
- Media files are forwarded to Telegram but not to Discord (URLs only)
- Consider the privacy implications before forwarding sensitive conversations
- Make sure you have permission to forward messages from groups/channels
