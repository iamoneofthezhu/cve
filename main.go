package main

import (
	"fmt"
	"github.com/rabbitmq/amqp091-go"
	"log"

)

func main() {
	fmt.Println("Hello, World!")
	conn, err := amqp091.Dial("amqp://guest:guest@localhost:5672/")
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

// Consume messages
	msgs, err := ch.Consume(
		"cve_queue", // queue
		"",     // consumer
		true,   // auto-ack
		false,  // exclusive
		false,  // no-local
		false,  // no-wait
		nil,    // args
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
