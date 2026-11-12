FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Optional banner text for a public demo deployment (see deploy/docker-compose.single.yml)
ARG VITE_DEMO_NOTICE=""
ENV VITE_DEMO_NOTICE=$VITE_DEMO_NOTICE
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
RUN chmod -R a+rX /usr/share/nginx/html && chmod 644 /etc/nginx/conf.d/default.conf
EXPOSE 80
