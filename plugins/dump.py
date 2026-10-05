from pyrogram import Client, filters
from helper.database import digital_botz

@Client.on_message(filters.private & filters.command('dump'))
async def add_dump(client, message):
    rkn = await message.reply_text("__**Processing...**__")
    if len(message.command) == 1:
       return await rkn.edit("**__Dump Channel ID kudu bro__\n\nEx :- `/dump -1001234567890`**")
    try:
        dump_id = int(message.text.split(" ", 1)[1])
    except ValueError:
        return await rkn.edit("**__Dump Channel ID numbers la mattum thaan irukkanum!__**")
    await digital_botz.set_dump(message.from_user.id, dump_id=dump_id)
    await rkn.edit(f"**Dump Channel ID super a set aaiduchu:** `{dump_id}`")

@Client.on_message(filters.private & filters.command(['del_dump', 'delete_dump']))
async def delete_dump(client, message):
    rkn = await message.reply_text("__**Processing...**__")
    dump_id = await digital_botz.get_dump(message.from_user.id)
    if not dump_id:
       return await rkn.edit("**__Neenga innum entha Dump Channel ID yum set pannala!__**")
    await digital_botz.set_dump(message.from_user.id, dump_id=None)
    await rkn.edit("**__Dump Channel ID Delete aaiduchu!__**")

@Client.on_message(filters.private & filters.command(['see_dump', 'view_dump']))
async def see_dump(client, message):
    rkn = await message.reply_text("__**Processing...**__")
    dump_id = await digital_botz.get_dump(message.from_user.id)
    if dump_id:
       await rkn.edit(f"**Unga Dump Channel ID :-**\n\n`{dump_id}`")
    else:
       await rkn.edit("**__Neenga innum entha Dump Channel ID yum set pannala!__**")
