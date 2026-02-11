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
# CGO_ENABLED=0 ensures a statically linked binary compatible with 'scratch'
RUN CGO_ENABLED=0 go build -o /app/app .


# Stage 2: Create the final, minimal runtime image
# Use scratch for maximum minimization and security
FROM scratch

# Copy only the compiled binary from the builder stage
COPY --from=builder /app/app /app/app

# Set the entry point to run your compiled binary
ENTRYPOINT ["/app/app"]