FROM node:22-alpine

WORKDIR /app
COPY server.js ./server.js

ENV PORT=8099
ENV DATA_DIR=/data
EXPOSE 8099

CMD ["node", "server.js"]
