"""
run with JSK,
,jsk py
from cogs.lore.to_db import convert_to_db
await convert_to_db(bot.db)
"""

import os
import json


async def convert_to_db(db):
    def check_values(lore: dict):
        if not lore.get("content"):
            return False
        if not lore.get("message_id"):
            return False
        return True

    path = "Lorebooks"
    if not os.path.exists(path):
        print(f"Path {path} does not exist.")
        return
    files = os.listdir(path)
    async with db.acquire() as conn:
        for file in files:
            with open(f"{path}/{file}", "r") as fc:
                res = json.loads(fc.read())
                for lore in res:
                    user_id = int(
                        fc.name.replace(".json", "").replace("Lorebooks/", "")
                    )
                    if not check_values(lore):
                        continue
                    try:
                        await conn.execute(
                            """
                            INSERT INTO lore (id, user_id, content)
                            VALUES ($1, $2, $3)
                        """,
                            lore["message_id"],
                            user_id,
                            lore["content"],
                        )
                    except Exception as e:
                        print(
                            f"Error inserting lore for user {user_id} with message ID {lore['message_id']}: {e}"
                        )
                        continue
