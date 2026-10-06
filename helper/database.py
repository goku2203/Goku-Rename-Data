# (c) @RknDeveloperr
# Rkn Developer 
# Don't Remove Credit 😔
# Telegram Channel @RknDeveloper & @Rkn_Botz
# Developer @RknDeveloperr
# Special Thanks To (https://github.com/JayMahakal98)
# Update Channel @Digital_Botz & @DigitalBotz_Support

import motor.motor_asyncio, datetime, pytz
from config import Config
from helper.utils import send_log

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.user
        
    def new_user(self, id):
        return dict(
            _id=int(id),
            file_id=None,
            caption=None,
            prefix=None,
            suffix=None,
            dump_id=None,
            watermark=None,
            scale=None,
            join_date=datetime.date.today().isoformat(),
            format_template="{filename}",            
            upload_type=None,
            rename_mode="auto",
            ban_status=dict(
                is_banned=False,
                ban_duration=0,
                banned_on=datetime.date.max.isoformat(),
                ban_reason=''
            )
        )

    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            user = self.new_user(u.id)
            await self.col.insert_one(user)            
            await send_log(b, u)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return bool(user)

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.col.find({})
        return all_users

    async def delete_user(self, user_id):
        await self.col.delete_many({'_id': int(user_id)})

    async def set_thumbnail(self, id, file_id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'file_id': file_id}})

    async def get_thumbnail(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('file_id', None)

    async def set_caption(self, id, caption):
        await self.col.update_one({'_id': int(id)}, {'$set': {'caption': caption}})
        
    async def get_caption(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('caption', None)

    async def get_user_data(self, id) -> dict:
        user_data = await self.col.find_one({'_id': int(id)})
        return user_data or None
            
    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_duration=0,
            banned_on=datetime.date.max.isoformat(),
            ban_reason=''
        )
        await self.col.update_one({'_id': int(id)}, {'$set': {'ban_status': ban_status}})

    async def ban_user(self, user_id, ban_duration, ban_reason):
        ban_status = dict(
            is_banned=True,
            ban_duration=ban_duration,
            banned_on=datetime.date.today().isoformat(),
            ban_reason=ban_reason)
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_duration=0,
            banned_on=datetime.date.max.isoformat(),
            ban_reason='')
        user = await self.col.find_one({'_id': int(id)})
        return user.get('ban_status', default)

    async def get_all_banned_users(self):
        banned_users = self.col.find({'ban_status.is_banned': True})
        return banned_users
    
    async def add_user_format_template(self, user_id: int, template: str):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {"format_template": template}},
            upsert=True
        )

    async def get_format_template(self, user_id: int):
        user = await self.col.find_one({"_id": int(user_id)})
        return user.get("format_template") if user else None

    async def set_upload_type(self, id, upload_type):
        await self.col.update_one({'_id': int(id)}, {'$set': {'upload_type': upload_type}})

    async def get_upload_type(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('upload_type', None) if user else None

    async def set_rename_mode(self, id, rename_mode):
        await self.col.update_one({'_id': int(id)}, {'$set': {'rename_mode': rename_mode}})

    async def get_rename_mode(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('rename_mode', 'auto') if user else 'auto'

    async def set_prefix(self, id, prefix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'prefix': prefix}})

    async def get_prefix(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('prefix', None) if user else None

    async def set_suffix(self, id, suffix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'suffix': suffix}})

    async def get_suffix(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('suffix', None) if user else None

    async def set_dump(self, id, dump_id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'dump_id': dump_id}})

    async def get_dump(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('dump_id', None) if user else None

    async def set_watermark(self, id, watermark):
        await self.col.update_one({'_id': int(id)}, {'$set': {'watermark': watermark}})

    async def get_watermark(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('watermark', None) if user else None

    async def set_wm_scale(self, id, scale):
        await self.col.update_one({'_id': int(id)}, {'$set': {'wm_scale': float(scale)}})

    async def get_wm_scale(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return float(user.get('wm_scale', 1.0)) if user else 1.0
    
digital_botz = Database(Config.DB_URL, Config.DB_NAME)
