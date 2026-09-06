import React, { useEffect, useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';

/**
 * Renders a protected file as an object URL.
 *
 * Authorization is carried by the httpOnly session cookie (credentials: 'include').
 * A token is NEVER placed in the URL, so this is safe for <img> rendering.
 * The object URL is always released on unmount or src change.
 */
export const AuthenticatedFileImage = ({ src, alt = 'file', className = '', testId }) => {
  const [objectUrl, setObjectUrl] = useState('');
  const [state, setState] = useState('loading');

  useEffect(() => {
    if (!src) {
      setState('error');
      return undefined;
    }

    let created = '';
    let cancelled = false;
    setState('loading');
    setObjectUrl('');

    (async () => {
      try {
        const response = await fetch(src, { credentials: 'include' });
        if (!response.ok) throw new Error(`file_fetch_failed_${response.status}`);
        const blob = await response.blob();
        if (cancelled) return;
        created = URL.createObjectURL(blob);
        setObjectUrl(created);
        setState('ready');
      } catch (error) {
        if (!cancelled) setState('error');
      }
    })();

    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [src]);

  if (state === 'loading') {
    return (
      <div
        className="w-full h-full flex items-center justify-center"
        data-testid={testId ? `${testId}-loading` : 'authenticated-file-loading'}
      >
        <Loader2 size={18} className="animate-spin opacity-60" />
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div
        className="w-full h-full flex items-center justify-center"
        title="تعذر تحميل الملف"
        data-testid={testId ? `${testId}-error` : 'authenticated-file-error'}
      >
        <AlertTriangle size={18} className="opacity-60" />
      </div>
    );
  }

  return (
    <img
      src={objectUrl}
      alt={alt}
      className={className}
      data-testid={testId || 'authenticated-file-image'}
    />
  );
};

export default AuthenticatedFileImage;
