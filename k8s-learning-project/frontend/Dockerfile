FROM nginx:1.27-alpine

ENV API_UPSTREAM=http://backend:8000 \
    NGINX_ENVSUBST_FILTER=^API_UPSTREAM$

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY src/ /usr/share/nginx/html/

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

