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

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)  # redirect to stdout
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    
    connection = None
    channel = None
    queue = None

    MAX_RETRIES = 6
    RETRY_DELAY = 1 # seconds

    # Connect to RabbitMQ and create queue
    def getRabbitMQConnection(self):
        
        attempts = 0

        while attempts < RabbitMQClient.MAX_RETRIES: #retries up to MAX_RETRIES times
            try:
                RabbitMQClient.logger.info(f"yalin retry delay is : {RabbitMQClient.RETRY_DELAY} seconds")
                RabbitMQClient.logger.info(f"Connecting to: {self.connection_url}")
                
                RabbitMQClient.connection = pika.BlockingConnection(pika.URLParameters(self.connection_url))
                RabbitMQClient.logger.info("Connection established successfully.")

                
                RabbitMQClient.channel = RabbitMQClient.connection.channel()
                RabbitMQClient.logger.info("Channel created.")

                #Declare a queue
                RabbitMQClient.queue = RabbitMQClient.channel.queue_declare("cve_queue", durable=True)
                RabbitMQClient.logger.info(f"Queue 'cve_queue' declared.")

                # If all the above succeeds, we can return the objects
                return RabbitMQClient.connection, RabbitMQClient.channel, RabbitMQClient.queue

            except (ConnectionError, AMQPConnectionError) as e:
                RabbitMQClient.logger.error(f"yalin: {e}")  
                attempts += 1
                if attempts < RabbitMQClient.MAX_RETRIES:
                    RabbitMQClient.logger.warning(f"Failed to connect to RabbitMQ: {e}. Retrying in {RabbitMQClient.RETRY_DELAY} second(s)...")
                    asyncio.sleep(RabbitMQClient.RETRY_DELAY)
                else:
                    RabbitMQClient.logger.error(f"Failed to connect to RabbitMQ after {RabbitMQClient.MAX_RETRIES} attempts.")
                    raise # Re-raise the final error after max retries are hit

            except Exception as e:
                RabbitMQClient.logger.error(f"yalin2: {e}")  
                RabbitMQClient.logger.critical(f"An unexpected error occurred: {e}")
                RabbitMQClient.logger.critical("Exiting due to unexpected error.")
                # If an unexpected error occurs (like a channel declaration issue), re-raise it
                raise

        # This part should be unreachable if 'raise' is used correctly, but good practice to have
        return None, None, None 

    # Send message to RabbitMQ
    def sendMsgRabbitMQ(self, message: str):
        RabbitMQClient.logger.info("message to rabbitmq is : " + str(message))
        if not self.connection:
            RabbitMQClient.logger.error("Failed to connect to RabbitMQ. Message not sent.")
            asyncio.sleep(5)
            if not self.connection:
                RabbitMQClient.logger.error("Still not connected to RabbitMQ after waiting.")
            return

        try:
            message_body = json.dumps(message).encode('utf-8')
            RabbitMQClient.channel.basic_publish(
                exchange='', # Often empty string for default exchange
                routing_key=RabbitMQClient.queue.method.queue,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                    content_type='application/json' # good to specify content type
                )
            )
            RabbitMQClient.logger.info(f"Message sent to RabbitMQ: {message}")
        except Exception as e:
            RabbitMQClient.logger.error(f"Failed to send message to RabbitMQ: {e}")

