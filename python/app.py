import asyncio
import os
from aiormq import AMQPConnectionError
import requests
import aio_pika
import json
import logging
import aiohttp
import sys

class App:
    
    connection = None
    channel = None
    queue = None

    # Read the host from the environment variable; default to 'localhost' for local testing
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    CONNECTION_URL = f"amqp://guest:guest@{RABBITMQ_HOST}/"

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)  # redirect to stdout
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False


    logger.info("This should show up in docker logs for python-cve service")

    async def get_vulnerabilities(self):
    #url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        url = "https://nvd.nist.gov/extensions/nudp/services/json/nvd/cve/search/results"
        params = {
            "resultType": "records",
            "sortOrder": "3",
            "sortDirection": "2",
            "offset": "0",
            "rowCount": "25"
        }
        App.logger.info("url is : " + url)

        #spoofing the headers to mimic a browser request for now
        #todo: go to https://nvd.nist.gov and click on Developers. From there should find the API docs and proper way to call it
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://nvd.nist.gov/vuln/search",
            "X-Requested-With": "XMLHttpRequest"
        }


        App.logger.info(f"Sending request to NVD API: {url} with params: {params}")
        #response = requests.get(url, params=params, headers=headers)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    App.logger.info(f"Response Status Code: {response.status}")
                    #logger.info(f"Response Data: {data}")

                    vulnerabilities = data["response"][0]["grid"]["vulnerabilities"]

                    oneCve = vulnerabilities[0]["cve"]
                    App.logger.info(f"One CVE is : {oneCve['id']} - {oneCve['descriptions'][0]['value']}")
                    App.logger.info("--------")
                    App.logger.info(oneCve)
                    #asyncio.run(sendMsgRabbitMQ(oneCve))
                    await self.sendMsgRabbitMQ(oneCve)
                else:
                    App.logger.error(f"Failed to retrieve data from NVD API: {response.status}")
                    return []

        #logger.info(f"Response Status Code: {response.status}")
        #data = response.json()

        # vulnerabilities = data["response"][0]["grid"]["vulnerabilities"]
        

        # oneCve = vulnerabilities[0]["cve"]
        # logger.info(f"{oneCve['id']} - {oneCve['descriptions'][0]['value']}")
        # #asyncio.run(sendMsgRabbitMQ(oneCve))
        # await sendMsgRabbitMQ(oneCve)

    # Connect to RabbitMQ and create queue
    async def getRabbitMQConnection(self):
        max_retries = 6
        retry_delay = 1 # seconds
        attempts = 0

        while attempts < max_retries: #retries up to max_retries times
            try:
                App.logger.info(f"yalin retry delay is : {retry_delay} seconds")
                App.logger.info(f"Connecting to: {App.CONNECTION_URL}")
                # Step 1: Establish the connection outside the 'async with' block
                App.connection = await aio_pika.connect_robust(App.CONNECTION_URL)
                App.logger.info("Connection established successfully.")

                # Step 2: Create a channel
                App.channel = await App.connection.channel()
                App.logger.info("Channel created.")

                # Step 3: Declare a queue
                App.queue = await App.channel.declare_queue("cve_queue", durable=True)
                App.logger.info(f"Queue 'cve_queue' declared.")

                # If all the above succeeds, we can return the objects
                return App.connection, App.channel, App.queue

            except (ConnectionError, AMQPConnectionError) as e:
                App.logger.error(f"yalin: {e}")  
                attempts += 1
                if attempts < max_retries:
                    App.logger.warning(f"Failed to connect to RabbitMQ: {e}. Retrying in {retry_delay} second(s)...")
                    await asyncio.sleep(retry_delay)
                else:
                    App.logger.error(f"Failed to connect to RabbitMQ after {max_retries} attempts.")
                    raise # Re-raise the final error after max retries are hit

            except Exception as e:
                App.logger.error(f"yalin2: {e}")  
                App.logger.critical(f"An unexpected error occurred: {e}")
                App.logger.critical("Exiting due to unexpected error.")
                # If an unexpected error occurs (like a channel declaration issue), re-raise it
                raise

        # This part should be unreachable if 'raise' is used correctly, but good practice to have
        return None, None, None 

    # Send message to RabbitMQ
    async def sendMsgRabbitMQ(self, message: str):
        #connection, channel, queue = await getRabbitMQConnection()
        App.logger.info("message to rabbitmq is : " + str(message))
        if not App.connection:
            App.logger.error("Failed to connect to RabbitMQ. Message not sent.")
            await asyncio.sleep(5)
            if not App.connection:
                App.logger.error("Still not connected to RabbitMQ after waiting.")
            return

        try:
            await App.channel.default_exchange.publish(
                        aio_pika.Message(body=json.dumps(message).encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                    ),
                    routing_key=App.queue.name,
                    )
            App.logger.info(f"Message sent to RabbitMQ: {message}")
        except Exception as e:
            App.logger.error(f"Failed to send message to RabbitMQ: {e}")
        finally:
            await App.connection.close() #consider moving this to main so we don't close connection after every message


async def main():
    app = App()
    await app.getRabbitMQConnection()
    await app.get_vulnerabilities()

if __name__ == "__main__":
    asyncio.run(main())

