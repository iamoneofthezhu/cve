package queue

import (
	"fmt"

	amqp "github.com/rabbitmq/amqp091-go"
)

type RabbitConfig struct {
	URI      string
	Queue    string
	Durable  bool
	AutoAck  bool
	Consumer string
}

func (c RabbitConfig) Validate() error {
	if c.URI == "" {
		return fmt.Errorf("rabbitmq uri is empty")
	}
	if c.Queue == "" {
		return fmt.Errorf("rabbitmq queue is empty")
	}
	return nil
}

type Consumer struct {
	conn *amqp.Connection
	ch   *amqp.Channel
}

func NewConsumer(cfg RabbitConfig) (*Consumer, amqp.Queue, error) {
	if err := cfg.Validate(); err != nil {
		return nil, amqp.Queue{}, err
	}

	conn, err := amqp.Dial(cfg.URI)
	if err != nil {
		return nil, amqp.Queue{}, err
	}

	ch, err := conn.Channel()
	if err != nil {
		_ = conn.Close()
		return nil, amqp.Queue{}, err
	}

	q, err := ch.QueueDeclare(
		cfg.Queue,
		cfg.Durable,
		false, // auto-delete
		false, // exclusive
		false, // no-wait
		nil,   // args
	)
	if err != nil {
		_ = ch.Close()
		_ = conn.Close()
		return nil, amqp.Queue{}, err
	}

	return &Consumer{conn: conn, ch: ch}, q, nil
}

func (c *Consumer) Close() error {
	if c == nil {
		return nil
	}
	if c.ch != nil {
		_ = c.ch.Close()
	}
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

func (c *Consumer) Consume(cfg RabbitConfig) (<-chan amqp.Delivery, error) {
	if c == nil || c.ch == nil {
		return nil, fmt.Errorf("rabbit consumer not initialized")
	}
	return c.ch.Consume(
		cfg.Queue,
		cfg.Consumer,
		cfg.AutoAck,
		false, // exclusive
		false, // no-local
		false, // no-wait
		nil,   // args
	)
}

