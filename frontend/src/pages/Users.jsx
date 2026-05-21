import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { useToast } from '../hooks/use-toast';
import { resolveBackendBase } from '../utils/backendBase';
import rolePermissions from '../config/rolePermissions.json';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

const Users = () => {
  const { toast } = useToast();
  const roleOptions = Object.entries(rolePermissions?.roles || {});
  const defaultRoleKey = roleOptions.find(([key]) => key === 'technician')?.[0]
    || roleOptions[0]?.[0]
    || 'technician';
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ 
    name: '', 
    username: '',
    password: '',
    phone: '', 
    email: '',
    role: defaultRoleKey, 
    permissions: rolePermissions?.roles?.[defaultRoleKey]?.permissions || {},
    isActive: true 
  });
  const [editingId, setEditingId] = useState(null);

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${API_URL}/users`);
      const data = await res.json();
      setUsers(data || []);
    } catch (e) {
      console.error('fetch_users_failed', e);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const submit = async () => {
    try {
      setLoading(true);
      if (!form.name || !form.username || (!editingId && !form.password)) {
        toast({ title: 'تنبيه', description: 'الاسم واسم الدخول وكلمة المرور مطلوبة', variant: 'destructive' });
        return;
      }
      const payload = { ...form };
      if (editingId && !payload.password) {
        delete payload.password;
      }
      const res = await fetch(`${API_URL}/users${editingId ? '/' + editingId : ''}`, {
        method: editingId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'failed');
      toast({ title: editingId ? 'تم التعديل' : 'تم الإضافة' });
      const resetRole = defaultRoleKey;
      setForm({
        name: '',
        username: '',
        password: '',
        phone: '',
        email: '',
        role: resetRole,
        permissions: rolePermissions?.roles?.[resetRole]?.permissions || {},
        isActive: true,
      });
      setEditingId(null);
      fetchUsers();
    } catch (e) {
      toast({ title: 'خطأ', description: 'تعذر حفظ المستخدم', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const edit = (u) => {
    setEditingId(u.id);
    setForm({
      name: u.name || '',
      username: u.username || '',
      password: '',
      phone: u.phone || '',
      email: u.email || '',
      role: u.role || defaultRoleKey,
      permissions: u.permissions || rolePermissions?.roles?.[u.role]?.permissions || {},
      isActive: u.isActive !== false,
    });
  };

  const remove = async (id) => {
    if (!window.confirm('حذف المستخدم؟')) return;
    try {
      const res = await fetch(`${API_URL}/users/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('failed');
      toast({ title: 'تم الحذف' });
      fetchUsers();
    } catch (e) {
      toast({ title: 'خطأ', description: 'تعذر حذف المستخدم', variant: 'destructive' });
    }
  };

  return (
    <Layout>
      <div className="container mx-auto p-6" dir="rtl">
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>المستخدمون</CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
              <div>
                <Label>الاسم</Label>
                <Input data-testid="users-name-input" value={form.name} onChange={e=>setForm({...form, name:e.target.value})} />
              </div>
              <div>
                <Label>اسم الدخول</Label>
                <Input data-testid="users-username-input" value={form.username} onChange={e=>setForm({...form, username:e.target.value})} />
              </div>
              <div>
                <Label>كلمة المرور</Label>
                <Input data-testid="users-password-input" type="password" value={form.password} onChange={e=>setForm({...form, password:e.target.value})} placeholder={editingId ? 'اتركه فارغًا للإبقاء' : ''} />
              </div>
              <div>
                <Label>الجوال</Label>
                <Input data-testid="users-phone-input" value={form.phone} onChange={e=>setForm({...form, phone:e.target.value})} placeholder="9665xxxxxxxx" />
              </div>
              <div>
                <Label>البريد الإلكتروني</Label>
                <Input data-testid="users-email-input" value={form.email} onChange={e=>setForm({...form, email:e.target.value})} />
              </div>
              <div>
                <Label>الدور</Label>
                <select
                  data-testid="users-role-select"
                  className="w-full border rounded p-2"
                  value={form.role}
                  onChange={e=>{
                    const nextRole = e.target.value;
                    setForm({
                      ...form,
                      role: nextRole,
                      permissions: rolePermissions?.roles?.[nextRole]?.permissions || {},
                    });
                  }}
                >
                  {roleOptions.map(([key, role]) => (
                    <option key={key} value={key}>{role?.name || key}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <Button data-testid="users-submit-button" onClick={submit} disabled={loading} className="w-full bg-blue-600 hover:bg-blue-700">{editingId ? 'تعديل' : 'إضافة'}</Button>
              </div>
            </div>

            <div className="mb-4 flex items-center gap-2">
              <input
                data-testid="users-active-checkbox"
                type="checkbox"
                checked={form.isActive}
                onChange={e=>setForm({...form, isActive: e.target.checked})}
              />
              <span>المستخدم نشط</span>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full border">
                <thead>
                  <tr className="bg-slate-50">
                    <th className="border p-2">الاسم</th>
                    <th className="border p-2">الجوال</th>
                    <th className="border p-2">الدور</th>
                    <th className="border p-2">نشط</th>
                    <th className="border p-2">إجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id}>
                      <td className="border p-2" data-testid={`users-row-name-${u.id}`}>{u.name || '-'}</td>
                      <td className="border p-2" data-testid={`users-row-phone-${u.id}`}>{u.phone}</td>
                      <td className="border p-2" data-testid={`users-row-role-${u.id}`}>{rolePermissions?.roles?.[u.role]?.name || u.role}</td>
                      <td className="border p-2" data-testid={`users-row-active-${u.id}`}>{u.isActive === false ? 'لا' : 'نعم'}</td>
                      <td className="border p-2 space-x-2 space-x-reverse">
                        <Button data-testid={`users-edit-${u.id}`} variant="outline" onClick={()=>edit(u)}>تعديل</Button>
                        <Button data-testid={`users-delete-${u.id}`} variant="destructive" onClick={()=>remove(u.id)}>حذف</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default Users;