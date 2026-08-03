import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    const message = error?.message || '';

    // Auto-recover stale/missing lazy chunks once
    const isChunkError =
      message.includes('Loading chunk') ||
      message.includes('ChunkLoadError') ||
      message.includes("Unexpected token '<'");

    if (isChunkError) {
      const reloadKey = 'chunk-reload-attempted';
      const alreadyRetried = sessionStorage.getItem(reloadKey) === '1';

      if (!alreadyRetried) {
        sessionStorage.setItem(reloadKey, '1');
        window.location.reload();
        return;
      }
    }

    // Ignore translation-related errors
    if (message && (
      message.includes('removeChild') ||
      message.includes('Maximum call stack') ||
      message.includes('NotFoundError')
    )) {
      console.log('Translation error caught and ignored');
      this.setState({ hasError: false });
      return;
    }
    console.error('Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 20, textAlign: 'center' }}>
          <h2>Something went wrong</h2>
          <p style={{ color: '#666', marginBottom: 12 }}>
            حصل تعارض مؤقت في ملفات الصفحة. اضغط إعادة التحميل للمتابعة.
          </p>
          <button onClick={() => {
            try {
              sessionStorage.removeItem('chunk-reload-attempted');
            } catch (error) {
              console.warn('Unable to clear chunk reload flag', error);
            }
            window.location.reload();
          }}>Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
