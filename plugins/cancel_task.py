from pyrogram import Client, filters, StopPropagation
from helper.utils import ACTIVE_TASKS, task_key, safe_delete


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
