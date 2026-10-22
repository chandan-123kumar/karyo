from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math

OUT=Path(__file__).parent
im=Image.new('RGB',(1800,1500),'#10151d'); d=ImageDraw.Draw(im)
regular='/System/Library/Fonts/Supplemental/Arial.ttf'
bold='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def text(x,y,s,size=28,color='#dce5ef',heavy=False):
    d.text((x,y),s,font=ImageFont.truetype(bold if heavy else regular,size),fill=color)
def box(x,y,w,h,title,lines,accent='#b8df87'):
    d.rounded_rectangle((x,y,x+w,y+h),radius=20,fill='#202a36',outline='#415166',width=2)
    d.rounded_rectangle((x+22,y+25,x+28,y+56),radius=2,fill=accent)
    text(x+44,y+24,title,29,heavy=True)
    for i,line in enumerate(lines):text(x+25,y+82+i*36,line,25,'#b1bfd0')
def arrow(points,color='#b8df87',both=False):
    d.line(points,fill=color,width=4,joint='curve')
    def head(a,b):
        t=math.atan2(b[1]-a[1],b[0]-a[0]);n=14
        d.polygon([b,(b[0]-n*math.cos(t-.5),b[1]-n*math.sin(t-.5)),(b[0]-n*math.cos(t+.5),b[1]-n*math.sin(t+.5))],fill=color)
    head(points[-2],points[-1])
    if both:head(points[1],points[0])
text(80,65,'KARYO',26,'#b8df87',True)
text(80,115,'A coding agent you can inspect.',65,heavy=True)
text(83,206,'From a terminal prompt to a model response — with a local record of every step.',29,'#a5b4c6')
d.rounded_rectangle((80,300,1190,1290),radius=28,fill='#151e29',outline='#36465a',width=2)
text(110,325,'YOUR MACHINE',21,'#b8df87',True)
d.rounded_rectangle((1250,300,1720,920),radius=28,fill='#182332',outline='#456481',width=2)
text(1280,325,'HOSTED INFERENCE',21,'#8ec8ff',True)
box(120,400,220,170,'You',['Terminal','query'])
box(410,400,340,170,'Karyo CLI',['Conversation memory','Agent + tool loop'])
box(820,400,330,170,'Configuration',['Provider + model','Timeout + output limit'])
arrow([(340,480),(410,480)])
arrow([(820,480),(750,480)],'#8092a9')
box(410,730,340,185,'Local tools',['Read / write files','Search + shell'])
arrow([(580,570),(580,730)],both=True)
text(610,638,'Calls / results',22,'#b8df87')
box(1280,400,410,375,'Hugging Face',['Inference routing','','Featherless AI (default)','','Qwen3-Coder-Next'],'#8ec8ff')
arrow([(750,535),(785,535),(785,640),(1280,640)],'#8ec8ff',both=True)
text(835,596,'Requests / responses',25,'#8ec8ff')
text(1282,817,'Only inference runs remotely.',23,'#a5b4c6')
text(1282,855,'Prompts go to the provider.',23,'#a5b4c6')
box(120,1040,445,195,'Session log · JSONL',['User turns + model I/O','Tool calls + results','Tokens + timing + status'])
box(660,1040,490,195,'Local trace viewer',['Read-only localhost server','Browser: sessions + call details','Live refresh + raw JSON'])
arrow([(410,525),(370,525),(370,980),(250,980),(250,1040)])
text(130,785,'Record each',24,'#b8df87')
text(130,821,'conversation',24,'#b8df87')
arrow([(580,915),(580,985),(455,985),(455,1040)])
arrow([(565,1130),(660,1130)])
text(577,1088,'Read',21,'#b8df87')
text(1255,1000,'VISIBLE BY DESIGN',23,'#b8df87',True)
text(1255,1058,'One session per launch.',25)
text(1255,1101,'Each turn stays connected.',25)
text(1255,1144,'Inspect inputs and outputs.',25)
text(1255,1205,'Local logs may contain',23,'#9baabe')
text(1255,1238,'private conversation data.',23,'#9baabe')
d.line((80,1345,1720,1345),fill='#36465a',width=2)
text(80,1380,'Python  /  uv  /  Hugging Face',25,'#9baabe')
text(1090,1380,'github.com/chandan-123kumar/karyo',24,'#b8df87')
im.save(OUT/'karyo-architecture.jpg',quality=96,subsampling=0)
