//go:build !debugtest
// +build !debugtest

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/oneofthezhu/cve_go/internal/cveStructs"
	"github.com/oneofthezhu/cve_go/internal/queue"
	"github.com/oneofthezhu/cve_go/internal/storage"
)

const cveQueueName = "cve_queue"

func getSecret(pathEnv string) string {
	filePath := os.Getenv(pathEnv)
	content, err := os.ReadFile(filePath)
	if err != nil {
		log.Printf("Could not read secret file: %v", err)
		return ""
	}
	return strings.TrimSpace(string(content))
}

func main() {
	fmt.Println("Hello, World!")

	// ctx is the root "lifetime" for this process. It is cancelled when we receive
	// an interrupt/terminate signal like Ctrl+C so the rest of the code knows when to shut down.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop() // stop releases internal resources used by signal.NotifyContext

	// ---- MongoDB: connect once ----
	rootUserName := getSecret("MONGO_ROOT_USERNAME_FILE")
	rootPassword := getSecret("MONGO_ROOT_PASSWORD_FILE")
	// NewMongoRepo uses ctx so that if startup is cancelled (e.g. Ctrl+C),
	// the connection attempt will also be cancelled.
	mongoRepo, err := storage.NewMongoRepo(ctx, storage.MongoConfig{
		URI:        "mongodb://mongo:27017",
		AuthSource: "admin",
		Username:   rootUserName,
		Password:   rootPassword,
		Database:   "web_scraper_db",
		Collection: "cve_collection",
	})
	if err != nil {
		log.Fatalf("Failed to connect to MongoDB: %v", err)
	}
	// When main exits we want to give MongoDB a short, bounded window to disconnect
	// cleanly, even if ctx has already been cancelled. So we create a fresh context
	// with its own 10s timeout just for Close.
	defer func() {
		cctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = mongoRepo.Close(cctx)
	}()

	// ---- RabbitMQ: connect once ----
	rabbitmqHost := os.Getenv("RABBITMQ_HOST")
	if rabbitmqHost == "" {
		rabbitmqHost = "localhost"
	}
	rabbitURI := fmt.Sprintf("amqp://guest:guest@%s:5672/", rabbitmqHost)

	consumer, q, err := queue.NewConsumer(queue.RabbitConfig{
		URI:     rabbitURI,
		Queue:   cveQueueName,
		Durable: true,
		AutoAck: true,
	})
	if err != nil {
		log.Fatalf("Failed to connect to RabbitMQ: %v", err)
	}
	defer func() { _ = consumer.Close() }()
	log.Printf("Queue ready: %s (messages: %d, consumers: %d)", q.Name, q.Messages, q.Consumers)

	// Consume messages
	log.Println("Registering consumer...")
	msgs, err := consumer.Consume(queue.RabbitConfig{
		Queue:   cveQueueName,
		AutoAck: true,
	})
	if err != nil {
		log.Fatalf("Failed to register a consumer: %v", err)
	}
	log.Println("Consumer registered successfully")

	log.Println("Waiting for messages...")
	for {
		select {
		case <-ctx.Done():
			// Global context was cancelled (e.g. SIGINT/SIGTERM). Time to stop.
			log.Println("Shutting down...")
			return
		case msg, ok := <-msgs:
			if !ok {
				log.Println("RabbitMQ delivery channel closed")
				return
			}

			log.Printf("Received message (length: %d bytes)", len(msg.Body))

			var cve cveStructs.CVE
			if err := json.Unmarshal(msg.Body, &cve); err != nil {
				log.Printf("JSON unmarshal error: %v", err)
				continue
			}

			result, err := cveStructs.Transform(cve)
			if err != nil {
				log.Printf("Transform error: %v", err)
				continue
			}

			ictx, cancel := context.WithTimeout(ctx, 10*time.Second)
			err = mongoRepo.InsertOne(ictx, result)
			cancel()
			if err != nil {
				log.Printf("Mongo insert error: %v", err)
				continue
			}
			log.Printf("Inserted CVE %s", result.ID)
			b, _ := json.Marshal(result)
			log.Printf("Inserted CVE %s", b)
		}
	}

}
