# Tomchi

Tomchi — avtomoyka uchun bonus tizimi. Backend bir nechta boxni boshqaradi: avtomobil kelishlari umumiy sanaladi, displey har bir box uchun alohida yuritiladi, bonus esa texnik topshiriqdagi kabi butun moyka uchun bitta faol bonus bo'ladi.

## Strukturasi

- `backend/` — FastAPI server, SQLite ma'lumotlar bazasi va biznes logika
- `admin/` — React + Vite admin panel
- `hardware/` — ESP32-CAM va panel controller uchun Arduino skretchlari
- `docs/` — qo'shimcha hujjatlar

## Tez boshlash

### 1) Maxfiy sozlamalar

```bash
cd /home/saidov/tomchi
cp backend/.env.example .env
openssl rand -hex 32
```

`.env` ichida `DEVICE_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` va `ADMIN_TOKEN_SECRET` qiymatlarini belgilang. `ADMIN_TOKEN_SECRET` uchun yuqoridagi buyruq bergan tasodifiy qiymatdan foydalaning. Bu faylni yoki kalitlarni GitHub'ga yubormang. `ADMIN_ORIGINS` ga admin panel ochiladigan manzilni kiriting.

### 2) Python va dependencylar

Mahalliy ANPR/OCR uchun Tesseract va ingliz alifbosi modeli kerak:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

```bash
cd /home/saidov/tomchi
export PYTHONPATH=/home/saidov/tomchi/backend
python3 -m pip install --user -r backend/requirements.txt
```

### 3) Backend ishga tushirish

```bash
cd /home/saidov/tomchi
export PYTHONPATH=/home/saidov/tomchi/backend
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000/docs

### 4) Admin panelni ishga tushirish

```bash
cd /home/saidov/tomchi/admin
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Open: http://localhost:5173

## Internetdan xavfsiz kirish (public HTTPS)

`deploy/Caddyfile.example` va `deploy/tomchi.service.example` production konfiguratsiyasi uchun namunalar. O'z domeningiz bo'lmasa, DuckDNS kabi bepul DDNS subdomenidan foydalanish mumkin. Haqiqiy public URL yoqilishi uchun DNS serverning public IP manziliga yo'naltirilishi, serverda yoki routerda 80/443 portlari ochiq bo'lishi kerak. CGNAT bo'lsa, VPS yoki tunnel kerak bo'ladi.

1. `.env` da `APP_ENV=prod`, `ADMIN_ORIGINS=https://your-domain.example`, `ALLOWED_HOSTS=your-domain.example` va kuchli, bo'sh bo'lmagan `DEVICE_KEY` belgilang. `DEVICE_KEY` ni ikkala ESP32 firmware'iga ham aynan bir xil kiriting. Admin parolini internetga chiqarishdan avval almashtirish tavsiya qilinadi.
2. `admin/` ichida `npm ci && npm run build` bajaring; hosil bo'lgan `admin/dist/` fayllarini Caddy o'qiy oladigan `/var/www/tomchi/` ga joylang.
3. Caddy'ni o'rnating va `deploy/Caddyfile.example` ni `/etc/caddy/Caddyfile` ga o'rnating. Faylda `tomchi.duckdns.org` oldindan sozlangan. Caddy TLS sertifikatini avtomatik olishi uchun DNS to'g'ri bo'lishi va 80/443 tashqaridan yetib borishi kerak.
4. `deploy/tomchi.service.example` dagi foydalanuvchi va yo'llarni moslang, `/etc/systemd/system/tomchi.service` ga o'rnating va `sudo systemctl enable --now tomchi` bilan ishga tushiring.
5. Firewall'da faqat kerakli 80/443 portlariga ruxsat bering; **8000 (backend) va 5173 (Vite dev server) portlarini internetga ochmang**. Backend `127.0.0.1:8000` da qoladi, HTTPS proxy esa production frontend va API'ni bitta origin'da taqdim etadi.

DuckDNS ishlatsangiz, `deploy/duckdns.env.example` dagi qiymatlarni o'zingizning token bilan `/etc/tomchi/duckdns.env` fayliga kiriting, updater script/unit/timer namunalari o'rnatib `tomchi-duckdns.timer` ni yoqing. Tokenni chatga yoki GitHub'ga yubormang. `tomchi.duckdns.org` domeni `ADMIN_ORIGINS`, `ALLOWED_HOSTS` va Caddyfile'da ishlatilishi kerak.

Production rejimida `/docs`, `/redoc` va OpenAPI schema o'chadi, noto'g'ri `Host` headerlar bloklanadi, login urinishlari IP bo'yicha cheklanadi. ESP32'lar domenni HTTPS bilan ishlatishi uchun `SERVER_URL` ni `https://your-subdomain.duckdns.org` qiling va `SERVER_ROOT_CA` ga shu ACME sertifikatiga mos ishonchli CA sertifikatini kiriting.

### 5) Hardware skriptlarini yuklash

