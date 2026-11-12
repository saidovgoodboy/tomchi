import { useEffect, useState, type FormEvent } from 'react';

type TabKey = 'dashboard' | 'cars' | 'visits' | 'bonus' | 'cameras';
type PulsePolarity = 'HIGH' | 'LOW';
type PulseFrequencyMs = 50 | 100 | 200;
type Language = 'uz' | 'ru';
type Theme = 'dark' | 'light';

const PULSE_FREQUENCIES_MS: PulseFrequencyMs[] = [50, 100, 200];
const copy = {
  uz: {
    subtitle: 'Avtomoyka bonus tizimi',
    dashboard: 'Bosh sahifa',
    cars: 'Mashinalar',
    visits: 'Kelishlar',
    bonus: 'Bonus',
    cameras: 'Kameralar',
    username: 'Foydalanuvchi nomi',
    password: 'Parol',
    signIn: 'Kirish',
    signingIn: 'Kirilmoqda…',
    logOut: 'Chiqish',
    loginFailed: 'Kirish amalga oshmadi',
    switchToDay: 'Kunduzgi mavzuga o‘tish',
    switchToNight: 'Tungi mavzuga o‘tish',
    chooseLanguage: 'Interfeys tili',
    theme: 'Mavzu',
    imageUnavailable: 'Rasm mavjud emas',
    loadingImage: 'Rasm yuklanmoqda…',
    cameraOffline: 'Kamera ishlamayapti',
    connectionLost: 'Aloqa uzildi · oxirgi kadr ko‘rsatilmoqda',
    plateNumber: 'Davlat raqami',
    visitRegistered: 'Kelish ro‘yxatga olindi',
    saving: 'Saqlanmoqda…',
    correctPlate: 'Raqamni tuzatish va kelishni ro‘yxatga olish',
    carsCount: 'Mashinalar',
    visitsCount: 'Kelishlar',
    bonusPaid: 'Berilgan bonus',
    activeBonus: 'Faol bonuslar',
    manualDetection: 'Raqamni qo‘lda kiritish',
    detect: 'Aniqlash',
    systemStatus: 'Tizim holati',
    ocrReady: 'Mahalliy OCR faol',
    ocrDisabled: 'OCR o‘chirilgan',
    ocrUnavailable: 'OCR yoqilgan, lekin Tesseract topilmadi',
    ocrSuggestion: 'OCR taklifi — raqamni tekshiring',
    confirmPlate: 'Tasdiqlash va kelishni ro‘yxatga olish',
    duplicateCheck: '24 soatlik takroriy aniqlash faol',
    bonusEvery: 'Bonus har',
    authenticationEnabled: 'Admin va qurilma himoyasi yoqilgan',
    carList: 'Mashinalar ro‘yxati',
    noCars: 'Mashinalar topilmadi.',
    noVisits: 'Kelishlar topilmadi.',
    plate: 'Raqam',
    visitImage: 'Surat',
    arrivalTime: 'Kelgan vaqt',
    viewImage: 'Avtomobil suratini ko‘rish',
    noImage: 'Surat yo‘q',
    close: 'Yopish',
    count: 'Soni',
    created: 'Qo‘shilgan sana',
    visit: 'Kelish',
    bonusLeft: 'Qolgan bonus',
    status: 'Holati',
    actions: 'Amallar',
    active: 'Faol',
    idle: 'Faol emas',
    save: 'Saqlash',
    cancel: 'Bekor qilish',
    editPlate: 'Raqamni tahrirlash',
    visitEditHint: 'Raqamni o‘zgartirish faqat tanlangan kelishga ta’sir qiladi; mashinalar ro‘yxati o‘zgarmaydi.',
    livePreview: 'Jonli tasvir',
    lastCar: 'Oxirgi mashina',
    noVisitYet: 'Hali kelish qayd etilmagan',
    noBoxes: 'Boxlar sozlanmagan.',
    capturedImages: 'Olingan raqam suratlari',
    selectedBox: 'Tanlangan box',
    imagesExpire: 'Suratlar 30 kundan keyin o‘chiriladi',
    noCapturedImages: 'Bu box uchun suratlar yo‘q.',
    detection: 'Aniqlash',
    confirmed: 'Kelish ro‘yxatga olindi',
    bonusOverview: 'Bonus haqida',
    bonusAmount: 'Bonus miqdori',
    perPress: 'Bir bosish uchun',
    bonusFrequency: 'Bonus berish oralig‘i',
    visitsUnit: 'kelishda',
    oneBonusRule: 'Bir vaqtda bitta faol bonus bo‘ladi va faqat berilgan boxda ishlatiladi',
    duplicateRule: '24 soat ichida boshqa mashina aniqlansa, avvalgi faol bonus bekor qilinadi',
    currentTotals: 'Umumiy ko‘rsatkichlar',
    totalPaid: 'Jami berilgan',
    activeBonusCount: 'Faol bonuslar',
    settings: 'Bonus va impuls sozlamalari',
    visitsBetweenBonuses: 'Bonuslar orasidagi kelishlar',
    pulsePolarity: 'Impuls qutbi',
    highActive: 'HIGH faol',
    lowActive: 'LOW faol',
    pulseFrequency: 'Impuls davri',
    periodHint: 'Impuls qutbi va davri tanlangan box uchun alohida saqlanadi. Bonus summasi umumiy.',
    perPressHint: 'Bir bosishdagi bonus miqdori impulslar sonini belgilaydi.',
    displayTextSettings: 'P10 displey yozuvlari',
    displayIdleText: 'Avtomobil yo‘q yozuvi',
    displayVisitLabel: 'Kelish yorlig‘i',
    displayRewardLabel: 'Mukofot yorlig‘i',
    displayRemainingLabel: 'Qolgan mukofot yozuvi',
    displayFinishedText: 'Mukofot tugagan yozuv',
    displayCurrencyLabel: 'Valyuta yozuvi',
    displayAsciiHint: 'Yozuvlar tanlangan box uchun alohida saqlanadi. P10 faqat ASCII belgilarini ko‘rsatadi.',
    settingsSaved: 'Sozlamalar saqlandi',
    boxPulseTest: 'Box impulsini sinash',
    startTesting: 'Sinovni boshlash',
    testAmount: 'Sinov bonus miqdori (so‘m)',
    testPulseHint: 'Har impuls 1 000 so‘mga teng. Sinov mijoz bonusidan yechilmaydi.',
    queueHint: 'ESP32 buyruqni navbatdagi so‘rovda oladi. Plata qabul qilganini tasdiqlamaydi.',
    queuedAmount: 'Navbatdagi summa',
    sendTestBonus: 'Sinov bonusini yuborish',
    finishTesting: 'Sinovni tugatish',
    testStarted: 'Sinov boshlandi',
    testQueued: 'Sinov bonusi navbatga qo‘yildi',
    testFinished: 'Sinov tugatildi',
    addWashBox: 'Box qo‘shish',
    boxId: 'Box ID',
    name: 'Nomi',
    backendOnline: 'Server ulangan',
    backendOffline: 'Server ulanmagan',
    selected: 'Tanlangan',
    adminPanel: 'Admin panel',
    total: 'Jami',
    manualPlatePlaceholder: '01A123BC',
    imageError: 'Rasmni yuklab bo‘lmadi',
    settingsLoadFailed: 'Sozlamalarni yuklab bo‘lmadi',
    unexpectedError: 'Kutilmagan xatolik',
  },
  ru: {
    subtitle: 'Бонусная система автомойки',
    dashboard: 'Главная',
    cars: 'Автомобили',
    visits: 'Визиты',
    bonus: 'Бонусы',
    cameras: 'Камеры',
    username: 'Имя пользователя',
    password: 'Пароль',
    signIn: 'Войти',
    signingIn: 'Вход…',
    logOut: 'Выйти',
    loginFailed: 'Не удалось войти',
    switchToDay: 'Включить светлую тему',
    switchToNight: 'Включить тёмную тему',
    chooseLanguage: 'Язык интерфейса',
    theme: 'Тема',
    imageUnavailable: 'Изображение недоступно',
    loadingImage: 'Загрузка изображения…',
    cameraOffline: 'Камера недоступна',
    connectionLost: 'Связь потеряна · показан последний кадр',
    plateNumber: 'Госномер',
    visitRegistered: 'Визит зарегистрирован',
    saving: 'Сохранение…',
    correctPlate: 'Исправить номер и зарегистрировать визит',
    carsCount: 'Автомобили',
    visitsCount: 'Визиты',
    bonusPaid: 'Выдано бонусов',
    activeBonus: 'Активные бонусы',
    manualDetection: 'Ввести номер вручную',
    detect: 'Распознать',
    systemStatus: 'Состояние системы',
    ocrReady: 'Локальный OCR активен',
    ocrDisabled: 'OCR отключён',
    ocrUnavailable: 'OCR включён, но Tesseract не найден',
    ocrSuggestion: 'Распознанный номер — проверьте его',
    confirmPlate: 'Подтвердить и зарегистрировать визит',
    duplicateCheck: 'Проверка повторов за 24 часа включена',
    bonusEvery: 'Бонус каждые',
    authenticationEnabled: 'Защита администратора и устройств включена',
    carList: 'Список автомобилей',
    noCars: 'Автомобили не найдены.',
    noVisits: 'Визиты не найдены.',
    plate: 'Номер',
    visitImage: 'Фото',
    arrivalTime: 'Время приезда',
    viewImage: 'Посмотреть фото автомобиля',
    noImage: 'Нет фото',
    close: 'Закрыть',
    count: 'Количество',
    created: 'Добавлен',
    visit: 'Визит',
    bonusLeft: 'Остаток бонуса',
    status: 'Статус',
    actions: 'Действия',
    active: 'Активен',
    idle: 'Неактивен',
    save: 'Сохранить',
    cancel: 'Отмена',
    editPlate: 'Изменить номер',
    visitEditHint: 'Изменение номера относится только к выбранному визиту и не меняет список автомобилей.',
    livePreview: 'Прямой эфир',
    lastCar: 'Последний автомобиль',
    noVisitYet: 'Визиты пока не зарегистрированы',
    noBoxes: 'Боксы не настроены.',
    capturedImages: 'Снимки номеров',
    selectedBox: 'Выбранный бокс',
    imagesExpire: 'Снимки удаляются через 30 дней',
    noCapturedImages: 'Для этого бокса снимков пока нет.',
    detection: 'Распознавание',
    confirmed: 'Визит зарегистрирован',
    bonusOverview: 'Сводка бонусов',
    bonusAmount: 'Размер бонуса',
    perPress: 'За одно нажатие',
    bonusFrequency: 'Интервал выдачи бонуса',
    visitsUnit: 'визитов',
    oneBonusRule: 'Одновременно активен один бонус; использовать его можно только в выдавшем боксе',
    duplicateRule: 'Если за 24 часа обнаружен другой автомобиль, предыдущий активный бонус отменяется',
    currentTotals: 'Итоги',
    totalPaid: 'Всего выдано',
    activeBonusCount: 'Активные бонусы',
    settings: 'Настройки бонусов и импульсов',
    visitsBetweenBonuses: 'Интервал визитов для бонуса',
    pulsePolarity: 'Полярность импульса',
    highActive: 'Активный HIGH',
    lowActive: 'Активный LOW',
    pulseFrequency: 'Период импульса',
    periodHint: 'Полярность и период импульса настраиваются отдельно для выбранного бокса. Размер бонуса общий.',
    perPressHint: 'Размер бонуса за нажатие определяет количество импульсов.',
    displayTextSettings: 'Текст на дисплее P10',
    displayIdleText: 'Текст «Нет автомобиля»',
    displayVisitLabel: 'Подпись визита',
    displayRewardLabel: 'Подпись бонуса',
    displayRemainingLabel: 'Текст оставшегося бонуса',
    displayFinishedText: 'Текст завершённого бонуса',
    displayCurrencyLabel: 'Обозначение валюты',
    displayAsciiHint: 'Тексты сохраняются отдельно для выбранного бокса. Дисплей P10 поддерживает только ASCII.',
    settingsSaved: 'Настройки сохранены',
    boxPulseTest: 'Тест импульсов бокса',
    startTesting: 'Начать тест',
    testAmount: 'Сумма тестового бонуса (сум)',
    testPulseHint: 'Один импульс равен 1 000 сум. Тест не списывает клиентский бонус.',
    queueHint: 'ESP32 получит команду при следующем запросе. Подтверждения от платы нет.',
    queuedAmount: 'В очереди',
    sendTestBonus: 'Отправить тестовый бонус',
    finishTesting: 'Завершить тест',
    testStarted: 'Тест начат',
    testQueued: 'Тестовый бонус добавлен в очередь',
    testFinished: 'Тест завершён',
    addWashBox: 'Добавить бокс',
    boxId: 'ID бокса',
    name: 'Название',
    backendOnline: 'Сервер подключён',
    backendOffline: 'Сервер не подключён',
    selected: 'Выбран',
    adminPanel: 'Панель администратора',
    total: 'Всего',
    manualPlatePlaceholder: '01A123BC',
    imageError: 'Не удалось загрузить изображение',
    settingsLoadFailed: 'Не удалось загрузить настройки',
    unexpectedError: 'Произошла непредвиденная ошибка',
  },
} as const;

