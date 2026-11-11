import { useEffect, useState } from 'react';

type TabKey = 'dashboard' | 'cars' | 'visits' | 'bonus' | 'cameras';

type Stats = {
  cars_count: number;
  visits_count: number;
  total_bonus_paid: number;
  active_bonus_count: number;
};

type VisitRow = {
  id: number;
  plate: string;
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
  status: string;
  frame_index: number;
  frame_count: number;
  created_at: string;
  image_url: string;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? `http://${window.location.hostname}:8000`;
const DEVICE_KEY = import.meta.env.VITE_DEVICE_KEY ?? 'TOMCHI_DEMO_KEY';

function AuthenticatedImage({
  url,
  alt,
  refreshMs = 0,
}: {
  url: string;
  alt: string;
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
        const response = await fetch(url, { headers: { 'X-Device-Key': DEVICE_KEY } });
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
  }, [url, refreshMs]);

  if (!source) {
    return <div className="image-placeholder">{failed ? (refreshMs > 0 ? 'Camera offline' : 'Image unavailable') : 'Loading image…'}</div>;
  }
  return (
    <div className="image-wrap">
      <img className={refreshMs > 0 ? 'live-preview' : 'detection-image'} src={source} alt={alt} />
      {failed && refreshMs > 0 && <span className="image-offline">Connection lost · showing last frame</span>}
    </div>
  );
}

