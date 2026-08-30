# 바이낸스 비동기 가격 수신 함수
async def  receive_binance_price(symbol):
    import aiohttp
    import asyncio

    url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    price = data['p']  # 가격 정보
                    print(f"Symbol: {symbol}, Price: {price}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

            
