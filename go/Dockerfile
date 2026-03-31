# Use an official Go runtime as a parent image
FROM golang:1.25 AS builder


# Set the working directory inside the container
WORKDIR /app

# Copy go.mod and go.sum first to cache dependencies
COPY go.mod go.sum ./
# Download dependencies into the cache layer
RUN go mod download

# Copy the rest of the source code
COPY . .

# Build the Go application, outputting a static binary named 'app'
# CGO_ENABLED=0 creates a statically linked binary that doesn't depend on C libraries
# go build compiles Go source files into an executable
# -o specifies the output file name
# . tells compiler to look for main package in current directory
RUN CGO_ENABLED=0 go build -o /app/app .


# Create the final runtime image; can't use scratch because of MongoDB Atlas TLS and needs ca-certificates
FROM debian:bookworm-slim

# Install CA certificates so MongoDB Atlas TLS works
RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates


# Copy only the compiled binary from the builder stage
COPY --from=builder /app/app /app/app

# Set the entry point to run your compiled binary
ENTRYPOINT ["/app/app"]