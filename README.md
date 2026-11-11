# Tomchi

Tomchi — avtomoyka uchun bonus tizimi. Backend bir nechta boxni boshqaradi: avtomobil kelishlari umumiy sanaladi, displey har bir box uchun alohida yuritiladi, bonus esa texnik topshiriqdagi kabi butun moyka uchun bitta faol bonus bo'ladi.

## Strukturasi

- `backend/` — FastAPI server, SQLite ma'lumotlar bazasi va biznes logika
- `admin/` — React + Vite admin panel
- `hardware/` — ESP32-CAM va panel controller uchun Arduino skretchlari
- `docs/` — qo'shimcha hujjatlar

## Tez boshlash

### 1) Python va dependencylar

```bash
cd /home/saidov/tomchi
export PYTHONPATH=/home/saidov/tomchi/backend
python3 -m pip install --user -r backend/requirements.txt
```

### 2) Backend ishga tushirish

```bash
cd /home/saidov/tomchi
export PYTHONPATH=/home/saidov/tomchi/backend
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000/docs

### 3) Admin panelni ishga tushirish

```bash
cd /home/saidov/tomchi/admin
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Open: http://localhost:5173

### 4) Hardware skriptlarini yuklash

- Admin panelning Bonus bo'limida box qo'shing. Box ID'sini (`box-1`, `box-2`...) shu boxdagi ESP32-CAM va panel ESP32 firmware'ida bir xil qilib sozlang.
- Server manzili, Wi-Fi va device key'ni kiriting; har boxdagi ikkala ESP32 bitta backend serverga ulanadi.
- Ulanish va apparat ogohlantirishlari uchun `INSTRUKTSIYA.md` ga qarang.
- Camera firmware PIR trigger bilan JPEG frame'larni serverga yuboradi; ANPR/OCR hali ulanmagan.
- Admin panelning Cameras bo'limida boxlar live ko'rinadi; aniqlangan mashina suratlari bilan keladi va raqamni tekshirib/tuzatib visit yaratish mumkin.
- Panel ESP32 HUB75 P10 matnini ko'rsatadi va tugmani o'qiydi; fizik bonus impulslari ataylab o'chirilgan.
- `PULSE_PERIOD_MS` sozlamasida bill acceptor pulse-frequency qiymatini 50, 100 yoki 200 ms qilib tanlash mumkin (default 100 ms). Impuls kengligi/polarligi sinovdan o'tmaguncha `ENABLE_BONUS_REDEMPTION` o'chirilgan qoladi.

### 5) Demo device key

```bash
TOMCHI_DEMO_KEY
```

## API

- `GET /health`
- `GET /api/stats`
- `GET /api/visits`
- `PUT /api/visits/{id}/plate`
- `GET /api/cars`
- `POST /api/detect`
- `GET /api/display`
- `GET /api/boxes`
- `POST /api/boxes`
- `POST /api/bonus/press`
- `POST /api/detect-image`
- `POST /api/boxes/{box_id}/live-frame` va `GET /api/boxes/{box_id}/live-frame`
- `GET /api/detections`, `GET /api/detections/{id}/image`, `PUT /api/detections/{id}/plate`

Box qurilmalari so'rovda `X-Box-Id` header yuboradi. Bonus sozlamalari, boxlar, mashinalar va kelishlar SQLite'da saqlanadi. DB fayli: `backend/database/tomchi.db`; uni muntazam zaxiralang.

Arxiv rasmlari SQLite BLOB emas, `backend/storage/detections/` ichida JPEG ko'rinishida saqlanadi (maksimal 640x480, qayta siqilgan). Rasmlar 30 kundan keyin yoki arxiv 512 MiB chegarasiga yetganda eng eskisidan o'chiriladi. Live preview har box uchun bitta kichik JPEG faylni yangilab boradi. ANPR/OCR modeli ulanmagan: Cameras sahifasida pending surat uchun davlat raqamini kiritish/tuzatish va visitni ro'yxatga olish kerak.
Visits sahifasida raqamni tahrirlash faqat tanlangan kelishga ta'sir qiladi; Cars ro'yxatidagi mashina raqami va boshqa kelishlar o'zgarmaydi.

## Xavfsizlik va kalit

Barcha so'rovlarda `X-Device-Key` sarlavhasi bo'lishi kerak. Demo kalit:

```bash
TOMCHI_DEMO_KEY
```

Yoki `.env` faylida o'zingizning kalitingizni qo'ying.

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
