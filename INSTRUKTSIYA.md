# Tomchi loyihasi — o'rnatish va ishlatish bo'yicha ko'rsatma

## 1. Loyihani olish

```bash
mkdir -p ~/tomchi
cd ~/tomchi
```

Agar bu katalogni GitHubdan klon qilgan bo'lsangiz:

```bash
git clone git@github.com:<username>/tomchi.git
cd tomchi
```

## 2. Backend o'rnatish

```bash
cd /home/saidov/tomchi
cp backend/.env.example .env
openssl rand -hex 32
```

`.env` ichida `DEVICE_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` va `ADMIN_TOKEN_SECRET` ni o'zingizga mos, noyob qiymatlar bilan to'ldiring. Secret buyruqdan yaratilgan tasodifiy qiymat bo'lsin; `.env` ni GitHub'ga yubormang. Admin panelga boshqa host yoki portdan kirsangiz, uning origin'ini `ADMIN_ORIGINS` ga qo'shing.

Mahalliy OCR uchun Tesseract va ingliz alifbosi modelini o'rnating:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

```bash
cd /home/saidov/tomchi
export PYTHONPATH=/home/saidov/tomchi/backend
python3 -m pip install --user -r backend/requirements.txt
```

## 3. Backendni ishga tushirish

```bash
cd /home/saidov/tomchi
export PYTHONPATH=/home/saidov/tomchi/backend
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000/docs

## 4. Admin panel o'rnatish

```bash
cd ~/tomchi/admin
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Open: http://localhost:5173

Admin panelga `.env` dagi `ADMIN_USERNAME` va `ADMIN_PASSWORD` bilan kiring.

## 5. Hardwareni sozlash

Har bir box uchun kamera va panel ESP32'ga alohida firmware yuklanadi. Ikkala qurilmada ham shu boxning bir xil ID'si bo'lishi kerak; boshqa boxda boshqa ID yoziladi (`box-2`, `box-3` va hokazo). Barcha qurilmalar bir backend serverga Wi-Fi orqali ulanadi.

### ESP32-CAM

1. Arduino IDE Board Manager'dan ESP32 paketini o'rnating va `AI Thinker ESP32-CAM` boardini tanlang.
2. PSRAM'li modul ishlating, partition scheme sifatida katta app joyi bo'lgan variantni tanlang; SD karta ishlatilmaydi (GPIO13 PIR uchun kerak).
3. `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_URL`, `DEVICE_KEY` va `BOX_ID` qiymatlarini kiriting.
4. `SERVER_URL` serverning boxlardan ko'rinadigan LAN IP manzili yoki domeni bo'lishi kerak; `localhost` ishlatmang.
5. VPS uchun `https://` URL va server root CA sertifikatini `SERVER_ROOT_CA` ga joylang. Sertifikat bo'lmasa HTTPS ulanish ataylab to'xtatiladi.
6. Firmware'ni ESP32-CAM'ga yuklang. Kamera har 1.5 soniyada QVGA live preview yuboradi; PIR yuqori signal berganda qo'shimcha 3 ta JPEG frame (400 ms interval) yuboradi. Harakat eventlari orasida kamida 5 soniya kutadi.

### Panel ESP32

