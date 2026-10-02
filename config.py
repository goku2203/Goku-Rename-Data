import re, os, time
id_pattern = re.compile(r'^.\d+$') 

class Config(object):
    # digital_botz client config
    API_ID = os.environ.get("API_ID", "25169055")
    API_HASH = os.environ.get("API_HASH", "d70362ef232cc5ec4cb0b8d1ba6cc60e")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "7706580536:AAH6l8NhZsSIGxiOJQmqcZJrKyMloCIyMHw") 
    BOT = None

    # premium account string session required 😢 
    STRING_SESSION = os.environ.get("STRING_SESSION", "")
    
    # database config
    DB_NAME = os.environ.get("DB_NAME","Digital_Auto_Rename_Bot")     
    DB_URL = os.environ.get("DB_URL","mongodb+srv://masamin643_db_user:aqunP8EES9YndDQt@cluster0.rgnbdf5.mongodb.net/?appName=Cluster0")
 
    # other configs
    RKN_PIC = os.environ.get("RKN_PIC", "https://files.catbox.moe/94kw2e.jpg")
    ADMIN = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMIN', '6629872386').split()]
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1003742596813"))

    # free upload limit 
    FREE_UPLOAD_LIMIT = 6442450944 # calculation 6*1024*1024*1024=results

    # premium mode feature ✅
    UPLOAD_LIMIT_MODE = True 
    PREMIUM_MODE = True 
    
    #force subs
    try:
        FORCE_SUB = int(os.environ.get("FORCE_SUB", "goku_n")) 
    except:
        FORCE_SUB = os.environ.get("FORCE_SUB", "goku_n")
        
    # wes response configuration     
    PORT = int(os.environ.get("PORT", "8080"))
    BOT_UPTIME = time.time()
