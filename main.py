import asyncio
import playwright
import requests
from playwright.async_api import async_playwright, Playwright
import aio_pika
import json



#hardcode the url for now
# async def fetch_page_content(playwright: Playwright, url: str) -> str:
#    # browser = await playwright.chromium.launch(headless=True)
#     #page = await browser.new_page()
#     #html = await page.goto(url)
#     #content = await html.text()
#     content = requests.get(url).text
#     #await browser.close()
#     return content

# async def main():
#     url = "https://nvd.nist.gov/vuln/search#/nvd/home?sortOrder=3&sortDirection=2&offset=0&rowCount=25&resultType=records"
#     async with async_playwright() as playwright:
#        html = await fetch_page_content(playwright, url)
#        print(html)

# asyncio.run(main())

def get_vulnerabilities():    
#url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    url = "https://nvd.nist.gov/extensions/nudp/services/json/nvd/cve/search/results"
    params = {
        "resultType": "records",
        "sortOrder": "3",
        "sortDirection": "2",
        "offset": "0",
        "rowCount": "25"
    }
    print(url)

    #spoofing the headers to mimic a browser request for now
    #todo: go to https://nvd.nist.gov and click on Developers. From there should find the API docs and proper way to call it
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://nvd.nist.gov/vuln/search",
        "X-Requested-With": "XMLHttpRequest"
    }


    response = requests.get(url, params=params, headers=headers)
    data = response.json()

    vulnerabilities = data["response"][0]["grid"]["vulnerabilities"]

        # for item in vulnerabilities:
        #     cve = item["cve"]
        #     print(cve["id"], "-", cve["descriptions"][0]["value"])

    oneCve = vulnerabilities[0]["cve"]
    print(oneCve["id"], "-", oneCve["descriptions"][0]["value"])
    asyncio.run(sendMsgRabbitMQ(oneCve))

async def sendMsgRabbitMQ(message: str):
   # async def main():
        # Connect to RabbitMQ server
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
        async with connection:
            # Create a channel
            channel = await connection.channel()
            # Declare a queue
            queue = await channel.declare_queue("cve_queue", durable=True)
            # Send a message
            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue.name,
            )            
           
            print(f" [x] Sent {message}")

def main():  
    get_vulnerabilities()

if __name__ == "__main__":
    main()

