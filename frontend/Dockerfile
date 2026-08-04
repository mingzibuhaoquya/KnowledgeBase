FROM node:24-alpine AS build

WORKDIR /app/frontend

ARG VITE_API_BASE_URL=http://127.0.0.1:8018/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80

