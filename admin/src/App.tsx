import { useEffect, useState } from 'react';

type TabKey = 'dashboard' | 'cars' | 'visits' | 'bonus';

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

const API_BASE = import.meta.env.VITE_API_BASE ?? `http://${window.location.hostname}:8000`;
const DEVICE_KEY = import.meta.env.VITE_DEVICE_KEY ?? 'TOMCHI_DEMO_KEY';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');
  const [stats, setStats] = useState<Stats | null>(null);
  const [visits, setVisits] = useState<VisitRow[]>([]);
  const [cars, setCars] = useState<CarRow[]>([]);
  const [boxes, setBoxes] = useState<BoxRow[]>([]);
  const [activeBoxId, setActiveBoxId] = useState('box-1');
  const [health, setHealth] = useState<{ ok: boolean; service?: string; bonus_amount?: number; bonus_per_press?: number } | null>(null);
  const [plate, setPlate] = useState('01A123BC');
  const [message, setMessage] = useState('');
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
          {message && <p className="message">{message}</p>}
        </div>

        <div className="panel">
          <h3>System status</h3>
          <ul className="simple-list">
            <li>ANPR mock active</li>
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
      <table>
        <thead>
          <tr>
            <th>Plate</th>
            <th>Visit</th>
            <th>Bonus left</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {visits.map((visit) => (
            <tr key={visit.id}>
              <td>{visit.plate}</td>
              <td>{visit.visit_no}</td>
              <td>{visit.bonus_left}</td>
              <td>{visit.is_active_bonus ? 'Active' : 'Idle'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
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
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Moyka bonus tizimi</p>
            <h2>{activeTab === 'dashboard' ? 'Admin panel' : activeTab === 'cars' ? 'Cars' : activeTab === 'visits' ? 'Visits' : 'Bonus'}</h2>
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
      </main>
    </div>
  );
}
