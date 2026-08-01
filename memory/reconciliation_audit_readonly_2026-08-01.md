# تقرير Reconciliation Audit — قراءة فقط

تاريخ التقرير: `2026-08-01T19:02:28.960023+00:00`  
الحالة: **READ_ONLY_AUDIT_NO_DELETE_NO_DB_MUTATION**

## 1) العدادات

- vehicles_total: **191**
- visits_total: **173**
- operations_total: **164**
- journal_entries_total: **182**
- dashboard_visible_current_logic_count: **15**
- semantic_archive_status_count: **178**
- archive_page_current_display_count: **191**

## 2) حالات المركبات

- `delivered`: **176**
- `NULL`: **5**
- `ready`: **4**
- `archived`: **2**
- `diagnosis`: **3**
- `تشخيص`: **1**

## 3) قائمة الـ15 الظاهرة حالياً في لوحة التحكم حسب الكود الحالي

| # | vehicle_id | العميل | اللوحة | الحالة | آخر زيارة | يظهر باللوحة | يظهر بصفحة الأرشيف الحالية | حالة أرشيفية نصياً | العمليات | إجمالي العمليات | ذمم متبقية |
|---|---|---|---|---|---|---|---|---|---:|---:|---:|
| 1 | `a57b698d-752d-43bf-be66-41a0337de9eb` | ابراهيم صالح  | ب ر ق 4806 | `ready` | `6484969a` 2026-07-27 | True | True | False | 1 | 1800.0 | 1800.0 |
| 2 | `a717c745-3d53-43d0-b235-ef90a794311f` | خالد عماش الحربي | ا ح ق 9342 | `ready` | `73ea8c01` 2026-07-26 | True | True | False | 1 | 2560.0 | 0.0 |
| 3 | `c02cc9c7-6ff5-4fc7-9414-b15787fa9000` | سلطان الشاص | ب ح ن 6923 | `تشخيص` | `b48c0850` 2026-07-23 | True | True | False | 1 | 300.0 | 300.0 |
| 4 | `61fe0b56-aa66-490d-a5e7-6f3b8195ed56` | محمد الحربي  | ا ح ا 5110 | `None` | `b1305e60` 2026-07-19 | True | True | False | 1 | 600.0 | 600.0 |
| 5 | `d5376421-bd6e-420e-8585-ba36c3314082` | فهد الطريسي | ح ل ص 5745 | `ready` | `3aa0a6dc` 2026-07-13 | True | True | False | 1 | 1943.0 | 0.0 |
| 6 | `b9fe95f6-e4c3-4466-b853-c0103dc75929` | فارس عوض  | ح ق م 5520 | `None` | `2635ecf1` 2026-07-12 | True | True | False | 1 | 2500.0 | 0.0 |
| 7 | `c5bfe993-c45a-4412-b196-be1cdd310c40` | عبد الكريم الشايعي  | ا ص ص 7293 | `None` | `72ccd3b0` 2026-07-05 | True | True | False | 1 | 800.0 | 800.0 |
| 8 | `ce2e776e-d750-4e34-b20a-ef21f49cad63` | ابو ركان عبدالله  | د ط ص 5787 | `diagnosis` | `77a3d80a` 2026-07-12 | True | True | False | 1 | 2350.0 | 0.0 |
| 9 | `0ee51492-8405-4235-8c63-4ca01b6bccc8` | عاصم التويجري | ا ل و 7121 | `None` | `ca32e1a6` 2026-06-08 | True | True | False | 1 | 150.0 | 150.0 |
| 10 | `235cb00f-facb-46aa-a4eb-8db039ec21ee` | 1062 ///ملحمة قويصرة   | ا ك ل 3820 | `archived` | `822ca57a` 2026-06-08 | True | True | True | 2 | 1877.0 | 0.0 |
| 11 | `523451c4-01a9-455e-902c-b21ae944a85f` | صالح  سليمان ابراهيم المهوس | ا ط ي  8204 | `diagnosis` | `2819677c` 2026-05-11 | True | True | False | 0 | 0.0 | 0.0 |
| 12 | `9004d4bd-ed82-4e0d-afa4-fd62e6e3d8fa` | 1059 ///بنقالي عناية ميزان | 1059 /// ا ر م 9460 | `archived` | `c2677678` 2026-05-22 | True | True | True | 0 | 0.0 | 0.0 |
| 13 | `c92405eb-2097-4f42-aa3e-ccd455d9812f` |    1046 ///صالح القصير |    1046  /// ب ص ر 6431 | `diagnosis` | `6973ed6f` 2026-07-06 | True | True | False | 1 | 500.0 | 500.0 |
| 14 | `6a8ace60-5ed7-48dd-bfd1-7d47d408f706` | 1036 /// ماجد الربعي | 0136///  ا ق ر 7756 | `None` | `ba89782c` 2026-04-15 | True | True | False | 1 | 100.0 | 0.0 |
| 15 | `bea27237-7274-4fe2-84b3-8106740645d7` | 77  //محمد  فهدالعمر | ا ر ح 6912 | `ready` | `4075cc96` 2026-04-06 | True | True | False | 1 | 250.0 | 0.0 |

