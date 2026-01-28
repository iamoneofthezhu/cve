//go:build !debugtest
// +build !debugtest

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/rabbitmq/amqp091-go"
	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type CVE struct {
	ID           string                `json:"id" bson:"id"`
	Published    string                `json:"published" bson:"published"`
	LastModified string                `json:"lastModified" bson:"lastModified"`
	Status       string                `json:"vulnStatus" bson:"vulnStatus"`
	Descriptions []Description         `json:"descriptions" bson:"descriptions"`
	Metrics      CVSS                  `json:"metrics" bson:"metrics"`
	Weaknesses   []WeaknessDescription `json:"weaknesses" bson:"weaknesses"`
	References   []Reference           `json:"references" bson:"references"`
}

type Description struct {
	Language string `json:"lang" bson:"lang"`
	Value    string `json:"value" bson:"value"`
}

type CVE_OUTPUT struct {
	ID           string      `json:"cve_id" bson:"cve_id"`
	Published    string      `json:"published" bson:"published"`
	LastModified string      `json:"last_modified" bson:"last_modified"`
	Status       string      `json:"status" bson:"status"`
	Descriptions []string    `json:"description" bson:"description"`
	Metrics      CVSS        `json:"metrics" bson:"metrics"`
	Weaknesses   []string    `json:"weaknesses" bson:"weaknesses"`
	References   []Reference `json:"references" bson:"references"`
}

type CVSS struct {
	CvssMetricV30 *[]CVSSMetricV31 `json:"cvssMetricV30,omitempty" bson:"cvssMetricV30,omitempty"`
	CvssMetricV31 *[]CVSSMetricV31 `json:"cvssMetricV31,omitempty" bson:"cvssMetricV31,omitempty"`
	CVSSMetricV40 *[]CVSSMetricV40 `json:"cvssMetricV40,omitempty" bson:"cvssMetricV40,omitempty"`
}

type CVSSMetricV31 struct {
	CVSSData            CVSSData `json:"cvssData" bson:"cvssData"`
	ExploitabilityScore float64  `json:"exploitabilityScore" bson:"exploitabilityScore"`
	ImpactScore         float64  `json:"impactScore" bson:"impactScore"`
}
type CVSSData struct {
	BaseScore    float64 `json:"baseScore" bson:"baseScore"`
	Severity     string  `json:"baseSeverity" bson:"baseSeverity"`
	Vector       string  `json:"vectorString" bson:"vectorString"`
	AttackVector string  `json:"attackVector" bson:"attackVector"`
}

type CVSSMetricV40 struct {
	Source     string   `json:"source" bson:"source"`
	Type       string   `json:"type" bson:"type"`
	CVSS40Data CVSSData `json:"cvssData" bson:"cvssData"`
}

type WeaknessDescription struct {
	Description []Description `json:"description" bson:"description"`
}

type Reference struct {
	URL string `json:"url,omitempty" bson:"url,omitempty"`
}

func convertToNewCveJson(cve CVE) CVE_OUTPUT {
	// var cve CVE
	// err := json.Unmarshal([]byte(cve_json), &cve)
	// if err != nil {
	// 	log.Fatalf("Failed to unmarshal message: %v", err)
	// }

	// log.Printf("Unmarshalled message: %+v", cve)

	var englishOnly []string

	for _, d := range cve.Descriptions {
		if d.Language == "en" {
			englishOnly = append(englishOnly, d.Value)
			break
		}
	}

	var englishWeaknesses []string
	var weakness []WeaknessDescription = cve.Weaknesses

	for _, d := range weakness {
		for _, f := range d.Description {

			if f.Language == "en" {
				englishWeaknesses = append(englishWeaknesses, f.Value)
				break
			}
		}
	}

	//Update the struct with only the English description
	updated_cve := CVE_OUTPUT{
		ID:           cve.ID,
		Published:    cve.Published,
		LastModified: cve.LastModified,
		Status:       cve.Status,
		Descriptions: englishOnly,
		Metrics:      cve.Metrics,
		Weaknesses:   englishWeaknesses,
		References:   cve.References,
	}
	//regenerate json
	cve_output, _ := json.MarshalIndent(updated_cve, "", "  ")

	log.Printf("Updated message: %+v", string(cve_output))

	return updated_cve
}

func getSecret(pathEnv string) string {
	log.Printf("secret pathenv is %s\n", pathEnv)

	filePath := os.Getenv(pathEnv)
	log.Printf("secret filePath is %s\n", filePath)

	content, err := os.ReadFile(filePath)
	if err != nil {
		log.Printf("Could not read secret file: %v", err)
		return ""
	}
	log.Printf("Get Secret %s\n", strings.TrimSpace(string(content)))
	return strings.TrimSpace(string(content))
}

func sendJsonToMongoDB(cve CVE_OUTPUT) {
	fmt.Println("inside sendJsonToMongoDB!")
	rootUserName := getSecret("MONGO_ROOT_USERNAME_FILE")
	rootPassword := getSecret("MONGO_ROOT_PASSWORD_FILE")

	// 1. Setup connection
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	client, err := mongo.Connect(options.Client().ApplyURI("mongodb://mongo:27017").
		SetAuth(options.Credential{AuthSource: "admin", //need this since user in admin db
			Username: rootUserName, Password: rootPassword}))

	if err != nil {
		log.Fatal(err)
	}
	defer client.Disconnect(ctx)

	collection := client.Database("web_scraper_db").Collection("cve_collection")
	res, err := collection.InsertOne(ctx, cve)
	data, _ := bson.MarshalExtJSON(cve, true, false)
	fmt.Println(string(data))

	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("Inserted document ID: %v\n", res.InsertedID)
}

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
	log.Println("Declaring queue 'cve_queue'...")
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
	log.Printf("Queue declared: %s (messages: %d, consumers: %d)", queue.Name, queue.Messages, queue.Consumers)

	// Consume messages
	log.Println("Registering consumer...")
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
	log.Println("Consumer registered successfully")

	// Read one message
	log.Println("Waiting for messages...")
	for msg := range msgs {
		log.Printf("Received message (length: %d bytes)", len(msg.Body))
		log.Printf("Raw message: %s\n", string(msg.Body))

		var cve CVE
		err := json.Unmarshal(msg.Body, &cve)
		if err != nil {
			log.Printf("DEBUG: JSON unmarshal error: %v", err)
			log.Printf("DEBUG: Message content: %s", string(msg.Body))
			log.Fatalf("Failed to unmarshal message: %v", err)
		}

		result := convertToNewCveJson(cve)

		log.Printf("Successfully unmarshalled CVE:")
		log.Printf("  ID: %s", result.ID)
		log.Printf("  Status: %s", result.Status)
		log.Printf("  CVSS V31: %+v", result.Metrics.CvssMetricV31)
		log.Printf("  CVSS V40: %+v", result.Metrics.CVSSMetricV40)
		log.Printf("  Weaknesses count: %d", len(result.Weaknesses))
		log.Printf("  References count: %d", len(result.References))
		log.Printf("Full CVE struct: %+v", result)

		sendJsonToMongoDB(result)

		break // exit after first message
	}

}
