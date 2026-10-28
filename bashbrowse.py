#!/usr/bin/env python3
"""BashBrowse: a tiny in-Termux text browser (no Chrome, no local web server)."""
import curses
import html
import re
import textwrap
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

HOME = "https://htmlonly.com/"

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.links, self.buf = [], [], ""
        self.skip = 0
        self.in_title = False
        self.title = ""
    def flush(self):
        s = re.sub(r"\s+", " ", self.buf).strip()
        if s:
            self.lines.append(s)
        self.buf = ""
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg", "head"):
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag == "a" and a.get("href"):
            self.flush()
            self.links.append((a["href"], ""))
            self.buf = f"[{len(self.links)}] "
        if tag in ("p","div","br","h1","h2","h3","h4","h5","li","tr","section","article","header","footer"):
            self.flush()
        if tag == "img" and a.get("alt") and not self.skip:
            self.buf += "[Image: " + a["alt"] + "] "
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "head") and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False
        if tag in ("p","div","br","h1","h2","h3","h4","h5","li","tr","section","article","header","footer","a"):
            self.flush()
    def handle_data(self, data):
        if self.skip:
            return
        if self.in_title:
            self.title += data
        if data.strip():
            self.buf += data + " "
    def close(self):
        super().close()
        self.flush()

class Browser:
    def __init__(self):
        self.url = HOME
        self.history = []
        self.forward = []
        self.lines = []
        self.links = []
        self.title = "BashBrowse"
        self.scroll = 0
        self.selected = 0
        self.status = "Loading page…"
        self.load(self.url, add_history=False)
    def load(self, url, add_history=True):
        url = url.strip()
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        if urlparse(url).scheme not in ("http", "https"):
            self.status = "Only http and https URLs are supported."
            return
        if add_history and self.url:
            self.history.append(self.url)
            self.forward.clear()
        self.url = url
        self.scroll = 0
        self.selected = 0
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"BashBrowse/1.0 (text browser)"})
            with urllib.request.urlopen(req, timeout=18) as response:
                data = response.read(2_500_000).decode(response.headers.get_content_charset() or "utf-8", "replace")
                self.url = response.geturl()
            parser = PageParser()
            parser.feed(data)
            self.lines = parser.lines or ["(This page contains no readable text.)"]
            self.links = [(urljoin(self.url, href), label) for href, label in parser.links]
            self.title = " ".join(parser.title.split()) or self.url
            self.status = f"Loaded: {self.title} · {len(self.links)} links"
        except Exception as e:
            self.lines = ["Could not load this page.", "", str(e), "", "Press g to enter another URL or r to retry."]
            self.links = []
            self.title = "Load error"
            self.status = "Load failed"
    def back(self):
        if self.history:
            self.forward.append(self.url)
            self.load(self.history.pop(), False)
        else:
            self.status = "No previous page"
    def next_page(self):
        if self.forward:
            self.history.append(self.url)
            self.load(self.forward.pop(), False)
        else:
            self.status = "No forward page"

