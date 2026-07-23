import { useCallback, useRef, useState } from 'react';
import { renderPdfAssets } from '../utils/pdfGenerator';
import {
  base64ToBlob,
  buildShareMaterial,
  computeSealCode,
  createShareAttempt,
  getFingerprint,
  getOutputAsset,
  logShareEvent,
  resolveOutboundMessage,
  uploadOutputAsset,
} from '../services/outboundShare';

const newIdempotencyKey = () => `idem-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

export const useWhatsAppShare = () => {
  const [share, setShare] = useState({ stage: 'idle' });
  const attemptRef = useRef(null);

  const logEvent = useCallback((event, meta = {}) => {
    if (!attemptRef.current) return Promise.resolve(null);
    return logShareEvent(attemptRef.current, event, meta);
  }, []);

  const prepare = useCallback(async ({
    docType, payload = {}, workshop = {}, templateId, templateVersion, templateSelectionReason,
    getElement, phone, fileBaseName, context = '',
  }) => {
    setShare({ stage: 'preparing' });
    attemptRef.current = null;
    let attemptId = null;
    try {
      const enrichedPayload = {
        ...payload,
        workshop,
        settings: {
          ...(payload.settings || {}),
          seal_code: payload.settings?.seal_code
            || computeSealCode(payload.settings?.document_number || payload.document_number),
        },
      };
      const material = buildShareMaterial({ docType, payload: enrichedPayload, workshop, templateId, templateVersion, templateSelectionReason });

      const resolved = await resolveOutboundMessage({
        doc_type: docType,
        status: material.status,
        payload: enrichedPayload,
      });
      if (resolved.missing_variables?.length) {
        const error = new Error(`رسالة واتساب غير مكتملة. المتغيرات الناقصة: ${resolved.missing_variables.join('، ')}`);
        error.code = 'message_template_incomplete';
        error.variables = resolved.missing_variables;
        throw error;
      }

      const fp = await getFingerprint(material);

      const attemptRes = await createShareAttempt({
        doc_type: docType,
        document_number: material.document_number,
        document_version: material.document_version,
        fingerprint: fp.fingerprint,
        action_key: resolved.template?.action_key,
        template_id: resolved.template?.id,
        template_version: resolved.template?.version,
        phone: phone || resolved.phone?.raw || '',
        message_text: resolved.message,
        context,
        initial_event: 'message_prepared',
        idempotency_key: newIdempotencyKey(),
      });
      attemptId = attemptRes.attempt?.id || null;
      attemptRef.current = attemptId;

      let pdfBlob = null; let imageBlob = null; let imageDataUrl = null; let cached = false;
      if (fp.cached && fp.has_pdf) {
        const assetRes = await getOutputAsset(fp.fingerprint);
        const asset = assetRes.asset || {};
        if (asset.pdf_base64) pdfBlob = base64ToBlob(asset.pdf_base64, 'application/pdf');
        if (asset.preview_image_base64) {
          imageBlob = base64ToBlob(asset.preview_image_base64, 'image/jpeg');
          imageDataUrl = `data:image/jpeg;base64,${asset.preview_image_base64}`;
        }
        cached = true;
        await logShareEvent(attemptId, 'cache_hit', { fingerprint: fp.fingerprint });
      }
      if (!pdfBlob) {
        const target = await getElement();
        let assets;
        try {
          assets = await renderPdfAssets(target.element, { backgroundColor: '#ffffff', scale: 1.6 });
        } finally {
          target.cleanup?.();
        }
        pdfBlob = assets.pdfBlob;
        imageBlob = assets.imageBlob;
        imageDataUrl = assets.imageDataUrl;
        await logShareEvent(attemptId, 'pdf_generated', { size: String(pdfBlob?.size || 0) });
        if (imageBlob) await logShareEvent(attemptId, 'preview_image_generated', { size: String(imageBlob.size) });
        uploadOutputAsset({
          material,
          pdf_base64: assets.pdfBase64,
          preview_image_base64: assets.imageBase64,
          idempotency_key: newIdempotencyKey(),
        }).catch(() => null);
      }

      setShare({
        stage: 'ready',
        attemptId,
        fingerprint: fp.fingerprint,
        cached,
        docType,
        documentNumber: material.document_number,
        fileBaseName: fileBaseName || material.document_number || 'document',
        message: resolved.message,
        missingVariables: resolved.missing_variables || [],
        allowEdit: resolved.template?.allow_edit_before_share !== false,
        template: resolved.template,
        phone: resolved.phone,
        initialPhone: phone || resolved.phone?.raw || '',
        customerId: payload?.customer?.id || null,
        pdfBlob,
        imageBlob,
        imageDataUrl,
      });
      return { pdfBlob, imageBlob, message: resolved.message, phone: phone || resolved.phone?.raw || '', documentNumber: material.document_number };
    } catch (error) {
      const detail = error?.response?.data?.detail;
      const code = (typeof detail === 'object' ? detail?.code : null) || error?.code || 'prepare_failed';
      if (attemptId) await logShareEvent(attemptId, 'prepare_failed', { code: String(code) });
      setShare({
        stage: 'error',
        code,
        message: code === 'superseded_document'
          ? 'هذا المستند مستبدل بنسخة أحدث ولا يمكن مشاركته'
          : (typeof detail === 'object' && detail?.message) || 'تعذر تجهيز الملفات للمشاركة — حاول مرة أخرى',
      });
    }
  }, []);

  const reset = useCallback(() => {
    attemptRef.current = null;
    setShare({ stage: 'idle' });
  }, []);

  return { share, prepare, reset, logEvent };
};
