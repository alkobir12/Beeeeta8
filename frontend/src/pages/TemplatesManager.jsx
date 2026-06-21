import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Upload, FileText, Trash2, Download, Eye, Plus, File } from 'lucide-react';
import axios from 'axios';
import { useToast } from '../hooks/use-toast';
import { useTranslation } from 'react-i18next';
import { resolveBackendBase } from '../utils/backendBase';

const API_URL = `${resolveBackendBase()}/api`;

const TemplatesManager = () => {
  const { toast } = useToast();
  const { t, i18n } = useTranslation();
  const isArabic = i18n.language === 'ar';
  
  const [templatesList, setTemplatesList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadForm, setUploadForm] = useState({
    name: '',
    description: '',
    type: 'invoice'
  });
  const [selectedFile, setSelectedFile] = useState(null);

  const docTypes = {
    invoice: isArabic ? 'فاتورة مبيعات' : 'Sales Invoice',
    diagnosis: isArabic ? 'تقرير تشخيص' : 'Diagnosis Report',
    quote: isArabic ? 'عرض سعر' : 'Price Quote',
    receipt: isArabic ? 'إيصال استلام' : 'Receipt'
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const response = await axios.get(`${API_URL}/templates`);
      const templatesData = response.data?.templates;
      if (Array.isArray(templatesData)) {
        setTemplatesList(templatesData);
      } else {
        console.warn('Templates data is not an array:', templatesData);
        setTemplatesList([]);
      }
    } catch (error) {
      console.error('Error loading templates:', error);
      setTemplatesList([]);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      // التحقق من نوع الملف
      const allowedTypes = ['text/html', 'application/pdf'];
      const fileExt = file.name.split('.').pop().toLowerCase();
      
      if (!['html', 'htm', 'pdf'].includes(fileExt)) {
        toast({
          title: isArabic ? 'خطأ' : 'Error',
          description: isArabic ? 'يُسمح فقط بملفات HTML أو PDF' : 'Only HTML or PDF files allowed',
          variant: 'destructive'
        });
        return;
      }
      
      setSelectedFile(file);
      // تعيين الاسم تلقائياً من اسم الملف
      if (!uploadForm.name) {
        setUploadForm(prev => ({ ...prev, name: file.name }));
      }
    }
  };

  const uploadTemplate = async () => {
    if (!selectedFile) {
      toast({
        title: isArabic ? 'خطأ' : 'Error',
        description: isArabic ? 'الرجاء اختيار ملف' : 'Please select a file',
        variant: 'destructive'
      });
      return;
    }

    if (!uploadForm.name) {
      toast({
        title: isArabic ? 'خطأ' : 'Error',
        description: isArabic ? 'الرجاء إدخال اسم النموذج' : 'Please enter template name',
        variant: 'destructive'
      });
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('name', uploadForm.name);
      formData.append('description', uploadForm.description);
      formData.append('type', uploadForm.type);

      const response = await axios.post(`${API_URL}/templates/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      toast({
        title: isArabic ? 'نجح' : 'Success',
        description: isArabic ? 'تم رفع النموذج بنجاح' : 'Template uploaded successfully'
      });

      // إعادة تعيين النموذج
      setUploadForm({ name: '', description: '', type: 'invoice' });
      setSelectedFile(null);
      document.getElementById('file-input').value = '';
      
      // إعادة تحميل القائمة
      loadTemplates();
    } catch (error) {
      toast({
        title: isArabic ? 'خطأ' : 'Error',
        description: error.response?.data?.detail || (isArabic ? 'فشل في رفع النموذج' : 'Failed to upload template'),
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const deleteTemplate = async (templateId) => {
    if (!window.confirm(isArabic ? 'هل أنت متأكد من حذف هذا النموذج؟' : 'Are you sure you want to delete this template?')) {
      return;
    }

    try {
      await axios.delete(`${API_URL}/templates/${templateId}`);
      toast({
        title: isArabic ? 'نجح' : 'Success',
        description: isArabic ? 'تم حذف النموذج' : 'Template deleted'
      });
      loadTemplates();
    } catch (error) {
      toast({
        title: isArabic ? 'خطأ' : 'Error',
        description: isArabic ? 'فشل في حذف النموذج' : 'Failed to delete template',
        variant: 'destructive'
      });
    }
  };

  const downloadTemplate = async (templateId, filename) => {
    try {
      const response = await axios.get(`${API_URL}/templates/${templateId}/download`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      toast({
        title: isArabic ? 'خطأ' : 'Error',
        description: isArabic ? 'فشل في تحميل النموذج' : 'Failed to download template',
        variant: 'destructive'
      });
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            {isArabic ? 'إدارة النماذج المخصصة' : 'Custom Templates Manager'}
          </h1>
          <p className="text-gray-500 mt-1">
            {isArabic ? 'رفع وإدارة نماذج الفواتير بصيغة HTML أو PDF' : 'Upload and manage invoice templates (HTML or PDF)'}
          </p>
        </div>
      </div>

      {/* رفع نموذج جديد */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload size={20} />
            {isArabic ? 'رفع نموذج جديد' : 'Upload New Template'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>{isArabic ? 'اسم النموذج' : 'Template Name'}</Label>
              <Input
                value={uploadForm.name}
                onChange={(e) => setUploadForm({ ...uploadForm, name: e.target.value })}
                placeholder={isArabic ? 'مثال: فاتورة Canva الاحترافية' : 'e.g., Professional Canva Invoice'}
              />
            </div>
            <div>
              <Label>{isArabic ? 'نوع المستند' : 'Document Type'}</Label>
              <Select value={uploadForm.type} onValueChange={(v) => setUploadForm({ ...uploadForm, type: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(docTypes).map(([key, label]) => (
                    <SelectItem key={key} value={key}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label>{isArabic ? 'الوصف (اختياري)' : 'Description (optional)'}</Label>
            <Textarea
              value={uploadForm.description}
              onChange={(e) => setUploadForm({ ...uploadForm, description: e.target.value })}
              placeholder={isArabic ? 'وصف مختصر عن النموذج...' : 'Brief description...'}
              rows={2}
            />
          </div>

          <div>
            <Label>{isArabic ? 'الملف (HTML أو PDF)' : 'File (HTML or PDF)'}</Label>
            <div className="flex items-center gap-4 mt-2">
              <Input
                id="file-input"
                type="file"
                accept=".html,.htm,.pdf"
                onChange={handleFileChange}
                className="flex-1"
              />
              {selectedFile && (
                <div className="text-sm text-green-600 flex items-center gap-2">
                  <File size={16} />
                  <span>{selectedFile.name}</span>
                </div>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {isArabic ? 'الأنواع المدعومة: HTML, PDF (حجم أقصى: 5MB)' : 'Supported: HTML, PDF (Max: 5MB)'}
            </p>
          </div>

          <Button onClick={uploadTemplate} disabled={loading || !selectedFile} className="w-full">
            <Upload size={18} className={isArabic ? 'ml-2' : 'mr-2'} />
            {loading ? (isArabic ? 'جاري الرفع...' : 'Uploading...') : (isArabic ? 'رفع النموذج' : 'Upload Template')}
          </Button>
        </CardContent>
      </Card>

      {/* قائمة النماذج */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText size={20} />
            {isArabic ? 'النماذج المحفوظة' : 'Saved Templates'}
            <span className="text-sm font-normal text-muted-foreground">
              ({Array.isArray(templatesList) ? templatesList.length : 0})
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!Array.isArray(templatesList) || templatesList.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <FileText size={48} className="mx-auto mb-4 opacity-20" />
              <p>{isArabic ? 'لا توجد نماذج محفوظة بعد' : 'No templates saved yet'}</p>
              <p className="text-sm mt-2">
                {isArabic ? 'ابدأ برفع نموذج HTML أو PDF من الأعلى' : 'Start by uploading an HTML or PDF template above'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.isArray(templatesList) && templatesList.map((template) => (
                <div
                  key={template.id}
                  className="border rounded-lg p-4 hover:shadow-lg transition-shadow bg-slate-50 dark:bg-slate-800"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {template.file_type === 'pdf' ? (
                        <div className="w-10 h-10 rounded bg-red-100 flex items-center justify-center">
                          <FileText size={20} className="text-red-600" />
                        </div>
                      ) : (
                        <div className="w-10 h-10 rounded bg-blue-100 flex items-center justify-center">
                          <FileText size={20} className="text-blue-600" />
                        </div>
                      )}
                      <div>
                        <h4 className="font-semibold text-sm">{template.name}</h4>
                        <p className="text-xs text-muted-foreground">
                          {docTypes[template.type]} • {template.file_type.toUpperCase()}
                        </p>
                      </div>
                    </div>
                  </div>

                  {template.description && (
                    <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
                      {template.description}
                    </p>
                  )}

                  <div className="text-xs text-muted-foreground mb-3">
                    <p>{formatFileSize(template.file_size)}</p>
                    <p>{new Date(template.created_at).toLocaleDateString('ar-SA')}</p>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => downloadTemplate(template.id, template.original_filename)}
                      className="flex-1"
                    >
                      <Download size={14} className={isArabic ? 'ml-1' : 'mr-1'} />
                      {isArabic ? 'تحميل' : 'Download'}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => deleteTemplate(template.id)}
                      className="text-red-500 hover:text-red-600"
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* إرشادات */}
      <Card className="bg-blue-50 dark:bg-blue-900/20 border-blue-200">
        <CardContent className="p-4">
          <h4 className="font-semibold text-blue-900 dark:text-blue-100 mb-2 flex items-center gap-2">
            <FileText size={16} />
            {isArabic ? '📋 كيفية إضافة نموذج من Canva' : '📋 How to Add Template from Canva'}
          </h4>
          <ol className="text-sm text-blue-800 dark:text-blue-200 space-y-1 list-decimal list-inside">
            <li>{isArabic ? 'افتح تصميمك في Canva' : 'Open your design in Canva'}</li>
            <li>{isArabic ? 'اضغط Share → Download' : 'Click Share → Download'}</li>
            <li>{isArabic ? 'اختر PDF (Standard) أو PNG' : 'Choose PDF (Standard) or PNG'}</li>
            <li>{isArabic ? 'حمّل الملف على جهازك' : 'Download to your device'}</li>
            <li>{isArabic ? 'ارفعه هنا باستخدام الزر أعلاه' : 'Upload it here using the button above'}</li>
          </ol>
          <p className="text-xs text-blue-700 dark:text-blue-300 mt-3">
            💡 {isArabic ? 'يمكنك أيضاً رفع ملفات HTML إذا كان لديك تصميم مخصص' : 'You can also upload HTML files if you have a custom design'}
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default TemplatesManager;