type CopyKey = keyof typeof copy.uz;
type Translate = (key: CopyKey) => string;

function AppearanceControls({
  language,
  theme,
  onLanguageChange,
  onThemeToggle,
  t,
}: {
  language: Language;
  theme: Theme;
  onLanguageChange: (language: Language) => void;
  onThemeToggle: () => void;
  t: Translate;
}) {
  return (
    <div className="appearance-controls">
      <label className="visually-hidden" htmlFor="language-select">{t('chooseLanguage')}</label>
      <select
        id="language-select"
        value={language}
        onChange={(event) => onLanguageChange(event.target.value === 'ru' ? 'ru' : 'uz')}
      >
        <option value="uz">O‘zbekcha</option>
        <option value="ru">Русский</option>
      </select>
      <button
        className="theme-toggle"
        type="button"
        onClick={onThemeToggle}
        aria-label={theme === 'dark' ? t('switchToDay') : t('switchToNight')}
        title={theme === 'dark' ? t('switchToDay') : t('switchToNight')}
      >
        <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>
      </button>
    </div>
  );
}

type Stats = {
  cars_count: number;
  visits_count: number;
  total_bonus_paid: number;
  active_bonus_count: number;
};

type VisitRow = {
  id: number;
  plate: string;
  image_url: string | null;
  visit_no: number;
  created_at: string;
  bonus_total: number;
  bonus_left: number;
  is_active_bonus: boolean;
};

