**CVE Scraper & Processor**

A distributed pipeline designed to monitor, extract, and store vulnerability data from the National Vulnerability Database (NVD), running on a local Kubernetes cluster.

**The system consists of two microservices communicating via a message broker:**

* Scraper (Python): Polls the NVD site for new CVEs and publishes raw data to RabbitMQ.
* Processor (Go): Consumes messages from RabbitMQ, extracts specific data points, and persists them to MongoDB Atlas.