- Admin panelning Bonus bo'limida box qo'shing. Box ID'sini (`box-1`, `box-2`...) shu boxdagi ESP32-CAM va panel ESP32 firmware'ida bir xil qilib sozlang.
- Server manzili, Wi-Fi va `.env` dagi device key'ni firmware'ga kiriting; har boxdagi ikkala ESP32 bitta backend serverga ulanadi.
- Ulanish va apparat ogohlantirishlari uchun `INSTRUKTSIYA.md` ga qarang.
- Camera firmware PIR trigger bilan JPEG frame'larni serverga yuboradi. Backend Tesseract yordamida raqam formatiga mos nomzodni mahalliy aniqlaydi; suratlar tashqi OCR xizmatiga yuborilmaydi.
- Admin panelning Cameras bo'limida OCR taklifi va ishonch foizi ko'rinadi. Admin raqamni tekshirib tasdiqlagandan keyingina visit yaratiladi; OCR xato bo'lsa, raqamni tuzatish mumkin.
- Panel ESP32 HUB75 P10 displeyida o'zbek lotin yozuvidagi matnni ko'rsatadi (`AVTOMOBIL YO'Q`, `KELISH`, `MUKOFOT`, `SO'M`) va bonus tasdiqlangach GPIO33 orqali impuls chiqaradi. Admin panelda box tanlab, o'sha box uchun faol qutbni (`HIGH`/`LOW`) va impuls davrini (`50`, `100` yoki `200` ms) sozlash mumkin; ESP32 qiymatlarni o'z box ID'si bo'yicha serverdan oladi.
- Tanlangan davr bitta to'liq impuls sikli bo'lib, signal davrning yarmida faol turadi. GPIO33 ni bill acceptor/main board'ga bevosita ulamang: kirish kuchlanishi va sxema talabiga mos optik ajratilgan yoki level-shifting interfeysdan foydalaning.
- Admin panelning Bonus bo'limida box test rejimini boshlash, 1 000–100 000 so'm oralig'ida test summasi yuborish va testni tugatish mumkin. Test impulslari mijoz bonusidan yechilmaydi; test vaqtida box tugmasi orqali odatiy bonus berilmaydi.

## API

- `GET /health`
- `POST /api/auth/login` — admin token olish
- `GET /api/stats`, `/api/visits`, `/api/cars`, `/api/boxes`, `/api/settings`, `/api/detections` — admin Bearer token talab qiladi
- `PUT /api/visits/{id}/plate`, `/api/settings`, `/api/detections/{id}/plate` — admin Bearer token talab qiladi
- `POST /api/detect`, `POST /api/boxes` — admin Bearer token talab qiladi
- `GET /api/detections/{id}/image`, `GET /api/boxes/{box_id}/live-frame` — admin Bearer token talab qiladi
- `GET /api/display`, `POST /api/bonus/press`, `POST /api/detect-image`, `POST /api/boxes/{box_id}/live-frame` — `X-Device-Key` talab qiladi

Box qurilmalari so'rovda `X-Box-Id` header yuboradi. Bonus sozlamalari, boxlar, mashinalar va kelishlar SQLite'da saqlanadi. DB fayli: `backend/database/tomchi.db`; uni muntazam zaxiralang.

Arxiv rasmlari SQLite BLOB emas, `backend/storage/detections/` ichida JPEG ko'rinishida saqlanadi (maksimal 640x480, qayta siqilgan). Rasmlar 30 kundan keyin yoki arxiv 512 MiB chegarasiga yetganda eng eskisidan o'chiriladi. Live preview har box uchun bitta kichik JPEG faylni yangilab boradi. Mahalliy OCR taklifi va ishonch darajasi detection bilan saqlanadi. `ANPR_ENABLED`, `ANPR_TESSERACT_CMD`, `ANPR_MIN_CONFIDENCE` va `ANPR_TIMEOUT_SECONDS` sozlamalarini `.env` orqali boshqarish mumkin; `/health` OCR ishga tayyormi ko'rsatadi.
Visits sahifasida raqamni tahrirlash faqat tanlangan kelishga ta'sir qiladi; Cars ro'yxatidagi mashina raqami va boshqa kelishlar o'zgarmaydi.

## Xavfsizlik va bonus qoidalari

Admin panel alohida `ADMIN_USERNAME`/`ADMIN_PASSWORD` bilan kiradi va muddati tugaydigan Bearer token ishlatadi; token brauzer sessiyasida saqlanadi. Qurilmalar faqat `X-Device-Key` bilan hardware API'larga kiradi. Backendda kalit yoki admin credential'lar uchun standart/demo qiymat yo'q; `.env` ni sozlamasdan hardware API'lardan foydalanib bo'lmaydi. CORS ruxsat etilgan admin manzillari `ADMIN_ORIGINS` orqali beriladi.

Bonus butun moyka uchun bitta bo'ladi va faqat bonus berilgan boxda ishlatiladi. Boshqa avtomobil avvalgi mashinaning 24 soatlik takror aniqlash oynasida kelsa, faol bonus qoldig'i bekor qilinadi; bonus egasi bo'lgan mashinaning takror aniqlanishi uning bonusini bekor qilmaydi.

## GitHubga yuborish

Git CLI o'rnatilgan bo'lganda quyidagi buyruq ishlatiladi:

```bash
git init -b main
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:<username>/tomchi.git
git push -u origin main
```

Agar GitHub CLI (`gh`) ishlatilsa:

```bash
gh auth login
gh repo create tomchi --public --source=. --remote=origin --push
```

## Muallif

Tomchi team / loyiha boshlang'ich versiyasi.
