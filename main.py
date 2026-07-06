import asyncio
from logging import Logger

from atribot.bot_framework import BotFramework
from atribot.core.service_container import container

logo_tmpl = r"""
_____/\\\\\\\\\____        __/\\\\\\\\\\\\\\\_        ____/\\\\\\\\\_____        __/\\\\\\\\\\\_        
 ___/\\\\\\\\\\\\\__        _\///////\\\/////__        __/\\\///////\\\___        _\/////\\\///__       
  __/\\\/////////\\\_        _______\/\\\_______        _\/\\\_____\/\\\___        _____\/\\\_____      
   _\/\\\_______\/\\\_        _______\/\\\_______        _\/\\\\\\\\\\\/____        _____\/\\\_____     
    _\/\\\\\\\\\\\\\\\_        _______\/\\\_______        _\/\\\//////\\\____        _____\/\\\_____    
     _\/\\\/////////\\\_        _______\/\\\_______        _\/\\\____\//\\\___        _____\/\\\_____   
      _\/\\\_______\/\\\_        _______\/\\\_______        _\/\\\_____\//\\\__        _____\/\\\_____  
       _\/\\\_______\/\\\_        _______\/\\\_______        _\/\\\______\//\\\_        __/\\\\\\\\\\\_ 
        _\///________\///__        _______\///________        _\///________\///__        _\///////////__
"""

async def main():
    log = container.get_by_type(Logger).getChild("Main")
    log.info(logo_tmpl)

    framework: BotFramework | None = None

    try:
        framework = await BotFramework.create()
    finally:
        if framework:
            await framework.graceful_shutdown()



if __name__ == "__main__":
    asyncio.run(main())
