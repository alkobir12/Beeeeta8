from datetime import datetime
from typing import Dict, Tuple

class AccountingSystemAuditor:
    """
    مدقق النظام المحاسبي للخدمات - يركز على الاختبار والتدقيق والتصحيح
    """
    
    def __init__(self, system_name="نظام محاسبي للخدمات"):
        self.system_name = system_name
        self.audit_log = []
        self.corrections_needed = []
        self.missing_items = []
        self.system_health_score = 100
        self.detected_issues = []
        
    def log_audit(self, message: str, status: str = "INFO"):
        """تسجيل رسائل التدقيق"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{status}] {message}"
        self.audit_log.append(log_entry)
        
        if status == "ERROR":
            self.system_health_score -= 10
            self.detected_issues.append(message)
        elif status == "WARNING":
            self.system_health_score -= 5
            self.detected_issues.append(message)
        
        return log_entry
    
    def check_accounting_equation(self, assets: float, liabilities: float, equity: float) -> Tuple[bool, str]:
        """
        التحقق من معادلة المحاسبة الأساسية
        """
        try:
            total_liabilities_equity = liabilities + equity
            
            if abs(assets - total_liabilities_equity) < 0.01:
                self.log_audit("✅ معادلة المحاسبة متوازنة: الأصول = الخصوم + حقوق الملكية", "SUCCESS")
                return True, "متوازن"
            else:
                imbalance = assets - total_liabilities_equity
                correction = f"تحتاج تصحيح بمقدار: {abs(imbalance):,.2f} ريال"
                
                if imbalance > 0:
                    suggestion = "اقتراح: زيادة حقوق الملكية أو الخصوم"
                else:
                    suggestion = "اقتراح: زيادة الأصول"
                
                self.log_audit(
                    f"❌ الميزانية غير متوازنة: الأصول ({assets:,.2f}) ≠ الخصوم+الملكية ({total_liabilities_equity:,.2f})",
                    "ERROR"
                )
                self.corrections_needed.append({
                    "issue": "عدم توازن الميزانية",
                    "amount": imbalance,
                    "correction": correction,
                    "suggestion": suggestion
                })
                return False, f"غير متوازن - {correction}"
                
        except Exception as e:
            self.log_audit(f"❌ خطأ في فحص معادلة المحاسبة: {str(e)}", "ERROR")
            return False, f"خطأ: {str(e)}"
    
    def analyze_financial_statements_consistency(self, 
                                                 balance_sheet: Dict,
                                                 income_statement: Dict,
                                                 cash_flow: Dict) -> Dict:
        """
        تحليل اتساق القوائم المالية مع بعضها
        """
        consistency_report = {
            "issues": [],
            "warnings": [],
            "recommendations": []
        }
        
        try:
            # التحقق من ارتباط صافي الربح بحقوق الملكية
            if 'net_profit' in income_statement and 'equity' in balance_sheet:
                net_profit = income_statement.get('net_profit', 0)
                
                if net_profit > balance_sheet.get('equity', 0) * 10:
                    consistency_report["warnings"].append(
                        "صافي الربح كبير جداً مقارنة بحقوق الملكية - تحقق من صحة التسجيلات"
                    )
                    self.log_audit("⚠️ صافي الربح كبير جداً مقارنة بحقوق الملكية", "WARNING")
            
            # التحقق من الربحية غير العادية
            if 'revenue' in income_statement and 'expenses' in income_statement:
                revenue = income_statement.get('revenue', 0)
                expenses = income_statement.get('expenses', 0)
                
                if revenue > 0 and expenses > 0:
                    profit_margin = (revenue - expenses) / revenue * 100
                    
                    if profit_margin > 95:
                        consistency_report["issues"].append(
                            f"هامش ربح غير واقعي: {profit_margin:.1f}%"
                        )
                        self.corrections_needed.append({
                            "issue": "هامش ربح غير واقعي",
                            "details": f"هامش الربح {profit_margin:.1f}% مرتفع جداً",
                            "suggestion": "تحقق من تسجيل جميع المصروفات"
                        })
                    
                    elif profit_margin < 0:
                        consistency_report["issues"].append(
                            f"خسارة: هامش ربح سلبي {profit_margin:.1f}%"
                        )
            
            if not consistency_report["issues"]:
                consistency_report["recommendations"].append("القوائم المالية متسقة بشكل عام")
                self.log_audit("✅ القوائم المالية متسقة مع بعضها", "SUCCESS")
            
        except Exception as e:
            self.log_audit(f"❌ خطأ في تحليل اتساق القوائم: {str(e)}", "ERROR")
        
        return consistency_report
    
    def check_firewall_health(self, firewall_data: Dict) -> Dict:
        """
        🛡️ فحص حالة جدار حماية المحاسبة في الوقت الفعلي.
        يحلل: قيود غير متوازنة، رفضيات، ضربات منع تكرار، انحراف عشري.
        """
        report = {
            "status": "ok",
            "issues": [],
            "warnings": [],
            "metrics": {},
        }

        try:
            summary = (firewall_data or {}).get("summary", {}) or {}
            drift = (firewall_data or {}).get("drift", {}) or {}

            total = int(summary.get("total_entries") or 0)
            balanced = int(summary.get("balanced_entries") or 0)
            unbalanced_db = int(summary.get("unbalanced_entries_in_db") or 0)
            rejections = int(summary.get("lifetime_rejections") or 0)
            idemp_hits = int(summary.get("lifetime_idempotency_hits") or 0)
            cogs_count = int(summary.get("cogs_entries") or 0)
            cogs_total = float(summary.get("cogs_total_amount") or 0)
            health_pct = float(summary.get("balance_health_percent") or 100.0)
            max_drift = float(drift.get("max") or 0)
            threshold = float(drift.get("threshold") or 0.009)

            report["metrics"] = {
                "total_entries": total,
                "balanced_entries": balanced,
                "unbalanced_entries_in_db": unbalanced_db,
                "balance_health_percent": health_pct,
                "lifetime_rejections": rejections,
                "lifetime_idempotency_hits": idemp_hits,
                "cogs_entries": cogs_count,
                "cogs_total_amount": cogs_total,
                "max_drift": max_drift,
                "drift_threshold": threshold,
            }

            # CRITICAL: any unbalanced entry persisted in DB is a red flag
            if unbalanced_db > 0:
                msg = f"❌ يوجد {unbalanced_db} قيد(قيود) غير متوازنة في قاعدة البيانات"
                self.log_audit(msg, "ERROR")
                report["issues"].append(msg)
                self.corrections_needed.append({
                    "issue": "قيود تسربت غير متوازنة",
                    "count": unbalanced_db,
                    "suggestion": "افتح لوحة جدار الحماية وادرس كل قيد مكسور؛ الجدار يجب أن يرفض كل قيد غير متوازن.",
                })

            # CRITICAL: precision drift above tolerance
            if max_drift > threshold:
                msg = f"❌ انحراف عشري عبر العتبة: {max_drift:.6f} > {threshold:.4f}"
                self.log_audit(msg, "ERROR")
                report["issues"].append(msg)

            # WARNING: high rejection volume (likely user/UX problem)
            if rejections >= 20:
                msg = f"⚠️ رفضيات مرتفعة هذه الجلسة: {rejections}"
                self.log_audit(msg, "WARNING")
                report["warnings"].append(msg)
                self.corrections_needed.append({
                    "issue": "رفضيات مرتفعة",
                    "details": f"{rejections} قيود غير متوازنة رُفضت",
                    "suggestion": "راجع نموذج إدخال القيود؛ المستخدمون يدخلون قيوداً غير متوازنة بكثرة.",
                })

            # INFO: COGS coverage (just observe)
            if cogs_count == 0 and total > 5:
                msg = "ℹ️ لا توجد قيود COGS رغم وجود حركة قيود"
                report["warnings"].append(msg)

            # OK
            if not report["issues"] and not report["warnings"]:
                self.log_audit("✅ جدار حماية المحاسبة سليم تماماً", "SUCCESS")
                report["status"] = "ok"
            elif report["issues"]:
                report["status"] = "critical"
            else:
                report["status"] = "warning"
        except Exception as e:
            self.log_audit(f"❌ خطأ في فحص جدار الحماية: {e}", "ERROR")
            report["error"] = str(e)
            report["status"] = "error"
        return report

    def run_comprehensive_audit(self, financial_data: Dict) -> Dict:
        """
        تشغيل تدقيق شامل للنظام المحاسبي
        """
        audit_report = {
            "audit_date": datetime.now().isoformat(),
            "system_name": self.system_name,
            "health_score": 100,
            "summary": {},
            "details": {},
            "correction_plan": {}
        }
        
        try:
            # 1. فحص الميزانية
            if 'balance_sheet' in financial_data:
                bs = financial_data['balance_sheet']
                balance_result, balance_message = self.check_accounting_equation(
                    bs.get('assets', 0),
                    bs.get('liabilities', 0),
                    bs.get('equity', 0)
                )
                audit_report["details"]["balance_sheet_check"] = {
                    "result": balance_result,
                    "message": balance_message
                }
            
            # 2. تحليل اتساق القوائم
            if all(key in financial_data for key in ['balance_sheet', 'income_statement', 'cash_flow']):
                consistency = self.analyze_financial_statements_consistency(
                    financial_data['balance_sheet'],
                    financial_data['income_statement'],
                    financial_data['cash_flow']
                )
                audit_report["details"]["consistency_analysis"] = consistency

            # 3. 🛡️ فحص جدار حماية المحاسبة (Firewall Health)
            if 'firewall' in financial_data:
                firewall_check = self.check_firewall_health(financial_data['firewall'])
                audit_report["details"]["firewall_check"] = firewall_check

            # 4. حساب درجة الصحة النهائية
            audit_report["health_score"] = max(0, min(100, self.system_health_score))

            # 5. إنشاء الملخص
            audit_report["summary"] = {
                "total_issues": len(self.detected_issues),
                "corrections_needed": len(self.corrections_needed),
                "missing_items": len(self.missing_items),
                "audit_log_entries": len(self.audit_log),
                "final_verdict": self.get_final_verdict()
            }
            
            audit_report["corrections_needed"] = self.corrections_needed
            audit_report["audit_log"] = self.audit_log
            
        except Exception as e:
            error_msg = f"❌ خطأ في التدقيق الشامل: {str(e)}"
            self.log_audit(error_msg, "ERROR")
            audit_report["error"] = error_msg
        
        return audit_report
    
    def get_final_verdict(self) -> str:
        """الحكم النهائي على حالة النظام"""
        if self.system_health_score >= 90:
            return "✅ النظام يعمل بشكل جيد مع تحسينات طفيفة مطلوبة"
        elif self.system_health_score >= 70:
            return "⚠️ النظام يعمل لكن يحتاج تصحيحات"
        elif self.system_health_score >= 50:
            return "🔶 النظام يحتاج مراجعة شاملة"
        else:
            return "❌ النظام يحتاج إعادة هيكلة"