type CarRow = {
  id: number;
  plate: string;
  created_at: string;
  visit_count: number;
};

type BoxRow = {
  id: string;
  name: string;
  active_bonus_left: number;
  current_plate: string | null;
};

type DetectionRow = {
  id: number;
  box_id: string;
  plate: string | null;
  ocr_confidence?: number | null;
  status: string;
  frame_index: number;
  frame_count: number;
  created_at: string;
  image_url: string;
};

const API_BASE = import.meta.env.VITE_API_BASE
  ?? (import.meta.env.DEV ? `http://${window.location.hostname}:8000` : '');

function AuthenticatedImage({
  url,
  alt,
  token,
  t,
  refreshMs = 0,
}: {
  url: string;
  alt: string;
  token: string;
  t: Translate;
  refreshMs?: number;
}) {
  const [source, setSource] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let timer = 0;
    let objectUrl = '';

    const fetchImage = async () => {
      try {
        const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (!response.ok) throw new Error(`Image request failed: ${response.status}`);
        const blob = await response.blob();
        if (!active) return;
        const nextUrl = URL.createObjectURL(blob);
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = nextUrl;
        setSource(nextUrl);
        setFailed(false);
      } catch {
        if (active) setFailed(true);
      } finally {
        if (active && refreshMs > 0) {
          timer = window.setTimeout(fetchImage, refreshMs);
        }
      }
    };

    fetchImage();
    return () => {
      active = false;
      window.clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, refreshMs, token]);

  if (!source) {
    return (
      <div className="image-placeholder">
        {failed ? (refreshMs > 0 ? t('cameraOffline') : t('imageUnavailable')) : t('loadingImage')}
      </div>
    );
  }
  return (
    <div className="image-wrap">
      <img className={refreshMs > 0 ? 'live-preview' : 'detection-image'} src={source} alt={alt} />
      {failed && refreshMs > 0 && <span className="image-offline">{t('connectionLost')}</span>}
    </div>
  );
}

function DetectionReviewCard({
  detection,
  token,
  language,
  t,
  onSave,
}: {
  detection: DetectionRow;
  token: string;
  language: Language;
  t: Translate;
  onSave: (id: number, plate: string) => Promise<void>;
}) {
  const [plate, setPlate] = useState(detection.plate ?? '');
  const [plateEdited, setPlateEdited] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!plateEdited) setPlate(detection.plate ?? '');
  }, [detection.plate, plateEdited]);

  const submit = async () => {
    if (!plate.trim() || saving || detection.status === 'confirmed') return;
    setSaving(true);
    try {
      await onSave(detection.id, plate);
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="detection-card">
      <AuthenticatedImage
        url={`${API_BASE}${detection.image_url}`}
        alt={`${t('detection')} ${detection.id}`}
        token={token}
        t={t}
      />
      <div className="detection-details">
        <div className="detection-meta">
          <strong>{detection.box_id}</strong>
          <time>{new Date(detection.created_at).toLocaleString(language === 'uz' ? 'uz-UZ' : 'ru-RU')}</time>
        </div>
        <label>
          {t('plateNumber')}
          <input
            value={plate}
            disabled={detection.status === 'confirmed'}
            onChange={(event) => {
              setPlateEdited(true);
              setPlate(event.target.value.toUpperCase());
            }}
            placeholder="01A123BC"
          />
        </label>
        {detection.ocr_confidence != null && detection.status !== 'confirmed' && (
          <p className="ocr-suggestion">
            {t('ocrSuggestion')}: <strong>{detection.plate}</strong> · {Math.round(detection.ocr_confidence * 100)}%
          </p>
        )}
        {detection.status === 'confirmed' ? (
          <span className="confirmed-status">{t('visitRegistered')}: {detection.plate}</span>
        ) : (
          <button className="save-button" onClick={submit} disabled={!plate.trim() || saving}>
            {saving ? t('saving') : t(detection.ocr_confidence != null ? 'confirmPlate' : 'correctPlate')}
          </button>
        )}
      </div>
    </article>
  );
}

