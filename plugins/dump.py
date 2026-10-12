import asyncio
from pyrogram import Client, filters
from helper.database import goku_stark

@Client.on_message(filters.private & filters.command("dump"))
async def add_dump(client, message):
    rkn = await message.reply_text("⏳ **Processing...**")

    if len(message.command) == 1:
        await rkn.edit(
            "❌ **Please provide a Dump Channel ID.**\n\n"
            "📝 **Example:** `/dump -1001234567890`"
        )
    else:
        try:
            dump_id = int(message.text.split(" ", 1)[1])
            await goku_stark.set_dump(message.from_user.id, dump_id=dump_id)
            await rkn.edit(
                f"✅ **Dump Channel Set Successfully!**\n\n"
                f"🆔 **Channel ID:** `{dump_id}`"
            )
        except ValueError:
            await rkn.edit(
                "❌ **Invalid Channel ID!**\n\n"
                "🔢 Please enter numbers only."
            )

    # Auto Delete Both Messages after 10 Seconds
    await asyncio.sleep(10)
    try:
        await message.delete()
        await rkn.delete()
    except:
        pass

@Client.on_message(filters.private & filters.command(["del_dump", "delete_dump"]))
async def delete_dump(client, message):
    rkn = await message.reply_text("⏳ **Processing...**")
    
    dump_id = await goku_stark.get_dump(message.from_user.id)
    if not dump_id:
        await rkn.edit(
            "⚠️ **No Dump Channel Found!**\n\n"
            "Please set a Dump Channel first."
        )
    else:
        await goku_stark.set_dump(message.from_user.id, dump_id=None)
        await rkn.edit(
            "🗑️ **Dump Channel Removed Successfully!**"
        )

    # Auto Delete Both Messages after 10 Seconds
    await asyncio.sleep(10)
    try:
        await message.delete()
        await rkn.delete()
    except:
        pass

@Client.on_message(filters.private & filters.command(["see_dump", "view_dump"]))
async def see_dump(client, message):
    rkn = await message.reply_text("⏳ **Processing...**")

    dump_id = await goku_stark.get_dump(message.from_user.id)

    if dump_id:
        await rkn.edit(
            f"📦 **Your Dump Channel**\n\n"
            f"🆔 **Channel ID:** `{dump_id}`"
        )
    else:
        await rkn.edit(
            "⚠️ **No Dump Channel Found!**\n\n"
            "Please set a Dump Channel first."
        )
        
    # Auto Delete Both Messages after 10 Seconds
    await asyncio.sleep(10)
    try:
        await message.delete()
        await rkn.delete()
    except:
        pass
