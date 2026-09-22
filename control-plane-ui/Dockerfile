FROM node:22-alpine AS build
WORKDIR /app
COPY control-plane-ui/package*.json ./
RUN npm install
COPY control-plane-ui/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY control-plane-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/control-plane/browser /usr/share/nginx/html
EXPOSE 80