export default function App() {
  const [language, setLanguage] = useState<Language>(() => (
    localStorage.getItem('tomchi-language') === 'ru' ? 'ru' : 'uz'
  ));
  const [theme, setTheme] = useState<Theme>(() => (
    localStorage.getItem('tomchi-theme') === 'light' ? 'light' : 'dark'
  ));
  const [authToken, setAuthToken] = useState(() => sessionStorage.getItem('tomchi-admin-token') ?? '');
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginPending, setLoginPending] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');
  const [stats, setStats] = useState<Stats | null>(null);
  const [visits, setVisits] = useState<VisitRow[]>([]);
  const [cars, setCars] = useState<CarRow[]>([]);
  const [boxes, setBoxes] = useState<BoxRow[]>([]);
  const [detections, setDetections] = useState<DetectionRow[]>([]);
  const [activeBoxId, setActiveBoxId] = useState('box-1');
  const [health, setHealth] = useState<{
    ok: boolean;
    service?: string;
    bonus_amount?: number;
    bonus_per_press?: number;
    anpr_enabled?: boolean;
    anpr_available?: boolean;
  } | null>(null);
  const [plate, setPlate] = useState('01A123BC');
  const [message, setMessage] = useState('');
  const [editingVisitId, setEditingVisitId] = useState<number | null>(null);
  const [editingVisitPlate, setEditingVisitPlate] = useState('');
  const [selectedVisitPhoto, setSelectedVisitPhoto] = useState<{
    plate: string;
    imageUrl: string;
  } | null>(null);
  const [bonusAmount, setBonusAmount] = useState<number>(20000);
  const [bonusPerPress, setBonusPerPress] = useState<number>(5000);
  const [bonusEveryVisits, setBonusEveryVisits] = useState<number>(10);
  const [pulsePolarity, setPulsePolarity] = useState<PulsePolarity>('HIGH');
  const [pulseFrequencyMs, setPulseFrequencyMs] = useState<PulseFrequencyMs>(100);
  const [displayIdleText, setDisplayIdleText] = useState("AVTOMOBIL YO'Q");
  const [displayVisitLabel, setDisplayVisitLabel] = useState('KELISH');
  const [displayRewardLabel, setDisplayRewardLabel] = useState('MUKOFOT');
  const [displayRemainingLabel, setDisplayRemainingLabel] = useState('MUKOFOT QOLDI');
  const [displayFinishedText, setDisplayFinishedText] = useState('MUKOFOT TUGADI');
  const [displayCurrencyLabel, setDisplayCurrencyLabel] = useState("SO'M");
  const [boxTestActive, setBoxTestActive] = useState(false);
  const [testBonusAmount, setTestBonusAmount] = useState(1000);
  const [pendingTestAmount, setPendingTestAmount] = useState<number | null>(null);
  const [newBoxId, setNewBoxId] = useState('');
  const [newBoxName, setNewBoxName] = useState('');

  const t: Translate = (key) => copy[language][key];
  const formatNumber = (value: number) => value.toLocaleString(language === 'uz' ? 'uz-UZ' : 'ru-RU');
  const selectedBoxName = boxes.find((box) => box.id === activeBoxId)?.name ?? activeBoxId;
  const pageTitleKeys: Record<TabKey, CopyKey> = {
    dashboard: 'adminPanel',
    cars: 'cars',
    visits: 'visits',
    bonus: 'bonus',
    cameras: 'cameras',
  };

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = language;
    localStorage.setItem('tomchi-theme', theme);
    localStorage.setItem('tomchi-language', language);
    document.title = `Tomchi · ${t('adminPanel')}`;
  }, [theme, language]);

  useEffect(() => {
    if (!selectedVisitPhoto) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSelectedVisitPhoto(null);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [selectedVisitPhoto]);

  const apiFetch = async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const headers = new Headers(init.headers);
    if (authToken) headers.set('Authorization', `Bearer ${authToken}`);
    const response = await fetch(input, { ...init, headers });
    if (response.status === 401 && authToken) {
      sessionStorage.removeItem('tomchi-admin-token');
      setAuthToken('');
    }
    return response;
  };

  const loadData = async () => {
    if (!authToken) return;
    try {
      const [statsRes, visitsRes, carsRes, healthRes, boxesRes] = await Promise.all([
        apiFetch(`${API_BASE}/api/stats`),
        apiFetch(`${API_BASE}/api/visits?limit=10&box_id=${encodeURIComponent(activeBoxId)}`),
        apiFetch(`${API_BASE}/api/cars?limit=10`),
        fetch(`${API_BASE}/health`),
        apiFetch(`${API_BASE}/api/boxes`),
      ]);

      if (statsRes.ok) setStats(await statsRes.json());
      if (visitsRes.ok) setVisits(await visitsRes.json());
      if (carsRes.ok) setCars(await carsRes.json());
      if (healthRes.ok) setHealth(await healthRes.json());
      if (boxesRes.ok) {
        const boxData: BoxRow[] = await boxesRes.json();
        setBoxes(boxData);
        if (!boxData.some((box) => box.id === activeBoxId) && boxData.length) {
          setActiveBoxId(boxData[0].id);
        }
      }
    } catch (error) {
      console.error('loadData failed', error);
      setHealth({ ok: false, service: 'tomchi-backend' });
    }
  };

  useEffect(() => {
    if (!authToken) return;
    loadData();
    const id = window.setInterval(loadData, 10000);
    return () => window.clearInterval(id);
  }, [activeBoxId, authToken]);

  useEffect(() => {
    if (!authToken || activeTab !== 'cameras') return;
    let active = true;
    const loadDetections = async () => {
      try {
        const response = await apiFetch(
          `${API_BASE}/api/detections?limit=30&box_id=${encodeURIComponent(activeBoxId)}`,
        );
        if (!response.ok) throw new Error(`${t('settingsLoadFailed')}: ${response.status}`);
        const data: DetectionRow[] = await response.json();
        if (active) setDetections(data);
      } catch (error) {
        if (active) setMessage(error instanceof Error ? error.message : t('settingsLoadFailed'));
      }
    };

    loadDetections();
    const timer = window.setInterval(loadDetections, 10000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeTab, activeBoxId, authToken]);

  useEffect(() => {
    if (!authToken) return;
    let active = true;
    apiFetch(`${API_BASE}/api/settings?box_id=${encodeURIComponent(activeBoxId)}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(t('settingsLoadFailed'));
        return res.json();
      })
      .then((data) => {
        if (!active) return;
        setBonusAmount(data.bonus_amount);
        setBonusPerPress(data.bonus_per_press);
        setBonusEveryVisits(data.bonus_every_visits);
        setPulsePolarity(data.pulse_polarity);
        setPulseFrequencyMs(data.pulse_frequency_ms);
        setDisplayIdleText(data.display_idle_text);
        setDisplayVisitLabel(data.display_visit_label);
        setDisplayRewardLabel(data.display_reward_label);
        setDisplayRemainingLabel(data.display_remaining_label);
        setDisplayFinishedText(data.display_finished_text);
        setDisplayCurrencyLabel(data.display_currency_label);
      })
      .catch((error) => {
        if (active) console.error(error);
      });
    return () => {
      active = false;
    };
  }, [activeBoxId, authToken]);

  useEffect(() => {
    if (!authToken) return;
    let active = true;
    const loadTestStatus = async () => {
      try {
        const response = await apiFetch(
          `${API_BASE}/api/boxes/${encodeURIComponent(activeBoxId)}/test`,
        );
        if (!response.ok) throw new Error(`${t('settingsLoadFailed')}: ${response.status}`);
        const data = await response.json();
        if (active) {
          setBoxTestActive(data.active);
          setPendingTestAmount(data.pending_amount);
        }
      } catch (error) {
        if (active) console.error(error);
      }
    };

    loadTestStatus();
    const interval = window.setInterval(loadTestStatus, 2000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [activeBoxId, authToken]);

  useEffect(() => {
    if (!message) return;
    const timeout = window.setTimeout(() => setMessage(''), 4000);
    return () => window.clearTimeout(timeout);
  }, [message]);

  const handleDetect = async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/detect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Box-Id': activeBoxId,
        },
        body: JSON.stringify({ plate }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? t('unexpectedError'));
      }

      setMessage(`${t('visitRegistered')}: ${data.plate} / #${data.visit_no}`);
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('unexpectedError'));
    }
  };

  const handleSaveVisitPlate = async (visitId: number) => {
    try {
      const response = await apiFetch(`${API_BASE}/api/visits/${visitId}/plate`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ plate: editingVisitPlate }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? t('unexpectedError'));
      setEditingVisitId(null);
      setEditingVisitPlate('');
      setMessage(`${t('visit')} #${visitId}: ${data.plate}`);
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('unexpectedError'));
    }
  };

  const handleSaveSettings = async () => {
    try {
      const res = await apiFetch(
        `${API_BASE}/api/settings?box_id=${encodeURIComponent(activeBoxId)}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            bonus_amount: bonusAmount,
            bonus_per_press: bonusPerPress,
            bonus_every_visits: bonusEveryVisits,
            pulse_polarity: pulsePolarity,
            pulse_frequency_ms: pulseFrequencyMs,
            display_idle_text: displayIdleText,
            display_visit_label: displayVisitLabel,
            display_reward_label: displayRewardLabel,
            display_remaining_label: displayRemainingLabel,
            display_finished_text: displayFinishedText,
            display_currency_label: displayCurrencyLabel,
          }),
        },
      );

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? t('settingsLoadFailed'));
      }

      setDisplayIdleText(data.display_idle_text);
      setDisplayVisitLabel(data.display_visit_label);
      setDisplayRewardLabel(data.display_reward_label);
      setDisplayRemainingLabel(data.display_remaining_label);
      setDisplayFinishedText(data.display_finished_text);
      setDisplayCurrencyLabel(data.display_currency_label);
      setMessage(
        `${t('settingsSaved')} · ${selectedBoxName}: ${data.pulse_polarity} / ${data.pulse_frequency_ms} ms`,
      );
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('unexpectedError'));
    }
  };

  const handleStartBoxTest = async () => {
    try {
      const response = await apiFetch(
        `${API_BASE}/api/boxes/${encodeURIComponent(activeBoxId)}/test/start`,
        { method: 'POST' },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? t('unexpectedError'));
      setBoxTestActive(data.active);
      setPendingTestAmount(data.pending_amount);
      setMessage(`${selectedBoxName}: ${t('testStarted')}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('unexpectedError'));
    }
  };

  const handleSendTestBonus = async () => {
    try {
      const response = await apiFetch(
        `${API_BASE}/api/boxes/${encodeURIComponent(activeBoxId)}/test/pulses`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount: testBonusAmount }),
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? t('unexpectedError'));
      setPendingTestAmount(data.pending_amount);
      setMessage(`${selectedBoxName}: ${t('testQueued')}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('unexpectedError'));
    }
  };

  const handleFinishBoxTest = async () => {
    try {
      const response = await apiFetch(
        `${API_BASE}/api/boxes/${encodeURIComponent(activeBoxId)}/test/finish`,
        { method: 'POST' },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? t('unexpectedError'));
      setBoxTestActive(data.active);
      setPendingTestAmount(data.pending_amount);
      setMessage(`${selectedBoxName}: ${t('testFinished')}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('unexpectedError'));
    }
  };

  const handleCreateBox = async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/boxes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: newBoxId, name: newBoxName }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? t('unexpectedError'));
      setNewBoxId('');
      setNewBoxName('');
      setMessage(`${t('addWashBox')}: ${data.name} (${data.id})`);
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('unexpectedError'));
    }
  };

  const handleCorrectPlate = async (detectionId: number, correctedPlate: string) => {
    try {
      const response = await apiFetch(`${API_BASE}/api/detections/${detectionId}/plate`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ plate: correctedPlate }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? t('unexpectedError'));
      setMessage(`${t('visitRegistered')}: ${data.plate} / #${data.visit_no}`);
      const refreshed = await apiFetch(
        `${API_BASE}/api/detections?limit=30&box_id=${encodeURIComponent(activeBoxId)}`,
      );
      if (refreshed.ok) setDetections(await refreshed.json());
      await loadData();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('unexpectedError');
      setMessage(errorMessage);
    }
  };

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoginPending(true);
    setLoginError('');
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(t('loginFailed'));
      sessionStorage.setItem('tomchi-admin-token', data.access_token);
      setAuthToken(data.access_token);
      setLoginPassword('');
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : t('loginFailed'));
    } finally {
      setLoginPending(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem('tomchi-admin-token');
    setSelectedVisitPhoto(null);
    setAuthToken('');
  };

  const renderDashboard = () => (
    <>
      <section className="cards">
        <div className="card">
          <label>{t('carsCount')}</label>
          <strong>{formatNumber(stats?.cars_count ?? 0)}</strong>
        </div>
        <div className="card">
          <label>{t('visitsCount')}</label>
          <strong>{formatNumber(stats?.visits_count ?? 0)}</strong>
        </div>
        <div className="card">
          <label>{t('bonusPaid')}</label>
          <strong>{formatNumber(stats?.total_bonus_paid ?? 0)} so‘m</strong>
        </div>
        <div className="card">
          <label>{t('activeBonus')}</label>
          <strong>{formatNumber(stats?.active_bonus_count ?? 0)}</strong>
        </div>
      </section>

      <section className="split-layout">
        <div className="panel">
          <h3>{t('manualDetection')}</h3>
          <div className="inline-form">
            <input
              value={plate}
              onChange={(event) => setPlate(event.target.value.toUpperCase())}
              placeholder={t('manualPlatePlaceholder')}
            />
            <button type="button" onClick={handleDetect}>{t('detect')}</button>
          </div>
        </div>

        <div className="panel">
          <h3>{t('systemStatus')}</h3>
          <ul className="simple-list">
            <li>{health?.anpr_enabled ? (health.anpr_available ? t('ocrReady') : t('ocrUnavailable')) : t('ocrDisabled')}</li>
            <li>{t('duplicateCheck')}</li>
            <li>{t('bonusEvery')} {formatNumber(bonusEveryVisits)} {t('visitsUnit')}</li>
            <li>{t('authenticationEnabled')}</li>
          </ul>
        </div>
      </section>
    </>
  );

  const renderCars = () => (
    <section className="panel">
      <h3>{t('carList')}</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t('plate')}</th>
              <th>{t('visitsCount')}</th>
              <th>{t('created')}</th>
            </tr>
          </thead>
          <tbody>
            {cars.map((car) => (
              <tr key={car.id}>
                <td>{car.plate}</td>
                <td>{formatNumber(car.visit_count)}</td>
                <td>{new Date(car.created_at).toLocaleDateString(language === 'uz' ? 'uz-UZ' : 'ru-RU')}</td>
              </tr>
            ))}
            {!cars.length && <tr><td colSpan={3}>{t('noCars')}</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );

  const renderVisits = () => (
    <section className="panel">
      <h3>{t('visits')}</h3>
      <p className="settings-hint">{t('visitEditHint')}</p>
      <div className="table-wrap">
      <table className="visits-table">
        <thead>
          <tr>
            <th>{t('plate')}</th>
            <th>{t('visitImage')}</th>
            <th>{t('arrivalTime')}</th>
            <th>{t('visit')}</th>
            <th>{t('bonusLeft')}</th>
            <th>{t('status')}</th>
            <th>{t('actions')}</th>
          </tr>
        </thead>
        <tbody>
          {visits.map((visit) => (
            <tr key={visit.id}>
              <td>
                {editingVisitId === visit.id ? (
                  <input
                    className="plate-edit-input"
                    value={editingVisitPlate}
                    onChange={(event) => setEditingVisitPlate(event.target.value.toUpperCase())}
                    placeholder={t('manualPlatePlaceholder')}
                    aria-label={`${t('visit')} ${visit.id}: ${t('plate')}`}
                  />
                ) : visit.plate}
              </td>
              <td>
                {visit.image_url ? (
                  <button
                    className="visit-image-button"
                    type="button"
                    title={t('viewImage')}
                    aria-label={`${t('viewImage')}: ${visit.plate}`}
                    onClick={() => {
                      if (!visit.image_url) return;
                      setSelectedVisitPhoto({ plate: visit.plate, imageUrl: visit.image_url });
                    }}
                  >
                    <AuthenticatedImage
                      url={`${API_BASE}${visit.image_url}`}
                      alt={`${t('visitImage')} ${visit.plate}`}
                      token={authToken}
                      t={t}
                    />
                  </button>
                ) : (
                  <span className="visit-image-empty">{t('noImage')}</span>
                )}
              </td>
              <td>{new Date(visit.created_at).toLocaleString(language === 'uz' ? 'uz-UZ' : 'ru-RU', {
                dateStyle: 'short',
                timeStyle: 'short',
              })}</td>
              <td>{formatNumber(visit.visit_no)}</td>
              <td>{formatNumber(visit.bonus_left)}</td>
              <td>{visit.is_active_bonus ? t('active') : t('idle')}</td>
              <td className="table-actions">
                {editingVisitId === visit.id ? (
                  <>
                    <button className="table-action primary-action" onClick={() => handleSaveVisitPlate(visit.id)}>
                      {t('save')}
                    </button>
                    <button
                      className="table-action"
                      onClick={() => {
                        setEditingVisitId(null);
                        setEditingVisitPlate('');
                      }}
                    >
                      {t('cancel')}
                    </button>
                  </>
                ) : (
                  <button
                    className="table-action"
                    onClick={() => {
                      setEditingVisitId(visit.id);
                      setEditingVisitPlate(visit.plate);
                    }}
                  >
                    {t('editPlate')}
                  </button>
                )}
              </td>
            </tr>
          ))}
          {!visits.length && <tr><td colSpan={7}>{t('noVisits')}</td></tr>}
        </tbody>
      </table>
      </div>
    </section>
  );

  const renderCameras = () => (
    <>
      <section className="live-grid">
        {boxes.map((box) => (
          <article className="panel camera-card" key={box.id}>
            <header>
              <div>
                <h3>{box.name}</h3>
                <span>{box.id}</span>
              </div>
              <span className="live-indicator"><i /> {t('livePreview')}</span>
            </header>
            <AuthenticatedImage
              url={`${API_BASE}/api/boxes/${encodeURIComponent(box.id)}/live-frame`}
              alt={`${box.name} · ${t('livePreview')}`}
              token={authToken}
              t={t}
              refreshMs={1500}
            />
            <p className="camera-current">
              {box.current_plate ? `${t('lastCar')}: ${box.current_plate}` : t('noVisitYet')}
            </p>
          </article>
        ))}
        {!boxes.length && <div className="panel">{t('noBoxes')}</div>}
      </section>

      <section className="panel detections-panel">
        <div className="section-heading">
          <div>
            <h3>{t('capturedImages')}</h3>
            <p>{t('selectedBox')}: {selectedBoxName}</p>
          </div>
          <span>{t('imagesExpire')}</span>
        </div>
        <div className="detection-list">
          {detections.map((detection) => (
            <DetectionReviewCard
              key={detection.id}
              detection={detection}
              token={authToken}
              language={language}
              t={t}
              onSave={handleCorrectPlate}
            />
          ))}
          {!detections.length && <p className="empty-state">{t('noCapturedImages')}</p>}
        </div>
      </section>
    </>
  );

  const renderBonus = () => (
    <section className="two-column">
      <div className="panel">
        <h3>{t('bonusOverview')}</h3>
        <ul className="simple-list">
          <li>{t('bonusAmount')}: {formatNumber(bonusAmount)} so‘m</li>
          <li>{t('perPress')}: {formatNumber(bonusPerPress)} so‘m</li>
          <li>{t('bonusFrequency')}: {formatNumber(bonusEveryVisits)} {t('visitsUnit')}</li>
          <li>{t('oneBonusRule')}</li>
          <li>{t('duplicateRule')}</li>
        </ul>
      </div>

      <div className="panel">
        <h3>{t('currentTotals')}</h3>
        <ul className="simple-list">
          <li>{t('totalPaid')}: {formatNumber(stats?.total_bonus_paid ?? 0)} so‘m</li>
          <li>{t('activeBonusCount')}: {formatNumber(stats?.active_bonus_count ?? 0)}</li>
          <li>{t('carsCount')}: {formatNumber(stats?.cars_count ?? 0)}</li>
          <li>{t('visitsCount')}: {formatNumber(stats?.visits_count ?? 0)}</li>
        </ul>
      </div>

      <div className="panel bonus-panel">
        <h3>{t('settings')}</h3>
        <div className="settings-grid">
          <label>
            {t('bonusAmount')}
            <input
              type="number"
              min="1000"
              step="1000"
              value={bonusAmount}
              onChange={(event) => setBonusAmount(Number(event.target.value || 1000))}
            />
          </label>
          <label>
            {t('perPress')}
            <input
              type="number"
              min="1000"
              max="100000"
              step="1000"
              value={bonusPerPress}
              onChange={(event) => setBonusPerPress(Number(event.target.value || 1000))}
            />
          </label>
          <label>
            {t('visitsBetweenBonuses')}
            <input
              type="number"
              min="1"
              step="1"
              value={bonusEveryVisits}
              onChange={(event) => setBonusEveryVisits(Number(event.target.value || 1))}
            />
          </label>
          <label>
            {t('pulsePolarity')}
            <select
              value={pulsePolarity}
              onChange={(event) => {
                if (event.target.value === 'HIGH' || event.target.value === 'LOW') {
                  setPulsePolarity(event.target.value);
                }
              }}
            >
              <option value="HIGH">{t('highActive')}</option>
              <option value="LOW">{t('lowActive')}</option>
            </select>
          </label>
          <label>
            {t('pulseFrequency')}
            <select
              value={pulseFrequencyMs}
              onChange={(event) => {
                const value = PULSE_FREQUENCIES_MS.find(
                  (frequency) => frequency === Number(event.target.value),
                );
                if (value) setPulseFrequencyMs(value);
              }}
            >
              {PULSE_FREQUENCIES_MS.map((frequency) => (
                <option key={frequency} value={frequency}>{frequency} ms</option>
              ))}
            </select>
          </label>
        </div>
        <p className="settings-hint">{t('periodHint')}</p>
        <p className="settings-hint">{t('perPressHint')}</p>
        <h4>{t('displayTextSettings')} · {selectedBoxName}</h4>
        <div className="settings-grid">
          <label>
            {t('displayIdleText')}
            <input
              maxLength={48}
              value={displayIdleText}
              onChange={(event) => setDisplayIdleText(event.target.value)}
            />
          </label>
          <label>
            {t('displayVisitLabel')}
            <input
              maxLength={16}
              value={displayVisitLabel}
              onChange={(event) => setDisplayVisitLabel(event.target.value)}
            />
          </label>
          <label>
            {t('displayRewardLabel')}
            <input
              maxLength={16}
              value={displayRewardLabel}
              onChange={(event) => setDisplayRewardLabel(event.target.value)}
            />
          </label>
          <label>
            {t('displayRemainingLabel')}
            <input
              maxLength={24}
              value={displayRemainingLabel}
              onChange={(event) => setDisplayRemainingLabel(event.target.value)}
            />
          </label>
          <label>
            {t('displayFinishedText')}
            <input
              maxLength={32}
              value={displayFinishedText}
              onChange={(event) => setDisplayFinishedText(event.target.value)}
            />
          </label>
          <label>
            {t('displayCurrencyLabel')}
            <input
              maxLength={12}
              value={displayCurrencyLabel}
              onChange={(event) => setDisplayCurrencyLabel(event.target.value)}
            />
          </label>
        </div>
        <p className="settings-hint">{t('displayAsciiHint')}</p>
        <button className="save-button" onClick={handleSaveSettings}>{t('save')}</button>
      </div>
      <div className="panel">
        <h3>{t('boxPulseTest')}: {selectedBoxName}</h3>
        {!boxTestActive ? (
          <button className="save-button" onClick={handleStartBoxTest}>{t('startTesting')}</button>
        ) : (
          <>
            <label className="test-amount-label">
              {t('testAmount')}
              <input
                type="number"
                min="1000"
                max="100000"
                step="1000"
                value={testBonusAmount}
                onChange={(event) => setTestBonusAmount(Number(event.target.value || 1000))}
              />
            </label>
            <p className="settings-hint">{t('testPulseHint')}</p>
            <p className="settings-hint">{t('queueHint')}</p>
            {pendingTestAmount !== null && (
              <p className="settings-hint">{t('queuedAmount')}: {formatNumber(pendingTestAmount)} so‘m</p>
            )}
            <div className="test-actions">
              <button
                className="save-button"
                onClick={handleSendTestBonus}
                disabled={pendingTestAmount !== null}
              >
                {t('sendTestBonus')}
              </button>
              <button className="save-button finish-test-button" onClick={handleFinishBoxTest}>
                {t('finishTesting')}
              </button>
            </div>
          </>
        )}
      </div>
      <div className="panel">
        <h3>{t('addWashBox')}</h3>
        <div className="settings-grid">
          <label>
            {t('boxId')}
            <input value={newBoxId} onChange={(event) => setNewBoxId(event.target.value)} placeholder="box-2" />
          </label>
          <label>
            {t('name')}
            <input value={newBoxName} onChange={(event) => setNewBoxName(event.target.value)} placeholder="Box 2" />
          </label>
        </div>
        <button className="save-button" onClick={handleCreateBox}>{t('addWashBox')}</button>
      </div>
    </section>
  );

  if (!authToken) {
    return (
      <main className="login-page">
        <form className="login-form" onSubmit={handleLogin}>
          <div className="login-preferences">
            <AppearanceControls
              language={language}
              theme={theme}
              onLanguageChange={setLanguage}
              onThemeToggle={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              t={t}
            />
          </div>
          <div className="login-brand">
            <div className="brand-mark">T</div>
            <div>
              <h1>Tomchi</h1>
              <p>{t('subtitle')}</p>
            </div>
          </div>
          <label>
            {t('username')}
            <input
              autoComplete="username"
              value={loginUsername}
              onChange={(event) => setLoginUsername(event.target.value)}
              required
            />
          </label>
          <label>
            {t('password')}
            <input
              type="password"
              autoComplete="current-password"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              required
            />
          </label>
          {loginError && <p role="alert">{loginError}</p>}
          <button type="submit" disabled={loginPending}>
            {loginPending ? t('signingIn') : t('signIn')}
          </button>
        </form>
      </main>
    );
  }

  return (
    <div className="page">
      {message && <div className="toast-message" role="status">{message}</div>}
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark">T</div>
          <div>
            <h1>Tomchi</h1>
            <p>{t('subtitle')}</p>
          </div>
        </div>
        <nav>
          {([
            ['dashboard', t('dashboard'), '⌂'],
            ['cars', t('cars'), '◉'],
            ['visits', t('visits'), '↻'],
            ['bonus', t('bonus'), '✦'],
            ['cameras', t('cameras'), '▣'],
          ] as const).map(([tab, label, icon]) => (
            <button
              key={tab}
              type="button"
              className={activeTab === tab ? 'active' : ''}
              aria-current={activeTab === tab ? 'page' : undefined}
              onClick={() => setActiveTab(tab)}
            >
              <span className="nav-icon" aria-hidden="true">{icon}</span>
              {label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div className="topbar-title">
            <p className="eyebrow">{t('subtitle')}</p>
            <h2>{t(pageTitleKeys[activeTab])}</h2>
            <p className="active-box-label">{t('selected')}: {selectedBoxName}</p>
          </div>
          <div className="topbar-actions">
            <label className="visually-hidden" htmlFor="box-select">{t('selectedBox')}</label>
            <select id="box-select" aria-label={t('selectedBox')} value={activeBoxId} onChange={(event) => setActiveBoxId(event.target.value)}>
              {boxes.map((box) => <option key={box.id} value={box.id}>{box.name} ({box.id})</option>)}
            </select>
            <div className={`status ${health?.ok ? 'online' : 'offline'}`}>
              {health?.ok ? t('backendOnline') : t('backendOffline')}
            </div>
            <AppearanceControls
              language={language}
              theme={theme}
              onLanguageChange={setLanguage}
              onThemeToggle={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              t={t}
            />
            <button className="logout-button" type="button" onClick={handleLogout}>{t('logOut')}</button>
          </div>
        </header>

        {activeTab === 'dashboard' && renderDashboard()}
        {activeTab === 'cars' && renderCars()}
        {activeTab === 'visits' && renderVisits()}
        {activeTab === 'bonus' && renderBonus()}
        {activeTab === 'cameras' && renderCameras()}
      </main>
      {selectedVisitPhoto && (
        <div className="visit-photo-overlay" onClick={() => setSelectedVisitPhoto(null)}>
          <section
            className="visit-photo-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="visit-photo-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h2 id="visit-photo-title">{t('visitImage')} · {selectedVisitPhoto.plate}</h2>
              <button
                type="button"
                className="visit-photo-close"
                aria-label={t('close')}
                onClick={() => setSelectedVisitPhoto(null)}
              >
                ×
              </button>
            </header>
            <AuthenticatedImage
              url={`${API_BASE}${selectedVisitPhoto.imageUrl}`}
              alt={`${t('visitImage')} ${selectedVisitPhoto.plate}`}
              token={authToken}
              t={t}
            />
          </section>
        </div>
      )}
    </div>
  );
}
