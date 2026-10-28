# RO: The New World — Discord Event Reminder Bot

บอท Discord แจ้งเตือนเวลากิจกรรมของเกม **Ragnarok: The New World**
เขียนด้วย Python + discord.py แก้ตารางกิจกรรมได้เองในไฟล์ `events.json` โดยไม่ต้องแก้โค้ด

## ความสามารถ
- แจ้งเตือนล่วงหน้า (เช่น 15 และ 5 นาทีก่อนเริ่ม) และแจ้งอีกครั้งตอนกิจกรรมเริ่ม
- รองรับกิจกรรมที่เกิดซ้ำถี่ๆ เช่น Mimic Chest ทุก 30 นาที
- เวลาในข้อความใช้ Discord timestamp ทุกคนเห็นเป็นเวลาท้องถิ่นของตัวเอง
- ตั้งห้องและยศที่จะแท็กแยกต่อเซิร์ฟเวอร์ และปิดการแจ้งเตือนบางกิจกรรมได้
- โหลดตารางใหม่ด้วย `/ro reload` โดยไม่ต้องรีสตาร์ทบอท

## Slash commands
| คำสั่ง | หน้าที่ | สิทธิ์ |
|---|---|---|
| `/ro setchannel [channel]` | ตั้งห้องแจ้งเตือน | Manage Server |
| `/ro setrole [role]` | ตั้งยศที่จะแท็ก (ไม่ใส่ = ยกเลิก) | Manage Server |
| `/ro toggle <event>` | เปิด/ปิดแจ้งเตือนกิจกรรมนั้น | Manage Server |
| `/ro next [count]` | กิจกรรมที่กำลังจะมาถึง | ทุกคน |
| `/ro today` | ตารางวันนี้ | ทุกคน |
| `/ro week` | ตารางทั้งสัปดาห์ | ทุกคน |
| `/ro reload` | โหลด events.json ใหม่ | Manage Server |
| `/ro test` | ส่งข้อความทดสอบ | Manage Server |

## วิธีที่ง่ายที่สุด: รันบนเครื่องตัวเอง (Windows)
1. ติดตั้ง Python จาก https://www.python.org/downloads/ (ติ๊ก **Add python.exe to PATH**)
2. ดาวน์โหลดโค้ดนี้เป็น ZIP (ปุ่ม Code → Download ZIP) แล้วแตกไฟล์
3. ดับเบิลคลิก **`start.bat`** ครั้งแรกจะถามโทเคนบอท วางแล้วกด Enter เสร็จ
4. เปิดหน้าต่างนี้ทิ้งไว้ บอทจะเตือนตามเวลา ปิดหน้าต่าง = บอทหยุด

macOS / Linux ใช้ `bash start.sh` แทน

**แจกเป็น .exe ให้คนที่ไม่มี Python** รัน `build_exe.bat` บน Windows หนึ่งครั้ง
จะได้โฟลเดอร์ `dist\ro-bot-package` (มี `ro-bot.exe` + `events.json`) ส่งโฟลเดอร์นี้ให้เพื่อน
เพื่อนแค่ดับเบิลคลิก `ro-bot.exe` แล้วใส่โทเคนของตัวเอง

## วิธีติดตั้ง

### 1. สร้างบอทใน Discord Developer Portal
1. ไปที่ https://discord.com/developers/applications → **New Application**
2. เมนู **Bot** → **Reset Token** → คัดลอกโทเคนเก็บไว้
3. เมนู **OAuth2 → URL Generator** เลือก scope `bot` และ `applications.commands`
   สิทธิ์ที่ต้องมี: `Send Messages`, `Embed Links`, `Mention Everyone` (ถ้าจะแท็กยศ)
4. เปิดลิงก์ที่ได้เพื่อเชิญบอทเข้าเซิร์ฟเวอร์

### 2. รันบอท
```bash
pip install -r requirements.txt
cp .env.example .env     # แล้วแก้ไฟล์ .env ใส่ DISCORD_TOKEN
python bot.py
```

ถ้าใส่ `DEV_GUILD_ID` ใน `.env` slash command จะขึ้นในเซิร์ฟเวอร์นั้นทันที
(ถ้าไม่ใส่ คำสั่ง global อาจใช้เวลาถึง 1 ชั่วโมงกว่าจะปรากฏ)

### 3. ตั้งค่าในเซิร์ฟเวอร์
```
/ro setchannel #แจ้งเตือนกิจกรรม
/ro setrole @RO-Players
/ro test
```