1. Arduino IDE Library Manager'da `ArduinoJson` va `ESP32 HUB75 LED MATRIX PANEL DMA Display` kutubxonalarini o'rnating (Adafruit GFX dependency sifatida qo'shiladi).
2. `hardware/panel_esp32/panel_esp32.ino` faylida `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_URL`, `DEVICE_KEY` va boxning `BOX_ID` qiymatlarini kiriting.
3. VPS ishlatilsa, ESP32-CAM dagi kabi `SERVER_ROOT_CA` ni kiriting.
4. `PANEL_WIDTH`, `PANEL_HEIGHT`, `PANEL_CHAIN` va HUB75 `panelPins` qiymatlarini panelingiz xususiyatlariga moslang. Dastlabki qiymatlar bitta 32x16 panel uchun.
5. `BUTTON_PIN` ni tugmaga ulang (GPIO32 va GND; ichki pull-up ishlatiladi). HUB75 uchun yuqoridagi pin xaritasini wiring'dan oldin tekshiring.
6. Admin panelning yuqori qismidan box'ni tanlab, Bonus sozlamalarida shu box uchun `Pulse polarity` qiymatini `HIGH` yoki `LOW`, `Pulse frequency` qiymatini `50`, `100` yoki `200 ms` qilib belgilang. ESP32 sozlamalarni o'z `BOX_ID` qiymatiga mos `/api/display` javobidan oladi; o'zgartirish uchun firmware'ni qayta yuklash shart emas. Tanlangan ms qiymati to'liq impuls sikli, faol signal esa uning yarmi davom etadi.
7. Firmware'ni boxdagi ESP32 DevKit'ga yuklang. Displey server matnini har soniyada oladi va o'zbek lotin yozuvida marquee qilib chiqaradi: `AVTOMOBIL YO'Q`, `KELISH`, `MUKOFOT`, `SO'M`.

**Bonus API so'rovi qabul qilingach server bonus summasini yechadi, ESP32 esa qaytgan impulslar sonini GPIO33 orqali chiqaradi.** Bill acceptor/main board'dan qayta aloqa olinmaydi; impuls fizik qabul qilinganini dastur tasdiqlamaydi. GPIO33 ESP32'ning 3.3 V chiqishidir. Qurilmaning kirish kuchlanishi va elektr sxemasi tasdiqlanmagan bo'lsa, GPIO'ni bevosita ulamang; zarur bo'lsa optik izolyatsiya yoki kuchlanish moslashtirgichdan foydalaning.

Har bir box uchun `BOX_ID` admin paneldagi ID bilan aynan bir xil bo'lishi kerak. Admin paneldagi Bonus sahifasidan box qo'shing, so'ng ID'ni har ikkala qurilmaga yozing.

## 6. Test holatlari

- `POST /api/detect` ga `{"plate": "01A123BC"}` yuborish orqali test qilinadi.
- `GET /api/display` orqali ekran matni olinadi.
- `POST /api/bonus/press` bilan bonus bosish simulyatsiyasi ishlaydi.
- `GET /api/boxes` boxlar va har birining joriy bonus holatini qaytaradi.
- Detection, display va bonus so'rovlari boxni `X-Box-Id` header orqali tanlaydi.
- `POST /api/detect-image` `image` nomli JPEG multipart faylni, `event_id`, `frame_index` va `frame_count` maydonlari bilan qabul qiladi. Kadrlar Tesseract orqali mahalliy tekshiriladi; har event uchun eng ishonchli raqam taklifi detection bilan saqlanadi.
- Live frame'lar `POST /api/boxes/{box_id}/live-frame` orqali yuboriladi; admin panel ularni `GET /api/boxes/{box_id}/live-frame` orqali ko'rsatadi.
- Admin paneldagi Cameras bo'limida barcha boxlar jonli ko'rinadi; OCR raqam taklifi va ishonch foizini ko'rsatadi. Admin tekshirib tasdiqlagandan keyingina visit ro'yxatga olinadi; noto'g'ri taklifni qo'lda tuzatish mumkin. Noto'g'ri raqam allaqachon visitga bog'langan bo'lsa, tarixni buzmaslik uchun almashtirish bloklanadi.
- Visits bo'limida istalgan kelishning raqamini qayta tahrirlash mumkin. Bu faqat tanlangan kelish yozuviga ta'sir qiladi; mashinalar ro'yxati va o'sha avtomobilning boshqa kelishlari o'zgarmaydi.

Admin API so'rovlari muddati cheklangan Bearer token talab qiladi. ESP32-CAM va panel API so'rovlari `.env` dagi `DEVICE_KEY` bilan aynan mos `X-Device-Key` header yuborishi kerak.

Bonus sozlamalari SQLite'dagi `app_settings` jadvalida saqlanadi va server qayta ishga tushganda qoladi. Mashinalar va kelishlar `backend/database/tomchi.db` faylida qoladi; ushbu faylni muntazam zaxiralang.
Bonus bo'limida bonus summasi, bir bosishda ishlatiladigan summa va bonus beriladigan kelishlar oralig'ini sozlash mumkin. Masalan, oralig'ini `5` qilib belgilasangiz, har bir mashinaning 5-, 10-, 15-kelishlarida bonus beriladi. Yangi interval keyingi ro'yxatga olinadigan kelishlarga ta'sir qiladi; mavjud bonus miqdori o'zgarmaydi. Tanlangan box uchun impuls qutbi va chastotasi ham shu bo'limda alohida saqlanadi.
Butun moykada bir vaqtda bitta bonus faol bo'ladi va uni faqat bonus berilgan box ishlata oladi. 24 soatlik takror aniqlash oynasida boshqa mashina aniqlansa, boshqa mashinaga tegishli faol bonus qoldig'i bekor qilinadi; bonus egasi bo'lgan mashina qayta aniqlansa, uning bonusi saqlanadi.
Arxiv JPEG'lari `backend/storage/detections/` da saqlanadi, 640x480 gacha kichraytirilib qayta siqiladi va SQLite'da faqat metadata turadi. Arxiv 30 kunlik muddatga va 512 MiB umumiy limitga ega; limit oshsa eng eski arxiv rasmlari o'chiriladi. Live preview har box uchun bitta 320x240 gacha siqilgan fayl bo'lib, yangisi eskisini almashtiradi. `backend/storage/` papkasi `.gitignore`da.
Har bir apparat impulsi `1 000 so'm` deb hisoblanadi. Server per-press summasidan kerakli impuls sonini hisoblaydi; bir bosish uchun eng ko'pi bilan 100 impuls. Admin panelning Bonus bo'limida box testini boshlash, `1 000`–`100 000` so'm miqdorida test impulsi navbatga qo'yish va `Finish testing` bilan rejimni tugatish mumkin. Test pulsi mijoz bonusini kamaytirmaydi. Test rejimida qurilma tugmasidan odatiy bonus so'rovi rad etiladi; testni tugatish navbatda hali yuborilmagan buyruqni ham bekor qiladi.

## Muhim cheklovlar

- ESP32-CAM JPEG'larni yuboradi. Backend Tesseract yordamida raqam formatiga mos OCR nomzodini shu serverda aniqlaydi; tasvirlar uchinchi tomon xizmatlariga uzatilmaydi.
- Panel ESP32 HUB75 drayveri orqali matnni marquee qilib ko'rsatadi; o'lcham va pinlar aniq panelga moslanishi shart.
- Impuls qutbi va davri admin paneldan sozlanadi. Haqiqiy qurilmaga ulashdan oldin TB77/main board kirish parametrlari va interfeys elektr xavfsizligini tekshiring; ESP32 GPIO33 ni noma'lum kuchlanishli kirishga bevosita ulamang.

## Internetdan public HTTPS kirish

`deploy/Caddyfile.example` va `deploy/tomchi.service.example` namunalaridan foydalaning. O'z domeningiz bo'lmasa DuckDNS'dan bepul subdomen olishingiz mumkin. DNS serverning public IP manziliga qarashi va tashqaridan 80/443 portlari yetib borishi kerak; uy interneti CGNAT ortida bo'lsa VPS yoki tunnel talab etiladi.

1. `.env` da `APP_ENV=prod`, `ADMIN_ORIGINS=https://your-domain.example`, `ALLOWED_HOSTS=your-domain.example` va kuchli `DEVICE_KEY` belgilang. Keyni ikkala ESP32 firmware'iga ham kiriting; admin parolini public qilishdan oldin yangilang.
2. `admin/` da `npm ci && npm run build` bajaring va `admin/dist/` ni Caddy o'qiy oladigan `/var/www/tomchi/` ga joylang.
3. DuckDNS subdomeni ishlatsangiz, `deploy/duckdns.env.example` dagi o'zgaruvchilarni `/etc/tomchi/duckdns.env` ga tokenni oshkor qilmasdan kiriting. `deploy/duckdns-update.sh.example`, `deploy/tomchi-duckdns.service.example` va `.timer.example` namunalarini o'rnating; timer DNS yozuvini har 5 daqiqada yangilaydi. `deploy/Caddyfile.example` da `tomchi.duckdns.org` oldindan kiritilgan; uni `/etc/caddy/Caddyfile` ga o'rnating. DNS va 80/443 to'g'ri bo'lsa, Caddy HTTPS sertifikatini avtomatik oladi.
4. `deploy/tomchi.service.example` dagi foydalanuvchi va yo'llarni moslab systemd service sifatida ishga tushiring.
5. Firewall'da faqat 80/443 ni ochiq qoldiring. Backend 127.0.0.1:8000 da ishlasin; **8000 va 5173 portlarini internetga ochmang**. ESP32 firmware'da `SERVER_URL=https://your-subdomain.duckdns.org` va unga mos ishonchli `SERVER_ROOT_CA` sozlang.

Production rejimida API dokumentatsiyasi o'chadi, ruxsat etilmagan Host bloklanadi va login urinishlari IP bo'yicha cheklanadi. Hozirgi konfiguratsiya namunalari public xizmatni tayyorlaydi; domen/DNS va tashqi tarmoq sozlamalarisiz panelga internetdan ulanish yoqilmaydi.

## 7. Mahalliy ishlash jarayoni

1. Backendni ishga tushiring.
2. Admin panelini ishga tushiring.
3. ESP32-CAM qismi avtomatik tasvir yuboradi.
4. Server suratni arxivlaydi va OCR orqali raqam taklifini aniqlaydi. Tesseract ishlamasa ham surat saqlanib, qo'lda kiritish imkoniyati qoladi.
5. Admin panel Cameras bo'limida taklifni ko'rib, tasdiqlaydi yoki tuzatadi; tasdiqlangandan keyin visit ro'yxatga olinadi.
