import React, { useEffect, useState } from 'react';
import { Search, BookOpen, FileText, Upload, History, Zap, Database, Filter, GitCompare, X } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import axios from 'axios';
import { resolveBackendBase } from '../utils/backendBase';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

const KnowledgeBase = () => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [dtcCards, setDtcCards] = useState([]);
  const [searchMode, setSearchMode] = useState('smart'); // smart, dtc
  const [activeTab, setActiveTab] = useState('search');
  const [showHistory, setShowHistory] = useState(false);
  const [historyItems, setHistoryItems] = useState([]);

  useEffect(() => {
    // Initial load if needed
  }, []);

  const fetchHistory = async () => {
    try {
      const r = await axios.get(`${API_URL}/search/history`);
      setHistoryItems(r.data?.items || []);
    } catch (e) { setHistoryItems([]); }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      toast({ title: 'تنبيه', description: 'الرجاء إدخال كلمة للبحث', variant: 'default' });
      return;
    }

    try {
      setLoading(true);
      const dtcPattern = /^[PCUB][0-9A-F]{4}$/i;
      const isDTCSearch = dtcPattern.test(searchQuery.trim());
      
      if (isDTCSearch || searchMode === 'dtc') {
        const res = await axios.post(`${API_URL}/ai/kb/extract-dtc-cards`, { query: searchQuery.trim() });
        setDtcCards(res.data?.cards || []);
        setSearchResults([]);
        toast({ title: 'تم البحث', description: `تم العثور على ${res.data?.cards?.length || 0} بطاقة عطل` });
      } else {
        const res = await axios.post(`${API_URL}/ai/kb/smart-search`, { query: searchQuery, limit: 20 });
        setSearchResults(res.data?.results || []);
        setDtcCards([]);
        toast({ title: 'تم البحث', description: `تم العثور على ${res.data?.results?.length || 0} نتيجة` });
      }
    } catch (e) {
      console.error('Search error:', e);
      toast({ title: 'خطأ', description: 'حدث خطأ أثناء البحث', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    
      <div className="max-w-5xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-4 py-8">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl mx-auto flex items-center justify-center text-white shadow-lg shadow-blue-500/30">
            <Database size={32} />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">قاعدة المعرفة الذكية</h1>
          <p className="text-gray-500 text-lg max-w-2xl mx-auto">
            ابحث في آلاف المستندات، أكواد الأعطال، والمخططات الفنية باستخدام الذكاء الاصطناعي
          </p>
        </div>

        {/* Search Box */}
        <div className="max-w-3xl mx-auto">
          <div className="relative group">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl blur opacity-20 group-hover:opacity-30 transition-opacity"></div>
            <div className="relative bg-white rounded-2xl shadow-xl p-2 flex items-center gap-2 border border-gray-100">
              <div className="pl-3 pr-4 text-gray-400">
                <Search size={24} />
              </div>
              <input 
                className="flex-1 h-12 text-lg outline-none bg-transparent placeholder:text-gray-400"
                placeholder="ابحث عن كود عطل (P0300)، مشكلة ميكانيكية، أو استفسار فني..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                autoFocus
              />
              <button 
                onClick={handleSearch}
                disabled={loading}
                className="bg-[#0071E3] hover:bg-[#0077ED] text-white px-6 h-10 rounded-xl font-medium transition-all active:scale-95 disabled:opacity-50 disabled:scale-100"
              >
                {loading ? 'جاري البحث...' : 'بحث'}
              </button>
            </div>
          </div>

          {/* Search Options */}
          <div className="flex justify-center gap-4 mt-4">
            <label className={`cursor-pointer px-4 py-2 rounded-full text-sm font-medium transition-all ${searchMode === 'smart' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              <input type="radio" className="hidden" checked={searchMode === 'smart'} onChange={() => setSearchMode('smart')} />
              بحث ذكي
            </label>
            <label className={`cursor-pointer px-4 py-2 rounded-full text-sm font-medium transition-all ${searchMode === 'dtc' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              <input type="radio" className="hidden" checked={searchMode === 'dtc'} onChange={() => setSearchMode('dtc')} />
              بحث أكواد (DTC)
            </label>
            <button 
              onClick={() => { setShowHistory(true); fetchHistory(); }}
              className="px-4 py-2 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-all flex items-center gap-2"
            >
              <History size={14} />
              سجل البحث
            </button>
          </div>
        </div>

        {/* Results Area */}
        <div className="space-y-6">
          {/* DTC Cards */}
          {dtcCards.length > 0 && (
            <div className="grid gap-6">
              <div className="flex items-center gap-2 text-amber-600 bg-amber-50 px-4 py-2 rounded-lg w-fit mx-auto">
                <Zap size={18} />
                <span className="font-medium">تم العثور على {dtcCards.length} بطاقة تشخيص</span>
              </div>
              
              {dtcCards.map((card, idx) => (
                <div key={card?.code ?? card?.id ?? `dtc-${idx}`} className="apple-card overflow-hidden border-l-4 border-l-amber-500">
                  <div className="p-6">
                    <div className="flex items-start justify-between mb-6">
                      <div>
                        <div className="flex items-center gap-3 mb-2">
                          <h2 className="text-3xl font-bold text-gray-900">{card.code}</h2>
                          <span className="px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-bold">DTC</span>
                        </div>
                        <p className="text-gray-600 text-lg">{card.description}</p>
                      </div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <div className="bg-red-50 rounded-xl p-4">
                          <h3 className="font-bold text-red-700 mb-2 text-sm">الأسباب المحتملة</h3>
                          <p className="text-gray-700 text-sm leading-relaxed">{card.causes}</p>
                        </div>
                        <div className="bg-orange-50 rounded-xl p-4">
                          <h3 className="font-bold text-orange-700 mb-2 text-sm">الأعراض</h3>
                          <p className="text-gray-700 text-sm leading-relaxed">{card.symptoms}</p>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div className="bg-green-50 rounded-xl p-4">
                          <h3 className="font-bold text-green-700 mb-2 text-sm">الحلول المقترحة</h3>
                          <p className="text-gray-700 text-sm leading-relaxed">{card.fixes}</p>
                        </div>
                        
                        {/* Electrical Values */}
                        <div className="bg-blue-50 rounded-xl p-4">
                          <h3 className="font-bold text-blue-700 mb-3 text-sm flex items-center gap-2">
                            <Zap size={14} /> القيم الكهربائية
                          </h3>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="bg-white/60 p-2 rounded-lg">
                              <span className="text-xs text-gray-500 block">البطارية</span>
                              <span className="font-mono font-bold text-blue-600">12.6V</span>
                            </div>
                            <div className="bg-white/60 p-2 rounded-lg">
                              <span className="text-xs text-gray-500 block">الدينمو</span>
                              <span className="font-mono font-bold text-blue-600">13.8-14.4V</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Smart Search Results */}
          {searchResults.length > 0 && (
            <div className="grid gap-4">
              <div className="flex items-center gap-2 text-gray-500 px-4">
                <Filter size={16} />
                <span className="text-sm">نتائج البحث ({searchResults.length})</span>
              </div>
              
              {searchResults.map((result, idx) => (
                <div key={result?.id ?? result?.title ?? `sr-${idx}`} className="apple-card p-5 hover:shadow-md transition-all cursor-pointer group">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center text-gray-400 group-hover:bg-blue-50 group-hover:text-blue-600 transition-colors shrink-0">
                      <FileText size={20} />
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-900 mb-1 group-hover:text-blue-600 transition-colors">
                        {result.title || 'مستند فني'}
                      </h3>
                      <p className="text-gray-600 text-sm leading-relaxed line-clamp-2">
                        {result.excerpt || result.summary || result.text || ''}
                      </p>
                      <div className="flex gap-2 mt-3">
                        {result.score && (
                          <span className="text-xs px-2 py-1 rounded-md bg-gray-100 text-gray-600">
                            تطابق: {Math.round(result.score * 100)}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* History Modal */}
        {showHistory && (
          <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 flex justify-end">
            <div className="w-full max-w-md bg-white h-full shadow-2xl p-6 overflow-y-auto animate-in slide-in-from-right">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-gray-900">سجل البحث</h2>
                <button onClick={() => setShowHistory(false)} className="p-2 hover:bg-gray-100 rounded-full">
                  <X size={20} />
                </button>
              </div>
              
              <div className="space-y-3">
                {historyItems.map((item, idx) => (
                  <div key={item?.id ?? item?.createdAt ?? `hist-${idx}`} className="p-4 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer" onClick={() => { setSearchQuery(item.query); setShowHistory(false); handleSearch(); }}>
                    <div className="flex justify-between items-start mb-1">
                      <span className="font-medium text-gray-900">{item.query}</span>
                      <span className="text-xs text-gray-400">{new Date(item.createdAt).toLocaleDateString('ar-SA')}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <span className={`w-2 h-2 rounded-full ${item.ok ? 'bg-green-500' : 'bg-red-500'}`}></span>
                      <span>{item.count} نتيجة</span>
                    </div>
                  </div>
                ))}
                {historyItems.length === 0 && (
                  <div className="text-center py-10 text-gray-500">
                    <History size={32} className="mx-auto mb-2 opacity-50" />
                    <p>لا يوجد سجل بحث</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    
  );
};

export default KnowledgeBase;