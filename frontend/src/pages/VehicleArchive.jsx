import React, { useState, useEffect, useMemo } from 'react';
import { Car, Search, Calendar, User, Phone, FileText, MoreVertical, Wrench, Trash2, History } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { useNavigate } from 'react-router-dom';
import { vehicleAPI } from '../services/api';
import { getStatusLabel, getStatusColor } from '../mock/data';
import { hasPermission } from '../utils/permissions';

const VehicleArchive = () => {
  const ARCHIVE_AUDIT_KEY = 'vehicle-archive-edit-audit-v1';
  const { toast } = useToast();
  const navigate = useNavigate();
  const session = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('session') || '{}'); } catch (e) { return {}; }
  }, []);
  const canEditArchive = hasPermission(session, 'archive', 'edit') || hasPermission(session, 'vehicles', 'edit');
  const canDeleteArchive = hasPermission(session, 'archive', 'delete') || hasPermission(session, 'vehicles', 'delete');
  const [vehicles, setVehicles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [archiveAuditRows, setArchiveAuditRows] = useState([]);

  useEffect(() => {
    fetchVehicles();
    loadArchiveAudit();
    const refresh = () => {
      fetchVehicles();
      loadArchiveAudit();
    };
    window.addEventListener('finance:updated', refresh);
    window.addEventListener('vehicleUpdated', refresh);
    window.addEventListener('vehicles:updated', refresh);
    window.addEventListener('operations:updated', refresh);
    window.addEventListener('archive:updated', refresh);
    return () => {
      window.removeEventListener('finance:updated', refresh);
      window.removeEventListener('vehicleUpdated', refresh);
      window.removeEventListener('vehicles:updated', refresh);
      window.removeEventListener('operations:updated', refresh);
      window.removeEventListener('archive:updated', refresh);
    };
  }, []);

  const loadArchiveAudit = () => {
    try {
      const raw = localStorage.getItem(ARCHIVE_AUDIT_KEY);
      const rows = raw ? JSON.parse(raw) : [];
      setArchiveAuditRows(Array.isArray(rows) ? rows.slice(0, 20) : []);
    } catch {
      setArchiveAuditRows([]);
    }
  };

  const fetchVehicles = async () => {
    try {
      setLoading(true);
      let response = null;
      for (let attempt = 1; attempt <= 2; attempt += 1) {
        try {
          response = await vehicleAPI.getAll();
          break;
        } catch (error) {
          if (attempt === 2) throw error;
          await new Promise((resolve) => setTimeout(resolve, 450));
        }
      }
      setVehicles(Array.isArray(response?.data) ? response.data : []);
    } catch (error) {
      console.error(error);
      toast({ title: 'تعذر تحميل الملفات', description: 'حاول فتح الأرشيف مرة أخرى.', variant: 'destructive' });
      setVehicles([]);
    } finally { setLoading(false); }
  };

  const handleDelete = async (vehicleId) => {
    if (!window.confirm('هل أنت متأكد من الحذف؟')) return;
    try {
      await vehicleAPI.delete(vehicleId);
      toast({ title: "تم الحذف", description: "تم حذف المركبة من الأرشيف" });
      fetchVehicles();
      window.dispatchEvent(new CustomEvent('archive:updated', { detail: { action: 'delete', vehicleId } }));
      window.dispatchEvent(new CustomEvent('vehicles:updated', { detail: { source: 'archive', action: 'delete', vehicleId } }));
    } catch (error) { toast({ title: "خطأ", variant: "destructive" }); }
  };

  const filteredVehicles = vehicles.filter(vehicle => {
    const matchesSearch = !searchQuery || 
      vehicle.plateNumber?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      vehicle.customerName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      String(vehicle.fileNumber || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      String(vehicle.customerFileNumber || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || vehicle.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">أرشيف المركبات</h1>
            <p className="text-gray-500 mt-1">سجل كامل لجميع المركبات والصيانات السابقة</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="apple-card p-5 flex items-center justify-between">
            <div><p className="text-sm text-gray-500 mb-1">إجمالي المركبات</p><p className="text-2xl font-bold text-blue-600">{vehicles.length}</p></div>
            <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600"><Car size={20} /></div>
          </div>
          <div className="apple-card p-5 flex items-center justify-between">
            <div><p className="text-sm text-gray-500 mb-1">تم التسليم</p><p className="text-2xl font-bold text-green-600">{vehicles.filter(v => v.status === 'delivered').length}</p></div>
            <div className="w-10 h-10 rounded-full bg-green-50 flex items-center justify-center text-green-600"><FileText size={20} /></div>
          </div>
          <div className="apple-card p-5 flex items-center justify-between">
            <div><p className="text-sm text-gray-500 mb-1">قيد العمل</p><p className="text-2xl font-bold text-orange-600">{vehicles.filter(v => v.status !== 'delivered' && v.status !== 'ready').length}</p></div>
            <div className="w-10 h-10 rounded-full bg-orange-50 flex items-center justify-center text-orange-600"><Wrench size={20} /></div>
          </div>
        </div>

        <div className="apple-card p-4" data-testid="vehicle-archive-audit-panel">
          <div className="flex items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2 text-slate-700" data-testid="vehicle-archive-audit-title">
              <History size={16} />
              <span className="font-semibold text-sm">سجل تعديلات الأرشيف</span>
            </div>
            <span className="text-xs text-slate-500" data-testid="vehicle-archive-audit-count">{archiveAuditRows.length} سجل</span>
          </div>
          {archiveAuditRows.length === 0 ? (
            <div className="text-xs text-slate-500" data-testid="vehicle-archive-audit-empty">لا توجد تعديلات مسجلة من الأرشيف بعد.</div>
          ) : (
            <div className="space-y-2 max-h-44 overflow-y-auto" data-testid="vehicle-archive-audit-list">
              {archiveAuditRows.map((row, idx) => (
                <div key={`${row.timestamp}-${idx}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" data-testid={`vehicle-archive-audit-row-${idx}`}>
                  <div className="text-xs font-semibold text-slate-700">{row.actionLabel || row.action || 'تعديل'}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {row.plateNumber || '-'} • {row.fileNumber || '-'} • {row.timeLabel || '-'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="apple-card p-4 flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
            <input className="apple-input pr-10" placeholder="بحث برقم اللوحة أو اسم العميل أو رقم الملف..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} data-testid="vehicle-archive-search-input" />
          </div>
          <div className="flex gap-2 overflow-x-auto pb-2 md:pb-0">
            {['all', 'diagnosis', 'quotation', 'repair', 'ready', 'delivered'].map(status => (
              <button key={status} onClick={() => setStatusFilter(status)} className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${statusFilter === status ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                {status === 'all' ? 'الكل' : getStatusLabel(status)}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          {loading ? (
            <div className="text-center py-10 text-gray-500" data-testid="vehicle-archive-loading">
              جاري تحميل الملفات...
            </div>
          ) : filteredVehicles.length === 0 ? (
            <div className="text-center py-10 text-gray-500">
              لا توجد مركبات في هذا التصنيف
            </div>
          ) : (
            filteredVehicles.map(vehicle => (
              <div key={vehicle.id} onClick={() => navigate(`/vehicle/${vehicle.id}?source=archive&editMode=full`)} className="apple-card p-5 hover:shadow-md transition-all cursor-pointer group" data-testid={`vehicle-archive-card-${vehicle.id}`}>
                <div className="flex flex-col md:flex-row justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center text-gray-600 font-bold text-lg">
                      {vehicle.brand?.[0]}
                    </div>
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-bold text-gray-900 text-lg">{vehicle.plateNumber}</h3>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(vehicle.status)} text-white`}>{getStatusLabel(vehicle.status)}</span>
                      </div>
                      <p className="text-gray-500 text-sm">{vehicle.brand} {vehicle.model} - {vehicle.year}</p>
                      <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
                        <span className="flex items-center gap-1"><User size={14} /> {vehicle.customerName}</span>
                        <span className="flex items-center gap-1"><Phone size={14} /> {vehicle.customerPhone}</span>
                        <span
                          className="flex items-center gap-1.5 font-bold text-base text-cyan-600"
                          data-testid={`vehicle-archive-file-number-${vehicle.id}`}
                        >
                          <FileText size={16} />
                          {vehicle.fileNumber || vehicle.customerFileNumber
                            ? <span>{vehicle.fileNumber || vehicle.customerFileNumber}</span>
                            : <span className="font-normal text-gray-400 text-sm">—</span>
                          }
                        </span>
                        <span className="flex items-center gap-1"><Calendar size={14} /> {new Date(vehicle.entryDate).toLocaleDateString('ar-SA')}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity self-start md:self-center">
                    {canEditArchive ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/vehicle/${vehicle.id}?source=archive&editMode=full`);
                      }}
                      className="px-3 py-1.5 rounded-lg bg-cyan-50 text-cyan-700 text-xs font-semibold border border-cyan-200"
                      data-testid={`vehicle-archive-edit-button-${vehicle.id}`}
                    >
                      تحرير شامل
                    </button>
                    ) : null}
                    {canDeleteArchive ? (
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(vehicle.id); }} className="p-2 hover:bg-red-50 text-red-500 rounded-lg transition-colors" data-testid={`vehicle-archive-delete-button-${vehicle.id}`}><Trash2 size={18} /></button>
                    ) : null}
                    <button className="p-2 hover:bg-gray-100 text-gray-500 rounded-lg transition-colors"><MoreVertical size={18} /></button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    
  );
};

export default VehicleArchive;
