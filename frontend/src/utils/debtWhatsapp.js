import { getWhatsAppLink } from './constants';

export const normalizeWhatsAppPhone = (phone) =>
  String(phone || '')
    .replace(/[^\d+]/g, '')
    .replace(/^\+/, '')
    .replace(/^0+/, '');

export const buildDebtWhatsAppMessage = (entity, entityType) => {
  const name = entity?.name || 'العميل';
  const debit = Number(entity?.debitBalance || 0);
  const credit = Number(entity?.creditBalance || 0);
  const ajel = Number(entity?.ajelBalance || entity?.overdueBalance || 0);
  const settled = Number(entity?.settledAmount || 0);
  const net = debit - credit || ajel;
  const typeLabel = entityType === 'supplier' ? 'المورد' : 'العميل';
  const fmt = (n) => Number(n || 0).toLocaleString('ar-SA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const today = new Date().toLocaleDateString('ar-SA');

  const lines = [
    `السلام عليكم ${name} 🌟`,
    `كشف حساب ${typeLabel} — ${today}`,
    '━━━━━━━━━━━━━━━',
  ];
  if (debit > 0) lines.push(`• إجمالي المستحق (مدين): ${fmt(debit)} ر.س`);
  if (credit > 0) lines.push(`• دفعات/رصيد دائن: ${fmt(credit)} ر.س`);
  if (ajel > 0) lines.push(`• آجل مستحق حالياً: ${fmt(ajel)} ر.س`);
  if (settled > 0) lines.push(`• إجمالي ما تم سداده: ${fmt(settled)} ر.س`);
  lines.push('━━━━━━━━━━━━━━━');
  lines.push(`💰 الرصيد المستحق: ${fmt(Math.abs(net))} ر.س`);
  lines.push('');
  lines.push('نأمل مراجعة الرصيد والتواصل معنا لإتمام التسوية. شاكرين تعاونكم 🙏');
  return lines.join('\n');
};

export const buildDebtWhatsAppDraft = (entity, entityType) => {
  const phone = normalizeWhatsAppPhone(entity?.phone || entity?.whatsapp || '');
  const message = buildDebtWhatsAppMessage(entity, entityType);
  return {
    id: `${entityType}-${entity?.id || entity?.name || Math.random().toString(36).slice(2)}`,
    entityId: entity?.id,
    entityType,
    name: entity?.name || '-',
    phone,
    message,
    url: phone ? getWhatsAppLink(phone, message) : '',
  };
};
