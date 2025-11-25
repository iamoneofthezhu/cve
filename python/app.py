import asyncio
from pdb import run
import threading
import requests
import logging
import sys
from datetime import date, timedelta
import math
from rabbitmq import RabbitMQClient

class App:
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)  # redirect to stdout
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    logger.info("This should show up in docker logs for python-cve service")

    CVE_URL = "https://nvd.nist.gov/extensions/nudp/services/json/nvd/cve/search/results"
    
    def __init__(self):
        self.rabbitmq_client = RabbitMQClient()

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
     
        App.logger.info("url is : " + self.CVE_URL)

        #spoofing the headers to mimic a browser request for now
        #todo: go to https://nvd.nist.gov and click on Developers. From there should find the API docs and proper way to call it
        

        App.logger.info(f"Sending request to NVD API: {self.CVE_URL} with params: {params}")
        response = requests.get(self.CVE_URL, params=params, headers=self.HEADERS)
       
        data = self.executeGetAndReturnResult(response, params)

        if(len(data) > 0):
            totalRecords = data["response"][0]["grid"]["totalResults"]
            totalPages = math.ceil(totalRecords / 25)
            App.logger.info(f"Total records: {totalRecords}")

            asyncio.run(asyncio.to_thread(lambda: self.extractVulnerabilitiesAndSendToRabbitMQ(data)))

            for page in range(1, totalPages):
                params = self.setParams(publishDateRangeStart, publishDateRangeEnd, page * 25)
                response = requests.get(self.CVE_URL, params=params, headers=self.HEADERS)
                asyncio.run(asyncio.to_thread(lambda: self.executeGetAndExtractData(response, params)))

    def executeGetAndExtractData(self, response, params):
        print(f"[executeGetAndExtractData] Running in thread: {threading.current_thread().name}")
        data = self.executeGetAndReturnResult(response, params)
        App.logger.info(f"executeGetAndExtractData data size is :{len(data)}")
        self.extractVulnerabilitiesAndSendToRabbitMQ(data)

    def executeGetAndReturnResult(self, response, params):
        if response.status_code == 200:
            data = response.json()
            App.logger.info(f"Response Status Code: {response.status_code}")
            return data
        else:
            App.logger.error(f"Failed to retrieve data from NVD API: {response.status_code}")
            return []



    def extractVulnerabilitiesAndSendToRabbitMQ(self, data):
        print(f"[extractVulnerabilitiesAndSendToRabbitMQ] Running in thread: {threading.current_thread().name}")
        App.logger.info(f"extractVulnerabilitiesAndSendToRabbitMQ data size is :{len(data)}")
        vulnerabilities = data["response"][0]["grid"]["vulnerabilities"]
      #  for vulnerability in vulnerabilities:
           # oneCve = vulnerability["cve"]
        oneCve = vulnerabilities[0]["cve"]
        App.logger.info(f"One CVE is : {oneCve['id']} - {oneCve['descriptions'][0]['value']}")
        App.logger.info("--------")
        App.logger.info(oneCve)
        self.rabbitmq_client.sendMsgRabbitMQ(oneCve)


def main():
    app = App()
    try:
        app.rabbitmq_client.getRabbitMQConnection()

        #query_date = date.today().strftime("%Y-%m-%d")
        #todo: using yesterday's date to avoid problem with calling API with tomorrow's date. There's no data for tomorrow's date.
        # This is bec base python image in Docker uses UTC and date.today() would return tomorrow's date sometimes        
        #Need to decide if want to set Docker image to use EST
        query_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d") 
        params = app.setParams(query_date, query_date, 0)
        app.get_vulnerabilities(query_date, query_date, params)
    finally:
       if RabbitMQClient.CONNECTION:
           RabbitMQClient.CONNECTION.close() 

if __name__ == "__main__":
    main()

