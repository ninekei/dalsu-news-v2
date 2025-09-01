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
BASE = "https://news.nate.com/rank/interest?sc=all&p=day&date="
W,H=1080,1920
OUT_DIR="out"
ASSETS="assets"

FONT_PATH_CANDIDATES=[
    "assets/fonts/NanumGothic.ttf",
    "assets/fonts/NotoSansKR-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/Supplemental/AppleSDGothicNeo.ttc",
]

def ensure_font():
    for p in FONT_PATH_CANDIDATES:
        if os.path.exists(p):
            return p
    raise RuntimeError("❌ 한글 폰트를 찾을 수 없습니다. assets/fonts에 폰트를 추가하세요.")

def yyyymmdd(offset=0):
    d=datetime.datetime.now(tz=KST)-datetime.timedelta(days=offset)
    return d.strftime("%Y%m%d")

def fetch_html(url):
    headers={"User-Agent":"Mozilla/5.0 (DalsuBot)"}
    r=requests.get(url,headers=headers,timeout=20); r.raise_for_status()
    return r.text

def parse_top(url,take=6):
    html=fetch_html(url)
    soup=BeautifulSoup(html,"lxml")
    links=[]
    for a in soup.find_all("a",href=True):
        href=a["href"]
        if href.startswith("https://news.nate.com/view/"):
            title=a.get_text(" ",strip=True)
            if title and len(title)>5:
                links.append((title,href))
    seen=set(); items=[]
    for t,u in links:
        if (u,t) in seen: continue
        seen.add((u,t))
        items.append({"title":t,"url":u})
        if len(items)>=take: break
    return items

def og_image(url):
    try:
        h=fetch_html(url)
        m=re.search("<meta[^>]+property=['\"]og:image['\"][^>]+content=['\"]([^'\"]+)['\"]",h,re.I)
        if m: return m.group(1).replace("&amp;","&")
    except: return ""
    return ""

def download_image(url,fname):
    if not url: return None
    try:
        r=requests.get(url,timeout=20)
        if r.status_code==200:
            p=os.path.join(OUT_DIR,fname)
            open(p,"wb").write(r.content); return p
    except: return None
    return None

def fetch_summary(article_url,max_len=30):
    try:
        html=fetch_html(article_url)
        soup=BeautifulSoup(html,"lxml")
        p_tags=soup.select("div.article p")
        if not p_tags: p_tags=soup.find_all("p")
        text=" ".join(p.get_text(" ",strip=True) for p in p_tags)
        if not text: return ""
        return text[:max_len]+"…" if len(text)>max_len else text
    except: return ""

def default_gagline(title):
    return "오늘도 달수는 쿨~합니다!"

def wrap(text,width=22): return "\n".join(textwrap.wrap(text,width=width))

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
    if title: draw.multiline_text((60,80),wrap(title,18),fill="white",font=font_title,stroke_fill="black",stroke_width=2)
    if caption: draw.multiline_text((60,H-400),wrap(caption,20),fill="white",font=font_body,stroke_fill="black",stroke_width=2)
    tmp=os.path.join(OUT_DIR,f"slide_{uuid.uuid4().hex}.png"); base.save(tmp,"PNG")
    return ImageClip(tmp).set_duration(dur)

def main():
    os.makedirs(OUT_DIR,exist_ok=True)
    date=yyyymmdd(0); url=BASE+date; items=parse_top(url,TAKE)
    if not items:
        print("오늘 뉴스 없음→어제 뉴스로 대체")
        date=yyyymmdd(1); url=BASE+date; items=parse_top(url,TAKE)
    for i,it in enumerate(items,1):
        it["image"]=og_image(it["url"])
        it["img_file"]=download_image(it["image"],f"news_{i}.jpg")
        it["sec"]=DEFAULT_SEC
        it["summary"]=fetch_summary(it["url"])
        it["gag"]=default_gagline(it["title"])
    md=["## 인트로","안녕하십니까, 수달 아나운서 달수입니다.","오늘의 뉴스를 전해드리겠습니다.",""]
    for i,it in enumerate(items,1):
        md+=[f"### 뉴스 {i}",f"- 제목: {it['title']}",f"- 요약: {it['summary']}",f"- 멘트: {it['gag']}",""]
    md+=["## 클로징","지금까지 달수 뉴스였습니다.","내일도 쿨~하게 전해드리겠습니다."]
    open(os.path.join(OUT_DIR,f"Dalsu_{date}.md"),"w",encoding="utf-8").write("\n".join(md))
    # srt
    def srt_time(sec): return f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d},000"
    idx,t=1,0; srt=[]
    srt.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+INTRO_SEC)}\n안녕하십니까\n수달 아나운서 달수입니다.\n오늘의 뉴스를 전해드리겠습니다.\n")
    idx+=1; t+=INTRO_SEC
    for i,it in enumerate(items,1):
        srt.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+it['sec'])}\n{it['summary']}\n{it['gag']}\n"); idx+=1; t+=it['sec']
    srt.append(f"{idx}\n{srt_time(t)} --> {srt_time(t+CLOSING_SEC)}\n지금까지 달수 뉴스였습니다.\n내일도 쿨~하게 소식 전해드리겠습니다.\n")
    open(os.path.join(OUT_DIR,f"Dalsu_{date}.srt"),"w",encoding="utf-8").write("\n".join(srt))
    # video
    intro_img=os.path.join(ASSETS,"intro.png"); outro_img=os.path.join(ASSETS,"outro.png")
    intro=make_slide(intro_img,"달수 뉴스룸",INTRO_SEC,"오늘의 뉴스를 전해드립니다.")
    news=[make_slide(it["img_file"],"",it["sec"],f"{it['summary']}\n{it['gag']}") for it in items]
    outro=make_slide(outro_img,"지금까지 달수 뉴스였습니다",CLOSING_SEC,"내일도 쿨~하게 소식 전해드리겠습니다.")
    final=concatenate_videoclips([intro,*news,outro],method="compose")
    outmp4=os.path.join(OUT_DIR,f"Dalsu_{date}.mp4"); final.write_videofile(outmp4,fps=30,codec="libx264",audio=False)

if __name__=="__main__": main()
