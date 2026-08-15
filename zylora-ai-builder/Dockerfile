FROM node:24.6.0-alpine
WORKDIR /srv/ai-builder
ENV NODE_ENV=production PORT=8090
RUN addgroup -S zylora && adduser -S zylora -G zylora
COPY --chown=zylora:zylora package.json ./
COPY --chown=zylora:zylora src ./src
USER zylora
EXPOSE 8090
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:8090/liveness').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "src/server.mjs"]