## 4) التداخل

- IDs تظهر ضمن الـ15 الحالية وحالتها نصياً أرشيف/مسلمة: `235cb00f-facb-46aa-a4eb-8db039ec21ee, 9004d4bd-ed82-4e0d-afa4-fd62e6e3d8fa`
- ملاحظة الأرشيف: VehicleArchive.jsx حالياً يعرض vehicleAPI.getAll() بدون فلتر أرشيف؛ لذلك كل المركبات الـ191 تظهر في صفحة الأرشيف عند filter=all.

## 5) تقسيم العمليات

```json
{
  "dashboard_visible_15": {
    "count": 14,
    "total": 15730.0,
    "by_method": {
      "cash": 4727.0,
      "credit": 4150.0,
      "transfer": 6853.0
    }
  },
  "semantic_archive": {
    "count": 151,
    "total": 164794.5,
    "by_method": {
      "card": 18270.0,
      "cash": 53911.5,
      "credit": 49985.0,
      "transfer": 42628.0
    }
  },
  "overlap_active_archive": {
    "count": 2,
    "total": 1877.0,
    "by_method": {
      "cash": 1877.0
    }
  },
  "unlinked_pos_workshop": {
    "count": 1,
    "total": 350.0,
    "by_method": {
      "bank": 350.0
    }
  }
}
```

## 6) تصنيف القيود وأثرها

```json
{
  "counts": {
    "أرشيف": 163,
    "نشط": 15,
    "قديم مستبعد": 2,
    "مشكوك/تداخل نشط+أرشيف": 2
  },
  "impacts": {
    "أرشيف": {
      "revenue": 163127.5,
      "expenses": 15200.0,
      "ar_net": 30785.0,
      "cash_net": 55144.5,
      "bank_transfer_net": 58928.0,
      "pos_net": 18270.0,
      "payments_reduce_ar": 19200.0,
      "credit_sales_ar_debit": 49985.0
    },
    "نشط": {
      "revenue": 13853.0,
      "expenses": 1400.0,
      "ar_net": 4650.0,
      "cash_net": 2350.0,
      "bank_transfer_net": 6853.0,
      "pos_net": 0.0,
      "payments_reduce_ar": 2000.0,
      "credit_sales_ar_debit": 6650.0
    },
    "قديم مستبعد": {
      "revenue": 0.0,
      "expenses": 0.0,
      "ar_net": 16300.0,
      "cash_net": 0.0,
      "bank_transfer_net": 0.0,
      "pos_net": 0.0,
      "payments_reduce_ar": 0.0,
      "credit_sales_ar_debit": 16300.0
    },
    "مشكوك/تداخل نشط+أرشيف": {
      "revenue": 1877.0,
      "expenses": 0.0,
      "ar_net": 0.0,
      "cash_net": 1877.0,
      "bank_transfer_net": 0.0,
      "pos_net": 0.0,
      "payments_reduce_ar": 0.0,
      "credit_sales_ar_debit": 0.0
    }
  }
}
```

## 7) نقاط المصالحة المطلوبة

