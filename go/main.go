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
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/oneofthezhu/cve_go/internal/cveStructs"
	"github.com/oneofthezhu/cve_go/internal/queue"
	"github.com/oneofthezhu/cve_go/internal/storage"
	amqp "github.com/rabbitmq/amqp091-go"
)

const (
	cveQueueName   = "cve_queue"
	defaultWorkers = 5 // Default number of concurrent workers
)

func getSecret(pathEnv string) string {
	filePath := os.Getenv(pathEnv)
	content, err := os.ReadFile(filePath)
	if err != nil {
		log.Printf("Could not read secret file: %v", err)
		return ""
	}
	return strings.TrimSpace(string(content))
}

// getWorkerCount returns the number of workers from env var or default; env var is not set for now so default is used
func getWorkerCount() int {
	workersStr := os.Getenv("WORKER_COUNT")
	if workersStr == "" {
		return defaultWorkers
	}
	workers, err := strconv.Atoi(workersStr)
	if err != nil || workers < 1 {
		log.Printf("Invalid WORKER_COUNT '%s', using default %d", workersStr, defaultWorkers)
		return defaultWorkers
	}
	return workers
}

// processMessage handles a single CVE message: unmarshal, transform, and insert to MongoDB
func processMessage(ctx context.Context, mongoRepo *storage.MongoRepo, msg amqp.Delivery, workerID int) {

	log.Printf("Worker %d processing message (length: %d bytes)", workerID, len(msg.Body))

	var cve cveStructs.CVE
	if err := json.Unmarshal(msg.Body, &cve); err != nil {
		log.Printf("Worker %d: JSON unmarshal error: %v", workerID, err)
		return
	}

	result, err := cveStructs.Transform(cve)
	if err != nil {
		log.Printf("Worker %d: Transform error: %v", workerID, err)
		return
	}

	ictx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	err = mongoRepo.InsertOne(ictx, result)
	if err != nil {
		log.Printf("Worker %d: Mongo insert error: %v", workerID, err)
		return
	}

	log.Printf("Worker %d: Successfully inserted CVE %s", workerID, result.ID)
	b, _ := json.Marshal(result)
	log.Printf("Worker %d: Inserted CVE %s", workerID, string(b))

}

func main() {
	fmt.Println("Hello, World!")

	// ctx is the root "lifetime" for this process. It is cancelled when we receive
	// an interrupt/terminate signal like Ctrl+C so the rest of the code knows when to shut down.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop() // stop releases internal resources used by signal.NotifyContext

	// ---- MongoDB: connect once ----
	//rootUserName := getSecret("MONGO_ROOT_USERNAME_FILE")
	//rootPassword := getSecret("MONGO_ROOT_PASSWORD_FILE")

	// NewMongoRepo uses ctx so that if startup is cancelled (e.g. Ctrl+C),
	// the connection attempt will also be cancelled.
	// mongoRepo, err := storage.NewMongoRepo(ctx, storage.MongoConfig{
	// 	URI:        "mongodb://mongo:27017",
	// 	AuthSource: "admin",
	// 	Username:   rootUserName,
	// 	Password:   rootPassword,
	// 	Database:   "web_scraper_db",
	// 	Collection: "cve_collection",
	// })

	mongoRepo, err := storage.NewMongoRepo(ctx, storage.MongoConfig{
		URI:        "mongodb+srv://cluster0.pmdqc8v.mongodb.net/?appName=Cluster0",
		AuthSource: "admin",
		Username:   "mongoAtlasAdmin",
		Password:   "q6e7oppCokTljb1W",
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

	// ---- Worker Pool: Process messages concurrently ----
	numWorkers := getWorkerCount()
	log.Printf("Starting %d worker goroutines for concurrent message processing", numWorkers)

	var wg sync.WaitGroup
	wg.Add(numWorkers)

	// Launch worker goroutines
	for i := 0; i < numWorkers; i++ {
		workerID := i + 1
		go func() {
			defer wg.Done()
			log.Printf("Worker %d started", workerID)

			for {
				select {
				case <-ctx.Done():
					// Context cancelled, worker should stop
					log.Printf("Worker %d shutting down", workerID)
					return
				case msg, ok := <-msgs:
					if !ok {
						// Channel closed, worker should stop
						log.Printf("Worker %d: message channel closed", workerID)
						return
					}
					// Process message concurrently
					processMessage(ctx, mongoRepo, msg, workerID)
				}
			}
		}()
	}

	log.Println("All workers started. Waiting for messages...")

	// Wait for all workers to finish (they'll exit when ctx is cancelled or channel closes)
	wg.Wait()
	log.Println("All workers finished. Shutting down...")

}
