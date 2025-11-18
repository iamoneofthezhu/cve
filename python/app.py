import asyncio
import os
from pdb import run
import threading
from aiormq import AMQPConnectionError
import requests
import aio_pika
import json
import logging
import aiohttp
import sys
from datetime import date
import math
import pika

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

    CVE_URL = "https://nvd.nist.gov/extensions/nudp/services/json/nvd/cve/search/results"

    HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://nvd.nist.gov/vuln/search",
            "X-Requested-With": "XMLHttpRequest"
        }

    def setParams(self, publishDateRangeStart, publishDateRangeEnd, offset):
        params = {
            "resultType": "records",            
            "offset": offset,
            "rowCount": "25", #doesn't seem to make a difference. Api always returns 25 records at a time
            "publishDateRangeStart": publishDateRangeStart,
            "publishDateRangeEnd": publishDateRangeEnd,
            "sortOrder": "3",
            "sortDirection": "2",
        }
        return params

    def get_vulnerabilities(self, publishDateRangeStart, publishDateRangeEnd, params):
       # url = "https://nvd.nist.gov/extensions/nudp/services/json/nvd/cve/search/results"
        # params = {
        #     "resultType": "records",            
        #     "offset": offset,
        #     "rowCount": "50", #doesn't seem to make a difference. Api always returns 25 records at a time
        #     "publishDateRangeStart": publishDateRangeStart,
        #     "publishDateRangeEnd": publishDateRangeEnd,
        #     "sortOrder": "3",
        #     "sortDirection": "2",
        # }
        App.logger.info("url is : " + self.CVE_URL)

        #spoofing the headers to mimic a browser request for now
        #todo: go to https://nvd.nist.gov and click on Developers. From there should find the API docs and proper way to call it
        

        App.logger.info(f"Sending request to NVD API: {self.CVE_URL} with params: {params}")
        response = requests.get(self.CVE_URL, params=params, headers=self.HEADERS)
        #async with aiohttp.ClientSession() as session:
            # async with session.get(self.CVE_URL, params=params, headers=self.HEADERS) as response:
            #     if response.status == 200:
            #         data = await response.json()
            #         App.logger.info(f"Response Status Code: {response.status}")

        data = self.executeGetAndReturnResult(response, params)

        if(len(data) > 0):
            totalRecords = data["response"][0]["grid"]["totalResults"]
            totalPages = math.ceil(totalRecords / 25)
            App.logger.info(f"Total records: {totalRecords}")

          #  vulnerabilities = data["response"][0]["grid"]["vulnerabilities"]
          #  loop = asyncio.get_event_loop()
            #loop.run_until_complete(asyncio.to_thread(self.extractVulnerabilitiesAndSendToRabbitMQ(data)))
            asyncio.run(asyncio.to_thread(lambda: self.extractVulnerabilitiesAndSendToRabbitMQ(data)))
            for page in range(1, totalPages):
                params = self.setParams(publishDateRangeStart, publishDateRangeEnd, page * 25)
                response = requests.get(self.CVE_URL, params=params, headers=self.HEADERS)
                asyncio.run(asyncio.to_thread(lambda: self.executeGetAndExtractData(response, params)))

                        # data = self.executeGetAndReturnResults(self, session, params)
                        # vulnerabilities = data["response"][0]["grid"]["vulnerabilities"]

                        # asyncio.run(self.extractVulnerabilitiesAndSendToRabbitMQ(self, vulnerabilities))

                   
                    # vulnerabilities = data["response"][0]["grid"]["vulnerabilities"]

                    # for vulnerability in vulnerabilities:
                    #     oneCve = vulnerability["cve"]
                    #     App.logger.info(f"One CVE is : {oneCve['id']} - {oneCve['descriptions'][0]['value']}")
                    #     App.logger.info("--------")
                    #     App.logger.info(oneCve)
                    #     #asyncio.run(sendMsgRabbitMQ(oneCve))
                    #     await self.sendMsgRabbitMQ(oneCve)
                # else:
                #     App.logger.error(f"Failed to retrieve data from NVD API: {response.status}")
                #     return []
    def executeGetAndExtractData(self, response, params):
       # with aiohttp.ClientSession() as session:
        print(f"[executeGetAndExtractData] Running in thread: {threading.current_thread().name}")
        data = self.executeGetAndReturnResult(response, params)
        self.extractVulnerabilitiesAndSendToRabbitMQ(data)

    def executeGetAndReturnResult(self, response, params):
        #async with aiohttp.ClientSession() as session:
            #with session.get(self.CVE_URL, params=params, headers=self.HEADERS) as response:
                if response.status_code == 200:
                    data = response.json()
                    App.logger.info(f"Response Status Code: {response.status_code}")
                    return data
                else:
                    App.logger.error(f"Failed to retrieve data from NVD API: {response.status_code}")
                    return []



    def extractVulnerabilitiesAndSendToRabbitMQ(self, data):
        print(f"[extractVulnerabilitiesAndSendToRabbitMQ] Running in thread: {threading.current_thread().name}")
        vulnerabilities = data["response"][0]["grid"]["vulnerabilities"]
      #  for vulnerability in vulnerabilities:
           # oneCve = vulnerability["cve"]
        oneCve = vulnerabilities[0]["cve"]
        App.logger.info(f"One CVE is : {oneCve['id']} - {oneCve['descriptions'][0]['value']}")
        App.logger.info("--------")
        App.logger.info(oneCve)
          #asyncio.run(sendMsgRabbitMQ(oneCve))
        self.sendMsgRabbitMQ(oneCve)

    # Connect to RabbitMQ and create queue
    def getRabbitMQConnection(self):
        max_retries = 6
        retry_delay = 1 # seconds
        attempts = 0

        while attempts < max_retries: #retries up to max_retries times
            try:
                App.logger.info(f"yalin retry delay is : {retry_delay} seconds")
                App.logger.info(f"Connecting to: {App.CONNECTION_URL}")
                
                App.connection = pika.BlockingConnection(pika.URLParameters(App.CONNECTION_URL))
                App.logger.info("Connection established successfully.")

                
                App.channel = App.connection.channel()
                App.logger.info("Channel created.")

                #Declare a queue
                App.queue = App.channel.queue_declare("cve_queue", durable=True)
                App.logger.info(f"Queue 'cve_queue' declared.")

                # If all the above succeeds, we can return the objects
                return App.connection, App.channel, App.queue

            except (ConnectionError, AMQPConnectionError) as e:
                App.logger.error(f"yalin: {e}")  
                attempts += 1
                if attempts < max_retries:
                    App.logger.warning(f"Failed to connect to RabbitMQ: {e}. Retrying in {retry_delay} second(s)...")
                    asyncio.sleep(retry_delay)
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
    def sendMsgRabbitMQ(self, message: str):
        #connection, channel, queue = await getRabbitMQConnection()
        App.logger.info("message to rabbitmq is : " + str(message))
        if not App.connection:
            App.logger.error("Failed to connect to RabbitMQ. Message not sent.")
            asyncio.sleep(5)
            if not App.connection:
                App.logger.error("Still not connected to RabbitMQ after waiting.")
            return

        try:
            message_body = json.dumps(message).encode('utf-8')
            App.channel.basic_publish(
                exchange='', # Often empty string for default exchange
                routing_key=App.queue.method.queue,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent, # Note the uppercase 'P' in Persistent
                    content_type='application/json' # Good practice to specify content type
                )
            )
            App.logger.info(f"Message sent to RabbitMQ: {message}")
        except Exception as e:
            App.logger.error(f"Failed to send message to RabbitMQ: {e}")
       # finally:
             #consider moving this to main so we don't close connection after every message


def main():
    app = App()
    try:
        app.getRabbitMQConnection()

        today = date.today().strftime("%Y-%m-%d")
        params = app.setParams(today, today, 0)
        app.get_vulnerabilities(today, today, params)
    finally:
       App.connection.close() 

if __name__ == "__main__":
    main()