```json
{
  "credit_sales_total": 54135.0,
  "allocated_payments_against_credit_ops": 2900.0,
  "remaining_credit_ops": 51235.0,
  "difference_2400_explanation": "الفرق بين مبيعات آجل 54,135 ورصيد عمليات الآجل المتبقي المحسوب من العمليات والدفعات المرتبطة يظهر كدفعات مخصصة. endpoint /ar/customers الحالي يحسب 51,735 لأنه لا يأخذ إلا source=operation_payment ويهمل مصادر مثل visit_receipt_voucher وبعض القيود الافتتاحية؛ لذلك يحتاج توحيد تخصيص الدفعات.",
  "credit_ops_samples": [
    {
      "operation_id": "668bed7b-935f-4cc0-9a15-324d4ba9506d",
      "vehicle_id": "32b67a06-e631-4121-94ac-7f1ef6e44645",
      "vehicle_status": "delivered",
      "plate": "1037  ///ا ع ن 6730",
      "customer": "1037  ا///اياس حمود العقيلي",
      "total": 50.0,
      "paid_allocated": 0.0,
      "remaining": 50.0
    },
    {
      "operation_id": "fd598837-6a9c-49d3-a047-9ca90f38f197",
      "vehicle_id": "5b1843a1-d934-4f09-bd82-f150786397ef",
      "vehicle_status": "delivered",
      "plate": "ر ح ن 6278",
      "customer": "نايف المقحم",
      "total": 5380.0,
      "paid_allocated": 0.0,
      "remaining": 5380.0
    },
    {
      "operation_id": "bbdf0bdd-3324-4803-bd9f-ff3f0680390d",
      "vehicle_id": "f0aacb00-839b-46ef-a9c2-21ba5515c723",
      "vehicle_status": "delivered",
      "plate": "ا ك ا 8218",
      "customer": "نايف المطيري البدائع ",
      "total": 350.0,
      "paid_allocated": 0.0,
      "remaining": 350.0
    },
    {
      "operation_id": "4c1ee5de-8fb0-425e-a3cc-7d9174955428",
      "vehicle_id": "604576c6-90ab-421a-8000-bd81e9c56e29",
      "vehicle_status": "delivered",
      "plate": "ا ا د 506",
      "customer": "علي اليحيى",
      "total": 890.0,
      "paid_allocated": 0.0,
      "remaining": 890.0
    },
    {
      "operation_id": "3276012a-80fb-43d7-aac3-3bc1093ad31b",
      "vehicle_id": "00a8d7b2-40e3-4848-9201-c75996906220",
      "vehicle_status": "delivered",
      "plate": "ا ن ق 4011",
      "customer": "غلام باكستاني",
      "total": 100.0,
      "paid_allocated": 0.0,
      "remaining": 100.0
    },
    {
      "operation_id": "f4f34aa0-d651-4b96-a3d7-41cabf37e5b9",
      "vehicle_id": "d394b77e-52fa-42e0-ab24-28539304b141",
      "vehicle_status": "delivered",
      "plate": "ب د ل 2282",
      "customer": "زياد الحربي",
      "total": 300.0,
      "paid_allocated": 0.0,
      "remaining": 300.0
    },
    {
      "operation_id": "3dab92e3-3066-47f0-94b5-a484d34c2d07",
      "vehicle_id": "54d13d80-c9a9-407b-9137-b42f9f6eb023",
      "vehicle_status": "delivered",
      "plate": "ب ع س 6247",
      "customer": "ابو عبدالله العوفي",
      "total": 1200.0,
      "paid_allocated": 0.0,
      "remaining": 1200.0
    },
    {
      "operation_id": "b48c0850-1453-4740-9639-1a99687fda67",
      "vehicle_id": "c02cc9c7-6ff5-4fc7-9414-b15787fa9000",
      "vehicle_status": "تشخيص",
      "plate": "ب ح ن 6923",
      "customer": "سلطان الشاص",
      "total": 300.0,
      "paid_allocated": 0.0,
      "remaining": 300.0
    },
    {
      "operation_id": "3acd2af5-989d-405e-b656-23d972dbfcab",
      "vehicle_id": "67b3bb9a-ee06-45ef-a071-94711c25db5f",
      "vehicle_status": "delivered",
      "plate": "ب س ص 1230",
      "customer": "عبد العزيز العتيبي",
      "total": 4000.0,
      "paid_allocated": 0.0,
      "remaining": 4000.0
    },
    {
      "operation_id": "2e371c2b-dca5-4884-8207-aa8d0b1147ad",
      "vehicle_id": "987c4fef-47ce-464e-a3e6-f5c4e1a7bdaa",
      "vehicle_status": "delivered",
      "plate": "ح م ص 1554",
      "customer": "996///راشد الربيعان ",
      "total": 130.0,
      "paid_allocated": 0.0,
      "remaining": 130.0
    },
    {
      "operation_id": "feb09cfe-b7d7-4b35-8f1d-648e037b6083",
      "vehicle_id": "8edf695c-60e8-4d65-b83d-9de0595e64f2",
      "vehicle_status": "delivered",
      "plate": "ب ن ه 3533",
      "customer": "نايف الحربي",
      "total": 2000.0,
      "paid_allocated": 0.0,
      "remaining": 2000.0
    },
    {
      "operation_id": "6c4693aa-9de6-4ddd-88b5-318b1f1ff0ba",
      "vehicle_id": "efd4ef26-2b6a-44bc-9b1b-7030ec8492f1",
      "vehicle_status": "delivered",
      "plate": "ا د ق 7737",
      "customer": "عبدالله الذياب",
      "total": 50.0,
      "paid_allocated": 0.0,
      "remaining": 50.0
    },
    {
      "operation_id": "ca32e1a6-a0d5-46f0-b2c0-ede7439c1da0",
      "vehicle_id": "0ee51492-8405-4235-8c63-4ca01b6bccc8",
      "vehicle_status": null,
      "plate": "ا ل و 7121",
      "customer": "عاصم التويجري",
      "total": 150.0,
      "paid_allocated": 0.0,
      "remaining": 150.0
    },
    {
      "operation_id": "38478ae1-3f3a-4666-ad14-4477eb34583a",
      "vehicle_id": "945e9f2c-02f7-4883-960e-21a47bf33654",
      "vehicle_status": "delivered",
      "plate": "ب ق ه 7484",
      "customer": "ابراهيم القبيشي",
      "total": 4000.0,
      "paid_allocated": 0.0,
      "remaining": 4000.0
    },
    {
      "operation_id": "817430ba-f4ba-4ec1-8928-0fb965d67aae",
      "vehicle_id": "b433407c-0172-4587-8ba2-2de2f24a4307",
      "vehicle_status": "delivered",
      "plate": "ا ص ط 6365",
      "customer": "ماجد الرشيدي",
      "total": 1700.0,
      "paid_allocated": 0.0,
      "remaining": 1700.0
    },
    {
      "operation_id": "f441c5f2-9365-4fc5-928e-2182224b9311",
      "vehicle_id": "2430aecb-6b36-4abc-9eb8-963faa3339cd",
      "vehicle_status": "delivered",
      "plate": "كويت 15/55256",
      "customer": "ماجد العنزي ",
      "total": 4300.0,
      "paid_allocated": 0.0,
      "remaining": 4300.0
    },
    {
      "operation_id": "df718c5c-dcaf-400a-ace6-695ff4491ead",
      "vehicle_id": "680106d7-c9b5-43f6-9229-4df9f7f7a582",
      "vehicle_status": "delivered",
      "plate": "ب ي ط 7538",
      "customer": "د خالد الراجح",
      "total": 3500.0,
      "paid_allocated": 0.0,
      "remaining": 3500.0
    },
    {
      "operation_id": "33e2870f-f74c-4738-bf23-9b377112c90f",
      "vehicle_id": "3f4d770d-73d3-43e8-b4ea-4ca50219fe65",
      "vehicle_status": "delivered",
      "plate": "ا ب و  1266",
      "customer": "ابو عبدالله ",
      "total": 100.0,
      "paid_allocated": 0.0,
      "remaining": 100.0
    },
    {
      "operation_id": "c09dba75-105d-4e63-b9e6-fc4c021e8260",
      "vehicle_id": "ca81024e-195b-464e-9671-0f532aad1545",
      "vehicle_status": "delivered",
      "plate": "ب ح ر 7042",
      "customer": "997///محمد شعبان",
      "total": 50.0,
      "paid_allocated": 0.0,
      "remaining": 50.0
    },
    {
      "operation_id": "3a9fe0ce-e179-43f6-b555-fe2f593a3a9d",
      "vehicle_id": "44d8587d-5524-43ab-aa32-b4bb0de023dd",
      "vehicle_status": "delivered",
      "plate": "ح ل ه 5177",
      "customer": "خالد الربيش ",
      "total": 4500.0,
      "paid_allocated": 0.0,
      "remaining": 4500.0
    },
    {
      "operation_id": "3df2e7b7-0a44-41ae-ba3d-28d7a25f2810",
      "vehicle_id": "945244d1-5997-4052-84dd-d0ea02607f4e",
      "vehicle_status": "delivered",
      "plate": "اه د  6464",
      "customer": "ابو تميم ",
      "total": 40.0,
      "paid_allocated": 0.0,
      "remaining": 40.0
    },
    {
      "operation_id": "72ccd3b0-f63b-4efc-957a-30c92aa163cf",
      "vehicle_id": "c5bfe993-c45a-4412-b196-be1cdd310c40",
      "vehicle_status": null,
      "plate": "ا ص ص 7293",
      "customer": "عبد الكريم الشايعي ",
      "total": 800.0,
      "paid_allocated": 0.0,
      "remaining": 800.0
    },
    {
      "operation_id": "104c0779-88f8-475e-b167-a5fc71bcce6e",
      "vehicle_id": "f3422cc1-dd9c-4e69-8205-0aa50b3795a1",
      "vehicle_status": "delivered",
      "plate": "قطر 278675",
      "customer": "سيف حمدان المنصوري",
      "total": 90.0,
      "paid_allocated": 0.0,
      "remaining": 90.0
    },
    {
      "operation_id": "473634cc-fc80-44c8-9714-1b2091d734a3",
      "vehicle_id": "f77ab3ea-5ea2-4cf6-8e89-1acfadef0098",
      "vehicle_status": "delivered",
      "plate": "ب ر ق 3019",
      "customer": "1009///محمد الشعيبي",
      "total": 600.0,
      "paid_allocated": 0.0,
      "remaining": 600.0
    },
    {
      "operation_id": "62e31d3a-06d8-4e3f-94dc-5d43632dcac9",
      "vehicle_id": "f58df376-b5aa-4c10-bfe0-fd38aa55b186",
      "vehicle_status": "delivered",
      "plate": " ا  ر  س  7576",
      "customer": "عميل نقدي",
      "total": 150.0,
      "paid_allocated": 0.0,
      "remaining": 150.0
    },
    {
      "operation_id": "0aff7cd4-16f5-48af-a4e1-4e22b6cf608a",
      "vehicle_id": "c80b56b3-ca07-4840-86b4-7687dd560c07",
      "vehicle_status": "delivered",
      "plate": "ب ر م 9827",
      "customer": "جاويد المخرطة ",
      "total": 4000.0,
      "paid_allocated": 0.0,
      "remaining": 4000.0
    },
    {
      "operation_id": "840b8a23-4fe3-4b97-b4b3-ddcd014acb68",
      "vehicle_id": "cf10edb0-ef41-4d09-87ea-c62c52c5b86a",
      "vehicle_status": "delivered",
      "plate": "ب ا م 8263",
      "customer": "فهد شليبيط المطيري",
      "total": 2050.0,
      "paid_allocated": 2000.0,
      "remaining": 50.0
    },
    {
      "operation_id": "bcd4ccf2-7521-4d3a-8242-4a8649676fc4",
      "vehicle_id": "59108515-b840-46dc-97d6-83673a05ea49",
      "vehicle_status": "delivered",
      "plate": "ب ص ن 2140",
      "customer": "احمد الجمعه",
      "total": 50.0,
      "paid_allocated": 0.0,
      "remaining": 50.0
    },
    {
      "operation_id": "2dd3dbae-6cc9-46b6-b72d-f76364cc36f7",
      "vehicle_id": "5b1843a1-d934-4f09-bd82-f150786397ef",
      "vehicle_status": "delivered",
      "plate": "ر ح ن 6278",
      "customer": "نايف المقحم",
      "total": 800.0,
      "paid_allocated": 0.0,
      "remaining": 800.0
    },
    {
      "operation_id": "c841307c-1fb6-452d-beef-9f4a0d6f5959",
      "vehicle_id": "fe9f4e57-8522-492b-8878-c5d1a8fa107c",
      "vehicle_status": "delivered",
      "plate": "د ك هـ 1736",
      "customer": "928///ابو احمد الدبيخي                                                                                                                                                                                                                                    ",
      "total": 300.0,
      "paid_allocated": 0.0,
      "remaining": 300.0
    },
    {
      "operation_id": "87a7e860-d0b0-45ea-a854-1278a4fbfb23",
      "vehicle_id": "8cac2ba9-ce30-4042-9fbf-fcb3186177b4",
      "vehicle_status": "delivered",
      "plate": "1040 /// د ل ك 5248",
      "customer": "1040  /// خضير الخضيري",
      "total": 450.0,
      "paid_allocated": 0.0,
      "remaining": 450.0
    },
    {
      "operation_id": "a93a70b8-ad73-4477-b63d-2c2b7dd4c00c",
      "vehicle_id": "020dcc0a-5ebf-4900-b837-388e33d3b915",
      "vehicle_status": "delivered",
      "plate": "د ك ه 1736",
      "customer": "ابو احمد الدبيخي",
      "total": 50.0,
      "paid_allocated": 0.0,
      "remaining": 50.0
    },
    {
      "operation_id": "43a736a3-efa0-41cf-be96-b1ca30256b6c",
      "vehicle_id": "c61c7020-daf9-4a59-9a86-22ae2a9a12fd",
      "vehicle_status": "delivered",
      "plate": "ا ب ق 9252",
      "customer": "ابو فيصل",
      "total": 400.0,
      "paid_allocated": 0.0,
      "remaining": 400.0
    },
    {
      "operation_id": "f395e31a-0b92-4781-92cc-5c02f5b0127f",
      "vehicle_id": "c86260bc-8a43-4820-975f-2cbb5305ed1d",
      "vehicle_status": "delivered",
      "plate": "ا ص د 8685",
      "customer": "ابو تركي العوفي ",
      "total": 350.0,
      "paid_allocated": 0.0,
      "remaining": 350.0
    },
    {
      "operation_id": "b1305e60-4c05-4c10-bbf7-185601cbe66c",
      "vehicle_id": "61fe0b56-aa66-490d-a5e7-6f3b8195ed56",
      "vehicle_status": null,
      "plate": "ا ح ا 5110",
      "customer": "محمد الحربي ",
      "total": 600.0,
      "paid_allocated": 0.0,
      "remaining": 600.0
    },
    {
      "operation_id": "6973ed6f-8895-42cf-ad24-331832ebef96",
      "vehicle_id": "c92405eb-2097-4f42-aa3e-ccd455d9812f",
      "vehicle_status": "diagnosis",
      "plate": "   1046  /// ب ص ر 6431",
      "customer": "   1046 ///صالح القصير",
      "total": 500.0,
      "paid_allocated": 0.0,
      "remaining": 500.0
    },
    {
      "operation_id": "b666d607-dfde-46e4-b221-0dab4111d0bc",
      "vehicle_id": "8c99b2ba-cfb2-4e75-af18-2a45d29a3a16",
      "vehicle_status": "delivered",
      "plate": "1041  ///  ب ط ع  1676",
      "customer": "1041///  اسامه السوداني ",
      "total": 400.0,
      "paid_allocated": 0.0,
      "remaining": 400.0
    },
    {
      "operation_id": "0dd49396-8748-4276-8272-2fc5ec70ff09",
      "vehicle_id": "bd714910-1e07-40b4-b4e7-5c6cc98a6d1d",
      "vehicle_status": "delivered",
      "plate": "ب ص ر 303",
      "customer": "سلطان الصالح",
      "total": 285.0,
      "paid_allocated": 200.0,
      "remaining": 85.0
    },
    {
      "operation_id": "e83a015b-1579-4138-b5ed-84bb6b380763",
      "vehicle_id": "073d6ec7-53f7-4f64-b251-e4cf75cd6356",
      "vehicle_status": "delivered",
      "plate": "1043  ///  ب س ك 6549",
      "customer": "1043  /// مجاهد العبدالله                                                                                                                                   ",
      "total": 700.0,
      "paid_allocated": 0.0,
      "remaining": 700.0
    },
    {
      "operation_id": "99970dc5-5e16-481f-a925-65cce2d374f7",
      "vehicle_id": "5287aa8d-2969-48ed-bc5e-2ca0f97a03a3",
      "vehicle_status": "delivered",
      "plate": "1060 ///  ب ص م  7782",
      "customer": "1060 /// ابو ياسر الزويد",
      "total": 2300.0,
      "paid_allocated": 0.0,
      "remaining": 2300.0
    },
    {
      "operation_id": "6f733df9-1d6a-402f-95d1-e70a44509af6",
      "vehicle_id": "67787800-50d1-4184-a26d-f1ba8db3fcf8",
      "vehicle_status": "delivered",
      "plate": " 1052  // ا س ص 1977",
      "customer": "1051 /// عبدالرحمن العمرو",
      "total": 1300.0,
      "paid_allocated": 700.0,
      "remaining": 600.0
    },
    {
      "operation_id": "6484969a-7714-43f8-b0b9-782c915b8abc",
      "vehicle_id": "a57b698d-752d-43bf-be66-41a0337de9eb",
      "vehicle_status": "ready",
      "plate": "ب ر ق 4806",
      "customer": "ابراهيم صالح ",
      "total": 1800.0,
      "paid_allocated": 0.0,
      "remaining": 1800.0
    },
    {
      "operation_id": "20cc3c86-2b08-4244-9a4b-8519f8196add",
      "vehicle_id": "27fe3a2a-f3ac-443e-8c93-461c0046af63",
      "vehicle_status": "delivered",
      "plate": "1065 /// ح د ط  7811",
      "customer": "صالح المحيميمد ",
      "total": 3070.0,
      "paid_allocated": 0.0,
      "remaining": 3070.0
    }
  ],
  "difference_210_revenue_041": [
    {
      "journal_id": "940b4786-85ac-4ae9-91b9-16a7178eca01",
      "amount": 210.0,
      "source": "operation",
      "reference_id": "ef0a3030-d377-4a96-ba7f-acf302cf3ad4",
      "operation_id": "ef0a3030-d377-4a96-ba7f-acf302cf3ad4",
      "vehicle_id": "6f17d9b6-1683-45fd-919e-8897aca46600",
      "vehicle_status": "delivered",
      "plate": "1062 /// ب ع ا 9069",
      "customer": "1059  /// عطية (فهد الشعيبي)",
      "operation_total": 1523.0,
      "description": "عملية من الزيارة ef0a3030"
    }
  ],
  "opening_balances": [
    {
      "journal_id": "033d9832-6b01-47ed-983a-23ce56191cd6",
      "reference_id": "opening-شاص 2019",
      "ar_net": 16000.0,
      "description": "قيد تصحيحي — رصيد افتتاحي ذمم ما قبل النظام [PARTY:شاص 2019]"
    },
    {
      "journal_id": "b736be49-3367-4b05-bbf1-96d6b6c7db44",
      "reference_id": "opening-عمر الخضيري",
      "ar_net": 300.0,
      "description": "قيد تصحيحي — رصيد افتتاحي ذمم ما قبل النظام [PARTY:عمر الخضيري]"
    }
  ]
}
```

