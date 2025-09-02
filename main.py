\
import os, re, datetime, textwrap, uuid
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
BASE = "https://news.nate.com/rank"
W, H = 1080, 1920
OUT_DIR = "out"
ASSETS = "assets"

FONT_PATH_CANDIDATES = [
    "assets/fonts/NanumGothic.ttf",
    "assets/fonts/NotoSansKR-Regular.otf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/Supplemental/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/malgun.ttf",
]

def ensure_font():
    for p in FONT_PATH_CANDIDATES:
        if os.path.exists(p):
            return p
    raise RuntimeError("❌ 폰트를 찾을 수 없습니다. assets/fonts에 NanumGothic.ttf 추가하세요.")

def yyyymmdd(offset=0):
    d = datetime.datetime.now(tz=KST)-datetime.timedelta(days=offset)
    return d.strftime("%Y%m%d")

def fetch_html(url):
    headers={"User-Agent":"Mozilla/5.0 DalsuBot"}
    r=requests.get(url,headers=headers,timeout=20)
    r.raise_for_status()
    return r.text

def abs_url(href):
    if not href: return ""
    if href.startswith("//"): return "https:"+href
    if href.startswith("/"): return "https://news.nate.com"+href
    if href.startswith("http"): return href
    return ""

def fetch_og_title(url):
    try:
        h=fetch_html(url)
        m=re.search(r'<meta[^>]+property=[\'"]og:title[\'"][^>]+content=[\'"]([^\'"]+)[\'"]',h,re.I)
        if m: return m.group(1).strip()
        t=re.search(r'<title>([^<]+)</title>',h,re.I)
        return t.group(1).strip() if t else ""
    except: return ""

def parse_top(url,take=6):
    html=fetch_html(url)
    soup=BeautifulSoup(html,"lxml")
    cand=[]
    for a in soup.select("div.ranknews a[href]"):
        u=abs_url(a.get("href",""))
        if "news.nate.com/view/" in u:
            title=a.get_text(" ",strip=True)
            cand.append((title,u))
    if len(cand)<take:
        for u in re.findall(r'https://news\.nate\.com/view/[0-9A-Za-z]+',html):
            cand.append(("",u))
    items,seen=[],set()
    for title,u in cand:
        if not u or u in seen: continue
        seen.add(u)
        t=(title or "").strip()
        if len(t)<6:
            t2=fetch_og_title(u)
            if t2: t=t2
        if t: items.append({"title":t,"url":u})
        if len(items)>=take: break
    return items

def og_image(url):
    try:
        h=fetch_html(url)
        m=re.search(r'<meta[^>]+property=[\'"]og:image[\'"][^>]+content=[\'"]([^\'"]+)[\'"]',h,re.I)
        if m: return m.group(1).replace("&amp;","&")
    except: return ""
    return ""

def download_image(url,fname):
    if not url: return None
    try:
        r=requests.get(url,timeout=20)
        if r.status_code==200:
            p=os.path.join(OUT_DIR,fname)
            with open(p,"wb") as f: f.write(r.content)
            return p
    except: return None
    return None

def fetch_summary(url,max_len=30):
    try:
        html=fetch_html(url)
        soup=BeautifulSoup(html,"lxml")
        p_tags=soup.select("div.article p")
        if not p_tags: p_tags=soup.find_all("p")
        text=" ".join(p.get_text(" ",strip=True) for p in p_tags)
        if not text: return ""
        return text[:max_len]+"…" if len(text)>max_len else text
    except: return ""

def default_gagline(title):
    return "오늘도 달수는 쿨~합니다!"

def wrap(text,width=22):
    return "\n".join(textwrap.wrap(text,width=width))

