# cve
Plan 0:
Python to scrape cve pages and sends message to RabbitMQ
RabbitMQ running on Docker locally
GoLang listens to RabbitMQ for message

Plan 1:
Deploy python, rabbitmq, and go as 3 separate services in docker
Retrieve only 1 cve, send message to rabbitmq, and go app will consume message and just print out message for now

Plan 2:
Update python to retry to connect to rabbitmq if failed the first time

Plan 3:
Combine the python project repo and go project repo on github

Plan 4:
Optimize Python code to scrape all CVEs that are published today on multiple pages




