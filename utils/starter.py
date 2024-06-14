import os
from utils.vertus import Vertus
from utils.core import logger
import datetime
import pandas as pd
from utils.telegram import Accounts
from aiohttp.client_exceptions import ContentTypeError
import asyncio


async def start(thread: int, session_name: str, phone_number: str, proxy: [str, None]):
    vertus = Vertus(session_name=session_name, phone_number=phone_number, thread=thread, proxy=proxy)
    account = session_name + '.session'

    if await vertus.login():
        logger.success(f"Thread {thread} | {account} | Login")
        while True:
            try:
                data = await vertus.get_data()

                if not await vertus.is_activated(data):
                    wallet = await vertus.create_wallet()
                    logger.success(f"Thread {thread} | {account} | Create wallet: {wallet}")

                if await vertus.can_collect_first(data):
                    amount = await vertus.first_collect()
                    logger.success(f"Thread {thread} | {account} | First collect {amount} VERT")

                storage = vertus.get_storage(data)

                if storage >= 0.003:
                    status, balance = await vertus.collect()
                    if status == 201:
                        logger.success(f"Thread {thread} | {account} | Collect VERT! New balance: {balance}")
                    else:
                        logger.error(f"Thread {thread} | {account} | Can't collect VERT! Response {status}: {balance}")
                        continue

                balance = vertus.get_balance(data)
                farm, population = vertus.get_upgrades(data)

                if farm['priceToLevelUp'] < population['priceToLevelUp'] and balance >= farm['priceToLevelUp']:
                    upgrade = "farm"
                elif farm['priceToLevelUp'] > population['priceToLevelUp'] and balance >= population['priceToLevelUp']:
                    upgrade = "population"
                elif farm['priceToLevelUp'] == population['priceToLevelUp'] and balance >= population['priceToLevelUp']:
                    upgrade = "farm"
                else:
                    upgrade = ""

                if upgrade:
                    status, balance = await vertus.upgrade(upgrade)
                    if status == 201:
                        logger.success(f"Thread {thread} | {account} | Upgrade {upgrade}! New balance: {balance}")
                    else:
                        logger.error(f"Thread {thread} | {account} | Can't upgrade {upgrade}! Response {status}: {balance}")

                if vertus.can_claim_daily_reward(data):
                    status, claim_count = await vertus.claim_daily_reward()
                    if status == 201:
                        logger.success(f"Thread {thread} | {account} | Claim daily reward: {claim_count} VERT!")
                    else:
                        logger.error(f"Thread {thread} | {account} | Can't claim daily reward! Response {status}: {claim_count}")
                await asyncio.sleep(10)
            except ContentTypeError as e:
                logger.error(f"Thread {thread} | {account} | Error: {e}")
                await asyncio.sleep(120)

            except Exception as e:
                logger.error(f"Thread {thread} | {account} | Error: {e}")
                await asyncio.sleep(5)

    else:
        await vertus.logout()


async def stats():
    accounts = await Accounts().get_accounts()

    tasks = []
    for thread, account in enumerate(accounts):
        session_name, phone_number, proxy = account.values()
        tasks.append(asyncio.create_task(Vertus(session_name=session_name, phone_number=phone_number, thread=thread, proxy=proxy).stats()))

    data = await asyncio.gather(*tasks)

    path = f"statistics/statistics_{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
    columns = ['Registered', 'Phone number', 'Name', 'Balance', 'Referrals', 'Referral link', 'Wallet', 'Proxy (login:password@ip:port)']

    if not os.path.exists('statistics'): os.mkdir('statistics')
    df = pd.DataFrame(data, columns=columns)
    df.to_csv(path, index=False, encoding='utf-8-sig')

    logger.success(f"Saved statistics to {path}")