def make_slide(img_path,title,dur,caption=None):
    base=Image.new("RGB",(W,H),"black")
    if img_path and os.path.exists(img_path):
        im=Image.open(img_path).convert("RGB")
        im.thumbnail((W,int(H*0.6)))
        bx=(W-im.width)//2; by=(int(H*0.55)-im.height)//2+int(H*0.15)
        base.paste(im,(bx,by))
    draw=ImageDraw.Draw(base)
    font_path=ensure_font()
    try:
        font_title=ImageFont.truetype(font_path,64)
        font_body=ImageFont.truetype(font_path,48)
    except:
        font_title=ImageFont.load_default(); font_body=ImageFont.load_default()
    if title:
        draw.multiline_text((60,80),wrap(title,18),fill="white",font=font_title,stroke_fill="black",stroke_width=2)
    if caption:
        draw.multiline_text((60,H-400),wrap(caption,20),fill="white",font=font_body,stroke_fill="black",stroke_width=2)
    os.makedirs(OUT_DIR,exist_ok=True)
    tmp=os.path.join(OUT_DIR,f"slide_{uuid.uuid4().hex}.png")
    base.save(tmp,"PNG")
    return ImageClip(tmp).set_duration(dur)

def main():
    os.makedirs(OUT_DIR,exist_ok=True)
    date=yyyymmdd()
    items=parse_top(BASE,TAKE)
    if not items: raise RuntimeError("❌ 뉴스를 찾지 못했습니다.")
    for i,it in enumerate(items,1):
        it["image"]=og_image(it["url"])
        it["img_file"]=download_image(it["image"],f"news_{i}.jpg")
        it["sec"]=DEFAULT_SEC
        it["summary"]=fetch_summary(it["url"])
        it["gag"]=default_gagline(it["title"])
    # md
    md=["## 🎬 인트로","안녕하십니까, 수달 아나운서 달수입니다.","오늘의 뉴스를 전해드리겠습니다.",""]
    for i,it in enumerate(items,1):
        md+=[f"### 뉴스 {i}",f"- 제목: {it['title']}",f"- 요약: {it['summary']}",f"- 능청 멘트: {it['gag']}",""]
    md+=["## 🎤 클로징","지금까지 달수 뉴스였습니다.","내일도 쿨~하게 소식 전해드리겠습니다."]
    open(os.path.join(OUT_DIR,f"Dalsu_{date}.md"),"w",encoding="utf-8").write("\n".join(md))
    # srt
    def srt_time(sec): h=sec//3600; m=(sec%3600)//60; s=sec%60; return f"{h:02d}:{m:02d}:{s:02d},000"
    idx,t=1,0; srt=[]
    srt.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+INTRO_SEC)}\n안녕하십니까\n수달 아나운서 달수입니다.\n오늘의 뉴스를 전해드리겠습니다.\n"); idx+=1; t+=INTRO_SEC
    for i,it in enumerate(items,1):
        srt.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+it['sec'])}\n{it['summary']}\n{it['gag']}\n"); idx+=1; t+=it['sec']
    srt.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+CLOSING_SEC)}\n지금까지 달수 뉴스였습니다.\n내일도 쿨~하게 소식 전해드리겠습니다.\n")
    open(os.path.join(OUT_DIR,f"Dalsu_{date}.srt"),"w",encoding="utf-8").write("\n".join(srt))
    # video
    intro=make_slide(os.path.join(ASSETS,"intro.png"),"달수 뉴스룸",INTRO_SEC,"오늘의 뉴스를 전해드립니다.")
    news=[make_slide(it["img_file"],"",it["sec"],f"{it['summary']}\n{it['gag']}") for it in items]
    outro=make_slide(os.path.join(ASSETS,"outro.png"),"지금까지 달수 뉴스였습니다",CLOSING_SEC,"내일도 쿨~하게 소식 전해드리겠습니다.")
    final=concatenate_videoclips([intro,*news,outro],method="compose")
    final.write_videofile(os.path.join(OUT_DIR,f"Dalsu_{date}.mp4"),fps=30,codec="libx264",audio=False)

if __name__=="__main__": main()
