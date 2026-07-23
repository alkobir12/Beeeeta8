# تقرير تشخيص P0 — نظام قوالب الطباعة

**النطاق:** جرد قراءة فقط قبل أي دمج لقالب جديد أو ترحيل.

## الخلاصة التنفيذية

نظام القوالب الحالي غير موحد: توجد طبقة ملفات مخصصة نشطة، وطبقتان قديمتان في MongoDB، وقوالب HTML ثابتة، وقالب React ثابت في `DocumentPrint`. لا يوجد عقد موحد لـ `tenant_id + document_type + locale` ولا سجل قرار واحد يحدد القالب المستخدم فعلياً.

## الجرد الفعلي

| الاسم | النوع | اللغة | المستأجر | الإصدار | الحالة | افتراضي | مستخدم فعلياً | المصدر | آخر تعديل | التصنيف |
|---|---|---|---|---|---|---|---|---|---|---|
| فاتورة الورشة — ختم إلكتروني | invoice | غير مخزن (عربي في المحتوى) | غير مخزن | غير مخزن | active | نعم | QuickPrint فقط عند عدم وجود افتراضي مخصص | builtin في `routes_templates.py` | 2026-07-21 | صالح لكن بلا نطاق tenant/locale |
| تقرير تشخيص — ختم إلكتروني | diagnosis | غير مخزن | غير مخزن | غير مخزن | active | نعم | QuickPrint فقط | builtin في `routes_templates.py` | 2026-07-21 | صالح لكن بلا نطاق tenant/locale |
| عرض سعر — ختم إلكتروني | quote | غير مخزن | غير مخزن | غير مخزن | active | نعم | QuickPrint فقط | builtin في `routes_templates.py` | 2026-07-21 | صالح لكن بلا نطاق tenant/locale |
| سند زيارة — ختم إلكتروني | receipt | غير مخزن | غير مخزن | غير مخزن | active | نعم | QuickPrint فقط | builtin في `routes_templates.py` | 2026-07-21 | صالح لكن بلا نطاق tenant/locale |
| Invoice ux | invoice | غير مخزن | غير مخزن | غير مخزن | active | لا | متاح في QuickPrint عند اختياره | `uploads/custom_templates_index.json` + ملف HTML | 2026-07-22 | يحتاج إصلاح (لا يتبع للعقد الموحد) |
| نموذج | invoice | غير مخزن | غير مخزن | غير مخزن | active | لا | لا؛ PDF للتحميل فقط | `uploads/custom_templates_index.json` + ملف PDF | 2026-07-23 | غير صالح كقالب HTML |
| نسخة HTML غير مفهرسة `85a9...` | غير معروف | غير مخزن | غير مخزن | غير مخزن | غير معروف | لا | لا | `backend/custom_templates/` | 2026-07-22 | غير مستخدم / مكرر (نفس SHA-256 لـ Invoice ux) |
| classic_pro / mechanic / modern / modern_pro / repair_ar | غير موحد | غير مخزن | غير مخزن | غير مخزن | fallback ثابت | لا | مسار `/print/resolve-template` فقط عند عمله | ملفات HTML ثابتة في backend | 2026-01-31 | قديم / غير موحد |
| print_templates | متنوع | غير مخزن | غير مخزن | غير مخزن | فارغ | — | لا | MongoDB | — | غير مستخدم |
| invoice_templates | فاتورة XLSX/مصمم | غير مخزن | غير مخزن | غير مخزن | فارغ | — | لا | MongoDB / GridFS | — | غير مستخدم |
| Dash Pro electronic sheet | كل الأنواع | غير مخزن | غير مخزن | v1 ثابت | active | ضمني | DocumentPrint وPDF وواتساب من صفحة الطباعة | React `DocumentPrint.jsx` | ضمن الكود | يحتاج ترحيل؛ يتجاهل القوالب |

## ما يستخدم فعلياً الآن

