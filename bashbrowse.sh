#!/usr/bin/env bash
# BashBrowse — a tiny text-based browser for Bash, curl, and Python 3.
# Free to use. JavaScript-heavy sites may not render correctly.

set -u

# Serve the GUI over localhost instead of opening a Termux-private file:// URL.
# Android Chrome cannot reliably read files directly from Termux's private storage.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
GUI_URL="http://127.0.0.1:8765/bashbrowse.html"

if [[ -f "$SCRIPT_DIR/bashbrowse.html" ]] && command -v python3 >/dev/null 2>&1; then
    if ! curl -fsS --max-time 1 "$GUI_URL" >/dev/null 2>&1; then
        python3 -m http.server 8765 --bind 127.0.0.1 --directory "$SCRIPT_DIR" \
            >"$SCRIPT_DIR/.bashbrowse-server.log" 2>&1 &
        SERVER_PID=$!
        # Wait briefly for the local server to start.
        for _ in {1..20}; do
            if curl -fsS --max-time 1 "$GUI_URL" >/dev/null 2>&1; then
                break
            fi
            sleep 0.25
        done
    fi

    if curl -fsS --max-time 2 "$GUI_URL" >/dev/null 2>&1; then
        if command -v termux-open-url >/dev/null 2>&1; then
            termux-open-url "$GUI_URL"
            exit $?
        elif command -v termux-open >/dev/null 2>&1; then
            termux-open "$GUI_URL"
            exit $?
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$GUI_URL" >/dev/null 2>&1 &
            exit 0
        elif command -v open >/dev/null 2>&1; then
            open "$GUI_URL"
            exit $?
        else
            printf 'BashBrowse GUI is running at: %s\n' "$GUI_URL"
            exit 0
        fi
    else
        printf 'Could not start the BashBrowse web server. See %s/.bashbrowse-server.log\n' "$SCRIPT_DIR" >&2
    fi
fi

URL="https://example.com"
declare -a HISTORY=()
PAGE_HTML=""

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        printf 'Missing dependency: %s\n' "$1"
        exit 1
    }
}

load_page() {
    PAGE_HTML=$(curl -fLsS --max-time 25 "$URL") || {
        printf '\nCould not load: %s\n' "$URL"
        PAGE_HTML=""
        return 1
    }
    return 0
}

render_page() {
    clear
    printf '%s\n' '============================================'
    printf '%s\n' '             BashBrowse 🌐'
    printf '%s\n' '============================================'
    printf 'URL: %s\n' "$URL"
    printf '%s\n' '--------------------------------------------'

    if [[ -z "$PAGE_HTML" ]]; then
        printf 'No page content available. Try [r]eload or [o]pen URL.\n'
        return
    fi

    printf '%s' "$PAGE_HTML" | python3 -c '
from html.parser import HTMLParser
import sys

class TextPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.links = []
        self.title = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "title":
            self.title = True
        if tag == "a" and attrs.get("href"):
            self.links.append((attrs["href"], " ".join(attrs.get("title", "").split())))
            print(f" [{len(self.links)}] ", end="")
        if tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "li", "tr", "section"):
            print()
        if tag == "img" and attrs.get("alt") and not self.skip:
            print("[Image: " + attrs["alt"] + "]", end=" ")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        if tag == "title":
            self.title = False
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "li", "tr", "section"):
            print()
    def handle_data(self, data):
        if self.skip:
            return
        text = " ".join(data.split())
        if text:
            print(text, end=" ")
    def close(self):
        super().close()
        print("\n\n-------------- LINKS --------------")
        for i, (url, title) in enumerate(self.links, 1):
            suffix = (" — " + title) if title else ""
            print(f"[{i}] {url}{suffix}")

parser = TextPage()
parser.feed(sys.stdin.read())
parser.close()
'
}

open_url() {
    local target="$1"
    if [[ "$target" =~ ^https?:// ]]; then
        :
    elif [[ "$target" =~ ^[[:alnum:]][[:alnum:].+-]*: ]]; then
        printf 'Only http:// and https:// URLs are supported.\n'
        return 1
    else
        target="https://$target"
    fi
    HISTORY+=("$URL")
    URL="$target"
    load_page || true
}

need_cmd curl
need_cmd python3
load_page || true

while true; do
    render_page
    printf '\nCommands: [o] open URL/link  [b] back  [r] reload  [q] quit\n'
    read -r -p 'BashBrowse> ' cmd || break

    case "$cmd" in
        o|O)
            read -r -p 'URL or link number: ' target
            if [[ "$target" =~ ^[0-9]+$ ]]; then
                resolved=$(printf '%s' "$PAGE_HTML" | python3 -c '
from html.parser import HTMLParser
from urllib.parse import urljoin
import sys
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items=[]
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href=dict(attrs).get("href")
            if href:
                self.items.append(href)
p=Links()
p.feed(sys.stdin.read())
n=int(sys.argv[1])
if 1 <= n <= len(p.items):
    print(urljoin(sys.argv[2], p.items[n-1]))
' "$target" "$URL" 2>/dev/null) || resolved=""
                if [[ -n "$resolved" ]]; then
                    open_url "$resolved"
                else
                    printf 'That link number was not found.\n'
                    sleep 1
                fi
            elif [[ -n "$target" ]]; then
                open_url "$target"
            fi
            ;;
        b|B)
            if (("${#HISTORY[@]}" > 0)); then
                URL="${HISTORY[-1]}"
                unset 'HISTORY[-1]'
                load_page || true
            else
                printf 'No previous page in history.\n'
                sleep 1
            fi
            ;;
        r|R) load_page || true ;;
        q|Q) printf 'Goodbye! 👋\n'; exit 0 ;;
        *) printf 'Unknown command.\n'; sleep 1 ;;
    esac
done