function DetectionReviewCard({
  detection,
  onSave,
}: {
  detection: DetectionRow;
  onSave: (id: number, plate: string) => Promise<void>;
}) {
  const [plate, setPlate] = useState(detection.plate ?? '');
  const [saving, setSaving] = useState(false);

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
        alt={`Detection ${detection.id}`}
      />
      <div className="detection-details">
        <div className="detection-meta">
          <strong>{detection.box_id}</strong>
          <time>{new Date(detection.created_at).toLocaleString()}</time>
        </div>
        <label>
          Plate number
          <input
            value={plate}
            disabled={detection.status === 'confirmed'}
            onChange={(event) => setPlate(event.target.value.toUpperCase())}
            placeholder="01A123BC"
          />
        </label>
        {detection.status === 'confirmed' ? (
          <span className="confirmed-status">Visit registered: {detection.plate}</span>
        ) : (
          <button className="save-button" onClick={submit} disabled={!plate.trim() || saving}>
            {saving ? 'Saving…' : 'Correct plate and register visit'}
          </button>
        )}
      </div>
    </article>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');
  const [stats, setStats] = useState<Stats | null>(null);
  const [visits, setVisits] = useState<VisitRow[]>([]);
  const [cars, setCars] = useState<CarRow[]>([]);
  const [boxes, setBoxes] = useState<BoxRow[]>([]);
  const [detections, setDetections] = useState<DetectionRow[]>([]);
  const [activeBoxId, setActiveBoxId] = useState('box-1');
  const [health, setHealth] = useState<{ ok: boolean; service?: string; bonus_amount?: number; bonus_per_press?: number } | null>(null);
  const [plate, setPlate] = useState('01A123BC');
  const [message, setMessage] = useState('');
  const [editingVisitId, setEditingVisitId] = useState<number | null>(null);
  const [editingVisitPlate, setEditingVisitPlate] = useState('');
  const [bonusAmount, setBonusAmount] = useState<number>(20000);
  const [bonusPerPress, setBonusPerPress] = useState<number>(5000);
  const [bonusEveryVisits, setBonusEveryVisits] = useState<number>(10);
  const [newBoxId, setNewBoxId] = useState('');
  const [newBoxName, setNewBoxName] = useState('');

  const loadData = async () => {
    try {
      const [statsRes, visitsRes, carsRes, healthRes, boxesRes] = await Promise.all([
        fetch(`${API_BASE}/api/stats`),
        fetch(`${API_BASE}/api/visits?limit=10&box_id=${encodeURIComponent(activeBoxId)}`),
        fetch(`${API_BASE}/api/cars?limit=10`),
        fetch(`${API_BASE}/health`),
        fetch(`${API_BASE}/api/boxes`),
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
    loadData();
    const id = window.setInterval(loadData, 10000);
    return () => window.clearInterval(id);
  }, [activeBoxId]);

  useEffect(() => {
    if (activeTab !== 'cameras') return;
    let active = true;
    const loadDetections = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/detections?limit=30&box_id=${encodeURIComponent(activeBoxId)}`,
          { headers: { 'X-Device-Key': DEVICE_KEY } },
        );
        if (!response.ok) throw new Error(`Detections load failed: ${response.status}`);
        const data: DetectionRow[] = await response.json();
        if (active) setDetections(data);
      } catch (error) {
        if (active) setMessage(error instanceof Error ? error.message : 'Could not load camera detections');
      }
    };

    loadDetections();
    const timer = window.setInterval(loadDetections, 10000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeTab, activeBoxId]);

  useEffect(() => {
    fetch(`${API_BASE}/api/settings`, { headers: { 'X-Device-Key': DEVICE_KEY } })
      .then(async (res) => {
        if (!res.ok) throw new Error('Settings load failed');
        return res.json();
      })
      .then((data) => {
        setBonusAmount(data.bonus_amount);
        setBonusPerPress(data.bonus_per_press);
        setBonusEveryVisits(data.bonus_every_visits);
      })
      .catch((error) => console.error(error));
  }, []);

  useEffect(() => {
    if (!message) return;
    const timeout = window.setTimeout(() => setMessage(''), 4000);
    return () => window.clearTimeout(timeout);
  }, [message]);

  const handleDetect = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/detect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-Key': DEVICE_KEY,
          'X-Box-Id': activeBoxId,
        },
        body: JSON.stringify({ plate }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? 'Detection request failed');
      }

      setMessage(`Detection accepted: ${data.plate} / visit #${data.visit_no}`);
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unexpected error');
    }
  };

  const handleSaveVisitPlate = async (visitId: number) => {
    try {
      const response = await fetch(`${API_BASE}/api/visits/${visitId}/plate`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-Key': DEVICE_KEY,
        },
        body: JSON.stringify({ plate: editingVisitPlate }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Plate update failed');
      setEditingVisitId(null);
      setEditingVisitPlate('');
      setMessage(`Visit #${visitId} plate updated to ${data.plate}`);
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unexpected error');
    }
  };

  const handleSaveSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-Key': DEVICE_KEY,
        },
        body: JSON.stringify({
          bonus_amount: bonusAmount,
          bonus_per_press: bonusPerPress,
          bonus_every_visits: bonusEveryVisits,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? 'Settings update failed');
      }

      setMessage(`Saved: ${data.bonus_amount} so'm every ${data.bonus_every_visits} visits; ${data.bonus_per_press} so'm per press`);
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unexpected error');
    }
  };

  const handleCreateBox = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/boxes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-Key': DEVICE_KEY },
        body: JSON.stringify({ id: newBoxId, name: newBoxName }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? 'Box creation failed');
      setNewBoxId('');
      setNewBoxName('');
      setMessage(`Box created: ${data.name} (${data.id})`);
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unexpected error');
    }
  };

  const handleCorrectPlate = async (detectionId: number, correctedPlate: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/detections/${detectionId}/plate`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-Key': DEVICE_KEY,
        },
        body: JSON.stringify({ plate: correctedPlate }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Could not save corrected plate');
      setMessage(`Plate ${data.plate} saved; visit #${data.visit_no} registered`);
      const refreshed = await fetch(
        `${API_BASE}/api/detections?limit=30&box_id=${encodeURIComponent(activeBoxId)}`,
        { headers: { 'X-Device-Key': DEVICE_KEY } },
      );
      if (refreshed.ok) setDetections(await refreshed.json());
      await loadData();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unexpected error';
      setMessage(errorMessage);
    }
  };

  const renderDashboard = () => (
    <>
      <section className="cards">
        <div className="card">
          <label>Cars</label>
          <strong>{stats?.cars_count ?? 0}</strong>
        </div>
        <div className="card">
          <label>Visits</label>
          <strong>{stats?.visits_count ?? 0}</strong>
        </div>
        <div className="card">
          <label>Bonus paid</label>
          <strong>{stats ? `${stats.total_bonus_paid.toLocaleString()} so'm` : "0 so'm"}</strong>
        </div>
        <div className="card">
          <label>Active bonus</label>
          <strong>{stats?.active_bonus_count ?? 0}</strong>
        </div>
      </section>

      <section className="split-layout">
        <div className="panel">
          <h3>Manual detection</h3>
          <div className="inline-form">
            <input
              value={plate}
              onChange={(event) => setPlate(event.target.value.toUpperCase())}
              placeholder="01A123BC"
            />
            <button onClick={handleDetect}>Detect</button>
          </div>
        </div>

        <div className="panel">
          <h3>System status</h3>
          <ul className="simple-list">
            <li>ANPR/OCR not connected</li>
            <li>24h duplicate-check active</li>
            <li>Bonus every {bonusEveryVisits} visits</li>
            <li>Device key validation enabled</li>
          </ul>
        </div>
      </section>
    </>
  );

  const renderCars = () => (
    <section className="panel">
      <h3>Cars</h3>
      <table>
        <thead>
          <tr>
            <th>Plate</th>
            <th>Visits</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {cars.map((car) => (
            <tr key={car.id}>
              <td>{car.plate}</td>
              <td>{car.visit_count}</td>
              <td>{new Date(car.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );

  const renderVisits = () => (
    <section className="panel">
      <h3>Visits</h3>
      <p className="settings-hint">Raqamni tahrirlash faqat tanlangan kelishga ta’sir qiladi; Cars bo‘limi o‘zgarmaydi.</p>
      <table>
        <thead>
          <tr>
            <th>Plate</th>
            <th>Visit</th>
            <th>Bonus left</th>
            <th>Status</th>
            <th>Actions</th>
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
                    placeholder="01A123BC"
                    aria-label={`Visit ${visit.id} plate`}
                  />
                ) : visit.plate}
              </td>
              <td>{visit.visit_no}</td>
              <td>{visit.bonus_left}</td>
              <td>{visit.is_active_bonus ? 'Active' : 'Idle'}</td>
              <td className="table-actions">
                {editingVisitId === visit.id ? (
                  <>
                    <button className="table-action primary-action" onClick={() => handleSaveVisitPlate(visit.id)}>
                      Save
                    </button>
                    <button
                      className="table-action"
                      onClick={() => {
                        setEditingVisitId(null);
                        setEditingVisitPlate('');
                      }}
                    >
                      Cancel
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
                    Edit plate
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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
              <span className="live-indicator"><i /> Live preview</span>
            </header>
            <AuthenticatedImage
              url={`${API_BASE}/api/boxes/${encodeURIComponent(box.id)}/live-frame`}
              alt={`${box.name} live camera`}
              refreshMs={1500}
            />
            <p className="camera-current">
              {box.current_plate ? `Last car: ${box.current_plate}` : 'No car visit registered yet'}
            </p>
          </article>
        ))}
        {!boxes.length && <div className="panel">No boxes configured.</div>}
      </section>

      <section className="panel detections-panel">
        <div className="section-heading">
          <div>
            <h3>Captured plate images</h3>
            <p>Selected box: {boxes.find((box) => box.id === activeBoxId)?.name ?? activeBoxId}</p>
          </div>
          <span>Images expire after 30 days</span>
        </div>
        <div className="detection-list">
          {detections.map((detection) => (
            <DetectionReviewCard
              key={detection.id}
              detection={detection}
              onSave={handleCorrectPlate}
            />
          ))}
          {!detections.length && <p className="empty-state">No captured plate images for this box yet.</p>}
        </div>
      </section>
    </>
  );

  const renderBonus = () => (
    <section className="two-column">
      <div className="panel">
        <h3>Bonus overview</h3>
        <ul className="simple-list">
          <li>Bonus amount: {bonusAmount.toLocaleString()} so'm</li>
          <li>Per press: {bonusPerPress.toLocaleString()} so'm</li>
          <li>Bonus frequency: every {bonusEveryVisits} visits</li>
          <li>Only one bonus is active across the wash; a new visit at any box cancels the previous remainder</li>
        </ul>
      </div>

      <div className="panel">
        <h3>Current totals</h3>
        <ul className="simple-list">
          <li>Total paid: {stats ? `${stats.total_bonus_paid.toLocaleString()} so'm` : "0 so'm"}</li>
          <li>Active bonus count: {stats?.active_bonus_count ?? 0}</li>
          <li>Cars: {stats?.cars_count ?? 0}</li>
          <li>Visits: {stats?.visits_count ?? 0}</li>
        </ul>
      </div>

      <div className="panel bonus-panel">
        <h3>Bonus settings</h3>
        <div className="settings-grid">
          <label>
            Bonus amount
            <input
              type="number"
              min="1000"
              step="1000"
              value={bonusAmount}
              onChange={(event) => setBonusAmount(Number(event.target.value || 1000))}
            />
          </label>
          <label>
            Bonus per press
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
            Visits between bonuses
            <input
              type="number"
              min="1"
              step="1"
              value={bonusEveryVisits}
              onChange={(event) => setBonusEveryVisits(Number(event.target.value || 1))}
            />
          </label>
        </div>
        <p className="settings-hint">Miqdorlar 1 000 so'mlik qadamda bo'ladi; per-press qiymati impulslar sonini belgilaydi.</p>
        <button className="save-button" onClick={handleSaveSettings}>Save settings</button>
      </div>
      <div className="panel">
        <h3>Add wash box</h3>
        <div className="settings-grid">
          <label>
            Box ID
            <input value={newBoxId} onChange={(event) => setNewBoxId(event.target.value)} placeholder="box-2" />
          </label>
          <label>
            Name
            <input value={newBoxName} onChange={(event) => setNewBoxName(event.target.value)} placeholder="Box 2" />
          </label>
        </div>
        <button className="save-button" onClick={handleCreateBox}>Add box</button>
      </div>
    </section>
  );

  return (
    <div className="page">
      {message && <div className="toast-message" role="status">{message}</div>}
      <aside className="sidebar">
        <h1>Tomchi</h1>
        <nav>
          <span className={activeTab === 'dashboard' ? 'active' : ''} onClick={() => setActiveTab('dashboard')}>
            Dashboard
          </span>
          <span className={activeTab === 'cars' ? 'active' : ''} onClick={() => setActiveTab('cars')}>
            Cars
          </span>
          <span className={activeTab === 'visits' ? 'active' : ''} onClick={() => setActiveTab('visits')}>
            Visits
          </span>
          <span className={activeTab === 'bonus' ? 'active' : ''} onClick={() => setActiveTab('bonus')}>
            Bonus
          </span>
          <span className={activeTab === 'cameras' ? 'active' : ''} onClick={() => setActiveTab('cameras')}>
            Cameras
          </span>
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Moyka bonus tizimi</p>
            <h2>{activeTab === 'dashboard' ? 'Admin panel' : activeTab === 'cars' ? 'Cars' : activeTab === 'visits' ? 'Visits' : activeTab === 'bonus' ? 'Bonus' : 'Cameras'}</h2>
            <p className="active-box-label">Tanlangan: {boxes.find((box) => box.id === activeBoxId)?.name ?? activeBoxId}</p>
          </div>
          <div className="topbar-actions">
            <select aria-label="Current wash box" value={activeBoxId} onChange={(event) => setActiveBoxId(event.target.value)}>
              {boxes.map((box) => <option key={box.id} value={box.id}>{box.name} ({box.id})</option>)}
            </select>
            <div className={`status ${health?.ok ? 'online' : 'offline'}`}>
              {health?.ok ? 'Backend online' : 'Backend offline'}
            </div>
          </div>
        </header>

        {activeTab === 'dashboard' && renderDashboard()}
        {activeTab === 'cars' && renderCars()}
        {activeTab === 'visits' && renderVisits()}
        {activeTab === 'bonus' && renderBonus()}
        {activeTab === 'cameras' && renderCameras()}
      </main>
    </div>
  );
}
