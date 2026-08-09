FROM node:22.14.0-alpine3.21

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

EXPOSE 4173
CMD ["npm", "run", "preview"]
