FROM node:20-alpine AS build

WORKDIR /app/frontend

ARG VITE_APP_BASE_PATH=/
ENV VITE_APP_BASE_PATH=${VITE_APP_BASE_PATH}

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80
