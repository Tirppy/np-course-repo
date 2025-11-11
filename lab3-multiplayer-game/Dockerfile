# Simple Dockerfile to build and run tests for the Memory Scramble project
FROM node:22-bullseye-slim

WORKDIR /usr/src/app

# Copy package metadata first to leverage layer caching
COPY package.json package-lock.json* ./

# Install deps
RUN npm ci --silent || npm install --silent

# Copy source
COPY . .

# Build TypeScript
RUN npm run compile

# Default command: start the server (can be overridden by `docker run <image> npm test`)
CMD ["npm", "start"]
