"""
Helper script to get user IDs from a group.
Run this once to find the IDs of User A and User B.
"""
import asyncio
from telethon import TelegramClient
from config import API_ID, API_HASH, PHONE_NUMBER, SOURCE_GROUPS

client = TelegramClient('session', API_ID, API_HASH)


async def get_user_ids():
    """Print all user IDs in the source groups."""
    await client.start()
    
    if not await client.is_user_authorized():
        await client.send_code_request(PHONE_NUMBER)
        code = input('Enter the code you received: ')
        try:
            await client.sign_in(PHONE_NUMBER, code)
        except Exception as e:
            if 'password' in str(e).lower():
                password = input('Enter your 2FA password: ')
                await client.sign_in(password=password)
    
    # Process all source groups
    for group_identifier in SOURCE_GROUPS:
        try:
            group = await client.get_entity(group_identifier)
            print(f"\n📋 Members in '{group.title or group.username}':\n")
            
            async for user in client.iter_participants(group):
                if not user.bot and not user.deleted:
                    username = f"@{user.username}" if user.username else "No username"
                    print(f"  {user.first_name} {user.last_name or ''} ({username})")
                    print(f"    ID: {user.id}\n")
        except Exception as e:
            print(f"Error accessing group '{group_identifier}': {e}")


if __name__ == '__main__':
    asyncio.run(get_user_ids())