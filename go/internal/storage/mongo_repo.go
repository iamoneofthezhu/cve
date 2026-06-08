package storage

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type MongoConfig struct {
	URI        string
	AuthSource string
	Username   string
	Password   string
	Database   string
	Collection string
}

func (c MongoConfig) Validate() error {
	if strings.TrimSpace(c.URI) == "" {
		return fmt.Errorf("mongo uri is empty")
	}
	if strings.TrimSpace(c.Database) == "" {
		return fmt.Errorf("mongo database is empty")
	}
	if strings.TrimSpace(c.Collection) == "" {
		return fmt.Errorf("mongo collection is empty")
	}
	if c.AuthSource == "" {
		c.AuthSource = "admin"
	}
	return nil
}

type MongoRepo struct {
	client *mongo.Client
	coll   *mongo.Collection
}

func NewMongoRepo(ctx context.Context, cfg MongoConfig) (*MongoRepo, error) {
	if err := cfg.Validate(); err != nil {
		return nil, err
	}

	log.Printf("Mongo URI is: %s", cfg.URI)

	opts := options.Client().ApplyURI(cfg.URI)
	if strings.TrimSpace(cfg.Username) != "" || strings.TrimSpace(cfg.Password) != "" {
		opts.SetAuth(options.Credential{
			AuthSource: cfg.AuthSource,
			Username:   cfg.Username,
			Password:   cfg.Password,
		})
	}

	cctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	client, err := mongo.Connect(opts)
	if err != nil {
		return nil, err
	}

	// Ping to fail fast on bad URI/creds.
	if err := client.Ping(cctx, nil); err != nil {
		_ = client.Disconnect(cctx)
		return nil, err
	}

	coll := client.Database(cfg.Database).Collection(cfg.Collection)
	return &MongoRepo{client: client, coll: coll}, nil
}

func (r *MongoRepo) Close(ctx context.Context) error {
	if r == nil || r.client == nil {
		return nil
	}
	return r.client.Disconnect(ctx)
}

func (r *MongoRepo) InsertOne(ctx context.Context, doc any) error {
	if r == nil || r.coll == nil {
		return fmt.Errorf("mongo repo not initialized")
	}
	_, err := r.coll.InsertOne(ctx, doc)
	return err
}
