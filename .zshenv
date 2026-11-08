# CA local do homelab (Caddy): Node confia em https://*.home.void
[ -f "$HOME/caddy-root.crt" ] && export NODE_EXTRA_CA_CERTS="$HOME/caddy-root.crt"
