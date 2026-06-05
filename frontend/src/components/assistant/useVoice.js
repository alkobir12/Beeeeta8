import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * 🎙️ useVoice — voice for كاترينا using the browser-native Web Speech API.
 *   • STT (microphone) via SpeechRecognition / webkitSpeechRecognition (lang ar-SA)
 *   • TTS (speaking) via speechSynthesis with an Arabic voice
 *
 * 100% browser-native: no API keys, no backend round-trip, real-time "live talk".
 * Gracefully no-ops where unsupported (exposes `supported` flags).
 */
export function useVoice({ lang = 'ar-SA' } = {}) {
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState('');
  const [supported, setSupported] = useState({ stt: false, tts: false });
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SR = (typeof window !== 'undefined') && (window.SpeechRecognition || window.webkitSpeechRecognition);
    const tts = (typeof window !== 'undefined') && ('speechSynthesis' in window);
    setSupported({ stt: !!SR, tts: !!tts });
    // Pre-warm voice list (some browsers populate async)
    try { window.speechSynthesis?.getVoices?.(); } catch (e) { /* noop */ }
    return () => {
      try { window.speechSynthesis?.cancel?.(); } catch (e) { /* noop */ }
      try { recognitionRef.current?.stop?.(); } catch (e) { /* noop */ }
    };
  }, []);

  const startListening = useCallback((onFinal) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return false;
    try {
      const rec = new SR();
      rec.lang = lang;
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;
      rec.onresult = (e) => {
        let finalT = '';
        let interimT = '';
        for (let i = e.resultIndex; i < e.results.length; i += 1) {
          const t = e.results[i][0].transcript;
          if (e.results[i].isFinal) finalT += t; else interimT += t;
        }
        setInterim(interimT);
        if (finalT && onFinal) onFinal(finalT.trim());
      };
      rec.onend = () => { setListening(false); setInterim(''); };
      rec.onerror = () => { setListening(false); setInterim(''); };
      recognitionRef.current = rec;
      rec.start();
      setListening(true);
      return true;
    } catch (e) {
      setListening(false);
      return false;
    }
  }, [lang]);

  const stopListening = useCallback(() => {
    try { recognitionRef.current?.stop?.(); } catch (e) { /* noop */ }
    setListening(false);
  }, []);

  const _pickArabicVoice = () => {
    try {
      const voices = window.speechSynthesis.getVoices() || [];
      return voices.find((v) => (v.lang || '').toLowerCase().startsWith('ar')) || null;
    } catch (e) { return null; }
  };

  const speak = useCallback((text) => {
    if (!('speechSynthesis' in window) || !text) return;
    try {
      window.speechSynthesis.cancel();
      // Strip markdown / table pipes / emojis so speech sounds natural.
      const clean = String(text)
        .replace(/```[\s\S]*?```/g, ' ')
        .replace(/[#*_`>|~]/g, ' ')
        .replace(/\[(.*?)\]\(.*?\)/g, '$1')
        .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 700);
      if (!clean) return;
      const u = new SpeechSynthesisUtterance(clean);
      u.lang = lang;
      const v = _pickArabicVoice();
      if (v) u.voice = v;
      u.rate = 1.0;
      u.pitch = 1.0;
      u.onstart = () => setSpeaking(true);
      u.onend = () => setSpeaking(false);
      u.onerror = () => setSpeaking(false);
      window.speechSynthesis.speak(u);
    } catch (e) {
      setSpeaking(false);
    }
  }, [lang]);

  const stopSpeaking = useCallback(() => {
    try { window.speechSynthesis.cancel(); } catch (e) { /* noop */ }
    setSpeaking(false);
  }, []);

  return { listening, speaking, interim, supported, startListening, stopListening, speak, stopSpeaking };
}

export default useVoice;
