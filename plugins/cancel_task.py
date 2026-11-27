from pyrogram import Client, filters, StopPropagation
from helper.utils import ACTIVE_TASKS, QUEUE_WAITING, task_key, safe_delete


# group=-1  -> start_and_cb.py-la irukkura catch-all callback-ku munnaadi run aagum
@Client.on_callback_query(filters.regex(r"^cancel_task$"), group=-1)
async def cancel_task_cb(client, query):
    key = task_key(query.message)
    task = ACTIVE_TASKS.get(key)

    if task and not task.done():
        await query.answer("❌ Cancelling...")
        task.cancel()
    else:
        await query.answer("⚠️ Process already finished.")
        await safe_delete(query.message)

    raise StopPropagation


# Single "Queue N" message-la irukkura Cancel -> queue-la kadaisiya serndha link / file remove aagum
@Client.on_callback_query(filters.regex(r"^cancel_queue$"), group=-1)
async def cancel_queue_cb(client, query):
    chat_id = query.message.chat.id
    mine = [s for s in QUEUE_WAITING if s.chat_id == chat_id]

    task = ACTIVE_TASKS.get(task_key(mine[-1].msg)) if mine else None
    if task and not task.done():
        await query.answer("❌ Last item queue-la irunthu remove aachu")
        task.cancel()
    else:
        await query.answer("⚠️ Queue-la edhuvum illa")

    raise StopPropagation