## 8) سجلات مشكوك/غير مرتبطة

```json
[
  {
    "journal_id": "6f8e2836-ac97-4e55-9e76-b812e3042ffe",
    "source": "operation",
    "reference_id": "2fa1bd0a-9b77-43da-8944-9680a3671f94",
    "vehicle_id": "235cb00f-facb-46aa-a4eb-8db039ec21ee",
    "operation_id": "2fa1bd0a-9b77-43da-8944-9680a3671f94",
    "visit_id": "2fa1bd0a-9b77-43da-8944-9680a3671f94",
    "total": 877.0,
    "reason": "vehicle_id موجود في قائمة لوحة التحكم الحالية وفي حالة أرشيفية/مسلمة",
    "description": "عملية من الزيارة 2fa1bd0a"
  },
  {
    "journal_id": "8abbce80-3c88-4db0-b08d-35e953327eb3",
    "source": "operation",
    "reference_id": "822ca57a-2cd2-4b2f-84c6-f5001170ce73",
    "vehicle_id": "235cb00f-facb-46aa-a4eb-8db039ec21ee",
    "operation_id": "822ca57a-2cd2-4b2f-84c6-f5001170ce73",
    "visit_id": "822ca57a-2cd2-4b2f-84c6-f5001170ce73",
    "total": 1000.0,
    "reason": "vehicle_id موجود في قائمة لوحة التحكم الحالية وفي حالة أرشيفية/مسلمة",
    "description": "عملية من الزيارة 822ca57a"
  }
]
```

