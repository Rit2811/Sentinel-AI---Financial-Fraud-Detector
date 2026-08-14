FROM node:22.14.0-alpine3.21

ENV NODE_ENV=production

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY src ./src
COPY migrations ./migrations

EXPOSE 8000
CMD ["sh", "-c", "npm run migrate:up && node src/server.js"]