## แก้ตารางกิจกรรม (`events.json`)
```json
{
  "id": "luminous_vale_boss",          // รหัสไม่ซ้ำ (ใช้กับ /ro toggle)
  "name": "Luminous Vale - บอสเกิด",
  "emoji": "🐉",
  "days": ["sat"],                     // mon tue wed thu fri sat sun หรือ "daily"
  "times": ["09:00", "12:00"],         // เวลาเริ่ม (เวลาเซิร์ฟเวอร์)
  "duration_min": 30,                  // ระยะเวลา (ใช้แสดงเวลาสิ้นสุด)
  "remind_before": [15, 5],            // เตือนล่วงหน้ากี่นาที (ไม่ใส่ = ใช้ default)
  "note": "แนะนำอยู่ channel 1"
}
```
กิจกรรมที่เกิดซ้ำทุก N นาที ให้ใช้ `window` แทน `times`:
```json
"window": { "start": "08:00", "end": "23:00", "every_min": 30 }
```
`timezone` ด้านบนสุดของไฟล์คือโซนเวลาของเวลาที่กรอก (ค่าเริ่มต้น `Asia/Bangkok` = GMT+7)
แก้ไฟล์เสร็จแล้วพิมพ์ `/ro reload`

> ⚠️ ตารางเริ่มต้นในไฟล์รวบรวมจากไกด์/วิกิของแฟนเกม ไม่ใช่ประกาศทางการ
> และเวลาอาจต่างกันในแต่ละเซิร์ฟเวอร์/ช่วง OBT กรุณาตรวจกับหน้ากิจกรรมในเกมแล้วปรับให้ตรง

## รันค้างไว้ตลอด 24 ชม.
- **Docker**: `docker build -t ro-bot . && docker run -d --env-file .env -v $(pwd)/settings.json:/app/settings.json ro-bot`
- **systemd / pm2 / screen** หรือโฮสต์ฟรีอย่าง Railway, Render, Oracle Cloud ก็ได้

## Deploy บน Railway
ไฟล์ `railway.json`, `Procfile`, `.python-version` เตรียมไว้แล้ว Railway จะ build และรัน `python bot.py` ให้เอง

1. push โค้ดโฟลเดอร์นี้ขึ้น GitHub (อย่า push ไฟล์ `.env`)
2. https://railway.app → **New Project → Deploy from GitHub repo** → เลือก repo นี้
3. แท็บ **Variables** เพิ่ม
   - `DISCORD_TOKEN` = โทเคนบอท
   - `SETTINGS_PATH` = `/data/settings.json`
   - `DEV_GUILD_ID` = ไอดีเซิร์ฟเวอร์ (ไม่บังคับ)
4. แท็บ **Settings → Volumes → Add Volume** ตั้ง Mount Path เป็น `/data`
   (ถ้าไม่ทำ ค่าห้อง/ยศที่ตั้งด้วย `/ro setchannel` จะหายทุกครั้งที่ redeploy)
5. Settings → **Networking** ไม่ต้องสร้าง domain เพราะบอทไม่ได้เปิดเว็บ
6. ดู **Deploy Logs** จนเห็นข้อความ `ล็อกอินเป็น ...` แล้วไปพิมพ์ `/ro setchannel` ใน Discord

ทางเลือกไม่ใช้ GitHub: ติดตั้ง Railway CLI บนเครื่องแล้วรัน `railway login`, `railway init`, `railway up` ในโฟลเดอร์นี้

## ทางเลือกอื่นถ้าใช้ Railway ไม่ได้
บอทมี health endpoint ในตัว (เปิดอัตโนมัติเมื่อโฮสต์ตั้งตัวแปร `PORT`) จึงรันบนโฮสต์แบบ Web Service ได้

**Render (ฟรี)** มีไฟล์ `render.yaml` ให้แล้ว
1. https://render.com → New → **Blueprint** → เลือก repo นี้ → ใส่ `DISCORD_TOKEN`
2. แผนฟรีจะหลับเมื่อไม่มีคนเรียก 15 นาที ให้ตั้ง https://uptimerobot.com หรือ https://cron-job.org
   ยิง URL ของ service (เช่น `https://ronewworld-bot.onrender.com/health`) ทุก 5 นาที
3. ค่าที่ตั้งด้วย `/ro setchannel` จะหายเมื่อ redeploy (ดิสก์ฟรีไม่ถาวร) ให้พิมพ์ตั้งใหม่หลัง deploy

**Koyeb (ฟรี)** New Service → GitHub → repo นี้ → Run command `python bot.py` → ใส่ `DISCORD_TOKEN` → Port 8000

**VPS / Oracle Cloud Free Tier** ใช้ `Dockerfile` หรือรัน `python bot.py` ใน `screen`/`systemd` เสถียรที่สุด
