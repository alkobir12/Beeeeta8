import React, { useState } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Plus, Trash2, FileText, Download, Eye, Loader2 } from 'lucide-react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { resolveBackendBase } from '../utils/backendBase';

const API_URL = `${resolveBackendBase()}/api`;

const QuotationGenerator = () => {
  const { i18n } = useTranslation();
  const isArabic = i18n.language === 'ar';
  
  const [loading, setLoading] = useState(false);
  const [previewHtml, setPreviewHtml] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [services, setServices] = useState([]);
  const [showServiceModal, setShowServiceModal] = useState(false);
  
  const [formData, setFormData] = useState({
    // بيانات الشركة
    company: {
      name: 'ورشة السيارات',
      name_en: 'Auto Workshop',
      address: 'الرياض - المملكة العربية السعودية',
      phone: '',
      email: '',
      website: '',
      tax_number: ''
    },
    // بيانات العميل
    client: {
      name: '',
      company: '',
      address: '',
      phone: '',
      email: ''
    },
    // وصف المشروع
    project_description: '',
    // البنود
    items: [],
    // الشروط
    terms: [
      'هذا العرض صالح لمدة 30 يوماً من تاريخ الإصدار',
      'يتطلب دفع 50% مقدماً لبدء العمل',
      'المدة المتوقعة للتسليم حسب نطاق المشروع'
    ],
    // الإعدادات
    theme: 'أزرق',
    style: 'حديث',
    tax_rate: 15
  });

  // Load settings and services on mount
  React.useEffect(() => {
    const loadData = async () => {
      try {
        // 🎯 Load workshop info from BOTH profile (priority) and settings (fallback)
        const [settingsRes, profileRes] = await Promise.all([
          axios.get(`${API_URL}/settings`).catch(() => ({ data: {} })),
          axios.get(`${API_URL}/profile`).catch(() => ({ data: {} })),
        ]);
        const settings = settingsRes?.data || {};
        const profile = profileRes?.data?.profile || profileRes?.data?.data || profileRes?.data || {};
        setFormData(prev => ({
          ...prev,
          company: {
            // الأولوية: Profile (يحدّثه المستخدم من ملف الورشة) > Settings (افتراضي)
            name: profile.business_name || profile.name || settings.workshopName || 'ورشتي',
            name_en: profile.name_english || profile.nameEnglish || settings.workshopNameEn || '',
            address: profile.address || settings.workshopAddress || '',
            phone: profile.phone || profile.phone_number || settings.workshopPhone || '',
            email: profile.email || settings.workshopEmail || '',
            website: profile.website || settings.workshopWebsite || '',
            tax_number: profile.taxNumber || profile.tax_number || settings.taxNumber || settings.workshopTaxNumber || '',
            commercial_register: profile.commercialRegister || profile.commercial_register || settings.commercialRegister || '',
            logo: profile.logo || profile.logo_url || settings.logoUrl || '',
          },
          tax_rate: (settings.taxRate ?? 15)
        }));
        
        // Load services
        const servicesRes = await axios.get(`${API_URL}/services`);
        setServices(servicesRes.data || []);
      } catch (error) {
        console.error('Error loading data:', error);
      }
    };
    loadData();
  }, []);

  const themes = ['أزرق', 'أخضر', 'بنفسجي', 'برتقالي', 'أحمر', 'تركوازي', 'ذهبي', 'رمادي'];
  const styles = ['حديث', 'كلاسيكي', 'فاخر'];

  const handleCompanyChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      company: { ...prev.company, [field]: value }
    }));
  };

  const handleClientChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      client: { ...prev.client, [field]: value }
    }));
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...formData.items];
    newItems[index] = { ...newItems[index], [field]: field === 'description' ? value : parseFloat(value) || 0 };
    setFormData(prev => ({ ...prev, items: newItems }));
  };

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { description: '', quantity: 1, unit_price: 0, discount: 0 }]
    }));
  };

  const addServiceAsItem = (service) => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { 
        description: service.name, 
        quantity: 1, 
        unit_price: service.price || 0, 
        discount: 0 
      }]
    }));
    setShowServiceModal(false);
  };

  const removeItem = (index) => {
    if (formData.items.length > 1) {
      setFormData(prev => ({
        ...prev,
        items: prev.items.filter((_, i) => i !== index)
      }));
    }
  };

  const handleTermChange = (index, value) => {
    const newTerms = [...formData.terms];
    newTerms[index] = value;
    setFormData(prev => ({ ...prev, terms: newTerms }));
  };

  const addTerm = () => {
    setFormData(prev => ({
      ...prev,
      terms: [...prev.terms, '']
    }));
  };

  const removeTerm = (index) => {
    if (formData.terms.length > 1) {
      setFormData(prev => ({
        ...prev,
        terms: prev.terms.filter((_, i) => i !== index)
      }));
    }
  };

  const calculateTotal = () => {
    const subtotal = formData.items.reduce((sum, item) => {
      return sum + (item.quantity * item.unit_price) - item.discount;
    }, 0);
    const tax = subtotal * (formData.tax_rate / 100);
    return { subtotal, tax, total: subtotal + tax };
  };

  const generateQuotation = async (preview = false) => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_URL}/quotations/generate`, {
        company: formData.company,
        client: formData.client,
        project_description: formData.project_description,
        items: formData.items.filter(item => item.description),
        terms: formData.terms.filter(term => term),
        theme: formData.theme,
        style: formData.style,
        tax_rate: formData.tax_rate
      });

      if (response.data.success) {
        if (preview) {
          setPreviewHtml(response.data.html);
          setShowPreview(true);
        } else {
          // تحميل الملف
          const blob = new Blob([response.data.html], { type: 'text/html;charset=utf-8' });
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `quotation_${response.data.quotation_number}.html`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        }
      }
    } catch (error) {
      console.error('Error generating quotation:', error);
      alert(isArabic ? 'حدث خطأ أثناء إنشاء العرض' : 'Error generating quotation');
    } finally {
      setLoading(false);
    }
  };

  const totals = calculateTotal();

  return (
    <Layout>
      <div className="container mx-auto p-4 sm:p-6 max-w-6xl">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
              {isArabic ? 'مولد عروض الأسعار' : 'Quotation Generator'}
            </h1>
            <p className="text-muted-foreground">
              {isArabic ? 'إنشاء عروض أسعار احترافية بتصاميم متعددة' : 'Create professional quotations with multiple designs'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => generateQuotation(true)}
              disabled={loading}
            >
              <Eye size={18} className={isArabic ? 'ml-2' : 'mr-2'} />
              {isArabic ? 'معاينة' : 'Preview'}
            </Button>
            <Button
              onClick={() => generateQuotation(false)}
              disabled={loading}
              className="bg-gradient-to-r from-blue-600 to-indigo-600"
            >
              {loading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Download size={18} className={isArabic ? 'ml-2' : 'mr-2'} />
              )}
              {isArabic ? 'تحميل' : 'Download'}
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* بيانات الشركة */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText size={20} />
                {isArabic ? 'بيانات الشركة' : 'Company Details'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>{isArabic ? 'اسم الشركة (عربي)' : 'Company Name (Arabic)'}</Label>
                  <Input
                    value={formData.company.name}
                    onChange={(e) => handleCompanyChange('name', e.target.value)}
                  />
                </div>
                <div>
                  <Label>{isArabic ? 'اسم الشركة (إنجليزي)' : 'Company Name (English)'}</Label>
                  <Input
                    value={formData.company.name_en}
                    onChange={(e) => handleCompanyChange('name_en', e.target.value)}
                  />
                </div>
              </div>
              <div>
                <Label>{isArabic ? 'العنوان' : 'Address'}</Label>
                <Input
                  value={formData.company.address}
                  onChange={(e) => handleCompanyChange('address', e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>{isArabic ? 'الهاتف' : 'Phone'}</Label>
                  <Input
                    value={formData.company.phone}
                    onChange={(e) => handleCompanyChange('phone', e.target.value)}
                  />
                </div>
                <div>
                  <Label>{isArabic ? 'البريد الإلكتروني' : 'Email'}</Label>
                  <Input
                    value={formData.company.email}
                    onChange={(e) => handleCompanyChange('email', e.target.value)}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>{isArabic ? 'الموقع الإلكتروني' : 'Website'}</Label>
                  <Input
                    value={formData.company.website}
                    onChange={(e) => handleCompanyChange('website', e.target.value)}
                  />
                </div>
                <div>
                  <Label>{isArabic ? 'الرقم الضريبي' : 'Tax Number'}</Label>
                  <Input
                    value={formData.company.tax_number}
                    onChange={(e) => handleCompanyChange('tax_number', e.target.value)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* بيانات العميل */}
          <Card>
            <CardHeader>
              <CardTitle>{isArabic ? 'بيانات العميل' : 'Client Details'}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>{isArabic ? 'اسم العميل' : 'Client Name'}</Label>
                  <Input
                    value={formData.client.name}
                    onChange={(e) => handleClientChange('name', e.target.value)}
                    placeholder={isArabic ? 'أحمد محمد' : 'John Doe'}
                  />
                </div>
                <div>
                  <Label>{isArabic ? 'الشركة' : 'Company'}</Label>
                  <Input
                    value={formData.client.company}
                    onChange={(e) => handleClientChange('company', e.target.value)}
                  />
                </div>
              </div>
              <div>
                <Label>{isArabic ? 'العنوان' : 'Address'}</Label>
                <Input
                  value={formData.client.address}
                  onChange={(e) => handleClientChange('address', e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>{isArabic ? 'الهاتف' : 'Phone'}</Label>
                  <Input
                    value={formData.client.phone}
                    onChange={(e) => handleClientChange('phone', e.target.value)}
                  />
                </div>
                <div>
                  <Label>{isArabic ? 'البريد الإلكتروني' : 'Email'}</Label>
                  <Input
                    value={formData.client.email}
                    onChange={(e) => handleClientChange('email', e.target.value)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* وصف المشروع */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>{isArabic ? 'وصف المشروع' : 'Project Description'}</CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea
                value={formData.project_description}
                onChange={(e) => setFormData(prev => ({ ...prev, project_description: e.target.value }))}
                placeholder={isArabic ? 'وصف تفصيلي للمشروع أو الخدمة المطلوبة...' : 'Detailed description of the project or service...'}
                rows={3}
              />
            </CardContent>
          </Card>

          {/* البنود */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>{isArabic ? 'البنود' : 'Items'}</CardTitle>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setShowServiceModal(true)}>
                  <Plus size={16} className={isArabic ? 'ml-1' : 'mr-1'} />
                  {isArabic ? 'إضافة من الخدمات' : 'Add from Services'}
                </Button>
                <Button variant="outline" size="sm" onClick={addItem}>
                  <Plus size={16} className={isArabic ? 'ml-1' : 'mr-1'} />
                  {isArabic ? 'إضافة بند يدوي' : 'Add Manual Item'}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {formData.items.length === 0 && (
                  <div className="text-center py-8 text-gray-500">
                    <p>{isArabic ? 'لا توجد بنود. اضغط "إضافة من الخدمات" لإضافة خدمات من القائمة' : 'No items. Click "Add from Services" to add services from list'}</p>
                  </div>
                )}
                {formData.items.map((item, index) => (
                  <div key={item?.id ?? `qitem-${index}`} className="flex flex-wrap gap-2 items-end p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <div className="flex-1 min-w-[200px]">
                      <Label>{isArabic ? 'الوصف' : 'Description'}</Label>
                      <Input
                        value={item.description}
                        onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                        placeholder={isArabic ? 'وصف البند' : 'Item description'}
                      />
                    </div>
                    <div className="w-24">
                      <Label>{isArabic ? 'الكمية' : 'Qty'}</Label>
                      <Input
                        type="number"
                        value={item.quantity}
                        onChange={(e) => handleItemChange(index, 'quantity', e.target.value)}
                        min="1"
                      />
                    </div>
                    <div className="w-32">
                      <Label>{isArabic ? 'السعر' : 'Price'}</Label>
                      <Input
                        type="number"
                        value={item.unit_price}
                        onChange={(e) => handleItemChange(index, 'unit_price', e.target.value)}
                        min="0"
                      />
                    </div>
                    <div className="w-28">
                      <Label>{isArabic ? 'الخصم' : 'Discount'}</Label>
                      <Input
                        type="number"
                        value={item.discount}
                        onChange={(e) => handleItemChange(index, 'discount', e.target.value)}
                        min="0"
                      />
                    </div>
                    <div className="w-32 text-center">
                      <Label>{isArabic ? 'المجموع' : 'Total'}</Label>
                      <p className="font-bold text-lg">
                        {((item.quantity * item.unit_price) - item.discount).toLocaleString()}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeItem(index)}
                      disabled={formData.items.length === 1}
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 size={18} />
                    </Button>
                  </div>
                ))}
              </div>

              {/* الإجماليات */}
              <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className="flex justify-between py-2">
                  <span>{isArabic ? 'المجموع الفرعي:' : 'Subtotal:'}</span>
                  <span className="font-semibold">{totals.subtotal.toLocaleString()} {isArabic ? 'ر.س' : 'SAR'}</span>
                </div>
                <div className="flex justify-between py-2">
                  <span>{isArabic ? `ضريبة القيمة المضافة (${formData.tax_rate}%):` : `VAT (${formData.tax_rate}%):`}</span>
                  <span className="font-semibold">{totals.tax.toLocaleString()} {isArabic ? 'ر.س' : 'SAR'}</span>
                </div>
                <div className="flex justify-between py-2 border-t-2 border-blue-200 dark:border-blue-700 text-lg font-bold text-blue-600 dark:text-blue-400">
                  <span>{isArabic ? 'المجموع الكلي:' : 'Total:'}</span>
                  <span>{totals.total.toLocaleString()} {isArabic ? 'ر.س' : 'SAR'}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* الإعدادات والشروط */}
          <Card>
            <CardHeader>
              <CardTitle>{isArabic ? 'إعدادات التصميم' : 'Design Settings'}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>{isArabic ? 'اللون' : 'Theme Color'}</Label>
                <Select
                  value={formData.theme}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, theme: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {themes.map(theme => (
                      <SelectItem key={theme} value={theme}>{theme}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>{isArabic ? 'نمط التصميم' : 'Design Style'}</Label>
                <Select
                  value={formData.style}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, style: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {styles.map(style => (
                      <SelectItem key={style} value={style}>{style}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>{isArabic ? 'نسبة الضريبة (%)' : 'Tax Rate (%)'}</Label>
                <Input
                  type="number"
                  value={formData.tax_rate}
                  onChange={(e) => setFormData(prev => ({ ...prev, tax_rate: parseFloat(e.target.value) || 0 }))}
                  min="0"
                  max="100"
                />
              </div>
            </CardContent>
          </Card>

          {/* الشروط والأحكام */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>{isArabic ? 'الشروط والأحكام' : 'Terms & Conditions'}</CardTitle>
              <Button variant="outline" size="sm" onClick={addTerm}>
                <Plus size={16} className={isArabic ? 'ml-1' : 'mr-1'} />
                {isArabic ? 'إضافة' : 'Add'}
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {formData.terms.map((term, index) => (
                  <div key={`term-${index}-${(term || '').slice(0, 20)}`} className="flex gap-2">
                    <Input
                      value={term}
                      onChange={(e) => handleTermChange(index, e.target.value)}
                      placeholder={isArabic ? 'شرط أو حكم...' : 'Term or condition...'}
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeTerm(index)}
                      disabled={formData.terms.length === 1}
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* نافذة المعاينة */}
        {showPreview && previewHtml && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white dark:bg-slate-900 rounded-lg w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="p-4 border-b flex justify-between items-center">
                <h3 className="font-bold text-lg">{isArabic ? 'معاينة عرض السعر' : 'Quotation Preview'}</h3>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => generateQuotation(false)}>
                    <Download size={16} className={isArabic ? 'ml-1' : 'mr-1'} />
                    {isArabic ? 'تحميل' : 'Download'}
                  </Button>
                  <Button variant="ghost" onClick={() => setShowPreview(false)}>
                    {isArabic ? 'إغلاق' : 'Close'}
                  </Button>
                </div>
              </div>
              <div className="flex-1 overflow-auto">
                <iframe
                  srcDoc={previewHtml}
                  className="w-full h-full min-h-[600px]"
                  title="Quotation Preview"
                />
              </div>
            </div>
          </div>
        )}
        
        {/* Services Modal */}
        {showServiceModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col">
              <div className="p-6 border-b flex justify-between items-center">
                <h2 className="text-xl font-bold">{isArabic ? 'اختر الخدمات' : 'Select Services'}</h2>
                <button 
                  onClick={() => setShowServiceModal(false)}
                  className="text-gray-500 hover:text-gray-700 text-2xl"
                >
                  ×
                </button>
              </div>
              
              <div className="flex-1 overflow-auto p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {services.map(service => (
                    <div 
                      key={service.id}
                      onClick={() => addServiceAsItem(service)}
                      className="p-4 border rounded-lg hover:border-blue-500 hover:bg-blue-50 cursor-pointer transition-all"
                    >
                      <h3 className="font-bold text-lg mb-2">{service.name}</h3>
                      <div className="flex justify-between items-center text-sm">
                        <span className="text-gray-600">{service.category}</span>
                        <span className="font-bold text-blue-600">{service.price} ر.س</span>
                      </div>
                      {service.duration && (
                        <div className="text-xs text-gray-500 mt-1">
                          {service.duration} دقيقة
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {services.length === 0 && (
                  <div className="text-center py-12 text-gray-500">
                    <p>{isArabic ? 'لا توجد خدمات متاحة' : 'No services available'}</p>
                  </div>
                )}
              </div>
              
              <div className="p-6 border-t bg-gray-50">
                <p className="text-sm text-gray-600">
                  {isArabic ? `عدد الخدمات المتاحة: ${services.length}` : `Available services: ${services.length}`}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default QuotationGenerator;