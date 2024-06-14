# api id, hash
API_ID = 1488
API_HASH = 'abcde1488'


DELAYS = {
    'ACCOUNT': [5, 15],  # delay between connections to accounts (the more accounts, the longer the delay)
}

PROXY_TYPES = {
    "TG": "socks5",  # proxy type for tg client. "socks4", "socks5" and "http" are supported
    "REQUESTS": "socks5"  # proxy type for requests. "http" for https and http proxys, "socks5" for socks5 proxy.
}

# session folder (do not change)
WORKDIR = "sessions/"

# timeout in seconds for checking accounts on valid
TIMEOUT = 30
