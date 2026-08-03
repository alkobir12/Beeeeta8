import React, { useState, useEffect } from 'react';
import { resolveBackendBase } from '../utils/backendBase';
import {
  FolderTree,
  Plus,
  Search,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Edit2,
  Trash2,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wallet,
  Power,
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

const formatCurrency = (amount) => {
  return new Intl.NumberFormat('ar-SA', {
    style: 'currency',
    currency: 'SAR',
    minimumFractionDigits: 2,
  }).format(amount || 0);
};

// Default Saudi Chart of Accounts - يُستخدم فقط إذا لم يكن هناك بيانات في API
const DEFAULT_ACCOUNTS = [
  // بيانات افتراضية فارغة
];

export default function ChartOfAccounts() {
  const { toast } = useToast();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingAccount, setSavingAccount] = useState(false);
  const [saveAccountError, setSaveAccountError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedAccounts, setExpandedAccounts] = useState(['header-asset', 'header-liability', 'header-equity', 'header-revenue', 'header-expense']);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedParent, setSelectedParent] = useState(null);
  const [editingAccount, setEditingAccount] = useState(null);
  const [savingEditAccount, setSavingEditAccount] = useState(false);
  const [editAccountError, setEditAccountError] = useState('');
  const [deletingAccountId, setDeletingAccountId] = useState('');
  const [togglingAccountId, setTogglingAccountId] = useState('');

  const sessionRole = (() => {
    try {
      const session = JSON.parse(localStorage.getItem('session') || '{}');
      return String(session?.role || '').toLowerCase();
    } catch {
      return '';
    }
  })();
  const sessionUserId = (() => {
    try {
      const session = JSON.parse(localStorage.getItem('session') || '{}');
      return String(session?.id || session?.userId || session?.name || 'manager').trim() || 'manager';
    } catch {
      return 'manager';
    }
  })();
  const canManageAccounts = ['admin', 'manager'].includes(sessionRole);

  const ensureManagerAccess = () => {
    if (canManageAccounts) return true;
    toast({ title: 'صلاحيات غير كافية', description: 'هذه العملية متاحة للمدير فقط', variant: 'destructive' });
    return false;
  };

  const getAuthHeaders = () => ({
    'Content-Type': 'application/json',
    'x-user-role': sessionRole,
    'x-user-id': sessionUserId,
  });

  // جلب الحسابات من الـ API عند تحميل الصفحة
  useEffect(() => {
    fetchAccounts();
    // 🔄 إعادة التحميل عند أي عملية مالية تؤثر على أرصدة الحسابات
    const onFinUpdated = () => fetchAccounts();
    window.addEventListener('finance:updated', onFinUpdated);
    return () => window.removeEventListener('finance:updated', onFinUpdated);
  }, []);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
      const [chartResponse, statusResponse] = await Promise.all([
        fetch(`${API_URL}/finance/chart-of-accounts?workshop_id=${workshopId}`),
        fetch(`${API_URL}/accounts/status-overrides`).catch(() => null),
      ]);
      const data = await chartResponse.json();
      const statusPayload = statusResponse ? await statusResponse.json().catch(() => ({})) : {};
      const statusOverrides = statusPayload?.overrides || {};
      
      if (data.success && data.data) {
        // تحويل البيانات من الـ API إلى format الصفحة
        const transformedAccounts = [];
        const accountsByType = {
          asset: [],
          liability: [],
          equity: [],
          revenue: [],
          expense: []
        };
        
        // تصنيف الحسابات حسب النوع
        data.data.forEach(acc => {
          const type = ['asset', 'liability', 'equity', 'revenue', 'expense'].includes(acc.type) ? acc.type : 'asset';
          if (accountsByType[type]) {
            accountsByType[type].push({
              id: acc.id || acc.code,
              code: acc.code,
              name_ar: acc.name_ar || acc.name,
              type: type,
              category: acc.category,
              parent_id: acc.parent_id || acc.parentAccount || acc.parentId || null,
              current_balance: acc.balance || 0,
              active: statusOverrides[String(acc.id || acc.code)] !== false,
            });
          }
        });
        
        // بناء شجرة الحسابات مع headers
        // استخدام IDs فريدة للـ headers لتجنب التعارض مع IDs الحسابات من الـ API
        if (accountsByType.asset.length > 0) {
          transformedAccounts.push({
            id: 'header-asset', code: '1', name_ar: 'الأصول', type: 'asset', 
            category: null, parent_id: null, current_balance: 0, isExpanded: true, active: true
          });
          accountsByType.asset.forEach(acc => {
            if (!acc.parent_id) acc.parent_id = 'header-asset';
            transformedAccounts.push(acc);
          });
        }
        
        if (accountsByType.liability.length > 0) {
          transformedAccounts.push({
            id: 'header-liability', code: '2', name_ar: 'الالتزامات', type: 'liability',
            category: null, parent_id: null, current_balance: 0, isExpanded: true, active: true
          });
          accountsByType.liability.forEach(acc => {
            if (!acc.parent_id) acc.parent_id = 'header-liability';
            transformedAccounts.push(acc);
          });
        }
        
        if (accountsByType.equity.length > 0) {
          transformedAccounts.push({
            id: 'header-equity', code: '3', name_ar: 'حقوق الملكية', type: 'equity',
            category: null, parent_id: null, current_balance: 0, isExpanded: true, active: true
          });
          accountsByType.equity.forEach(acc => {
            if (!acc.parent_id) acc.parent_id = 'header-equity';
            transformedAccounts.push(acc);
          });
        }
        
        if (accountsByType.revenue.length > 0) {
          transformedAccounts.push({
            id: 'header-revenue', code: '4', name_ar: 'الإيرادات', type: 'revenue',
            category: null, parent_id: null, current_balance: 0, isExpanded: true, active: true
          });
          accountsByType.revenue.forEach(acc => {
            if (!acc.parent_id) acc.parent_id = 'header-revenue';
            transformedAccounts.push(acc);
          });
        }
        
        if (accountsByType.expense.length > 0) {
          transformedAccounts.push({
            id: 'header-expense', code: '5', name_ar: 'المصروفات', type: 'expense',
            category: null, parent_id: null, current_balance: 0, isExpanded: true, active: true
          });
          accountsByType.expense.forEach(acc => {
            if (!acc.parent_id) acc.parent_id = 'header-expense';
            transformedAccounts.push(acc);
          });
        }
        
        setAccounts(transformedAccounts.length > 0 ? transformedAccounts : []);
      } else {
        // لا يوجد بيانات - عرض صفحة فارغة
        setAccounts([]);
      }
    } catch (error) {
      console.error('Error fetching chart of accounts:', error);
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  };

  const createAccount = async (payload) => {
    if (!ensureManagerAccess()) return;
    try {
      setSavingAccount(true);
      setSaveAccountError('');
      const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';

      const response = await fetch(`${API_URL}/finance/chart-of-accounts?workshop_id=${workshopId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success) {
        throw new Error(data?.detail || data?.error || data?.message || 'تعذر حفظ الحساب');
      }

      await fetchAccounts();
      if (payload.type) {
        const headerId = `header-${payload.type}`;
        setExpandedAccounts((prev) => (prev.includes(headerId) ? prev : [...prev, headerId]));
      }
      setShowAddModal(false);
      setSelectedParent(null);
      toast({ title: 'تم الحفظ', description: 'تم إنشاء الحساب بنجاح' });
    } catch (error) {
      setSaveAccountError(error?.message || 'تعذر حفظ الحساب');
      toast({ title: 'فشل الحفظ', description: error?.message || 'تعذر حفظ الحساب', variant: 'destructive' });
    } finally {
      setSavingAccount(false);
    }
  };

  const isHeaderAccount = (accountId) => String(accountId || '').startsWith('header-');
  const normalizeParentIdForApi = (parentIdValue) => {
    const value = parentIdValue || null;
    if (!value) return null;
    return isHeaderAccount(value) ? null : value;
  };

  const updateAccountById = async (accountId, payload) => {
    const response = await fetch(`${API_URL}/accounts/${accountId}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    let data = {};
    try {
      data = await response.json();
    } catch (parseErr) {
      console.warn('Response JSON parse failed:', parseErr);
    }
    if (!response.ok) {
      throw new Error(data?.detail || data?.error || data?.message || 'تعذر تحديث الحساب');
    }
    return data;
  };

  const trySmartAutoResolveUpdate = async (payload, currentAccountId, workshopId) => {
    try {
      const response = await fetch(`${API_URL}/finance/chart-of-accounts?workshop_id=${workshopId}`);
      const data = await response.json().catch(() => ({}));
      const rows = Array.isArray(data?.data) ? data.data : [];

      const normalize = (v) => String(v || '').trim().toLowerCase();
      const targetName = normalize(payload.name);
      const targetType = normalize(payload.type);
      const targetCode = String(payload.code || '').trim();

      const byNameAndType = rows.find((acc) => (
        String(acc?.id || '') !== String(currentAccountId || '')
        && normalize(acc?.name_ar || acc?.name) === targetName
        && normalize(acc?.type) === targetType
      ));

      const byCode = rows.find((acc) => (
        String(acc?.id || '') !== String(currentAccountId || '')
        && String(acc?.code || '').trim() === targetCode
      ));

      const candidates = [byNameAndType, byCode].filter(Boolean);
      if (!candidates.length) return false;

      for (const candidate of candidates) {
        try {
          await updateAccountById(candidate.id, payload);
          return true;
        } catch (error) {
          if (payload.code) {
            const { code, ...withoutCodePayload } = payload;
            try {
              await updateAccountById(candidate.id, withoutCodePayload);
              return true;
            } catch (_e) {
              // ignore and continue
            }
          }
        }
      }

      return false;
    } catch (_error) {
      return false;
    }
  };

  const saveEditedAccount = async (formValues) => {
    if (!editingAccount?.id) return;
    if (!ensureManagerAccess()) return;

    try {
      setSavingEditAccount(true);
      setEditAccountError('');
      const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';

      const payload = {
        code: String(formValues.code || '').trim(),
        name: String(formValues.name_ar || formValues.name || '').trim(),
        nameEn: String(formValues.name_en || '').trim(),
        type: formValues.type || 'asset',
        parentId: normalizeParentIdForApi(formValues.parent_id),
        balance: Number(formValues.current_balance || 0),
      };

      await updateAccountById(editingAccount.id, payload);
      await fetchAccounts();
      setShowEditModal(false);
      setEditingAccount(null);
      toast({ title: 'تم التحديث', description: 'تم تحديث الحساب بنجاح' });
    } catch (error) {
      const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
      const autoResolved = await trySmartAutoResolveUpdate(
        {
          code: String(formValues.code || '').trim(),
          name: String(formValues.name_ar || formValues.name || '').trim(),
          nameEn: String(formValues.name_en || '').trim(),
          type: formValues.type || 'asset',
          parentId: normalizeParentIdForApi(formValues.parent_id),
          balance: Number(formValues.current_balance || 0),
        },
        editingAccount.id,
        workshopId,
      );

      if (autoResolved) {
        await fetchAccounts();
        setShowEditModal(false);
        setEditingAccount(null);
        toast({ title: 'تم التحديث تلقائياً', description: 'تم حل التعارض وتحديث الحساب بنجاح' });
        return;
      }

      setEditAccountError(error?.message || 'تعذر تحديث الحساب');
      toast({ title: 'فشل التحديث', description: error?.message || 'تعذر تحديث الحساب', variant: 'destructive' });
    } finally {
      setSavingEditAccount(false);
    }
  };

  const openAddAccountModal = (parentAccount = null) => {
    if (!ensureManagerAccess()) return;
    setSelectedParent(parentAccount);
    setSaveAccountError('');
    setShowAddModal(true);
  };

  const toggleAccountActive = async (account) => {
    if (!ensureManagerAccess()) return;
    if (!account?.id || isHeaderAccount(account.id)) return;

    try {
      setTogglingAccountId(account.id);
      const response = await fetch(`${API_URL}/accounts/${account.id}/active`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ isActive: !(account.active !== false) }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data?.success === false) {
        throw new Error(data?.detail || data?.error || data?.message || 'تعذر تحديث حالة الحساب');
      }

      await fetchAccounts();
      toast({
        title: 'تم التحديث',
        description: account.active === false ? 'تم تفعيل الحساب' : 'تم تعطيل الحساب',
      });
    } catch (error) {
      toast({ title: 'فشل التحديث', description: error?.message || 'تعذر تحديث حالة الحساب', variant: 'destructive' });
    } finally {
      setTogglingAccountId('');
    }
  };

  const deleteAccountById = async (account) => {
    if (!ensureManagerAccess()) return;
    if (!account?.id || isHeaderAccount(account.id)) return;

    const confirmed = window.confirm(`هل أنت متأكد من حذف الحساب "${account.name_ar}"؟`);
    if (!confirmed) return;

    const finalConfirm = window.prompt('اكتب "حذف" للتأكيد النهائي', '');
    if (finalConfirm !== 'حذف') {
      toast({ title: 'تم الإلغاء', description: 'لم يتم حذف الحساب' });
      return;
    }

    try {
      setDeletingAccountId(account.id);
      const response = await fetch(`${API_URL}/accounts/${account.id}`, {
        method: 'DELETE',
        headers: { 'x-user-role': sessionRole },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data?.success === false) {
        throw new Error(data?.detail || data?.error || data?.message || 'تعذر حذف الحساب');
      }

      await fetchAccounts();
      toast({ title: 'تم الحذف', description: 'تم حذف الحساب بنجاح' });
    } catch (error) {
      toast({ title: 'فشل الحذف', description: error?.message || 'تعذر حذف الحساب', variant: 'destructive' });
    } finally {
      setDeletingAccountId('');
    }
  };

  const getAccountTypeInfo = (type) => {
    const types = {
      asset: { label: 'أصول', color: 'text-blue-400', bgColor: 'bg-blue-900/30', icon: Wallet },
      liability: { label: 'التزامات', color: 'text-red-400', bgColor: 'bg-red-900/30', icon: TrendingDown },
      equity: { label: 'حقوق ملكية', color: 'text-purple-400', bgColor: 'bg-purple-900/30', icon: DollarSign },
      revenue: { label: 'إيرادات', color: 'text-green-400', bgColor: 'bg-green-900/30', icon: TrendingUp },
      expense: { label: 'مصروفات', color: 'text-orange-400', bgColor: 'bg-orange-900/30', icon: TrendingDown },
    };
    return types[type] || types.asset;
  };

  const toggleExpand = (accountId) => {
    setExpandedAccounts(prev => 
      prev.includes(accountId) 
        ? prev.filter(id => id !== accountId)
        : [...prev, accountId]
    );
  };

  const getChildren = (parentId) => {
    return accounts.filter(acc => acc.parent_id === parentId);
  };

  const hasChildren = (accountId) => {
    return accounts.some(acc => acc.parent_id === accountId);
  };

  const filteredAccounts = accounts.filter(acc => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return acc.name_ar.toLowerCase().includes(query) || acc.code.includes(query);
  });

  const renderAccount = (account, level = 0) => {
    // منع infinite recursion
    if (level > 5) return null;
    if (!account || !account.id) return null;
    
    const children = getChildren(account.id);
    const isExpanded = expandedAccounts.includes(account.id);
    const typeInfo = getAccountTypeInfo(account.type);
    const TypeIcon = typeInfo.icon;

    // Skip if not matching search and no children match
    if (searchQuery && !filteredAccounts.find(a => a.id === account.id)) {
      const hasMatchingChild = children.some(child => 
        filteredAccounts.find(a => a.id === child.id)
      );
      if (!hasMatchingChild) return null;
    }

    return (
      <div key={account.id}>
        <div 
          className={`flex items-center gap-3 py-3 px-4 hover:bg-gray-700/30 transition-colors border-b border-gray-700/50 ${level > 0 ? 'bg-gray-800/30' : ''} ${account.active === false ? 'opacity-55' : ''}`}
          style={{ paddingRight: `${level * 24 + 16}px` }}
          data-testid={`account-row-${account.id}`}
        >
          {/* Expand/Collapse Button */}
          <button
            onClick={() => toggleExpand(account.id)}
            className={`p-1 rounded transition-colors ${hasChildren(account.id) ? 'hover:bg-gray-600' : 'invisible'}`}
          >
            {isExpanded ? (
              <ChevronDown size={16} className="text-gray-400" />
            ) : (
              <ChevronRight size={16} className="text-gray-400" />
            )}
          </button>

          {/* Account Code */}
          <span className="font-mono text-sm text-gray-500 w-16">{account.code}</span>

          {/* Account Type Icon */}
          <div className={`p-1.5 rounded ${typeInfo.bgColor}`}>
            <TypeIcon size={14} className={typeInfo.color} />
          </div>

          {/* Account Name */}
          <span className="flex-1 font-medium text-white">{account.name_ar}</span>

          <span
            className={`text-[10px] px-2 py-0.5 rounded ${account.active === false ? 'bg-red-900/40 text-red-300' : 'bg-emerald-900/40 text-emerald-300'}`}
            data-testid={`account-active-status-${account.id}`}
          >
            {account.active === false ? 'معطّل' : 'نشط'}
          </span>

          {/* Account Type Badge */}
          <span className={`text-xs px-2 py-0.5 rounded ${typeInfo.bgColor} ${typeInfo.color}`}>
            {typeInfo.label}
          </span>

          {/* Balance */}
          <span className={`font-mono text-sm w-32 text-left ${account.current_balance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {account.current_balance !== 0 ? formatCurrency(Math.abs(account.current_balance)) : '-'}
          </span>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <button 
              onClick={() => {
                openAddAccountModal(account);
              }}
              className="p-1.5 rounded hover:bg-gray-600 transition-colors disabled:opacity-50"
              title="إضافة حساب فرعي"
              data-testid={`account-add-child-${account.id}`}
              disabled={!canManageAccounts}
            >
              <Plus size={14} className="text-gray-400" />
            </button>
            <button
              className="p-1.5 rounded hover:bg-gray-600 transition-colors disabled:opacity-50"
              title="تعديل"
              data-testid={`account-edit-${account.id}`}
              onClick={() => {
                if (isHeaderAccount(account.id)) return;
                setEditingAccount(account);
                setEditAccountError('');
                setShowEditModal(true);
              }}
              disabled={isHeaderAccount(account.id) || !canManageAccounts}
            >
              <Edit2 size={14} className="text-gray-400" />
            </button>
            <button
              className="p-1.5 rounded hover:bg-gray-600 transition-colors disabled:opacity-50"
              title={account.active === false ? 'تفعيل' : 'تعطيل'}
              data-testid={`account-toggle-active-${account.id}`}
              onClick={() => toggleAccountActive(account)}
              disabled={isHeaderAccount(account.id) || togglingAccountId === account.id || !canManageAccounts}
            >
              <Power size={14} className={account.active === false ? 'text-emerald-400' : 'text-yellow-300'} />
            </button>
            <button
              className="p-1.5 rounded hover:bg-red-900/30 transition-colors disabled:opacity-50"
              title="حذف"
              data-testid={`account-delete-${account.id}`}
              onClick={() => deleteAccountById(account)}
              disabled={isHeaderAccount(account.id) || deletingAccountId === account.id || !canManageAccounts}
            >
              <Trash2 size={14} className="text-red-400" />
            </button>
          </div>
        </div>

        {/* Children */}
        {isExpanded && children.map(child => renderAccount(child, level + 1))}
      </div>
    );
  };

  // Calculate totals
  const totals = {
    assets: accounts.filter(a => a.type === 'asset' && a.current_balance !== 0).reduce((sum, a) => sum + a.current_balance, 0),
    liabilities: accounts.filter(a => a.type === 'liability' && a.current_balance !== 0).reduce((sum, a) => sum + a.current_balance, 0),
    equity: accounts.filter(a => a.type === 'equity' && a.current_balance !== 0).reduce((sum, a) => sum + a.current_balance, 0),
    revenue: accounts.filter(a => a.type === 'revenue' && a.current_balance !== 0).reduce((sum, a) => sum + a.current_balance, 0),
    expenses: accounts.filter(a => a.type === 'expense' && a.current_balance !== 0).reduce((sum, a) => sum + a.current_balance, 0),
  };
  const editableAccounts = accounts.filter((acc) => !isHeaderAccount(acc.id));

  return (
    <div className="p-6 space-y-6" data-testid="chart-of-accounts-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FolderTree className="text-blue-500" />
            دليل الحسابات
          </h1>
          <p className="text-gray-400">إدارة الحسابات المحاسبية وفقاً للنظام السعودي</p>
          <p className={`text-xs mt-1 ${canManageAccounts ? 'text-emerald-400' : 'text-amber-400'}`} data-testid="accounts-role-access-note">
            {canManageAccounts ? 'لديك صلاحية الإدارة (إضافة/تعديل/تعطيل/حذف)' : 'صلاحية العرض فقط - التعديل متاح للمدير'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              openAddAccountModal(null);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
            data-testid="add-account-btn"
            disabled={!canManageAccounts}
          >
            <Plus size={20} />
            <span>حساب جديد</span>
          </button>

          <button
            onClick={fetchAccounts}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
            data-testid="refresh-accounts-btn"
          >
            <RefreshCw size={18} />
            <span>تحديث</span>
          </button>
          
          <button
            onClick={async () => {
              if (!window.confirm('⚠️ تحذير: هل أنت متأكد من حذف جميع البيانات المالية؟\n\nسيتم حذف:\n• جميع الحسابات\n• جميع العمليات المالية\n• جميع القيود\n\nلا يمكن التراجع عن هذا الإجراء!')) {
                return;
              }
              
              const finalConfirm = window.prompt('اكتب "حذف كل شيء" للتأكيد النهائي:', '');
              if (finalConfirm !== 'حذف كل شيء') {
                alert('تم إلغاء العملية');
                return;
              }
              
              try {
                const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
                const response = await fetch(
                  `${API_URL}/finance/reset-all-data?workshop_id=${workshopId}&confirm=DELETE_ALL`,
                  { method: 'DELETE', headers: getAuthHeaders() }
                );
                const data = await response.json();
                
                if (data.success) {
                  alert('✅ تم حذف جميع البيانات المالية بنجاح!\n\nتم حذف:\n' + 
                    `• الحسابات: ${data.deleted_counts?.chart_of_accounts || 'all'}\n` +
                    `• العمليات: ${data.deleted_counts?.operations || 'all'}\n` +
                    `• القيود: ${data.deleted_counts?.journal_entries || 'all'}`
                  );
                  window.location.reload();
                } else {
                  alert('❌ فشل الحذف: ' + data.message);
                }
              } catch (error) {
                console.error('Error deleting data:', error);
                alert('❌ حدث خطأ أثناء الحذف');
              }
            }}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            title="حذف جميع البيانات المالية والبدء من الصفر"
            data-testid="reset-financial-data-button"
          >
            <Trash2 size={20} />
            <span>إعادة تعيين الكل</span>
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200">
          <div className="flex items-center justify-between mb-2">
            <Wallet className="text-blue-600" size={20} />
            <span className="text-xs font-semibold text-blue-800">الأصول</span>
          </div>
          <div className="text-2xl font-bold text-blue-900">{formatCurrency(totals.assets)}</div>
        </div>

        <div className="bg-gradient-to-br from-red-50 to-red-100 rounded-xl p-4 border border-red-200">
          <div className="flex items-center justify-between mb-2">
            <TrendingDown className="text-red-600" size={20} />
            <span className="text-xs font-semibold text-red-800">الالتزامات</span>
          </div>
          <div className="text-2xl font-bold text-red-900">{formatCurrency(totals.liabilities)}</div>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4 border border-purple-200">
          <div className="flex items-center justify-between mb-2">
            <DollarSign className="text-purple-600" size={20} />
            <span className="text-xs font-semibold text-purple-800">حقوق الملكية</span>
          </div>
          <div className="text-2xl font-bold text-purple-900">{formatCurrency(totals.equity)}</div>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-4 border border-green-200">
          <div className="flex items-center justify-between mb-2">
            <TrendingUp className="text-green-600" size={20} />
            <span className="text-xs font-semibold text-green-800">الإيرادات</span>
          </div>
          <div className="text-2xl font-bold text-green-900" data-testid="accounts-revenue-total">{formatCurrency(totals.revenue)}</div>
        </div>

        <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-xl p-4 border border-orange-200">
          <div className="flex items-center justify-between mb-2">
            <TrendingDown className="text-orange-600" size={20} />
            <span className="text-xs font-semibold text-orange-800">المصروفات</span>
          </div>
          <div className="text-2xl font-bold text-orange-900">{formatCurrency(totals.expenses)}</div>
        </div>
      </div>

      {/* Search */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
          <input
            type="text"
            placeholder="بحث بالاسم أو رقم الحساب..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pr-10 pl-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
            data-testid="search-accounts"
          />
        </div>
      </div>

      {/* Accounts Tree */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 py-3 px-4 bg-gray-700/50 border-b border-gray-600">
          <span className="w-8"></span>
          <span className="font-mono text-sm text-gray-400 w-16">الرمز</span>
          <span className="w-8"></span>
          <span className="flex-1 text-sm font-semibold text-gray-300">اسم الحساب</span>
          <span className="text-sm text-gray-400 w-20">النوع</span>
          <span className="text-sm text-gray-400 w-32 text-left">الرصيد</span>
          <span className="w-36"></span>
        </div>

        {/* Accounts List */}
        <div className="max-h-[600px] overflow-y-auto">
          {accounts.filter(acc => acc.parent_id === null).map(account => renderAccount(account))}
        </div>
      </div>

      {/* Add Account Modal */}
      {showAddModal && (
        <AddAccountModal
          parentAccount={selectedParent}
          isSubmitting={savingAccount}
          submitError={saveAccountError}
          onClose={() => {
            setShowAddModal(false);
            setSelectedParent(null);
            setSaveAccountError('');
          }}
          onAdd={createAccount}
        />
      )}

      {showEditModal && editingAccount && (
        <EditAccountModal
          key={editingAccount.id}
          account={editingAccount}
          allAccounts={editableAccounts}
          isSubmitting={savingEditAccount}
          submitError={editAccountError}
          onClose={() => {
            setShowEditModal(false);
            setEditingAccount(null);
            setEditAccountError('');
          }}
          onSave={saveEditedAccount}
        />
      )}
    </div>
  );
}

// Add Account Modal
function AddAccountModal({ parentAccount, onClose, onAdd, isSubmitting, submitError }) {
  const normalizeParentId = parentAccount?.id?.startsWith('header-') ? null : parentAccount?.id || null;
  const defaultType = parentAccount?.type || 'asset';

  const [formData, setFormData] = useState({
    code: '',
    name_ar: '',
    type: defaultType,
    category: '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    await onAdd({
      ...formData,
      name: formData.name_ar,
      parent_id: normalizeParentId,
      current_balance: 0,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl w-full max-w-md border border-gray-700">
        <div className="p-6 border-b border-gray-700">
          <h2 className="text-xl font-bold text-white">
            {parentAccount ? `إضافة حساب فرعي لـ "${parentAccount.name_ar}"` : 'إضافة حساب جديد'}
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">رمز الحساب</label>
            <input
              type="text"
              value={formData.code}
              onChange={(e) => setFormData({ ...formData, code: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
              placeholder={parentAccount?.code ? `مثال: ${parentAccount.code}01` : 'مثال: 1111'}
              required
              data-testid="add-account-code-input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">اسم الحساب</label>
            <input
              type="text"
              value={formData.name_ar}
              onChange={(e) => setFormData({ ...formData, name_ar: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
              placeholder="اسم الحساب بالعربي"
              required
              data-testid="add-account-name-input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">نوع الحساب</label>
            <select
              value={formData.type}
              onChange={(e) => setFormData({ ...formData, type: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
              data-testid="add-account-type-select"
            >
              <option value="asset">أصول</option>
              <option value="liability">التزامات</option>
              <option value="equity">حقوق ملكية</option>
              <option value="revenue">إيرادات</option>
              <option value="expense">مصروفات</option>
            </select>
          </div>

          {submitError && (
            <div className="text-sm text-red-400" data-testid="add-account-error-message">
              {submitError}
            </div>
          )}

          <div className="flex gap-3 justify-end pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg hover:bg-gray-600 text-white transition-colors"
              data-testid="add-account-cancel-btn"
              disabled={isSubmitting}
            >
              إلغاء
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              data-testid="add-account-submit-btn"
            >
              {isSubmitting ? 'جاري الحفظ...' : 'إضافة'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EditAccountModal({ account, allAccounts, onClose, onSave, isSubmitting, submitError }) {
  const [formData, setFormData] = useState({
    code: account?.code || '',
    name_ar: account?.name_ar || '',
    type: account?.type || 'asset',
    parent_id: account?.parent_id || null,
    current_balance: Number(account?.current_balance || 0),
    name_en: account?.name_en || '',
  });

  const parentOptions = (allAccounts || []).filter((acc) => String(acc.id) !== String(account?.id));

  const handleSubmit = async (e) => {
    e.preventDefault();
    await onSave(formData);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" data-testid="edit-account-modal-overlay">
      <div className="bg-gray-800 rounded-xl w-full max-w-md border border-gray-700" data-testid="edit-account-modal">
        <div className="p-6 border-b border-gray-700">
          <h2 className="text-xl font-bold text-white" data-testid="edit-account-modal-title">
            تعديل الحساب &quot;{account?.name_ar || account?.name}&quot;
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4" data-testid="edit-account-form">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">رمز الحساب</label>
            <input
              type="text"
              value={formData.code}
              onChange={(e) => setFormData({ ...formData, code: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
              required
              data-testid="edit-account-code-input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">اسم الحساب</label>
            <input
              type="text"
              value={formData.name_ar}
              onChange={(e) => setFormData({ ...formData, name_ar: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
              required
              data-testid="edit-account-name-input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">النوع</label>
            <select
              value={formData.type}
              onChange={(e) => setFormData({ ...formData, type: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
              data-testid="edit-account-type-select"
            >
              <option value="asset">أصول</option>
              <option value="liability">التزامات</option>
              <option value="equity">حقوق ملكية</option>
              <option value="revenue">إيرادات</option>
              <option value="expense">مصروفات</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">الحساب الأب</label>
            <select
              value={formData.parent_id || ''}
              onChange={(e) => setFormData({ ...formData, parent_id: e.target.value || null })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
              data-testid="edit-account-parent-select"
            >
              <option value="">بدون حساب أب</option>
              {parentOptions.map((parent) => (
                <option key={parent.id} value={parent.id}>
                  {parent.code} - {parent.name_ar}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">الرصيد</label>
            <input
              type="number"
              value={formData.current_balance}
              onChange={(e) => setFormData({ ...formData, current_balance: Number(e.target.value) })}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
              data-testid="edit-account-balance-input"
            />
          </div>

          {submitError && (
            <div className="text-sm text-red-400" data-testid="edit-account-error-message">
              {submitError}
            </div>
          )}

          <div className="flex gap-3 justify-end pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg hover:bg-gray-600 text-white transition-colors"
              data-testid="edit-account-cancel-btn"
              disabled={isSubmitting}
            >
              إلغاء
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              data-testid="edit-account-submit-btn"
            >
              {isSubmitting ? 'جاري الحفظ...' : 'حفظ التعديل'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}