1. **المعاينة في QuickPrintDialog:** تستخدم القالب المختار من `GET /api/templates` وتقرأ HTML من `POST /api/templates/{id}/use`. عند غياب اختيار صالح، تستدعي `/api/documents/generate`.
2. **PDF من QuickPrintDialog:** يحول نفس HTML المعروض إلى PDF، ولذلك يتبع اختيار QuickPrint فقط.
3. **DocumentPrint والمعاينة وPDF وواتساب من صفحة `/print`:** تستخدم `InvoiceSheet` ثابتاً في React. لا تقرأ `template_id` أو القالب الافتراضي.
4. **DocumentFormDialog:** يرسل `template_id` إلى `/api/print/resolve-template` لكن ذلك المسار يتجاهل المعرف، ثم يتجاهل فشل الاستدعاء، ويعرض نتيجة `/api/print/render`؛ لذلك الاختيار غير مضمون.
5. **`/api/documents/generate`:** يستخدم `UnifiedDocumentGenerator` و`ArabicQuotationBuilder` فقط؛ لا يقرأ `template_id` ولا الافتراضي.

## أسباب الخلل المؤكدة

- `POST /api/print/resolve-template` يفشل حالياً بـ500 لأن `routes_templates_extended.py` يستخدم `if db:` مع كائن MongoDB لا يسمح باختبار boolean. الرسالة الفعلية: `Database objects do not implement truth value testing...`.
- مسار الحلّ الخلفي لا يقرأ `template_id` أصلاً؛ يختار أول `print_templates` نشط بحسب النوع فقط.
- `DocumentPrint.jsx` يمرر `templateId: 'dash-pro-electronic-sheet'` ثابتاً لواتساب، ويعرض قالب React ثابتاً؛ لذلك يتجاهل الاختيار والافتراضي كلياً.
- `UnifiedDocumentGenerator` لا يستقبل أو يحل `template_id`، ولذلك كل fallback فيه ثابت وصامت.
- الواجهة تخزّن/تعرض الحقول المتباينة `active`, `isActive`, `is_default`, `isDefault` من دون عقد موحد.
- بيانات القالب النشطة لا تحتوي `tenant_id` أو `locale` أو `version` أو `status` موحداً، فلا يمكن ضمان قاعدة الافتراضي المطلوبة.
- لا يوجد فهرس/قيد ذري يمنع أكثر من افتراضي في نطاق واحد. في البيانات الفعلية الحالية لا يوجد تكرار داخل طبقة JSON (افتراضي مدمج واحد لكل نوع)، لكن التصميم يسمح بالتكرار عبر الطبقات المختلفة.

## المسارات التي تتجاهل template_id

- `DocumentPrint.jsx` (المعاينة، PDF، واتساب).
- `/api/documents/generate` و`/api/documents/generate-html`.
- `/api/print/resolve-template` (لا يقرأ المعرف الوارد).
- `DocumentFormDialog.jsx` (يمرره ثم يتجاهل أي فشل).

## خطة ترحيل آمنة مقترحة

1. إنشاء سجل قوالب موحد جديد فقط، مع إبقاء الملفات والسجلات القديمة للقراءة والتصنيف وعدم حذفها.
2. اعتماد عقد: `id, tenant_id, document_type, locale, version, status, active, is_default, source, content_ref, created_at, updated_at`.
3. إنشاء قيد فريد جزئي في MongoDB يمنع أكثر من `is_default=true` و`active=true` لكل `tenant_id + document_type + locale`.
4. إنشاء خدمة حل واحدة ترد بالقالب وبـ`selection_reason`: `explicit_document_template`, `tenant_default`, `system_default`, أو `internal_fallback`.
5. جعل Set Default عملية خلفية ذرية: إلغاء الافتراضي السابق في النطاق نفسه ثم تعيين القالب الهدف وتسجيل audit؛ لا تعتمد على حالة الواجهة.
6. ربط QuickPrint وDocumentPrint وPDF والمعاينة وواتساب بالخدمة نفسها؛ وعند فشل قالب مختار صراحةً يعاد خطأ واضح بلا fallback صامت.
7. حفظ `template_id`, `template_version`, و`template_selection_reason` داخل المستند/سجل المشاركة عند الإنشاء.
8. ترحيل القوالب الحالية بالتصنيف فقط أولاً، ثم اختبار end-to-end قبل اعتبار أي قالب جديد افتراضياً.

## قرار P0

لا يُدمج أو يُفعّل أي قالب جديد قبل تنفيذ العقد الموحد، خدمة الحل الموحدة، وربط كل مسارات الطباعة بها.