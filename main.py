\
import os, re, io, datetime, textwrap
import requests
from bs4 import BeautifulSoup
from dateutil.tz import gettz
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips

KST = gettz("Asia/Seoul")
TAKE = 6
INTRO_SEC = 6
CLOSING_SEC = 6
DEFAULT_SEC = 22
BASE = "https://news.nate.com/rank/interest?sc=all&p=day&date="
W, H = 1080, 1920
OUT_DIR = "out"
ASSETS = "assets"

FONT_PATH_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/Supplemental/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

def ensure_font():
    for p in FONT_PATH_CANDIDATES:
        if os.path.exists(p):
            return p
    return None

def today_yyyymmdd():
    return datetime.datetime.now(tz=KST).strftime("%Y%m%d")

def fetch_html(url):
    headers = {"User-Agent":"Mozilla/5.0 (compatible; DalsuNewsBot/1.0)"}
    return requests.get(url, headers=headers, timeout=20).text

def parse_top(url, take=6):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("https://news.nate.com/view/"):
            title = a.get_text(" ", strip=True)
            if title and len(title) > 5:
                links.append((title, href))
    seen=set(); items=[]
    for t,u in links:
        if (u,t) in seen: continue
        seen.add((u,t))
        items.append({"title":t,"url":u})
        if len(items)>=take: break
    return items

def og_image(url):
    try:
        h = fetch_html(url)
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', h, re.I)
        if m:
            return m.group(1).replace("&amp;","&")
    except Exception: pass
    return ""

def download_image(url, fname):
    if not url: return None
    try:
        r = requests.get(url, timeout=20)
        if r.status_code==200:
            pth = os.path.join(OUT_DIR,fname)
            with open(pth,"wb") as f: f.write(r.content)
            return pth
    except Exception: return None
    return None

def fetch_summary(article_url, max_len=30):
    try:
        html = fetch_html(article_url)
        soup = BeautifulSoup(html, "lxml")
        p_tags = soup.select("div.article p")
        if not p_tags:
            p_tags = soup.find_all("p")
        text = " ".join(p.get_text(" ", strip=True) for p in p_tags)
        if not text: return ""
        return text[:max_len] + "…" if len(text)>max_len else text
    except Exception: return ""

def default_gagline(title):
    return "오늘도 달수는 쿨~합니다!"

def wrap(text, width=22):
    return "\n".join(textwrap.wrap(text,width=width))

def make_slide(img_path, title, dur, caption=None):
    base = Image.new("RGB",(W,H),"black")
    if img_path and os.path.exists(img_path):
        im = Image.open(img_path).convert("RGB")
        im.thumbnail((W,int(H*0.6)))
        bx=(W-im.width)//2
        by=(int(H*0.55)-im.height)//2+int(H*0.15)
        base.paste(im,(bx,by))
    draw = ImageDraw.Draw(base)
    font_path = ensure_font()
    font_title = ImageFont.truetype(font_path,64) if font_path else None
    font_body = ImageFont.truetype(font_path,48) if font_path else None
    if title:
        draw.multiline_text((60,80), wrap(title,18), fill="white", font=font_title, stroke_fill="black", stroke_width=3)
    if caption:
        draw.multiline_text((60,H-400), wrap(caption,20), fill="white", font=font_body, stroke_fill="black", stroke_width=2)
    buf = io.BytesIO(); base.save(buf,format="PNG"); buf.seek(0)
    clip = ImageClip(buf).set_duration(dur)
    return clip

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    date = today_yyyymmdd()
    url = BASE+date
    items = parse_top(url, TAKE)
    for i,it in enumerate(items, start=1):
        it["image"]=og_image(it["url"])
        it["img_file"]=download_image(it["image"], f"news_{i}.jpg")
        it["sec"]=DEFAULT_SEC
        it["summary"]=fetch_summary(it["url"])
        it["gag"]=default_gagline(it["title"])

    # 대본(MD)
    md_lines=["## 🎬 인트로","안녕하십니까, 수달 아나운서 달수입니다.","오늘의 뉴스를 전해드리겠습니다.",""]
    for i,it in enumerate(items,1):
        md_lines += [f"### 뉴스 {i}",
                     f"- 제목: {it['title']}",
                     f"- 요약: {it['summary']}",
                     f"- 능청 멘트: {it['gag']}",""]
    md_lines+=["## 🎤 클로징","지금까지 달수 뉴스였습니다.","내일도 쿨~하게 소식 전해드리겠습니다."]
    with open(os.path.join(OUT_DIR,f"Dalsu_{date}.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # 자막(SRT)
    def srt_time(sec):
        h=sec//3600; m=(sec%3600)//60; s=sec%60
        return f"{h:02d}:{m:02d}:{s:02d},000"
    idx,t=1,0; srt_blocks=[]
    srt_blocks.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+INTRO_SEC)}\n안녕하십니까\n수달 아나운서 달수입니다.\n오늘의 뉴스를 전해드리겠습니다.\n")
    idx+=1; t+=INTRO_SEC
    for i,it in enumerate(items,1):
        srt_blocks.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+it['sec'])}\n{it['summary']}\n{it['gag']}\n")
        idx+=1; t+=it['sec']
    srt_blocks.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+CLOSING_SEC)}\n지금까지 달수 뉴스였습니다.\n내일도 쿨~하게 소식 전해드리겠습니다.\n")
    with open(os.path.join(OUT_DIR,f"Dalsu_{date}.srt"),"w",encoding="utf-8") as f:
        f.write("\n".join(srt_blocks))

    # 영상
    intro_img=os.path.join(ASSETS,"intro.png")
    outro_img=os.path.join(ASSETS,"outro.png")
    intro_clip=make_slide(intro_img,"달수 뉴스룸",INTRO_SEC,"오늘의 뉴스를 전해드립니다.")
    news_clips=[make_slide(it["img_file"],"",it["sec"], f"{it['summary']}\n{it['gag']}") for it in items]
    outro_clip=make_slide(outro_img,"지금까지 달수 뉴스였습니다",CLOSING_SEC,"내일도 쿨~하게 소식 전해드리겠습니다.")
    final=concatenate_videoclips([intro_clip,*news_clips,outro_clip],method="compose")
    outmp4=os.path.join(OUT_DIR,f"Dalsu_{date}.mp4")
    final.write_videofile(outmp4,fps=30,codec="libx264",audio=False)

if __name__=="__main__":
    main()
