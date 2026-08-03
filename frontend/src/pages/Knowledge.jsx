import React, { useEffect, useRef, useState } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { useToast } from '../hooks/use-toast';
import { resolveBackendBase } from '../utils/backendBase';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

const chunkSize = 5 * 1024 * 1024; // 5MB per chunk

const Knowledge = () => {
  const { toast } = useToast();
  const [active, setActive] = useState('docs');

  // Docs state
  const [docTitle, setDocTitle] = useState('');
  const [docTags, setDocTags] = useState('');
  const [docContent, setDocContent] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [docs, setDocs] = useState([]);

  // Electrical ingest/search/qa
  const [elecTitle, setElecTitle] = useState('');
  const [elecTags, setElecTags] = useState('electrical');
  const [elecContent, setElecContent] = useState('');
  const [elecQuery, setElecQuery] = useState('');
  const [elecResults, setElecResults] = useState([]);
  const [qaQuestion, setQaQuestion] = useState('');
  const [qaAnswer, setQaAnswer] = useState('');

  // Media upload
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [media, setMedia] = useState([]);
  const abortRef = useRef({ aborted: false });

  const fetchDocs = async () => {
    try {
      const res = await fetch(`${API_URL}/ai/kb/search-docs?query=${encodeURIComponent(searchQuery || '')}`);
      const data = await res.json();
      setDocs(data.results || []);
    } catch (e) {
      console.warn('فشل تحميل مستندات المعرفة', e);
    }
  };

  const fetchMedia = async () => {
    try {
      const res = await fetch(`${API_URL}/media/list`);
      const data = await res.json();
      setMedia(data.items || []);
    } catch (e) {
      console.warn('فشل تحميل الوسائط', e);
    }
  };

  useEffect(() => { fetchDocs(); }, []);
  useEffect(() => { if (active === 'media') fetchMedia(); }, [active]);

  const addDoc = async () => {
    try {
      const payload = {
        title: docTitle || 'مستند معرفي',
        content: docContent,
        tags: (docTags || '').split(',').map(s => s.trim()).filter(Boolean)
      };
      const res = await fetch(`${API_URL}/ai/kb/docs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error('failed');
      toast({ title: 'تم الحفظ', description: 'تمت إضافة المستند إلى قاعدة المعرفة' });
      setDocTitle(''); setDocTags(''); setDocContent('');
      fetchDocs();
    } catch (e) {
      toast({ title: 'خطأ', description: 'تعذر حفظ المستند', variant: 'destructive' });
    }
  };

  const doElecIngest = async () => {
    if (!elecContent.trim()) {
      toast({ title: 'مطلوب محتوى', description: 'الرجاء لصق نص مرجعي كهربائي', variant: 'destructive' });
      return;
    }
    try {
      const payload = { title: elecTitle || 'معرفة كهربائية', content: elecContent, tags: (elecTags||'').split(',').map(s=>s.trim()).filter(Boolean) };
      const res = await fetch(`${API_URL}/ai/kb/electrical/ingest`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      if (!res.ok) throw new Error('ingest failed');
      toast({ title: 'تم الاستخراج', description: 'تم تنظيم المعرفة الكهربائية' });
      setElecTitle(''); setElecContent('');
    } catch (e) {
      toast({ title: 'خطأ', description: 'تعذر تنظيم المعرفة الكهربائية', variant: 'destructive' });
    }
  };

  const doElecSearch = async () => {
    try {
      const res = await fetch(`${API_URL}/ai/kb/electrical/search?query=${encodeURIComponent(elecQuery)}`);
      const data = await res.json();
      setElecResults(data.results || []);
    } catch (e) {
      console.warn('فشل بحث المعرفة الكهربائية', e);
    }
  };

  const doElecQA = async () => {
    try {
      const res = await fetch(`${API_URL}/ai/electrical/qa`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ message: qaQuestion }) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'failed');
      setQaAnswer(data.response || '');
    } catch (e) {
      setQaAnswer('تعذر الحصول على إجابة ذكية. تأكد من تفعيل مفتاح LLM في البيئة.');
    }
  };

  const uploadVideo = async () => {
    if (!file) return;
    try {
      const initRes = await fetch(`${API_URL}/media/upload/init`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ filename: file.name, size: file.size, mimeType: file.type }) });
      if (!initRes.ok) throw new Error('init failed');
      const { uploadId } = await initRes.json();
      const totalChunks = Math.ceil(file.size / chunkSize);
      let offset = 0;
      abortRef.current.aborted = false;
      for (let index = 0; index < totalChunks; index++) {
        if (abortRef.current.aborted) throw new Error('aborted');
        const slice = file.slice(offset, offset + chunkSize);
        const form = new FormData();
        form.append('uploadId', uploadId);
        form.append('index', String(index));
        form.append('chunk', slice);
        const res = await fetch(`${API_URL}/media/upload/chunk`, { method:'POST', body: form });
        if (!res.ok) throw new Error('chunk failed');
        offset += chunkSize;
        setUploadProgress(Math.round(((index+1)/totalChunks)*100));
      }
      const compRes = await fetch(`${API_URL}/media/upload/complete`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ uploadId, totalChunks }) });
      if (!compRes.ok) throw new Error('complete failed');
      toast({ title: 'تم الرفع', description: 'تم رفع الفيديو واستخراج الصوت وإضافته للمعرفة' });
      setFile(null); setUploadProgress(0);
      fetchMedia();
    } catch (e) {
      toast({ title: 'خطأ', description: 'تعذر رفع الفيديو', variant: 'destructive' });
    }
  };

  return (
    <Layout>
      <div className="min-h-screen" dir="rtl">
        <div className="container mx-auto p-6 max-w-6xl">
          <h1 className="text-3xl font-bold text-slate-800 mb-6">إدارة المعرفة</h1>

          <Tabs value={active} onValueChange={setActive}>
            <TabsList className="grid grid-cols-4 mb-4">
              <TabsTrigger value="docs">مستندات عامة</TabsTrigger>
              <TabsTrigger value="electrical">المعرفة الكهربائية</TabsTrigger>
              <TabsTrigger value="media">فيديو وصوت</TabsTrigger>
              <TabsTrigger value="import">استيراد جماعي</TabsTrigger>
            </TabsList>

            <TabsContent value="docs">
              <Card className="mb-6">
                <CardHeader><CardTitle>إضافة مستند</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <Label>العنوان</Label>
                      <Input value={docTitle} onChange={e=>setDocTitle(e.target.value)} placeholder="عنوان المستند" />
                    </div>
                    <div>
                      <Label>وسوم (مفصولة بفواصل)</Label>
                      <Input value={docTags} onChange={e=>setDocTags(e.target.value)} placeholder="toyota, diesel, denso" />
                    </div>
                  </div>
                  <div>
                    <Label>المحتوى</Label>
                    <Textarea rows={10} value={docContent} onChange={e=>setDocContent(e.target.value)} placeholder="ألصق هنا نصاً فنياً أو ملاحظات" />
                  </div>
                  <Button onClick={addDoc} className="bg-blue-600 hover:bg-blue-700">حفظ</Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>بحث وعرض</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-3">
                  <div className="flex gap-3">
                    <Input value={searchQuery} onChange={e=>setSearchQuery(e.target.value)} placeholder="ابحث في المستندات" />
                    <Button onClick={fetchDocs}>بحث</Button>
                  </div>
                  <div className="space-y-3 mt-3">
                    {docs.map((d)=> (
                      <div key={d.id} className="p-3 border rounded">
                        <div className="font-bold">{d.title || d.file_name}</div>
                        <div className="text-sm text-slate-600">{(d.tags||[]).join(', ')}</div>
                        <div className="text-sm mt-1 whitespace-pre-wrap">{(d.content||'').slice(0,300)}{(d.content||'').length>300?'...':''}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="electrical">
              <Card className="mb-6">
                <CardHeader><CardTitle>تنظيم معرفة كهربائية من نص</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <Label>العنوان</Label>
                      <Input value={elecTitle} onChange={e=>setElecTitle(e.target.value)} placeholder="مثال: أساسيات الكهرباء" />
                    </div>
                    <div>
                      <Label>وسوم</Label>
                      <Input value={elecTags} onChange={e=>setElecTags(e.target.value)} placeholder="electrical, fuse" />
                    </div>
                  </div>
                  <div>
                    <Label>نص مرجعي</Label>
                    <Textarea rows={10} value={elecContent} onChange={e=>setElecContent(e.target.value)} placeholder="ألصق نصاً كهربائياً (دوائر/خطوات فحص/قيم جهد/مخططات)" />
                  </div>
                  <Button onClick={doElecIngest} className="bg-blue-600 hover:bg-blue-700">استخراج وتنظيم</Button>
                </CardContent>
              </Card>

              <Card className="mb-6">
                <CardHeader><CardTitle>بحث كهربائي</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-3">
                  <div className="flex gap-3">
                    <Input value={elecQuery} onChange={e=>setElecQuery(e.target.value)} placeholder="ابحث (فيوز، ريلاي، SCV، إلخ)" />
                    <Button onClick={doElecSearch}>بحث</Button>
                  </div>
                  <div className="space-y-3 mt-3">
                    {elecResults.map((r)=> (
                      <div key={r.id} className="p-3 border rounded">
                        <div className="font-bold">{r.title}</div>
                        <div className="text-sm text-slate-600">{(r.tags||[]).join(', ')}</div>
                        <pre className="text-xs whitespace-pre-wrap mt-2">{JSON.stringify(r.structured, null, 2).slice(0,800)}{JSON.stringify(r.structured||{}).length>800?'...':''}</pre>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>سؤال وجواب كهربائي</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-3">
                  <Input value={qaQuestion} onChange={e=>setQaQuestion(e.target.value)} placeholder="اسأل سؤالاً كهربائياً (مثال: كيف أفحص دائرة ريلاي مروحة؟)" />
                  <Button onClick={doElecQA}>إجابة ذكية</Button>
                  {qaAnswer && (
                    <div className="mt-3 p-3 border rounded whitespace-pre-wrap text-sm">{qaAnswer}</div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="media">
              <Card className="mb-6">
                <CardHeader><CardTitle>رفع فيديو (حتى 1 جيجا) مع استخراج صوت</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-3">
                  <Input type="file" accept="video/*" onChange={e=>setFile(e.target.files?.[0]||null)} />
                  <div className="flex items-center gap-3">
                    <Button onClick={uploadVideo} disabled={!file}>رفع</Button>
                    {uploadProgress>0 && <Progress value={uploadProgress} className="w-64" />}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>آخر الوسائط</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-2">
                  {media.map(m => (
                    <div key={m.id} className="p-3 border rounded text-sm">
                      <div className="font-bold">{m.filename}</div>
                      <div className="text-slate-600">الفيديو: {m.videoPath} • الصوت: {m.audioPath || '—'}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="import">
              <Card className="mb-6">
                <CardHeader><CardTitle>استيراد حلول منظمة (JSON)</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-3">
                  <Textarea id="jsonInput" rows={10} placeholder='{
  "items": [
    {"problem_type":"كهرباء","vehicle_info":"تويوتا","problem_description":"...","solution":"...","effectiveness_rating":5}
  ]
}' />
                  <Button onClick={async ()=>{
                    const txt = document.getElementById('jsonInput').value;
                    try {
                      const payload = JSON.parse(txt);
                      const res = await fetch(`${API_URL}/ai/kb/import/json`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
                      const data = await res.json();
                      if (!res.ok) throw new Error(data.detail||'failed');
                      toast({ title:'تم الاستيراد', description:`تمت إضافة ${data.created} عنصر` });
                    } catch(e){ toast({ title:'خطأ', description:'JSON غير صالح', variant:'destructive' }); }
                  }}>استيراد JSON</Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>استيراد CSV للحلول</CardTitle></CardHeader>
                <CardContent className="p-6 space-y-3">
                  <div className="text-sm text-slate-600">الرؤوس: problem_type, vehicle_info, problem_description, solution, technician_name, effectiveness_rating</div>
                  <Input type="file" accept=".csv" onChange={async (e)=>{
                    const f = e.target.files?.[0];
                    if (!f) return;
                    const form = new FormData();
                    form.append('file', f);
                    try {
                      const res = await fetch(`${API_URL}/ai/kb/import/csv`, { method:'POST', body: form });
                      const data = await res.json();
                      if (!res.ok) throw new Error(data.detail || 'failed');
                      toast({ title: 'تم الاستيراد', description: `تمت إضافة ${data.created} عنصر` });
                    } catch (e) { toast({ title:'خطأ', description:'تعذر الاستيراد', variant:'destructive' }); }
                  }} />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </Layout>
  );
};

export default Knowledge;