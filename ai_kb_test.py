#!/usr/bin/env python3
"""
AI Knowledge Base Comprehensive Testing
Tests all KB endpoints as requested in Arabic review
"""
import requests
import json
import time
from datetime import datetime
from io import BytesIO

# Backend URL
BASE_URL = "https://fleet-audit-system-2.preview.emergentagent.com/api"

# Test results storage
test_results = []

def log_test(test_name, status, details, duration=None):
    """Log test result"""
    result = {
        "test": test_name,
        "status": status,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    if duration:
        result["duration"] = f"{duration:.3f}s"
    test_results.append(result)
    
    status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"\n{status_icon} {test_name}")
    print(f"   {details}")
    if duration:
        print(f"   ⏱️  Duration: {duration:.3f}s")

def print_section(title):
    """Print section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")

# ============================================================================
# TEST 1: فحص المستندات المحفوظة (Check Saved Documents)
# ============================================================================
def test_get_saved_documents():
    """Test GET /api/ai/kb/docs - Check saved documents"""
    print_section("TEST 1: فحص المستندات المحفوظة")
    
    try:
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/ai/kb/docs", timeout=30)
        duration = time.time() - start_time
        
        if response.status_code != 200:
            log_test(
                "GET /api/ai/kb/docs",
                "FAIL",
                f"Status code: {response.status_code}, Response: {response.text[:200]}",
                duration
            )
            return False
        
        data = response.json()
        
        # Check structure
        if 'docs' not in data or 'count' not in data:
            log_test(
                "GET /api/ai/kb/docs - Structure",
                "FAIL",
                f"Missing 'docs' or 'count' in response. Keys: {list(data.keys())}",
                duration
            )
            return False
        
        docs = data['docs']
        count = data['count']
        
        print(f"\n📊 عدد المستندات: {count}")
        
        # Check if we have documents
        if count == 0:
            log_test(
                "GET /api/ai/kb/docs - Document Count",
                "WARN",
                "No documents found in knowledge base. This is acceptable but KB is empty.",
                duration
            )
            return True
        
        # Verify content field exists in documents
        docs_with_content = 0
        docs_with_summary = 0
        
        for i, doc in enumerate(docs[:5]):  # Check first 5 docs
            print(f"\n   المستند {i+1}:")
            print(f"   - ID: {doc.get('id', 'N/A')}")
            print(f"   - Title: {doc.get('title', 'N/A')[:50]}")
            print(f"   - Type: {doc.get('type', 'N/A')}")
            
            if 'content' in doc and doc['content']:
                docs_with_content += 1
                content_len = len(doc['content'])
                print(f"   - Content: ✅ ({content_len} chars)")
            else:
                print(f"   - Content: ❌ Missing")
            
            if 'summary' in doc and doc['summary']:
                docs_with_summary += 1
                print(f"   - Summary: ✅ ({len(doc['summary'])} chars)")
            else:
                print(f"   - Summary: ❌ Missing")
        
        # Summary
        print(f"\n📈 إحصائيات:")
        print(f"   - إجمالي المستندات: {count}")
        print(f"   - مستندات بمحتوى: {docs_with_content}/{min(5, count)}")
        print(f"   - مستندات بملخص: {docs_with_summary}/{min(5, count)}")
        
        if docs_with_content == 0:
            log_test(
                "GET /api/ai/kb/docs - Content Verification",
                "FAIL",
                f"Found {count} documents but NONE have content field",
                duration
            )
            return False
        
        log_test(
            "GET /api/ai/kb/docs",
            "PASS",
            f"Found {count} documents, {docs_with_content}/{min(5, count)} have content, {docs_with_summary}/{min(5, count)} have summaries",
            duration
        )
        return True
        
    except Exception as e:
        log_test(
            "GET /api/ai/kb/docs",
            "FAIL",
            f"Exception: {str(e)}",
            0
        )
        return False

# ============================================================================
# TEST 2: اختبار البحث الذكي (Smart Search Tests)
# ============================================================================
def test_smart_search():
    """Test POST /api/ai/kb/smart-search with multiple queries"""
    print_section("TEST 2: اختبار البحث الذكي")
    
    test_queries = [
        ("كهرباء", "Electricity"),
        ("محرك", "Engine"),
        ("Toyota", "Toyota")
    ]
    
    all_passed = True
    
    for arabic_query, english_desc in test_queries:
        print(f"\n🔍 Testing query: {arabic_query} ({english_desc})")
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/ai/kb/smart-search",
                json={"query": arabic_query, "limit": 10},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            duration = time.time() - start_time
            
            if response.status_code != 200:
                log_test(
                    f"Smart Search - '{arabic_query}'",
                    "FAIL",
                    f"Status code: {response.status_code}, Response: {response.text[:200]}",
                    duration
                )
                all_passed = False
                continue
            
            data = response.json()
            
            # Check structure
            required_keys = ['results', 'count', 'totalMatches', 'query']
            missing_keys = [k for k in required_keys if k not in data]
            
            if missing_keys:
                log_test(
                    f"Smart Search - '{arabic_query}' Structure",
                    "FAIL",
                    f"Missing keys: {missing_keys}",
                    duration
                )
                all_passed = False
                continue
            
            results = data['results']
            count = data['count']
            total_matches = data['totalMatches']
            
            print(f"   📊 Results: {count} returned, {total_matches} total matches")
            
            # Check relevance scoring
            if results:
                print(f"\n   Top {min(3, len(results))} results:")
                for i, result in enumerate(results[:3]):
                    relevance = result.get('relevance', 0)
                    title = result.get('title', 'N/A')[:50]
                    excerpt = result.get('excerpt', '')[:100]
                    
                    print(f"\n   Result {i+1}:")
                    print(f"   - Title: {title}")
                    print(f"   - Relevance Score: {relevance}")
                    print(f"   - Excerpt: {excerpt}...")
                    
                    # Verify relevance field exists
                    if 'relevance' not in result:
                        log_test(
                            f"Smart Search - '{arabic_query}' Relevance",
                            "FAIL",
                            "Result missing 'relevance' field",
                            duration
                        )
                        all_passed = False
                        continue
                    
                    # Verify excerpt exists
                    if 'excerpt' not in result:
                        log_test(
                            f"Smart Search - '{arabic_query}' Excerpt",
                            "FAIL",
                            "Result missing 'excerpt' field",
                            duration
                        )
                        all_passed = False
                        continue
                
                # Check if results are sorted by relevance
                relevance_scores = [r.get('relevance', 0) for r in results]
                is_sorted = all(relevance_scores[i] >= relevance_scores[i+1] for i in range(len(relevance_scores)-1))
                
                if not is_sorted:
                    log_test(
                        f"Smart Search - '{arabic_query}' Sorting",
                        "FAIL",
                        f"Results not sorted by relevance: {relevance_scores[:5]}",
                        duration
                    )
                    all_passed = False
                    continue
                
                log_test(
                    f"Smart Search - '{arabic_query}'",
                    "PASS",
                    f"Found {count} results, relevance scoring working, excerpts present, sorted correctly",
                    duration
                )
            else:
                log_test(
                    f"Smart Search - '{arabic_query}'",
                    "WARN",
                    f"No results found for query. KB may not have relevant content.",
                    duration
                )
        
        except Exception as e:
            log_test(
                f"Smart Search - '{arabic_query}'",
                "FAIL",
                f"Exception: {str(e)}",
                0
            )
            all_passed = False
    
    return all_passed

# ============================================================================
# TEST 3: اختبار مقارنة الملفات (File Comparison Test)
# ============================================================================
def test_file_comparison():
    """Test POST /api/ai/kb/compare-files"""
    print_section("TEST 3: اختبار مقارنة الملفات")
    
    try:
        # Create two small test files with Arabic automotive content
        file1_content = """دليل صيانة محرك تويوتا
        
