import random
import time
from datetime import datetime
from utils.core import logger
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestWebView
import asyncio
from urllib.parse import unquote, quote
from data import config
import aiohttp
from fake_useragent import UserAgent
from aiohttp_socks import ProxyConnector


class Vertus:
    def __init__(self, thread: int, session_name: str, phone_number: str, proxy: [str, None]):
        self.account = session_name + '.session'
        self.thread = thread
        self.proxy = f"{config.PROXY_TYPES['REQUESTS']}://{proxy}" if proxy is not None else None
        connector = ProxyConnector.from_url(self.proxy) if proxy else aiohttp.TCPConnector(verify_ssl=False)

        if proxy:
            proxy = {
                "scheme": config.PROXY_TYPES['TG'],
                "hostname": proxy.split(":")[1].split("@")[1],
                "port": int(proxy.split(":")[2]),
                "username": proxy.split(":")[0],
                "password": proxy.split(":")[1].split("@")[0]
            }

        self.client = Client(
            name=session_name,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            workdir=config.WORKDIR,
            proxy=proxy,
            lang_code='ru'
        )

        headers = {'User-Agent': UserAgent(os='android').random}
        self.session = aiohttp.ClientSession(headers=headers, trust_env=True, connector=connector)

    async def buy_upgrade_card(self, card_id: str):
        resp = await self.session.post('https://api.thevertus.app/upgrade-cards/upgrade', json={'cardId': card_id})
        resp_json = await resp.json()

        return resp.status, self.from_nano(resp_json.get('balance')) if resp_json.get("isSuccess") else await resp.text(), resp_json.get('cards')

    async def get_profitable_upgrade_card(self, balance, upgrade_cards: [dict, None] = None):
        if upgrade_cards:
            upgrade_cards = upgrade_cards.get('economyCards') + upgrade_cards.get('militaryCards') + upgrade_cards.get('scienceCards')
        else:
            upgrade_cards = await self.get_upgrades_cards()

        cards = []
        for card in upgrade_cards:
            if not card['isLocked'] and card['isUpgradable'] and self.from_nano(card['levels'][card['currentLevel']]['cost']) <= balance:
                cards.append({
                    "id": card['_id'],
                    "profitability": card['levels'][card['currentLevel']]['value'] / card['levels'][card['currentLevel']]['cost'],
                    "title": card['cardName'],
                    "category": card['type']
                })

        return max(cards, key=lambda x: x["profitability"]) if cards else None

    async def get_upgrades_cards(self):
        resp = await self.session.get('https://api.thevertus.app/upgrade-cards')
        r = await resp.json()

        return r.get('economyCards') + r.get('militaryCards') + r.get('scienceCards')

    async def stats(self):
        await self.login()
        data = await self.get_data()

        registered = '✅' if data.get('activated') else '❌'
        balance = self.from_nano(data.get('balance'))
        wallet = data.get('walletAddress')
        referral_link = 'https://t.me/vertus_app_bot/app?startapp=' + str(data.get('telegramId'))

        referrals = (await (await self.session.post('https://api.thevertus.app/users/get-referrals/1', json={})).json()).get('total')

        await self.logout()

        await self.client.connect()
        me = await self.client.get_me()
        phone_number, name = "'" + me.phone_number, f"{me.first_name} {me.last_name if me.last_name is not None else ''}"
        await self.client.disconnect()

        proxy = self.proxy.replace(f'{config.PROXY_TYPES["REQUESTS"]}://', "") if self.proxy is not None else '-'
        return [registered, phone_number, name, str(balance), str(referrals), referral_link, wallet, proxy]

    def can_claim_daily_reward(self, data):
        if data.get("dailyRewards").get('lastRewardClaimed') is None: return True
        return self.iso_to_unix_time(data.get("dailyRewards").get('lastRewardClaimed')) + 86400 < self.current_time()

    async def claim_daily_reward(self):
        resp = await self.session.post("https://api.thevertus.app/users/claim-daily", json={})
        resp_json = await resp.json()

        return resp.status, self.from_nano(resp_json.get('claimed')) if resp_json.get("success") else await resp.text()

    async def upgrade(self, upgrade):
        json_data = {"upgrade": upgrade}
        resp = await self.session.post('https://api.thevertus.app/users/upgrade', json=json_data)
        resp_json = await resp.json()

        return resp.status, self.from_nano(resp_json.get('newBalance')) if resp_json.get("success") else await resp.text()

    async def collect(self):
        resp = await self.session.post('https://api.thevertus.app/game-service/collect', json={})
        return resp.status, self.from_nano((await resp.json()).get('newBalance')) if resp.status == 201 else await resp.text()

    def get_storage(self, data):
        return self.from_nano(data.get('vertStorage'))

    def get_balance(self, data):
        return self.from_nano(data.get('balance'))

    async def first_collect(self):
        resp = await self.session.post('https://api.thevertus.app/game-service/collect-first', json={})
        return self.from_nano((await resp.json()).get('newBalance'))

    async def get_data(self):
        resp = await self.session.post('https://api.thevertus.app/users/get-data', json={})
        return (await resp.json()).get('user')

    async def create_wallet(self):
        resp = await self.session.post('https://api.thevertus.app/users/create-wallet', json={})
        return (await resp.json()).get('walletAddress')

    @staticmethod
    def get_offline_profit(data):
        return data.get('earnedOffline')

    @staticmethod
    def get_upgrades(data):
        return data.get('abilities').get('farm').get('priceToLevelUp'), data.get('abilities').get('population').get('priceToLevelUp')

    @staticmethod
    def iso_to_unix_time(iso_time: str):
        return int(datetime.strptime(iso_time, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()) + 1

    @staticmethod
    def current_time():
        return int(time.time())


    @staticmethod
    async def can_collect_first(data):
        return not data.get('storage') and not data.get('balance')

    @staticmethod
    async def is_activated(data):
        return data.get('activated')

    @staticmethod
    def from_nano(amount: int):
        return amount/1e18

    @staticmethod
    def to_nano(amount: int):
        return amount*1e18

    async def logout(self):
        await self.session.close()

    async def login(self):
        await asyncio.sleep(random.uniform(*config.DELAYS['ACCOUNT']))
        query = await self.get_tg_web_data()

        if query is None:
            logger.error(f"Thread {self.thread} | {self.account} | Session {self.account} invalid")
            await self.logout()
            return None

        self.session.headers['Authorization'] = 'Bearer ' + query
        return True

    async def get_tg_web_data(self):
        try:
            await self.client.connect()
            web_view = await self.client.invoke(RequestWebView(
                peer=await self.client.resolve_peer('Vertus_App_bot'),
                bot=await self.client.resolve_peer('Vertus_App_bot'),
                platform='android',
                from_bot_menu=False,
                url='https://t.me/vertus_app_bot/app'
            ))

            await self.client.disconnect()
            auth_url = web_view.url

            query = unquote(string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
            query_id = query.split('query_id=')[1].split('&user=')[0]
            user = quote(query.split("&user=")[1].split('&auth_date=')[0])
            auth_date = query.split('&auth_date=')[1].split('&hash=')[0]
            hash_ = query.split('&hash=')[1]

            return f"query_id={query_id}&user={user}&auth_date={auth_date}&hash={hash_}"
        except:
            return None
