package main

import (
	"fmt"
	"log"
	"os"

	"github.com/rabbitmq/amqp091-go"
)

func main() {
	fmt.Println("Hello, World!")
	rabbitmqHost, exists := os.LookupEnv("RABBITMQ_HOST")

	if !exists || rabbitmqHost == "" {
		rabbitmqHost = "localhost" // Fallback to default
	}

	connectionString := fmt.Sprintf("amqp://guest:guest@%s:5672/", rabbitmqHost)
	fmt.Printf("Connecting to RabbitMQ at %s\n", connectionString)
	// Connect to RabbitMQ
	conn, err := amqp091.Dial(connectionString)
	if err != nil {
		log.Fatalf("Failed to connect: %v", err)
	}

	fmt.Println("Connected to RabbitMQ successfully!")

	defer conn.Close()

	// Create a channel
	ch, err := conn.Channel()
	if err != nil {
		log.Fatalf("Failed to open a channel: %v", err)
	}
	defer ch.Close()

	// Declare a queue. RabbitMQ will not create the queue if it already exists. This way Go app doesn't depend on Python app to create the queue.
	queue, err := ch.QueueDeclare(
		"cve_queue", // name
		true,        // durable
		false,       // auto-delete
		false,       // exclusive
		false,       // no-wait
		nil,         // arguments
	)
	if err != nil {
		log.Fatalf("Failed to declare a queue: %v", err)
	}

	// Consume messages
	msgs, err := ch.Consume(
		queue.Name, // queue
		"",         // consumer
		true,       // auto-ack
		false,      // exclusive
		false,      // no-local
		false,      // no-wait
		nil,        // args
	)
	if err != nil {
		log.Fatalf("Failed to register a consumer: %v", err)
	}

	// Read one message
	for msg := range msgs {
		log.Printf("Received message: %s", msg.Body)
		break // exit after first message
	}

}
