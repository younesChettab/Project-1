import math, subprocess, wave, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import imageio_ffmpeg, speak
FF = imageio_ffmpeg.get_ffmpeg_exe(); W, H, FPS = 1280, 720, 24
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(s): return ImageFont.truetype(FONT, s, layout_engine=ImageFont.Layout.RAQM)

# --- cut the person out of the white background
src = Image.open("photo.jpg").convert("RGB")
a = np.asarray(src).astype(int); white = (a.min(2) > 232)
from scipy import ndimage
lab, _ = ndimage.label(white); bgl = set(np.unique(np.concatenate([lab[0], lab[:,0], lab[:,-1]]))) - {0}
bgm = np.isin(lab, list(bgl)); bgm = ndimage.binary_opening(bgm, iterations=1)
mask = Image.fromarray(np.where(bgm, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
person = src.copy(); person.putalpha(mask)

# scenes: (on-screen title, voiced text with tashkeel, palette, mood)
S = [
 ("شيخ الإسلام ابن تيمية\n٦٦١ – ٧٢٨ هـ", "شَيْخُ الإِسْلَامِ ابْنُ تَيْمِيَّةَ. سِيرَةٌ مُوجَزَةٌ مِنْ كُتُبِ الْمَكْتَبَةِ الشَّامِلَةِ.", ((20,24,40),(90,70,40)), "title"),
 ("تقي الدين أبو العباس\nأحمد بن عبد الحليم بن عبد السلام بن تيمية\nالحرّاني ثم الدمشقي", "هُوَ تَقِيُّ الدِّينِ، أَبُو الْعَبَّاسِ، أَحْمَدُ بْنُ عَبْدِ الْحَلِيمِ بْنِ عَبْدِ السَّلَامِ بْنِ تَيْمِيَّةَ، الْحَرَّانِيُّ ثُمَّ الدِّمَشْقِيُّ.", ((30,30,50),(120,90,50)), "n"),
 ("وُلد بحرّان في ربيع الأول سنة ٦٦١ هـ\nوقدم دمشق مع والده المفتي شهاب الدين", "وُلِدَ بِحَرَّانَ، فِي رَبِيعٍ الْأَوَّلِ، سَنَةَ إِحْدَى وَسِتِّينَ وَسِتِّمِائَةٍ. وَقَدِمَ دِمَشْقَ مَعَ وَالِدِهِ الْمُفْتِي شِهَابِ الدِّينِ.", ((60,40,20),(200,150,80)), "desert"),
 ("سمع ابنَ عبد الدائم وابنَ أبي اليسر والمجدَ بن عساكر\nونسخ وقرأ وانتقى، وبرع في علوم الآثار والسنن", "سَمِعَ مِنَ ابْنِ عَبْدِ الدَّائِمِ، وَابْنِ أَبِي الْيُسْرِ، وَالْمَجْدِ بْنِ عَسَاكِرَ. وَنَسَخَ وَقَرَأَ وَانْتَقَى، وَبَرَعَ فِي عُلُومِ الْآثَارِ وَالسُّنَنِ.", ((25,45,40),(110,150,120)), "mosque"),
 ("ودرّس وأفتى وفسّر، وصنّف التصانيف البديعة", "وَدَرَّسَ، وَأَفْتَى، وَفَسَّرَ، وَصَنَّفَ التَّصَانِيفَ الْبَدِيعَةَ.", ((40,30,20),(170,130,70)), "books"),
 ("«صحيح الذهن، سريع الإدراك، سيّال الفهم\nموصوفًا بفرط الشجاعة والكرم»\n— الذهبي", "قَالَ الذَّهَبِيُّ: كَانَ صَحِيحَ الذِّهْنِ، سَرِيعَ الْإِدْرَاكِ، سَيَّالَ الْفَهْمِ، مَوْصُوفًا بِفَرْطِ الشَّجَاعَةِ وَالْكَرَمِ، لَا لَذَّةَ لَهُ فِي غَيْرِ نَشْرِ الْعِلْمِ وَتَدْوِينِهِ وَالْعَمَلِ بِمُقْتَضَاهُ.", ((30,25,45),(140,110,160)), "n"),
 ("«فوالله ما قابلت عيني مثله\nولا رأى هو مثل نفسه» — الذهبي", "وَقَالَ: فَوَاللَّهِ مَا قَابَلَتْ عَيْنِي مِثْلَهُ، وَلَا رَأَى هُوَ مِثْلَ نَفْسِهِ.", ((35,30,25),(160,120,60)), "n"),
 ("سُجن غير مرّة\nوهو لا يرجع", "وَسُجِنَ غَيْرَ مَرَّةٍ، وَهُوَ لَا يَرْجِعُ.", ((12,12,16),(60,60,70)), "prison"),
 ("تُوفّي معتقلًا بقلعة دمشق\nفي ٢٠ ذي القعدة سنة ٧٢٨ هـ\nوشيّعه أممٌ لا يُحصَون إلى مقبرة الصوفية", "تُوُفِّيَ مُعْتَقَلًا بِقَلْعَةِ دِمَشْقَ، فِي الْعِشْرِينَ مِنْ ذِي الْقَعْدَةِ، سَنَةَ ثَمَانٍ وَعِشْرِينَ وَسَبْعِمِائَةٍ. وَشَيَّعَهُ أُمَمٌ لَا يُحْصَوْنَ إِلَى مَقْبَرَةِ الصُّوفِيَّةِ. رَحِمَهُ اللَّهُ.", ((15,15,25),(80,70,90)), "prison"),
 ("المصدر: الذهبي، المعجم المختص بالمحدثين، ص ٢٥–٢٦\nوترجمة المؤلف في المكتبة الشاملة", "", ((10,10,14),(40,35,30)), "end"),
]

def bg(c1, c2, mood, t):
    y = np.linspace(0,1,H)[:,None,None]
    img = (np.array(c1)*(1-y) + np.array(c2)*y) * np.ones((1,W,1))
    im = Image.fromarray(img.astype(np.uint8)); d = ImageDraw.Draw(im, "RGBA")
    if mood in ("mosque","books","title","n"):   # arches
        for i in range(-1,6):
            x = 60 + i*240 + int(t*6)
            d.rectangle([x, 330, x+150, H], fill=(0,0,0,70)); d.ellipse([x, 255, x+150, 405], fill=(0,0,0,70))
    if mood == "desert":
        d.ellipse([950,90,1090,230], fill=(255,220,150,160))
        d.polygon([(0,560),(400,470),(800,540),(1280,480),(1280,720),(0,720)], fill=(90,60,30,200))
    if mood == "prison":
        for i in range(0, W, 90): d.rectangle([i+int(t*3)%90, 0, i+int(t*3)%90+14, H], fill=(0,0,0,150))
    if mood == "books":
        for i in range(14): d.rectangle([40+i*38, 520-(i%3)*14, 70+i*38, 700], fill=(120+(i*29)%100, 60, 30, 200))
    return im

def frame(sc, t, dur):
    title, _, (c1,c2), mood = sc
    im = bg(c1, c2, mood, t)
    if mood != "end":
        z = 1.0 + 0.06*t/dur; ph = int(640*z); pw = int(person.width*ph/person.height)
        p = person.resize((pw, ph), Image.LANCZOS)
        if mood == "prison": p = Image.merge("RGBA", (*ImageOps.grayscale(p.convert("RGB")).convert("RGB").split(), p.getchannel("A")))
        if mood == "desert": p = Image.merge("RGBA", (*Image.blend(p.convert("RGB"), Image.new("RGB",p.size,(200,150,90)),0.18).split(), p.getchannel("A")))
        im.paste(p, (W-pw-30+int(10*math.sin(t/3)), H-ph+30), p)
    d = ImageDraw.Draw(im, "RGBA")
    f = font(44 if mood=="title" else 32)
    lines = title.split("\n"); lh = f.size+22
    tw = 1180 if mood=="end" else 720; x0 = 40
    y0 = (H - lh*len(lines))//2
    d.rectangle([x0-20, y0-24, x0+tw, y0+lh*len(lines)+10], fill=(0,0,0,120))
    for i, ln in enumerate(lines):
        w = d.textlength(ln, font=f, direction="rtl", language="ar")
        d.text((x0+tw-30-w, y0+i*lh), ln, font=f, fill=(245,230,200), direction="rtl", language="ar")
    a = min(1, t/0.6, (dur-t)/0.6)  # fade
    return (np.asarray(im).astype(np.float32)*max(a,0)).astype(np.uint8)

# narration
audio = []; durs = []
for i, sc in enumerate(S):
    if sc[1]:
        speak.say(sc[1], f"v{i}.wav"); wv = wave.open(f"v{i}.wav"); n = np.frombuffer(wv.readframes(wv.getnframes()), np.int16)
    else: n = np.zeros(0, np.int16)
    pad = np.zeros(int(22050*0.9), np.int16); seg = np.concatenate([pad, n, pad])
    if len(seg) < 22050*5: seg = np.concatenate([seg, np.zeros(int(22050*5)-len(seg), np.int16)])
    audio.append(seg); durs.append(len(seg)/22050)
aud = np.concatenate(audio); w = wave.open("narr.wav","wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(aud.tobytes()); w.close()
print("duration", sum(durs))

p = subprocess.Popen([FF,"-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-i","narr.wav",
    "-c:v","libx264","-preset","medium","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-shortest","/home/user/Project-1/ibn_taymiyyah.mp4"],
    stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
for sc, dur in zip(S, durs):
    for k in range(int(dur*FPS)): p.stdin.write(frame(sc, k/FPS, dur).tobytes())
p.stdin.close(); p.wait(); print("done", p.returncode)
