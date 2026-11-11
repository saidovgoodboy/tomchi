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
6. `PULSE_PERIOD_MS` ni bill acceptor'dagi pulse-frequency sozlamasiga moslab `50`, `100` yoki `200` ms dan tanlang (firmware defaulti `100` ms). Bu compile-time parametr; o'zgartirgandan keyin firmware'ni qayta yuklash kerak.
7. Firmware'ni boxdagi ESP32 DevKit'ga yuklang. Displey server matnini har soniyada oladi va marquee qilib chiqaradi.

**Bonus tugmasi aniqlanadi, lekin bonus API chaqiruvi hozir `ENABLE_BONUS_REDEMPTION = false` bilan o'chirilgan.** Shu sabab hozir tugma bosish bonus qoldig'ini kamaytirmaydi. `PULSE_PERIOD_MS` uchun 50/100/200 ms tanlovlari tayyor, ammo haqiqiy impuls kengligi va faol polarligi hali o'lchanmagan; ularni aniqlab, optik ajratilgan sxemani stol ustida sinamaguncha fizik impuls chiqishi va redemptionni yoqmang.

Har bir box uchun `BOX_ID` admin paneldagi ID bilan aynan bir xil bo'lishi kerak. Admin paneldagi Bonus sahifasidan box qo'shing, so'ng ID'ni har ikkala qurilmaga yozing.

## 6. Test holatlari

- `POST /api/detect` ga `{"plate": "01A123BC"}` yuborish orqali test qilinadi.
- `GET /api/display` orqali ekran matni olinadi.
- `POST /api/bonus/press` bilan bonus bosish simulyatsiyasi ishlaydi.
- `GET /api/boxes` boxlar va har birining joriy bonus holatini qaytaradi.
- Detection, display va bonus so'rovlari boxni `X-Box-Id` header orqali tanlaydi.
- `POST /api/detect-image` `image` nomli JPEG multipart faylni, `event_id`, `frame_index` va `frame_count` maydonlari bilan qabul qiladi. Bir eventning kadrlaridan siqilgan arxiv surati saqlanadi.
- Live frame'lar `POST /api/boxes/{box_id}/live-frame` orqali yuboriladi; admin panel ularni `GET /api/boxes/{box_id}/live-frame` orqali ko'rsatadi.
- Admin paneldagi Cameras bo'limida barcha boxlar jonli ko'rinadi; tanlangan boxning saqlangan suratlaridan pending detection'ga raqam kiritish/tuzatish va visitni ro'yxatga olish mumkin. Noto'g'ri raqam allaqachon visitga bog'langan bo'lsa, tarixni buzmaslik uchun almashtirish bloklanadi.
- Visits bo'limida istalgan kelishning raqamini qayta tahrirlash mumkin. Bu faqat tanlangan kelish yozuviga ta'sir qiladi; mashinalar ro'yxati va o'sha avtomobilning boshqa kelishlari o'zgarmaydi.

Bonus sozlamalari SQLite'dagi `app_settings` jadvalida saqlanadi va server qayta ishga tushganda qoladi. Mashinalar va kelishlar `backend/database/tomchi.db` faylida qoladi; ushbu faylni muntazam zaxiralang.
Bonus bo'limida bonus summasi, bir bosishda ishlatiladigan summa va bonus beriladigan kelishlar oralig'ini sozlash mumkin. Masalan, oralig'ini `5` qilib belgilasangiz, har bir mashinaning 5-, 10-, 15-kelishlarida bonus beriladi. Yangi interval keyingi ro'yxatga olinadigan kelishlarga ta'sir qiladi; mavjud bonus miqdori o'zgarmaydi.
Arxiv JPEG'lari `backend/storage/detections/` da saqlanadi, 640x480 gacha kichraytirilib qayta siqiladi va SQLite'da faqat metadata turadi. Arxiv 30 kunlik muddatga va 512 MiB umumiy limitga ega; limit oshsa eng eski arxiv rasmlari o'chiriladi. Live preview har box uchun bitta 320x240 gacha siqilgan fayl bo'lib, yangisi eskisini almashtiradi. `backend/storage/` papkasi `.gitignore`da.
Har bir apparat impulsi `1 000 so'm` deb qabul qilinadi. Server per-press summasidan kerakli impuls sonini hisoblaydi. Hozir fizik impuls chiqishi o'chirilgan va tugma bonus qoldig'ini kamaytirmaydi. Keyinchalik yoqilganda, per-press summasi 1 000 ga bo'linishi va bir bosish uchun eng ko'pi bilan 100 impuls bo'lishi kerak.

## Muhim cheklovlar

- ESP32-CAM JPEG'larni yuboradi, lekin ANPR/OCR modeli ulanmaguncha server raqamni aniqlamaydi.
- Panel ESP32 HUB75 drayveri orqali matnni marquee qilib ko'rsatadi; o'lcham va pinlar aniq panelga moslanishi shart.
- Fizik bonus impulslari ataylab amalga oshirilmagan. TB77 impuls qiymatlari o'lchanib, izolyatsiya va xavfsizlik tekshirilmaguncha main boardga ulamang.

## 7. Demo device key

```bash
TOMCHI_DEMO_KEY
```

## 8. Mahalliy ishlash jarayoni

1. Backendni ishga tushiring.
2. Admin panelini ishga tushiring.
3. ESP32-CAM qismi avtomatik tasvir yuboradi.
4. Server suratni arxivlaydi; OCR/ANPR ulanmaganligi sabab raqam avtomatik aniqlanmaydi.
5. Admin panel Cameras bo'limida suratni ko'rib, raqamni tasdiqlaydi/tuzatadi; panel esa ro'yxatga olingan visit holatini ko'rsatadi.
