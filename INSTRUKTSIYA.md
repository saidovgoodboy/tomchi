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
python3 -m pip install --user --upgrade fastapi uvicorn[standard] sqlalchemy pydantic pydantic-settings python-dotenv httpx
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

1. Arduino IDE'da ESP32 board support paketini va `hardware/esp32_cam/esp32_cam.ino` faylini sozlang.
2. `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_URL`, `DEVICE_KEY` va `BOX_ID` qiymatlarini kiriting.
3. `SERVER_URL` serverning boxlardan ko'rinadigan LAN IP manzili yoki VPS domeni bo'lishi kerak; `localhost` ishlatmang.
4. Firmware'ni ESP32-CAM'ga yuklang.

### Panel ESP32

1. Arduino IDE'da `ArduinoJson` kutubxonasini o'rnating va `hardware/panel_esp32/panel_esp32.ino` faylini oching.
2. `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_URL`, `DEVICE_KEY` va shu boxga tegishli `BOX_ID` ni kiriting.
3. `OPTOCOUPLER_PIN` faqat optronning LED kirish qismiga ulanadi; ESP32 GPIO'ni main boardga bevosita ulamang.
4. Main board impulsining qutbi, davomiyligi va oralig'i o'lchanib tasdiqlanmaguncha main boardga ulamang. Hozirgi `100ms` parametrlar faqat sinov qiymati.
5. Firmware'ni boxdagi ESP32 DevKit'ga yuklang.

Har bir box uchun `BOX_ID` admin paneldagi ID bilan aynan bir xil bo'lishi kerak. Admin paneldagi Bonus sahifasidan box qo'shing, so'ng ID'ni har ikkala qurilmaga yozing.

## 6. Test holatlari

- `POST /api/detect` ga `{"plate": "01A123BC"}` yuborish orqali test qilinadi.
- `GET /api/display` orqali ekran matni olinadi.
- `POST /api/bonus/press` bilan bonus bosish simulyatsiyasi ishlaydi.
- `GET /api/boxes` boxlar va har birining joriy bonus holatini qaytaradi.
- Detection, display va bonus so'rovlari boxni `X-Box-Id` header orqali tanlaydi.

Bonus sozlamalari SQLite'dagi `app_settings` jadvalida saqlanadi va server qayta ishga tushganda qoladi. Mashinalar va kelishlar `backend/database/tomchi.db` faylida qoladi; ushbu faylni muntazam zaxiralang.
Bonus bo'limida bonus summasi, bir bosishda ishlatiladigan summa va bonus beriladigan kelishlar oralig'ini sozlash mumkin. Masalan, oralig'ini `5` qilib belgilasangiz, har bir mashinaning 5-, 10-, 15-kelishlarida bonus beriladi. Yangi interval keyingi ro'yxatga olinadigan kelishlarga ta'sir qiladi; mavjud bonus miqdori o'zgarmaydi.
Har bir apparat impulsi `1 000 so'm` deb qabul qilinadi. Per-press qiymatini `5 000` qilsangiz panel ESP32 5 impuls, `3 000` qilsangiz 3 impuls chiqaradi. Bonus va per-press qiymatlari 1 000 ga bo'linadigan bo'lishi kerak; qurilmada bir bosish uchun eng ko'pi bilan 100 impuls ruxsat etilgan.

## Muhim cheklovlar

- Hozirgi ESP32-CAM firmware sinov uchun namuna raqamini yuboradi; kamera tasviridan ANPR/OCR hali ulanmagan.
- P10 panel drayveri firmware'ga ulanmagan; panel API'dan matnni Serial Monitor'ga chiqaradi.
- Server bonusni tasdiqlagandan keyin panel ESP32 5 impuls chiqaradi. Impuls vaqtlarini haqiqiy TB77 kirishi bilan o'lchamasdan qurilmaga ulash mumkin emas.

## 7. Demo device key

```bash
TOMCHI_DEMO_KEY
```

## 8. Mahalliy ishlash jarayoni

1. Backendni ishga tushiring.
2. Admin panelini ishga tushiring.
3. ESP32-CAM qismi avtomatik tasvir yuboradi.
4. Server raqamni aniqlaydi va bonus holatini sinxronlaydi.
5. P10 panel yoki admin panel orqali natija ko'riladi.