المحرك: 1KD-FTV
النوع: ديزل توربو
السعة: 3.0 لتر

خطوات الصيانة:
1. فحص مستوى الزيت
2. تغيير فلتر الهواء
3. فحص ضغط الوقود
4. تنظيف صمام EGR

التكلفة المتوقعة: 500-800 ريال
"""

        file2_content = """دليل صيانة محرك نيسان
        
المحرك: YD25
النوع: ديزل توربو
السعة: 2.5 لتر

خطوات الصيانة:
1. فحص مستوى الزيت
2. تغيير فلتر الديزل
3. فحص نظام الحقن
4. تنظيف البخاخات

التكلفة المتوقعة: 400-700 ريال
"""
        
        # Create file objects
        file1 = ('file1', ('toyota_maintenance.txt', BytesIO(file1_content.encode('utf-8')), 'text/plain'))
        file2 = ('file2', ('nissan_maintenance.txt', BytesIO(file2_content.encode('utf-8')), 'text/plain'))
        
        print("\n📄 Uploading test files:")
        print(f"   File 1: toyota_maintenance.txt ({len(file1_content)} bytes)")
        print(f"   File 2: nissan_maintenance.txt ({len(file2_content)} bytes)")
        
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/ai/kb/compare-files",
            files={'file1': file1[1], 'file2': file2[1]},
            timeout=60
        )
        duration = time.time() - start_time
        
        if response.status_code != 200:
            log_test(
                "File Comparison",
                "FAIL",
                f"Status code: {response.status_code}, Response: {response.text[:300]}",
                duration
            )
            return False
        
        data = response.json()
        
        # Check structure
        required_keys = ['file1', 'file2', 'comparison', 'extractedLength1', 'extractedLength2']
        missing_keys = [k for k in required_keys if k not in data]
        
        if missing_keys:
            log_test(
                "File Comparison - Structure",
                "FAIL",
                f"Missing keys: {missing_keys}. Keys present: {list(data.keys())}",
                duration
            )
            return False
        
        # Verify text extraction
        extracted1 = data['extractedLength1']
        extracted2 = data['extractedLength2']
        
        print(f"\n📊 Text Extraction:")
        print(f"   File 1: {extracted1} characters extracted")
        print(f"   File 2: {extracted2} characters extracted")
        
        if extracted1 == 0 or extracted2 == 0:
            log_test(
                "File Comparison - Text Extraction",
                "FAIL",
                f"Text extraction failed. Lengths: {extracted1}, {extracted2}",
                duration
            )
            return False
        
        # Verify comparison analysis
        comparison = data['comparison']
        
        print(f"\n🔍 Comparison Analysis:")
        print(f"   Length: {len(comparison)} characters")
        print(f"   Preview: {comparison[:300]}...")
        
        if len(comparison) < 50:
            log_test(
                "File Comparison - Analysis",
                "FAIL",
                f"Comparison analysis too short ({len(comparison)} chars). May indicate LLM failure.",
                duration
            )
            return False
        
        # Check if comparison contains expected sections (Arabic)
        expected_sections = ['التشابهات', 'الاختلافات', 'التوصيات', 'الخلاصة']
        found_sections = [s for s in expected_sections if s in comparison]
        
        print(f"\n✅ Found sections: {found_sections}")
        
        if len(found_sections) < 2:
            log_test(
                "File Comparison - Content Quality",
                "WARN",
                f"Comparison may lack structure. Found {len(found_sections)}/4 expected sections.",
                duration
            )
        
        log_test(
            "File Comparison",
            "PASS",
            f"Files compared successfully. Extracted {extracted1} and {extracted2} chars. Analysis: {len(comparison)} chars with {len(found_sections)}/4 sections.",
            duration
        )
        return True
        
    except Exception as e:
        log_test(
            "File Comparison",
            "FAIL",
            f"Exception: {str(e)}",
            0
        )
        return False

# ============================================================================
# TEST 4: فحص الأداء (Performance Check)
# ============================================================================
def test_performance():
    """Test performance of search and upload operations"""
    print_section("TEST 4: فحص الأداء")
    
    # Test 1: Search response time
    print("\n⏱️  Testing search response time...")
    search_times = []
    
    for i in range(3):
        try:
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/ai/kb/smart-search",
                json={"query": "محرك", "limit": 5},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                search_times.append(duration)
                print(f"   Attempt {i+1}: {duration:.3f}s")
        except Exception as e:
            print(f"   Attempt {i+1}: Failed - {str(e)}")
    
    if search_times:
        avg_search_time = sum(search_times) / len(search_times)
        max_search_time = max(search_times)
        min_search_time = min(search_times)
        
        print(f"\n📊 Search Performance:")
        print(f"   Average: {avg_search_time:.3f}s")
        print(f"   Min: {min_search_time:.3f}s")
        print(f"   Max: {max_search_time:.3f}s")
        
        if avg_search_time > 5.0:
            log_test(
                "Performance - Search Speed",
                "WARN",
                f"Average search time {avg_search_time:.3f}s exceeds 5s threshold",
                avg_search_time
            )
        else:
            log_test(
                "Performance - Search Speed",
                "PASS",
                f"Average search time: {avg_search_time:.3f}s (acceptable)",
                avg_search_time
            )
    else:
        log_test(
            "Performance - Search Speed",
            "FAIL",
            "All search attempts failed",
            0
        )
    
    # Test 2: Small file upload and analysis time
    print("\n⏱️  Testing file upload and analysis time...")
    
    try:
        small_file_content = "دليل صيانة سريع\n\nفحص الزيت: كل 5000 كم\nفحص الفرامل: كل 10000 كم"
        file_obj = ('file', ('quick_guide.txt', BytesIO(small_file_content.encode('utf-8')), 'text/plain'))
        
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/ai/kb/upload-and-analyze",
            files={'file': file_obj[1]},
            timeout=60
        )
        duration = time.time() - start_time
        
        print(f"   Upload + Analysis: {duration:.3f}s")
        
        if response.status_code == 200:
            if duration > 30.0:
                log_test(
                    "Performance - Upload & Analysis",
                    "WARN",
                    f"Upload and analysis time {duration:.3f}s exceeds 30s threshold",
                    duration
                )
            else:
                log_test(
                    "Performance - Upload & Analysis",
                    "PASS",
                    f"Upload and analysis completed in {duration:.3f}s (acceptable)",
                    duration
                )
        else:
            log_test(
                "Performance - Upload & Analysis",
                "FAIL",
                f"Upload failed with status {response.status_code}",
                duration
            )
    
    except Exception as e:
        log_test(
            "Performance - Upload & Analysis",
            "FAIL",
            f"Exception: {str(e)}",
            0
        )

# ============================================================================
# MAIN TEST EXECUTION
# ============================================================================
def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  🧪 AI Knowledge Base Comprehensive Testing")
    print("  اختبار شامل لنظام قاعدة المعرفة")
    print("="*80)
    print(f"\n🌐 Backend URL: {BASE_URL}")
    print(f"⏰ Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all tests
    test_get_saved_documents()
    test_smart_search()
    test_file_comparison()
    test_performance()
    
    # Summary
    print("\n" + "="*80)
    print("  📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in test_results if r['status'] == 'PASS')
    failed = sum(1 for r in test_results if r['status'] == 'FAIL')
    warned = sum(1 for r in test_results if r['status'] == 'WARN')
    total = len(test_results)
    
    print(f"\n✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {failed}/{total}")
    print(f"⚠️  Warnings: {warned}/{total}")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for r in test_results:
            if r['status'] == 'FAIL':
                print(f"   - {r['test']}: {r['details']}")
    
    if warned > 0:
        print("\n⚠️  WARNINGS:")
        for r in test_results:
            if r['status'] == 'WARN':
                print(f"   - {r['test']}: {r['details']}")
    
    # Save results to file
    with open('/app/ai_kb_test_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'warned': warned
            },
            'tests': test_results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Results saved to: /app/ai_kb_test_results.json")
    print(f"⏰ Test Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
