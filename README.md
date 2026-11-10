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
python3 -m pip install --user --upgrade fastapi uvicorn[standard] sqlalchemy pydantic pydantic-settings python-dotenv httpx
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
- Camera firmware hozircha rasm/OCR ishlatmaydi, mock davlat raqami yuboradi; haqiqiy ANPR/OCR keyingi bosqich.
- Panel firmware matnni Serial Monitor'ga chiqaradi; P10 panel drayveri hali ulanmagan.

### 5) Demo device key

```bash
TOMCHI_DEMO_KEY
```

## API

- `GET /health`
- `GET /api/stats`
- `GET /api/visits`
- `GET /api/cars`
- `POST /api/detect`
- `GET /api/display`
- `GET /api/boxes`
- `POST /api/boxes`
- `POST /api/bonus/press`
- `POST /api/detect-image`

Box qurilmalari so'rovda `X-Box-Id` header yuboradi. Bonus sozlamalari, boxlar, mashinalar va kelishlar SQLite'da saqlanadi. DB fayli: `backend/database/tomchi.db`; uni muntazam zaxiralang.

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
