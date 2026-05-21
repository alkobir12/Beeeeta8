from datetime import datetime
from typing import Dict


class DensoInjectorDiagnostics:
    """
    نظام تشخيص حاقنات Denso المتكامل
    Integrated Denso Injector Diagnostics System
    """

    def __init__(self):
        self.system_version = "7.0 Final"
        self.creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # المواصفات الرسمية لحاقنات Denso حسب المراجع الأصلية
        self.denso_specifications = {
            "G2_Generation": {
                "pressure_range": {
                    "value": "180 MPa",
                    "bar_equivalent": "1800 bar",
                    "psi_equivalent": "26100 psi",
                },
                "electrical_resistance": {
                    "range": "0.5-0.7 Ohms",
                    "measurement_conditions": "20°C ambient temperature",
                },
                "flow_rate_tolerance": "±5% of specified value",
                "injector_types": ["Common Rail", "Piezoelectric"],
            },
            "G3_Generation": {
                "pressure_range": {
                    "value": "200 MPa",
                    "bar_equivalent": "2000 bar",
                    "psi_equivalent": "29000 psi",
                },
                "electrical_resistance": {
                    "range": "0.4-0.6 Ohms",
                    "measurement_conditions": "20°C ambient temperature",
                },
                "response_time": "< 0.3 ms",
                "injector_types": ["Common Rail", "Piezoelectric", "Multi-hole Nozzle"],
            },
            "G4_Generation": {
                "pressure_range": {
                    "value": "220 MPa",
                    "bar_equivalent": "2200 bar",
                    "psi_equivalent": "31900 psi",
                },
                "G4S_max_pressure": {
                    "value": "250 MPa",
                    "bar_equivalent": "2500 bar",
                    "psi_equivalent": "36250 psi",
                },
                "electrical_resistance": {
                    "range": "0.3-0.5 Ohms",
                    "measurement_conditions": "20°C ambient temperature",
                },
                "response_time": "< 0.2 ms",
                "injector_types": [
                    "Common Rail",
                    "Piezoelectric",
                    "Ultra-High Pressure",
                ],
            },
            "HP3_System": {
                "application": "Passenger cars and light-duty vehicles",
                "pressure_capability": "Up to 180 MPa (1800 bar)",
                "fuel_delivery": "High precision metering",
                "control_type": "ECU controlled injection timing",
            },
            "HP4_System": {
                "application": "Medium-duty and commercial vehicles",
                "pressure_capability": "Up to 200 MPa (2000 bar)",
                "fuel_delivery": "Heavy-duty injection system",
                "control_type": "Advanced ECU with multiple injection events",
            },
        }

        # قاعدة بيانات المحركات المدعومة مع مواصفات Denso الأصلية
        self.engine_database = {
            "Toyota_1VD-FTV": {
                "label": "Toyota Land Cruiser (1VD-FTV)",
                "manufacturer": "Denso",
                "part_numbers": ["095000-9780", "23670-59025", "23670-51020"],
                "generation": "G3",
                "specifications": {
                    "pressure": "180 MPa (1800 bar)",
                    "flow_rate": "255 cc/min @ 3 bar",
                    "electrical_resistance": "0.28 Ω ±10%",
                    "injection_type": "Common Rail Piezoelectric",
                    "nozzle_holes": 8,
                    "spray_angle": "148°",
                },
                "test_parameters": {
                    "VL_mode_pressure": "1600-2000 bar",
                    "VL_mode_duration": "> 1400 μs",
                    "return_quantity_limit": "< 2 ml/min",
                    "opening_pressure": "1600 bar ±50 bar",
                },
            },
            "Toyota_2KD-FTV": {
                "label": "Toyota Hilux/Innova (2KD-FTV)",
                "manufacturer": "Denso",
                "part_numbers": ["095000-6353", "23670-30400", "23670-39375"],
                "generation": "G2",
                "specifications": {
                    "pressure": "160 MPa (1600 bar)",
                    "flow_rate": "185 cc/min @ 3 bar",
                    "electrical_resistance": "0.35 Ω ±10%",
                    "injection_type": "Common Rail Solenoid",
                    "nozzle_holes": 6,
                    "spray_angle": "144°",
                },
                "test_parameters": {
                    "VL_mode_pressure": "1350-1650 bar",
                    "VL_mode_duration": "> 1400 μs",
                    "return_quantity_limit": "< 1.5 ml/min",
                    "opening_pressure": "1350 bar ±40 bar",
                },
            },
            "Isuzu_4JJ1-TC": {
                "label": "Isuzu D-Max (4JJ1-TC)",
                "manufacturer": "Denso",
                "part_numbers": ["095000-6980", "095000-6981", "8-97602485-6"],
                "generation": "G3",
                "specifications": {
                    "pressure": "180 MPa (1800 bar)",
                    "flow_rate": "275 cc/min @ 3 bar",
                    "electrical_resistance": "0.4 Ω ±10%",
                    "injection_type": "Common Rail Piezoelectric",
                    "nozzle_holes": 8,
                    "spray_angle": "150°",
                },
                "test_parameters": {
                    "VL_mode_pressure": "1600-1800 bar",
                    "VL_mode_duration": "> 1400 μs",
                    "return_quantity_limit": "< 2.5 ml/min",
                    "opening_pressure": "1600 bar ±60 bar",
                    "fuel_rail_pressure": "27-33 MPa (270-330 bar) normal operation",
                    "max_fuel_rail_pressure": "> 70 MPa (700 bar) peak",
                },
            },
            "Mitsubishi_4D56": {
                "label": "Mitsubishi Pajero/L200 (4D56)",
                "manufacturer": "Denso",
                "part_numbers": ["095000-5600", "SM095000-56002D", "1465A041"],
                "generation": "G2",
                "specifications": {
                    "pressure": "160 MPa (1600 bar)",
                    "flow_rate": "210 cc/min @ 3 bar",
                    "electrical_resistance": "0.5 Ω ±10%",
                    "injection_type": "Common Rail Solenoid",
                    "nozzle_holes": 6,
                    "spray_angle": "145°",
                },
                "test_parameters": {
                    "VL_mode_pressure": "1350-1600 bar",
                    "VL_mode_duration": "> 1400 μs",
                    "return_quantity_limit": "< 1.8 ml/min",
                    "opening_pressure": "1350 bar ±45 bar",
                },
            },
            "Mitsubishi_4M41": {
                "label": "Mitsubishi Pajero 3.2L (4M41)",
                "manufacturer": "Denso",
                "part_numbers": ["095000-5760", "ME302143", "ME355278"],
                "generation": "G3",
                "specifications": {
                    "pressure": "180 MPa (1800 bar)",
                    "flow_rate": "290 cc/min @ 3 bar",
                    "electrical_resistance": "0.35 Ω ±10%",
                    "injection_type": "Common Rail Piezoelectric",
                    "nozzle_holes": 8,
                    "spray_angle": "152°",
                },
                "test_parameters": {
                    "VL_mode_pressure": "1600-1800 bar",
                    "VL_mode_duration": "> 1400 μs",
                    "return_quantity_limit": "< 2.2 ml/min",
                    "opening_pressure": "1600 bar ±55 bar",
                },
            },
            "Mitsubishi_4N15": {
                "label": "Mitsubishi L200 New (4N15)",
                "manufacturer": "Denso",
                "part_numbers": ["295050-0880", "1465A374", "ME456518"],
                "generation": "G4",
                "specifications": {
                    "pressure": "220 MPa (2200 bar)",
                    "flow_rate": "320 cc/min @ 3 bar",
                    "electrical_resistance": "0.3 Ω ±10%",
                    "injection_type": "Common Rail Piezoelectric Advanced",
                    "nozzle_holes": 8,
                    "spray_angle": "155°",
                },
                "test_parameters": {
                    "VL_mode_pressure": "1800-2200 bar",
                    "VL_mode_duration": "> 1400 μs",
                    "return_quantity_limit": "< 3.0 ml/min",
                    "opening_pressure": "1800 bar ±70 bar",
                },
            },
        }

    def get_injector_specifications(self, engine_type: str) -> Dict:
        """الحصول على مواصفات الحاقن للمحرك المحدد"""
        return self.engine_database.get(engine_type, {})

    def validate_vl_mode_reading(
        self, engine_type: str, pressure: float, duration: float, return_quantity: float
    ) -> Dict:
        """التحقق من صحة قراءات وضع VL حسب المواصفات الأصلية"""
        engine_specs = self.get_injector_specifications(engine_type)
        if not engine_specs:
            return {"valid": False, "message": "نوع المحرك غير مدعوم"}

        test_params = engine_specs.get("test_parameters", {})

        # تحليل ضغط VL
        pressure_range = (
            test_params.get("VL_mode_pressure", "").replace(" bar", "").split("-")
        )
        pressure_ok = False
        if len(pressure_range) == 2:
            min_pressure = float(pressure_range[0])
            max_pressure = float(pressure_range[1])
            pressure_ok = min_pressure <= pressure <= max_pressure

        # تحليل مدة التشغيل
        duration_ok = duration > 1400  # μs

        # تحليل كمية الإرجاع
        try:
            return_limit_str = test_params.get("return_quantity_limit", "< 2 ml/min")
            return_limit = float(
                return_limit_str.replace("< ", "").replace(" ml/min", "")
            )
            return_ok = return_quantity < return_limit
        except Exception:
            return_ok = False

        result = {
            "valid": pressure_ok and duration_ok and return_ok,
            "pressure_status": "مقبول" if pressure_ok else "خارج المدى",
            "duration_status": "مقبول" if duration_ok else "قصير جداً",
            "return_quantity_status": "مقبول" if return_ok else "مرتفع (تسريب عالي)",
            "test_params": test_params,
        }

        return result

    def generate_diagnostic_report(self, test_data: Dict) -> str:
        """إنتاج تقرير تشخيص شامل نصي"""
        specs = self.get_injector_specifications(test_data.get("engine_type", ""))
        if not specs:
            return "لا توجد بيانات لهذا المحرك"

        report = f"""
========================================
تقرير تشخيص حاقن الوقود - Denso Integrated System
التاريخ: {self.creation_date}
========================================

معلومات الحاقن:
- المحرك: {specs.get('label')}
- رقم القطعة: {', '.join(specs.get('part_numbers', []))}
- الجيل: {specs.get('generation')}

المواصفات الفنية:
- ضغط التشغيل: {specs['specifications'].get('pressure')}
- معدل التدفق: {specs['specifications'].get('flow_rate')}
- المقاومة: {specs['specifications'].get('electrical_resistance')}
- نوع الحقن: {specs['specifications'].get('injection_type')}

نتائج الاختبار المسجلة:
1. الفحص البصري: {test_data.get('visual_inspection', 'لم يتم')}
2. المقاومة المقاسة: {test_data.get('resistance', '0')} أوم
3. ضغط الفتح: {test_data.get('opening_pressure', '0')} بار
4. اختبار VL (الحمل الكامل): {test_data.get('vl_status', 'غير معروف')}

التوصيات:
{test_data.get('recommendations', 'لا توجد توصيات')}

الفني المسؤول: {test_data.get('technician', 'غير محدد')}
"""
        return report
