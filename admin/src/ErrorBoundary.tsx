import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = { children: ReactNode };
type State = { error: Error | null };

/**
 * Kutilmagan xato butun panelni oq ekranga aylantirmasin:
 * foydalanuvchiga xabar va "qayta yuklash" tugmasini ko'rsatadi.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Admin panel crashed', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="login-page">
          <div className="login-card">
            <h1>Xatolik yuz berdi</h1>
            <p role="alert">Interfeys kutilmagan holatga tushdi. Sahifani qayta yuklang.</p>
            <p className="settings-hint">{this.state.error.message}</p>
            <button type="button" className="save-button" onClick={() => window.location.reload()}>
              Qayta yuklash
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
