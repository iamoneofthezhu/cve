import os
import asyncio
import json
import logging
import sys
from aiormq import AMQPConnectionError
import pika


class RabbitMQClient:
      
    def __init__(self):  
        # Read the host from the environment variable; default to 'localhost' for local testing
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        self.connection_url = f"amqp://guest:guest@{self.rabbitmq_host}/"

    LOGGER = logging.getLogger(__name__)
    LOGGER.setLevel(logging.INFO)

    HANDLER = logging.StreamHandler(sys.stdout)  # redirect to stdout
    FORMATTER = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    HANDLER.setFormatter(FORMATTER)

    LOGGER.addHandler(HANDLER)
    LOGGER.propagate = False
    
    CONNECTION = None
    CHANNEL = None
    QUEUE = None

    MAX_RETRIES = 6
    RETRY_DELAY = 1 # seconds

    # Connect to RabbitMQ and create queue
    def getRabbitMQConnection(self):
        
        attempts = 0

        while attempts < RabbitMQClient.MAX_RETRIES: #retries up to MAX_RETRIES times
            try:
                RabbitMQClient.LOGGER.info(f"yalin retry delay is : {RabbitMQClient.RETRY_DELAY} seconds")
                RabbitMQClient.LOGGER.info(f"Connecting to: {self.connection_url}")
                
                RabbitMQClient.CONNECTION = pika.BlockingConnection(pika.URLParameters(self.connection_url))
                RabbitMQClient.LOGGER.info("Connection established successfully.")

                
                RabbitMQClient.CHANNEL = RabbitMQClient.CONNECTION.channel()
                RabbitMQClient.LOGGER.info("Channel created.")

                #Declare a queue
                RabbitMQClient.QUEUE = RabbitMQClient.CHANNEL.queue_declare("cve_queue", durable=True)
                RabbitMQClient.LOGGER.info(f"Queue 'cve_queue' declared.")

                # If all the above succeeds, we can return the objects
                return RabbitMQClient.CONNECTION, RabbitMQClient.CHANNEL, RabbitMQClient.QUEUE

            except (ConnectionError, AMQPConnectionError) as e:
                RabbitMQClient.LOGGER.error(f"yalin: {e}")  
                attempts += 1
                if attempts < RabbitMQClient.MAX_RETRIES:
                    RabbitMQClient.LOGGER.warning(f"Failed to connect to RabbitMQ: {e}. Retrying in {RabbitMQClient.RETRY_DELAY} second(s)...")
                    asyncio.sleep(RabbitMQClient.RETRY_DELAY)
                else:
                    RabbitMQClient.LOGGER.error(f"Failed to connect to RabbitMQ after {RabbitMQClient.MAX_RETRIES} attempts.")
                    raise # Re-raise the final error after max retries are hit

            except Exception as e:
                RabbitMQClient.LOGGER.error(f"yalin2: {e}")  
                RabbitMQClient.LOGGER.critical(f"An unexpected error occurred: {e}")
                RabbitMQClient.LOGGER.critical("Exiting due to unexpected error.")
                # If an unexpected error occurs (like a channel declaration issue), re-raise it
                raise

        # This part should be unreachable if 'raise' is used correctly, but good practice to have
        return None, None, None 

    # Send message to RabbitMQ
    def sendMsgRabbitMQ(self, message: str):
        RabbitMQClient.LOGGER.info("message to rabbitmq is : " + str(message))
        if not self.CONNECTION:
            RabbitMQClient.LOGGER.error("Failed to connect to RabbitMQ. Message not sent.")
            asyncio.sleep(5)
            if not self.CONNECTION:
                RabbitMQClient.LOGGER.error("Still not connected to RabbitMQ after waiting.")
            return

        try:
            message_body = json.dumps(message).encode('utf-8')
            RabbitMQClient.CHANNEL.basic_publish(
                exchange='', # Often empty string for default exchange
                routing_key=RabbitMQClient.QUEUE.method.queue,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                    content_type='application/json' # good to specify content type
                )
            )
            RabbitMQClient.LOGGER.info(f"Message sent to RabbitMQ: {message}")
        except Exception as e:
            RabbitMQClient.LOGGER.error(f"Failed to send message to RabbitMQ: {e}")