## 9) خريطة مسارات الكتابة الحالية

- **vehicle_file_visit_save**: Frontend VehicleDetails.jsx -> PUT /api/visits/{visit_id}; payments currently can POST /api/finance/journal-entries directly; visit_sync may mirror notes into operations.
- **operations_page_create_edit_delete**: Frontend Operations.jsx -> POST/PUT/DELETE /api/operations; backend routes_extended.py creates operations + journal_entries and deletes by reference_id.
- **smart_pos**: SmartPOSJournal.jsx: collect_customer uses /operations/{op_id}/confirm-payment; other POS templates POST /operations; bank_deposit/manual can POST /finance/journal-entries.
- **katrina**: core/action_runtime.py creates operation and journal; approved external_operation routes back to routes_extended.create_operation; external_operation_payment routes to confirm_operation_payment.
- **finance_reports**: routes_finance.py reads journal_entries and operations separately; current reports do not apply vehicle archive/live reporting_scope consistently.

## 10) نموذج المحرك المالي الموحد وخطة الترحيل

```json
{
  "model": {
    "origin_type": "vehicle_visit | standalone_pos_sale | purchase | receipt | opening_balance | manual_adjustment",
    "origin_id": "معرف المستند الأصلي",
    "vehicle_id": "معرف المركبة إن وجد",
    "visit_id": "معرف الزيارة إن وجد",
    "entry_channel": "vehicle_file | operations_page | smart_pos | katrina",
    "event_type": "sale_posted | credit_posted | payment_applied | expense_posted | reversal_posted",
    "idempotency_key": "معرف فريد لمنع التكرار",
    "reporting_scope": "live | archive | legacy_excluded | unlinked"
  },
  "plan": [
    "إضافة طبقة قراءة reconciliation فقط أولاً",
    "إضافة أعمدة/جدول financial_events دون تعديل القيود القديمة",
    "ربط events بالـ operations/journal_entries عبر origin_id وreversal_of",
    "تشغيل shadow reports ومقارنتها بالصفحات",
    "بعد اعتماد الأرقام: تحويل الواجهات للكتابة عبر المحرك فقط",
    "عدم حذف القيود القديمة؛ أي تصحيح يتم بقيد عكسي reversal_of"
  ],
  "acceptance_tests": [
    "إنشاء بيع آجل من ملف مركبة يظهر مرة واحدة في العمليات والذمم والدفتر",
    "تأكيد سداد جزئي يخفض الذمم ويرفع نقد/نقاط بيع/تحويل ولا يرفع الإيراد",
    "تكرار الطلب بنفس idempotency_key لا ينشئ قيداً ثانياً",
    "أرشفة مركبة تستبعد الأصل والدفعات والخصومات من live reports وتبقيها في archive reports",
    "استعادة مركبة تعيد مبالغها للحسبة مرة واحدة",
    "POS مستقل بلا مركبة يبقى في live",
    "POS مرتبط بمركبة مؤرشفة يصنف archive",
    "تعديل عملية مصدرها زيارة يحدّث origin وليس نسخة منفصلة"
  ]
}
```