def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    except Exception:
        pass
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)
    except Exception:
        pass
    b = Browser()
    button_ranges = []
    def put(y, x, text, attr=0, maxw=None):
        h, w = stdscr.getmaxyx()
        if y < 0 or y >= h or x >= w: return
        text = str(text).replace("\n", " ")
        if maxw is not None: text = text[:maxw]
        try: stdscr.addnstr(y, max(0,x), text, max(0,w-max(0,x)-1), attr)
        except curses.error: pass
    def prompt(label):
        curses.echo()
        try: curses.curs_set(1)
        except Exception: pass
        h,w = stdscr.getmaxyx()
        put(h-1,0,(label+" ")[:w-1], curses.color_pair(1))
        try:
            s = stdscr.getstr(h-1, min(len(label)+1,w-2), max(1,w-min(len(label)+2,w-2))).decode("utf-8","replace")
        except Exception: s = ""
        curses.noecho()
        try: curses.curs_set(0)
        except Exception: pass
        return s.strip()
    while True:
        stdscr.erase()
        h,w = stdscr.getmaxyx()
        if h < 8 or w < 35:
            put(0,0,"Enlarge the Termux terminal, then press any key.")
            stdscr.refresh(); stdscr.getch(); continue
        put(0,0," BashBrowse ",curses.color_pair(1)|curses.A_BOLD)
        controls = [("← Back","b"),("Forward →","f"),("↻ Reload","r"),("Go / URL","g"),("Home","h"),("Quit","q")]
        button_ranges=[]
        x=12
        for label,key in controls:
            txt=f"[ {label} ]"
            if x+len(txt)<w:
                put(0,x,txt,curses.color_pair(2)|curses.A_BOLD)
                button_ranges.append((x,x+len(txt),key))
                x += len(txt)+1
        put(1,0," URL: "+b.url,curses.A_BOLD,w-1)
        put(2,0,"─"* (w-1),curses.color_pair(2))
        put(3,0," "+b.title,curses.color_pair(3)|curses.A_BOLD,w-1)
        content_h=h-6
        maxscroll=max(0,len(b.lines)-content_h)
        b.scroll=max(0,min(b.scroll,maxscroll))
        for i in range(content_h):
            idx=b.scroll+i
            if idx < len(b.lines):
                put(4+i,0,b.lines[idx],0,w-1)
        put(h-2,0,"─"*(w-1),curses.color_pair(2))
        put(h-2,0," "+b.status,curses.color_pair(2),w-1)
        put(h-1,0,"↑↓ scroll  Tab/←→ select link  Enter open  g URL  b back  f forward  r reload  q quit",curses.A_DIM,w-1)
        stdscr.refresh()
        ch=stdscr.getch()
        if ch in (ord('q'),ord('Q')): break
        elif ch in (ord('g'),ord('G')):
            target=prompt("Open URL:")
            if target: b.load(target)
        elif ch in (ord('b'), curses.KEY_BACKSPACE, 127): b.back()
        elif ch in (ord('f'),): b.next_page()
        elif ch in (ord('r'),ord('R')): b.load(b.url,False)
        elif ch in (ord('h'),ord('H')): b.load(HOME)
        elif ch in (curses.KEY_UP,):
            b.scroll=max(0,b.scroll-1)
        elif ch in (curses.KEY_DOWN,):
            b.scroll=min(max(0,len(b.lines)-(h-6)),b.scroll+1)
        elif ch in (curses.KEY_PPAGE,): b.scroll=max(0,b.scroll-(h-6))
        elif ch in (curses.KEY_NPAGE,): b.scroll=min(max(0,len(b.lines)-(h-6)),b.scroll+(h-6))
        elif ch in (9,curses.KEY_RIGHT):
            if b.links: b.selected=(b.selected+1)%len(b.links)
            b.status=f"Selected link [{b.selected+1}/{len(b.links)}]: {b.links[b.selected][0]}" if b.links else "No links on this page"
        elif ch==curses.KEY_LEFT:
            if b.links: b.selected=(b.selected-1)%len(b.links)
            else: b.back()
        elif ch in (10,13,curses.KEY_ENTER):
            if b.links: b.load(b.links[b.selected][0])
        elif ch in (ord('o'),ord('O')):
            n=prompt("Open link number (or URL):")
            if n.isdigit() and 1<=int(n)<=len(b.links): b.load(b.links[int(n)-1][0])
            elif n: b.load(n)
        elif ch==curses.KEY_MOUSE:
            try:
                _,mx,my,_,_=curses.getmouse()
                if my==0:
                    for left,right,key in button_ranges:
                        if left<=mx<right:
                            if key=='b': b.back()
                            elif key=='f': b.next_page()
                            elif key=='r': b.load(b.url,False)
                            elif key=='g':
                                target=prompt("Open URL:")
                                if target: b.load(target)
                            elif key=='h': b.load(HOME)
                            elif key=='q': return
                            break
            except Exception: pass
        elif ch in (ord('1'),ord('2'),ord('3'),ord('4'),ord('5'),ord('6'),ord('7'),ord('8'),ord('9')):
            n=int(chr(ch))
            if 1<=n<=len(b.links): b.load(b.links[n-1][0])

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
